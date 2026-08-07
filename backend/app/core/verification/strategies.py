"""Verification 策略 — Phase E4 基础验证（程序验证优先）。

策略按工具名路由，接收 executor 的 tool record（含 arguments / result / success），
返回 VerificationResult。未知工具走 default_verify（skip/pass）。

第一版支持：
  1. write_file   — 重读磁盘校验：文件存在 + 内容一致
  2. run_command  — 解析结果内嵌的 [exit code N]：0 → passed；非零 → need_retry
  3. 其它工具      — 无策略，默认 passed（不阻塞流程）

注意：
  - 验证全程不依赖 LLM 判断，为确定性程序校验。
  - 只对 status == "success"（动作真实发生）的 record 调用；失败/拒绝的 record
    已在工具结果中回馈错误，不再重复验证。
"""

import os
import re
from typing import Optional

from app.core.verification.models import (
    VerificationResult,
    PASSED,
    FAILED,
    NEED_RETRY,
)


def _resolve_path(project_path: Optional[str], relative_path: str) -> Optional[str]:
    """沙箱内解析绝对路径；路径越权/非法时返回 None。"""
    if not project_path or not relative_path:
        return None
    try:
        target = os.path.realpath(os.path.join(project_path, relative_path))
    except (ValueError, TypeError):
        return None
    root = os.path.realpath(project_path)
    if target != root and not target.startswith(root + os.sep):
        return None
    return target


def verify_write_file(record: dict, project_path: Optional[str]) -> VerificationResult:
    """write_file 验证：文件是否存在 + 内容是否一致（重读磁盘）。

    - 文件不存在          → failed（动作未达成）
    - 内容不一致（可能被截断/编码问题）→ need_retry
    - 文件存在且内容一致    → passed
    """
    args = record.get("arguments") or {}
    rel = args.get("relative_path")
    expected = args.get("content")

    if not rel:
        return VerificationResult(
            FAILED, "验证失败: write_file 参数缺少 relative_path",
            strategy="write_file",
        )

    abs_path = _resolve_path(project_path, rel)
    if abs_path is None:
        return VerificationResult(
            NEED_RETRY, f"验证失败: 缺少有效项目路径，无法校验 {rel}",
            evidence={"relative_path": rel},
            strategy="write_file",
        )

    if not os.path.isfile(abs_path):
        return VerificationResult(
            FAILED,
            f"验证失败: 文件未创建 {rel}",
            evidence={"path": abs_path},
            strategy="write_file",
        )

    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
        actual = f.read()

    if expected is not None and actual != expected:
        return VerificationResult(
            NEED_RETRY,
            f"验证失败: 文件内容不一致 {rel}",
            evidence={
                "path": abs_path,
                "expected_len": len(expected),
                "actual_len": len(actual),
            },
            strategy="write_file",
        )

    return VerificationResult(
        PASSED,
        f"验证通过: 文件已写入且内容一致 {rel}",
        evidence={"path": abs_path, "size": os.path.getsize(abs_path)},
        strategy="write_file",
    )


def verify_run_command(record: dict, project_path: Optional[str]) -> VerificationResult:
    """run_command 验证：解析内嵌 exit code。

    - [exit code 0]          → passed
    - [exit code N>0]        → need_retry（命令失败，回喂模型重试）
    - 无退出码标记且工具失败   → failed
    - 无退出码标记且未知       → failed（无法程序化判定）
    """
    text = record.get("result", "") or ""
    m = re.search(r"\[exit code (\d+)\]", text)

    if m:
        code = int(m.group(1))
        if code == 0:
            return VerificationResult(
                PASSED, "验证通过: 命令退出码 0",
                evidence={"exit_code": code},
                strategy="run_command",
            )
        return VerificationResult(
            NEED_RETRY,
            f"验证失败: 命令退出码非零 ({code})",
            evidence={"exit_code": code, "output": text[:2000]},
            strategy="run_command",
        )

    if record.get("success") is False:
        return VerificationResult(
            FAILED, "验证失败: 命令工具执行失败",
            evidence={"result": text[:2000]},
            strategy="run_command",
        )

    return VerificationResult(
        FAILED, "验证失败: 无法解析命令退出码",
        evidence={"result": text[:2000]},
        strategy="run_command",
    )


def default_verify(record: dict, project_path: Optional[str]) -> VerificationResult:
    """默认策略：无验证需求，直接通过（skip/pass）。"""
    return VerificationResult(PASSED, "无验证策略，默认通过", strategy="default")


# 工具名 → 验证策略路由表
VERIFIERS = {
    "write_file": verify_write_file,
    "run_command": verify_run_command,
}
