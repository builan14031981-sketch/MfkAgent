"""本地项目 Git 工具集 —— 供 LLM Function Calling 使用。

全部通过 subprocess 调用系统 git（参数用 list 数组，不拼接 shell 字符串，
杜绝注入）；工作目录限定在 project_path 内（统一沙箱锚定）。无需下载任何额外文件。
"""
from typing import Dict, List, Optional
import os
import subprocess

from app.core.sandbox import (
    SandboxViolation,
    decode_subprocess_output,
    resolve_sandbox_path,
    run_subprocess,
)


class GitToolError(Exception):
    """Git 工具执行失败（消息原样返回给 LLM）"""


def _git(project_path: str, args: List[str], timeout: int = 60) -> str:
    """执行 git 命令，返回 stdout（stderr 合并）。"""
    if not project_path:
        raise GitToolError("project_path 不能为空")
    try:
        proj_real = str(resolve_sandbox_path(".", project_path))
    except SandboxViolation as e:
        raise GitToolError(f"{e}")
    if not os.path.isdir(proj_real):
        raise GitToolError(f"项目目录不存在: {project_path}")
    try:
        proc = run_subprocess(["git"] + args, cwd=proj_real, timeout=timeout)
    except FileNotFoundError:
        raise GitToolError("未检测到 git 命令，请先安装 Git")
    except subprocess.TimeoutExpired:
        raise GitToolError(f"git 命令执行超时（>{timeout}s）")
    if proc.returncode != 0:
        msg = (decode_subprocess_output(proc.stderr) or decode_subprocess_output(proc.stdout) or "").strip()
        raise GitToolError(msg or f"git 命令失败（exit {proc.returncode}）")
    return (decode_subprocess_output(proc.stdout) or "").strip()


def _is_repo(project_path: str) -> bool:
    try:
        _git(project_path, ["rev-parse", "--is-inside-work-tree"])
        return True
    except GitToolError:
        return False


def _resolve_rel(project_path: str, relative_path: str = "") -> str:
    """限定相对路径必须在项目工作区内（统一沙箱校验，防 ../ 与符号链接逃逸）。

    仅做校验，返回原始相对路径（git 需相对 cwd 的路径参数）。
    """
    if not relative_path:
        return "."
    try:
        resolve_sandbox_path(relative_path, project_path)  # 校验越权即抛
    except SandboxViolation as e:
        raise GitToolError(f"{e}")
    return relative_path


def git_status(project_path: str, relative_path: str = "") -> str:
    """查看项目 Git 工作区状态（改动的文件列表）。"""
    if not _is_repo(project_path):
        return "该项目尚未初始化 Git 仓库（无 .git 目录）"
    rel = _resolve_rel(project_path, relative_path)
    out = _git(project_path, ["status", "--short", "--", rel])
    if not out:
        return "工作区干净，无改动。"
    return out


def git_diff(project_path: str, relative_path: str = "") -> str:
    """查看项目未提交改动的内容差异（工作区 + 暂存区）。"""
    if not _is_repo(project_path):
        return "该项目尚未初始化 Git 仓库（无 .git 目录）"
    rel = _resolve_rel(project_path, relative_path)
    parts = []
    unstaged = _git(project_path, ["diff", "--", rel])
    if unstaged:
        parts.append("## 未暂存改动 (working tree):\n" + unstaged)
    staged = _git(project_path, ["diff", "--cached", "--", rel])
    if staged:
        parts.append("## 已暂存改动 (staged):\n" + staged)
    if not parts:
        return "没有未提交的改动。"
    return "\n\n".join(parts)


def git_log(project_path: str, n: int = 10) -> str:
    """查看项目最近提交历史（最多 n 条，默认 10）。"""
    if not _is_repo(project_path):
        return "该项目尚未初始化 Git 仓库（无 .git 目录）"
    n = max(1, min(int(n or 10), 50))
    return _git(project_path, ["log", f"-{n}", "--oneline", "--decorate", "--no-merges"])


