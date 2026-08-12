"""Completion Verification — pytest 执行档案解析（Round 2 验证逃逸防御）。

从工具执行记录中提取所有 pytest 类 run_command 的执行档案：
  - scope:        本次执行的测试范围（pytest 后的路径参数，缺省为全量）
  - exit_code:    命令退出码（解析输出中的 "[exit code N]"）
  - failed_files: 本次失败的测试文件集合（解析 "FAILED tests/..." 行）

供规则层 `rule_test_scope_guard` 判定：
  1. 最后一次测试执行是否全绿；
  2. 曾失败的测试文件是否被最后一次执行的范围覆盖（防“只跑必过子集”的验证逃逸）；
  3. 基线排除（仅限任务未要求全绿时）：首次执行即失败的文件视为既有失败，不计入拦截，
     防基线本身红的工程被永久卡死；任务明确要求“全绿/全部通过”时不适用基线排除。
"""

import re
from typing import List, Optional

EXIT_CODE_RE = re.compile(r"\[exit code\s+(-?\d+)\]", re.IGNORECASE)
FAILED_LINE_RE = re.compile(r"^FAILED\s+(\S+?)(?:::\S+)?\s*(?:-|$)", re.MULTILINE)
FAILED_COUNT_RE = re.compile(r"(\d+)\s+failed", re.IGNORECASE)

# 命令中的 pytest 定位：取 pytest 之后、下一个选项之前的路径参数
PYTEST_SCOPE_RE = re.compile(r"pytest\s+((?:[^\s\-][^\s]*\s+)*)(?=-|$)")


def _extract_command(record: dict) -> str:
    """从工具记录提取命令文本（run_command / execute_command）。"""
    tool = record.get("tool") or record.get("name") or ""
    if tool not in ("run_command", "execute_command"):
        return ""
    args = record.get("arguments") or {}
    if isinstance(args, dict):
        return str(args.get("command") or "")
    return ""


def _extract_scope(command: str) -> str:
    """提取 pytest 执行范围（规范化为正斜杠、去尾斜杠；空 = 全量）。"""
    m = PYTEST_SCOPE_RE.search(command)
    if not m:
        return ""
    parts = [p for p in m.group(1).split() if p and not p.startswith("-")]
    if not parts:
        return ""
    scope = parts[0].replace("\\", "/").rstrip("/")
    return "" if scope in (".", "./") else scope


def _extract_exit_code(result: str, success: bool) -> Optional[int]:
    """解析退出码：优先 "[exit code N]" 标记；缺失时按输出推断。"""
    m = EXIT_CODE_RE.search(result or "")
    if m:
        return int(m.group(1))
    if FAILED_COUNT_RE.search(result or ""):
        return 1
    return 0 if success else None


def _covers(scope: str, failed_file: str) -> bool:
    """判断执行范围是否覆盖某失败文件（空 scope = 全量，天然覆盖）。"""
    if not scope:
        return True
    f = failed_file.replace("\\", "/").lstrip("./")
    s = scope.lstrip("./")
    return f == s or f.startswith(s + "/")


def build_test_history(tool_records: List[dict]) -> List[dict]:
    """按执行顺序构建 pytest 执行档案列表。

    每项: {"scope": str, "exit_code": Optional[int], "failed_files": set[str]}
    非 pytest 的命令调用不入档。
    """
    history: List[dict] = []
    for record in tool_records or []:
        command = _extract_command(record)
        if not command or "pytest" not in command:
            continue
        result = str(record.get("result") or "")
        failed_files = {
            f.replace("\\", "/") for f in FAILED_LINE_RE.findall(result)
        }
        exit_code = _extract_exit_code(result, bool(record.get("success")))
        history.append({
            "scope": _extract_scope(command),
            "exit_code": exit_code,
            "failed_files": failed_files,
        })
    return history


def baseline_failed_files(history: List[dict]) -> set:
    """基线排除：首次执行即失败的文件视为既有失败。"""
    if not history:
        return set()
    return set(history[0].get("failed_files") or set())


def uncovered_new_failures(history: List[dict], require_all_green: bool = False) -> List[str]:
    """返回“曾失败但未被最后一次执行范围覆盖”的文件列表（空 = 无逃逸）。

    - 只在存在 ≥2 次执行时判定（单次执行由 exit_code 规则负责）；
    - 最后一次执行非全绿时不做范围判定（由 exit_code 规则负责）；
    - 基线排除（require_all_green=False）：首次执行即失败的文件视为既有失败不计入，
      防基线红的工程被永久卡死；require_all_green=True 时不适用基线排除
      （任务要求全绿，既有失败也属于任务范围）。
    """
    if len(history) < 2:
        return []
    last = history[-1]
    if last.get("exit_code") != 0:
        return []
    baseline = set() if require_all_green else baseline_failed_files(history)
    required: set = set()
    for run in history[:-1]:
        required |= (run.get("failed_files") or set()) - baseline
    return sorted(f for f in required if not _covers(last.get("scope", ""), f))
