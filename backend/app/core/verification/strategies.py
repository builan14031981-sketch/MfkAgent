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
from app.core.sandbox import SandboxViolation, resolve_sandbox_path


def _resolve_path(project_path: Optional[str], relative_path: str) -> Optional[str]:
    """沙箱内解析绝对路径；路径越权/非法时返回 None（统一沙箱校验）。"""
    if not project_path or not relative_path:
        return None
    try:
        return str(resolve_sandbox_path(relative_path, project_path))
    except (SandboxViolation, PermissionError, ValueError, TypeError):
        return None


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


def verify_replace_in_file(record: dict, project_path: Optional[str]) -> VerificationResult:
    """replace_in_file 验证：检查替换是否成功。

    - 文件不存在          → failed
    - 替换内容未找到       → need_retry（可能是路径或内容不匹配）
    - 替换成功            → passed
    """
    args = record.get("arguments") or {}
    rel = args.get("relative_path")
    old_str = args.get("old_str")
    new_str = args.get("new_str")

    if not rel:
        return VerificationResult(
            FAILED, "验证失败: replace_in_file 参数缺少 relative_path",
            strategy="replace_in_file",
        )

    abs_path = _resolve_path(project_path, rel)
    if abs_path is None:
        return VerificationResult(
            NEED_RETRY, f"验证失败: 缺少有效项目路径，无法校验 {rel}",
            evidence={"relative_path": rel},
            strategy="replace_in_file",
        )

    if not os.path.isfile(abs_path):
        return VerificationResult(
            FAILED,
            f"验证失败: 文件不存在 {rel}",
            evidence={"path": abs_path},
            strategy="replace_in_file",
        )

    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # 检查 old_str 是否还在文件中（如果还在说明替换失败）
    if old_str and old_str in content:
        return VerificationResult(
            NEED_RETRY,
            f"验证失败: 替换内容未生效 {rel}",
            evidence={"path": abs_path, "old_str_found": True},
            strategy="replace_in_file",
        )

    # 检查 new_str 是否在文件中（如果不在说明替换失败）
    if new_str and new_str not in content:
        return VerificationResult(
            NEED_RETRY,
            f"验证失败: 新内容未写入 {rel}",
            evidence={"path": abs_path, "new_str_found": False},
            strategy="replace_in_file",
        )

    return VerificationResult(
        PASSED,
        f"验证通过: 文件替换成功 {rel}",
        evidence={"path": abs_path, "size": os.path.getsize(abs_path)},
        strategy="replace_in_file",
    )


def verify_apply_patch(record: dict, project_path: Optional[str]) -> VerificationResult:
    """apply_patch 验证：检查 patch 是否应用成功。

    - 文件不存在          → failed
    - patch 应用失败       → need_retry
    - patch 应用成功       → passed
    """
    args = record.get("arguments") or {}
    rel = args.get("relative_path")
    patch_content = args.get("patch")

    if not rel:
        return VerificationResult(
            FAILED, "验证失败: apply_patch 参数缺少 relative_path",
            strategy="apply_patch",
        )

    abs_path = _resolve_path(project_path, rel)
    if abs_path is None:
        return VerificationResult(
            NEED_RETRY, f"验证失败: 缺少有效项目路径，无法校验 {rel}",
            evidence={"relative_path": rel},
            strategy="apply_patch",
        )

    if not os.path.isfile(abs_path):
        return VerificationResult(
            FAILED,
            f"验证失败: 文件不存在 {rel}",
            evidence={"path": abs_path},
            strategy="apply_patch",
        )

    # 检查工具执行结果中是否有错误标记
    result_text = record.get("result", "") or ""
    if "error" in result_text.lower() or "failed" in result_text.lower():
        return VerificationResult(
            NEED_RETRY,
            f"验证失败: patch 应用可能失败 {rel}",
            evidence={"path": abs_path, "result": result_text[:500]},
            strategy="apply_patch",
        )

    return VerificationResult(
        PASSED,
        f"验证通过: patch 应用成功 {rel}",
        evidence={"path": abs_path, "size": os.path.getsize(abs_path)},
        strategy="apply_patch",
    )


def verify_git_commit(record: dict, project_path: Optional[str]) -> VerificationResult:
    """git_commit 验证：检查提交是否成功。

    - 提交成功（包含 commit hash）→ passed
    - 提交失败（无 hash 或有错误）→ need_retry
    """
    result_text = record.get("result", "") or ""

    # 检查是否包含 commit hash（通常是 7-40 位十六进制）
    commit_hash_pattern = r"\b[a-f0-9]{7,40}\b"
    if re.search(commit_hash_pattern, result_text, re.IGNORECASE):
        return VerificationResult(
            PASSED,
            "验证通过: git commit 成功",
            evidence={"result": result_text[:500]},
            strategy="git_commit",
        )

    # 检查是否有错误标记
    if "error" in result_text.lower() or "failed" in result_text.lower():
        return VerificationResult(
            NEED_RETRY,
            "验证失败: git commit 失败",
            evidence={"result": result_text[:500]},
            strategy="git_commit",
        )

    # 无法确定结果
    return VerificationResult(
        NEED_RETRY,
        "验证失败: 无法确认 git commit 是否成功",
        evidence={"result": result_text[:500]},
        strategy="git_commit",
    )


def default_verify(record: dict, project_path: Optional[str]) -> VerificationResult:
    """默认策略：无验证需求，直接通过（skip/pass）。"""
    return VerificationResult(PASSED, "无验证策略，默认通过", strategy="default")


# 工具名 → 验证策略路由表
VERIFIERS = {
    "write_file": verify_write_file,
    "run_command": verify_run_command,
    "replace_in_file": verify_replace_in_file,
    "apply_patch": verify_apply_patch,
    "git_commit": verify_git_commit,
}