def git_commit(project_path: str, message: str) -> str:
    """暂存全部改动并提交（git add -A + git commit）。"""
    if not _is_repo(project_path):
        return "该项目尚未初始化 Git 仓库（无 .git 目录）"
    if not (message or "").strip():
        raise GitToolError("提交信息（message）不能为空")
    _git(project_path, ["add", "-A"])
    status = _git(project_path, ["status", "--short"])
    if not status:
        return "没有待提交的改动（工作区干净）。"
    try:
        head_before = _git(project_path, ["rev-parse", "--short", "HEAD"])
    except GitToolError:
        head_before = "(无提交)"
    _git(project_path, ["commit", "-m", message.strip()])
    head_after = _git(project_path, ["rev-parse", "--short", "HEAD"])
    return f"已提交: {head_before} -> {head_after}\n提交信息: {message.strip()}\n\n改动文件:\n{status}"


def git_restore(project_path: str, relative_path: str = "") -> str:
    """丢弃未提交的改动（回滚工作区/暂存区）。relative_path 为空则全部还原。"""
    if not _is_repo(project_path):
        return "该项目尚未初始化 Git 仓库（无 .git 目录）"
    rel = _resolve_rel(project_path, relative_path)
    targets = [rel] if rel != "." else None
    _git(project_path, ["restore", "--staged"] + (targets if targets else ["."]))
    _git(project_path, ["restore"] + (targets if targets else ["."]))
    scope = rel if rel != "." else "全部文件"
    return f"已丢弃未提交改动: {scope}"


def git_revert(project_path: str, commit_hash: str) -> str:
    """对指定已提交历史生成反向提交（git revert，保留历史安全回滚）。"""
    if not _is_repo(project_path):
        return "该项目尚未初始化 Git 仓库（无 .git 目录）"
    h = (commit_hash or "").strip()
    if not h:
        raise GitToolError("commit_hash 不能为空")
    _git(project_path, ["revert", "--no-edit", h])
    return f"已回滚提交 {h}（生成反向提交，历史保留）"


# ============ OpenAI Function Calling Schema ============

GIT_TOOLS_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": (
                "查看当前项目 Git 工作区状态（改动的文件列表）。"
                "当用户问「改了什么」「当前项目状态」「有没有改动」时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "限定查看的子路径（可选），默认整个项目",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "查看当前项目未提交改动的内容差异（工作区 + 暂存区）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "限定查看的文件/子路径（可选），默认全部",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "查看当前项目最近的提交历史（commit 列表）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "description": "返回条数，默认 10",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": (
                "暂存当前项目全部改动并提交。当用户说「提交代码」「提交一下」「保存版本」时调用，"
                "提交信息 message 根据改动内容自动生成或采用用户指定的话。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "提交信息，简述本次改动内容",
                    },
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_restore",
            "description": (
                "丢弃未提交的改动（回滚工作区）。当用户说「撤销改动」「回滚」「不要这些改动了」且改动未提交时调用。"
                "注意：会永久丢弃未提交的内容。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "只回滚指定文件/子路径（可选），默认全部",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_revert",
            "description": (
                "对指定的已提交历史生成反向提交（安全回滚，保留历史）。"
                "当用户说「回滚到某个提交」「撤销刚才那个提交」且改动已提交时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "commit_hash": {
                        "type": "string",
                        "description": "要回滚的 commit 哈希（可用 git_log 查看）",
                    },
                },
                "required": ["commit_hash"],
            },
        },
    },
]

GIT_TOOLS = {
    "git_status": git_status,
    "git_diff": git_diff,
    "git_log": git_log,
    "git_commit": git_commit,
    "git_restore": git_restore,
    "git_revert": git_revert,
}


def execute_git_tool(name: str, project_path: str, **kwargs) -> str:
    """执行 Git 工具并返回文本结果（成功返回输出，失败返回错误说明）。"""
    fn = GIT_TOOLS.get(name)
    if fn is None:
        return f"错误: 未知工具 {name}"
    try:
        return fn(project_path=project_path, **kwargs)
    except GitToolError as e:
        return f"错误: {e}"
    except Exception as e:
        return f"错误: {e}"
