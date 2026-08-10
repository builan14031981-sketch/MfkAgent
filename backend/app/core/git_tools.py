"""本地项目 Git 工具集 —— 供 LLM Function Calling 使用。

全部通过 subprocess 调用系统 git（参数用 list 数组，不拼接 shell 字符串，
杜绝注入）；工作目录限定在 project_path 内（统一沙箱锚定）。无需下载任何额外文件。

Phase 4 T1 增强：
- git_clone 执行前检查磁盘配额（剩余空间 ≥ 2GB），不足时拒绝
- git_clone 执行后写审计日志到 sandbox_audit_logs（旁路，失败不影响主流程）
"""
import logging
import re
import subprocess
from typing import Dict, List, Optional
import os
from urllib.parse import urlparse

from app.core.sandbox import (
    SandboxViolation,
    check_disk_quota,
    decode_subprocess_output,
    resolve_sandbox_path,
    run_subprocess,
    DISK_QUOTA_BYTES,
)

logger = logging.getLogger(__name__)


class GitToolError(Exception):
    """Git 工具执行失败（消息原样返回给 LLM）"""


def _truncate_audit_text(text: str, max_len: int = 8192) -> str:
    """审计日志文本截断（避免 LLM 长输出撑爆数据库）。"""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"...(truncated, total {len(text)} chars)"


