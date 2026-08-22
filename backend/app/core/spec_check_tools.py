"""verify_spec 工具 —— 机器校验文件是否符合规格断言（专治弱模型/小模型执行偏差）。

背景：构建类子代理（如 sub_frontend）常把精确规格改歪（px 写成 %、鼠标视差改成滚动
视差、内联占位图改成外链图），且会照着自己错的实现汇报。让模型"自觉自查"不可靠，
因此提供本工具：对目标文件跑一组可断言的正则检查，返回机器判定的 PASS/FAIL 清单，
结果硬性注入上下文，弱模型也无法把 FAIL 说成 PASS。

用法：
  verify_spec(
    relative_path="index.html",
    assertions=[
      {"name": "thumb_px", "pattern": "translate3d\\\\(\\\\$\\{px", "expect": "present",
       "hint": "滑块位移必须用 rect 计算出的 px，禁用 translateX(%)"},
      {"name": "no_google_fonts", "pattern": "fonts.googleapis.com", "expect": "absent"},
      {"name": "five_traits", "pattern": "'专业'|'友好'|'中性'|'创意'|'幽默'", "expect": "present",
       "count_min": 5, "hint": "滑块必须正好 5 档"},
    ]
  )
"""
import os
import re
from typing import Dict, List

from app.core.tools import ToolExecutionError
from app.core.sandbox import resolve_sandbox_path

MAX_FILE_SIZE = 2 * 1024 * 1024
MAX_ASSERTIONS = 30


def verify_spec(project_path: str, relative_path: str, assertions: List[Dict]) -> str:
    """对目标文件执行一组正则断言，返回逐条 PASS/FAIL 与最终 SPEC_CHECK_RESULT。"""
    relative_path = (relative_path or "").strip()
    if not relative_path:
        return "错误: relative_path 不能为空"
    try:
        target = resolve_sandbox_path(relative_path, project_path)
    except (ToolExecutionError, PermissionError) as e:
        return f"错误: {e}"
    if not os.path.isfile(target):
        return f"错误: 文件不存在: {relative_path}"

    try:
        if os.path.getsize(target) > MAX_FILE_SIZE:
            return f"错误: 文件过大（> {MAX_FILE_SIZE // 1024 // 1024}MB），无法校验: {relative_path}"
        with open(target, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except OSError as e:
        return f"错误: 读取文件失败: {e}"

    if not isinstance(assertions, list) or not assertions:
        return "错误: assertions 不能为空（至少一条断言）"

    assertions = assertions[:MAX_ASSERTIONS]
    lines: List[str] = []
    failed = 0
    for idx, a in enumerate(assertions, 1):
        if not isinstance(a, dict):
            lines.append(f"  [{idx}] FAIL 断言格式错误（须为对象）")
            failed += 1
            continue
        name = str(a.get("name") or f"assert_{idx}")[:60]
        pattern = a.get("pattern")
        expect = str(a.get("expect") or "present").strip().lower()
        case_sensitive = bool(a.get("case_sensitive", False))
        count_min = a.get("count_min")
        count_max = a.get("count_max")
        hint = str(a.get("hint") or "")[:200]

        if not isinstance(pattern, str) or not pattern:
            lines.append(f"  [{idx}] FAIL {name}: pattern 为空")
            failed += 1
            continue

        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            matches = re.findall(pattern, content, flags=flags)
        except re.error as e:
            lines.append(f"  [{idx}] FAIL {name}: 正则错误 {e}")
            failed += 1
            continue

        count = len(matches)
        status = "PASS"
        reason = ""
        if expect == "absent":
            if count > 0:
                status = "FAIL"
                reason = f"不应出现，实际命中 {count} 次"
        elif expect == "present":
            if count == 0:
                status = "FAIL"
                reason = "应出现，实际 0 次命中"
        else:
            status = "FAIL"
            reason = f"expect 仅支持 present/absent，收到 '{expect}'"

        if status == "PASS":
            if count_min is not None and count < int(count_min):
                status = "FAIL"
                reason = f"命中 {count} 次，低于 count_min={count_min}"
            elif count_max is not None and count > int(count_max):
                status = "FAIL"
                reason = f"命中 {count} 次，超过 count_max={count_max}"

        if status == "PASS":
            lines.append(f"  [{idx}] PASS {name} (命中 {count} 次)")
        else:
            failed += 1
            tail = f" | hint: {hint}" if hint else ""
            lines.append(f"  [{idx}] FAIL {name}: {reason}{tail}")

    result = "SPEC_CHECK_RESULT: FAIL" if failed else "SPEC_CHECK_RESULT: PASS"
    header = f"verify_spec 对 {relative_path} 校验 {len(assertions)} 条断言："
    body = "\n".join(lines)
    return f"{header}\n{body}\n{result}"


SPEC_CHECK_TOOLS_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "verify_spec",
            "description": (
                "对指定文件执行一组规格断言（正则 present/absent + 可选数量上下限），"
                "返回逐条 PASS/FAIL 与最终 SPEC_CHECK_RESULT（PASS/FAIL）。"
                "用于验证实现是否严格符合任务规格，是机器判定而非模型自查。"
                "每次写文件后必须调用，SPEC_CHECK_RESULT 为 FAIL 时必须修复后重新校验。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "待校验文件（相对项目根目录）",
                    },
                    "assertions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "断言名称（简短）",
                                },
                                "pattern": {
                                    "type": "string",
                                    "description": "正则表达式",
                                },
                                "expect": {
                                    "type": "string",
                                    "enum": ["present", "absent"],
                                    "description": "present=应出现；absent=不应出现",
                                },
                                "case_sensitive": {
                                    "type": "boolean",
                                    "description": "是否大小写敏感，默认 false",
                                },
                                "count_min": {
                                    "type": "integer",
                                    "description": "可选，命中次数下限",
                                },
                                "count_max": {
                                    "type": "integer",
                                    "description": "可选，命中次数上限",
                                },
                                "hint": {
                                    "type": "string",
                                    "description": "可选，FAIL 时提示如何修复",
                                },
                            },
                            "required": ["pattern", "expect"],
                        },
                        "description": "断言列表",
                    },
                },
                "required": ["relative_path", "assertions"],
            },
        },
    },
]

SPEC_CHECK_TOOLS = {
    "verify_spec": verify_spec,
}


def execute_spec_check_tool(name: str, project_path: str, **kwargs) -> str:
    """执行规格校验工具并返回文本结果（失败返回错误说明）。"""
    fn = SPEC_CHECK_TOOLS.get(name)
    if fn is None:
        return f"错误: 未知工具 {name}"
    try:
        return fn(project_path=project_path, **kwargs)
    except (ToolExecutionError, PermissionError) as e:
        return f"错误: {e}"
    except Exception as e:
        return f"错误: {e}"