def _write_git_audit(
    tool_name: str,
    command: str,
    cwd: str,
    duration_ms: int,
    exit_code: Optional[int],
    output_size: int,
    success: bool,
    error_message: Optional[str] = None,
    chat_id: Optional[int] = None,
    agent_run_id: Optional[int] = None,
) -> None:
    """Phase 4 T1: 写 git 操作审计日志（旁路设计，失败不影响主流程）。"""
    try:
        from app.core.database import SessionLocal
        from app.models.agent import SandboxAuditLog

        db = SessionLocal()
        try:
            log = SandboxAuditLog(
                chat_id=chat_id,
                agent_run_id=agent_run_id,
                tool_name=tool_name,
                command=_truncate_audit_text(command),
                cwd=_truncate_audit_text(cwd) if cwd else None,
                duration_ms=duration_ms,
                exit_code=exit_code,
                output_size=output_size,
                success=success,
                error_message=_truncate_audit_text(error_message) if error_message else None,
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.warning("[sandbox_audit] 写入 git 审计日志失败: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception as e:
        logger.warning("[sandbox_audit] 初始化 git 审计会话失败: %s", e)


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


def git_branch_list(project_path: str, show_remote: bool = False) -> str:
    """查看分支列表（只读）。默认显示本地分支，可选显示远程分支。"""
    if not _is_repo(project_path):
        return "该项目尚未初始化 Git 仓库（无 .git 目录）"
    args = ["branch", "-a"] if show_remote else ["branch"]
    out = _git(project_path, args)
    if not out:
        return "（无分支）"
    return out


def git_remote(project_path: str) -> str:
    """查看远程仓库信息（名称 + URL，只读）。"""
    if not _is_repo(project_path):
        return "该项目尚未初始化 Git 仓库（无 .git 目录）"
    out = _git(project_path, ["remote", "-v"])
    if not out:
        return "未配置远程仓库（无 remote）。"
    return out


# ──── 写操作工具 ────


def _derive_repo_name(url: str) -> str:
    """从 GitHub HTTPS URL 提取仓库名（如 my-repo）。"""
    # 支持格式: https://github.com/owner/repo.git 或 https://github.com/owner/repo
    path = urlparse(url).path.rstrip("/")
    name = path.rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name or "cloned_repo"


def _validate_github_url(url: str) -> None:
    """校验 URL 为合法的 GitHub HTTPS 地址。"""
    if not url:
        raise GitToolError("clone URL 不能为空")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise GitToolError("只支持 HTTPS 协议的 GitHub 地址（如 https://github.com/owner/repo.git）")
    if "github.com" not in parsed.netloc:
        raise GitToolError("只支持 github.com 的仓库地址")
    if not parsed.path or parsed.path == "/":
        raise GitToolError("URL 缺少仓库路径")


def git_clone(
    project_path: str,
    url: str,
    target_dir: str = "",
    chat_id: Optional[int] = None,
    agent_run_id: Optional[int] = None,
) -> str:
    """从 GitHub HTTPS 地址 clone 仓库到项目工作区。

    Args:
        project_path: 当前项目路径（用作 clone 的目标父目录）
        url: GitHub HTTPS 仓库地址
        target_dir: 目标目录名（可选，默认从 URL 提取）

    Returns:
        clone 结果描述（含目标路径）
    """
    _validate_github_url(url)
    if not target_dir or not target_dir.strip():
        target_dir = _derive_repo_name(url)
    else:
        target_dir = target_dir.strip()
        # 禁止目录名含路径分隔符或特殊字符
        if re.search(r'[/\\:*?"<>|]', target_dir):
            raise GitToolError(f"目标目录名包含非法字符: {target_dir}")

    # 沙箱校验：目标路径必须在 project_path 内
    try:
        target_real = str(resolve_sandbox_path(target_dir, project_path))
    except SandboxViolation as e:
        raise GitToolError(f"clone 目标路径越权: {e}")

    if os.path.exists(target_real):
        raise GitToolError(f"目标目录已存在: {target_dir}（请选择其他目录名或先删除已有目录）")

    # Phase 4 T1: 磁盘配额检查（剩余空间 ≥ 2GB）
    required_bytes = DISK_QUOTA_BYTES.get("git_clone", 0)
    if required_bytes > 0:
        ok, message = check_disk_quota(target_real, required_bytes)
        if not ok:
            _write_git_audit(
                tool_name="git_clone",
                command=f"git clone {url} {target_dir}".strip(),
                cwd=project_path or "",
                duration_ms=0,
                exit_code=None,
                output_size=0,
                success=False,
                error_message=f"磁盘配额不足: {message}",
                chat_id=chat_id,
                agent_run_id=agent_run_id,
            )
            raise GitToolError(f"【安全拦截】磁盘配额检查未通过: {message}")

    import time as _time
    start = _time.monotonic()
    try:
        _git(project_path, ["clone", url, target_dir], timeout=300)
    except GitToolError as e:
        elapsed_ms = int((_time.monotonic() - start) * 1000)
        _write_git_audit(
            tool_name="git_clone",
            command=f"git clone {url} {target_dir}".strip(),
            cwd=project_path or "",
            duration_ms=elapsed_ms,
            exit_code=1,
            output_size=0,
            success=False,
            error_message=str(e),
            chat_id=chat_id,
            agent_run_id=agent_run_id,
        )
        raise GitToolError(f"clone 失败: {e}")

    elapsed_ms = int((_time.monotonic() - start) * 1000)
    _write_git_audit(
        tool_name="git_clone",
        command=f"git clone {url} {target_dir}".strip(),
        cwd=project_path or "",
        duration_ms=elapsed_ms,
        exit_code=0,
        output_size=0,
        success=True,
        chat_id=chat_id,
        agent_run_id=agent_run_id,
    )

    return (
        f"已成功 clone 仓库到: {target_real}\n"
        f"仓库地址: {url}\n"
        f"目标目录: {target_dir}"
    )


def git_pull(project_path: str) -> str:
    """拉取远程更新（git pull），基于当前 project_path。

    要求当前项目已配置 remote，自动识别 .git/config。
    """
    if not _is_repo(project_path):
        return "该项目尚未初始化 Git 仓库（无 .git 目录）"
    remote_info = _git(project_path, ["remote", "-v"])
    if not remote_info:
        return "未配置远程仓库（无 remote），无法 pull。请先配置 remote。"
    try:
        out = _git(project_path, ["pull"], timeout=120)
    except GitToolError as e:
        raise GitToolError(f"pull 失败: {e}")
    return out if out else "已拉取远程更新（无冲突）。"


def git_push(project_path: str) -> str:
    """推送本地提交到远程仓库（git push）。

    基于当前 project_path 和当前分支，自动推送。
    """
    if not _is_repo(project_path):
        return "该项目尚未初始化 Git 仓库（无 .git 目录）"
    remote_info = _git(project_path, ["remote", "-v"])
    if not remote_info:
        return "未配置远程仓库（无 remote），无法 push。请先配置 remote。"
    try:
        out = _git(project_path, ["push"], timeout=120)
    except GitToolError as e:
        raise GitToolError(f"push 失败: {e}")
    return out if out else "已推送成功。"


def git_fetch(project_path: str) -> str:
    """从远程仓库获取最新信息（git fetch，只读操作）。

    不合并代码，仅更新远程跟踪分支。
    """
    if not _is_repo(project_path):
        return "该项目尚未初始化 Git 仓库（无 .git 目录）"
    remote_info = _git(project_path, ["remote", "-v"])
    if not remote_info:
        return "未配置远程仓库（无 remote），无法 fetch。请先配置 remote。"
    try:
        out = _git(project_path, ["fetch"], timeout=120)
    except GitToolError as e:
        raise GitToolError(f"fetch 失败: {e}")
    return out if out else "已获取远程更新（fetch 完成）。"


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
    {
        "type": "function",
        "function": {
            "name": "git_branch_list",
            "description": (
                "查看当前项目的 Git 分支列表（只读）。"
                "当用户问「有哪些分支」「当前在哪个分支」「分支列表」时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "show_remote": {
                        "type": "boolean",
                        "description": "是否同时显示远程分支（默认 false，仅本地分支）",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_remote",
            "description": (
                "查看当前项目的远程仓库信息（名称 + URL，只读）。"
                "当用户问「远程仓库是什么」「GitHub 地址」「remote 信息」时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_clone",
            "description": (
                "从 GitHub HTTPS 地址 clone 仓库到项目工作区。"
                "当用户说「clone 这个仓库」「下载这个项目」「克隆 xxx」时调用。"
                "注意：此操作需要用户审批。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "GitHub HTTPS 仓库地址（如 https://github.com/owner/repo.git）",
                    },
                    "target_dir": {
                        "type": "string",
                        "description": "目标目录名（可选，默认从 URL 自动提取仓库名）",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_pull",
            "description": (
                "拉取远程仓库的更新到本地（git pull）。"
                "当用户说「拉取更新」「同步远程代码」「pull 一下」时调用。"
                "注意：此操作需要用户审批。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_push",
            "description": (
                "推送本地提交到远程仓库（git push）。"
                "当用户说「推送代码」「push 到远程」「上传提交」时调用。"
                "注意：此操作需要用户审批。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_fetch",
            "description": (
                "从远程仓库获取最新信息（git fetch，只读操作，不合并）。"
                "当用户说「获取远程更新」「fetch 一下」「查看远程有没有新提交」时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
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
    "git_branch_list": git_branch_list,
    "git_remote": git_remote,
    "git_clone": git_clone,
    "git_pull": git_pull,
    "git_push": git_push,
    "git_fetch": git_fetch,
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
