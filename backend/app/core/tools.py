"""本地项目沙箱文件工具集 —— 供 LLM Function Calling 使用。

所有工具接收 `project_path` + `relative_path`，经由 app.core.sandbox 统一沙箱
校验（resolve + is_relative_to，Windows 大小写安全），确保读写范围严格限定
在项目工作区内，越权抛 PermissionError（SandboxViolation），防止路径穿越。

Phase 9 P1: 写入文件时通过 sanitize_filename 清理非法字符。
"""
from typing import Dict, List, Optional
import os

from app.core.sandbox import SandboxViolation, resolve_sandbox_path
from app.core.sanitize import sanitize_filename


class ToolExecutionError(Exception):
    """工具执行失败（消息会原样返回给 LLM）"""


def _sanitize_relative_path(relative_path: str) -> str:
    """Phase 9: 逐级清理相对路径中的非法文件名字符。

    仅清理文件名组件（不含路径分隔符），保留目录结构。
    """
    parts = relative_path.replace("\\", "/").split("/")
    cleaned = [sanitize_filename(p) for p in parts if p]
    return "/".join(cleaned)


def write_file(project_path: str, relative_path: str, content: str) -> str:
    """写入/覆写本地项目文件。若父目录不存在会自动创建。

    目标路径先过沙箱校验；其父目录是校验后目标的前缀，天然仍在项目内，
    因此 makedirs 不会越权。

    Phase 9: 文件名组件通过 sanitize_filename 清理非法字符。
    """
    # Phase 9: 逐级清理文件名中的非法字符
    sanitized = _sanitize_relative_path(relative_path)
    target = resolve_sandbox_path(sanitized, project_path)
    os.makedirs(target.parent, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    abs_path = str(target)
    return f"文件已写入: {sanitized} ({len(content)} 字符) | abs_path={abs_path}"


def read_file(project_path: str, relative_path: str) -> str:
    """读取本地项目文件内容。"""
    target = resolve_sandbox_path(relative_path, project_path)
    if not os.path.isfile(target):
        raise ToolExecutionError(f"文件不存在: {relative_path}")
    if os.path.getsize(target) > 100 * 1024:
        raise ToolExecutionError(f"文件过大（>100KB）: {relative_path}")
    with open(target, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def list_files(project_path: str, relative_path: str = ".") -> str:
    """查看本地项目目录结构。"""
    target = resolve_sandbox_path(relative_path, project_path)
    if not os.path.isdir(target):
        raise ToolExecutionError(f"目录不存在: {relative_path}")
    lines = []
    for name in sorted(os.listdir(target)):
        full = os.path.join(target, name)
        if os.path.isdir(full):
            lines.append(f"{name}/")
        else:
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            lines.append(f"{name} ({size} bytes)")
    return "\n".join(lines) if lines else "(空目录)"


def add_memory(scope: str, content: str, agent_id: str = None, project_id: int = None) -> str:
    """将内容持久化保存为记忆（三作用域隔离）。

    scope：global=所有对话可见；agent=当前 Agent 专属（需 agent_id）；
           project=当前项目下 Agent 共享（需 project_id）。
    """
    if scope not in ("global", "agent", "project"):
        return f"错误: scope 必须是 global/agent/project，收到: {scope}"
    if scope == "agent" and not agent_id:
        return "错误: agent 记忆需要当前 Agent 上下文"
    if scope == "project" and not project_id:
        return "错误: project 记忆需要当前项目上下文"
    content = (content or "").strip()
    if not content:
        return "错误: content 不能为空"
    from app.core.database import SessionLocal
    from app.models.agent import MemoryItem

    db = SessionLocal()
    try:
        item = MemoryItem(
            scope=scope,
            agent_id=agent_id if scope == "agent" else None,
            project_id=project_id if scope == "project" else None,
            content=content,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return f"记忆已保存（scope={scope}, id={item.id}）: {content[:80]}"
    except Exception as e:
        return f"错误: 记忆保存失败: {e}"
    finally:
        db.close()


# ============ OpenAI Function Calling Schema ============

FILE_TOOLS_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "将内容写入/覆写本地项目文件（工作区内，相对项目根路径）。"
                "当用户要求创建或修改代码/文件时，必须调用本工具真实写入磁盘。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "相对项目根目录的文件路径，如 src/app.py 或 README.md",
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的完整文件内容",
                    },
                },
                "required": ["relative_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取本地项目文件内容（工作区内，相对项目根路径）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "相对项目根目录的文件路径",
                    },
                },
                "required": ["relative_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出本地项目目录结构（工作区内，相对项目根路径）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "相对项目根目录的子目录路径，默认项目根目录",
                    },
                },
            },
        },
    },
]

FILE_TOOLS = {
    "write_file": write_file,
    "read_file": read_file,
    "list_files": list_files,
}


def execute_file_tool(name: str, project_path: str, **kwargs) -> str:
    """执行文件工具并返回文本结果（成功返回输出，失败返回错误说明）。"""
    fn = FILE_TOOLS.get(name)
    if fn is None:
        return f"错误: 未知工具 {name}"
    try:
        return fn(project_path=project_path, **kwargs)
    except SandboxViolation as e:
        # 路径越权（PermissionError）：显式拦截，不当作普通 Exception 吞掉
        return f"错误: {e}"
    except ToolExecutionError as e:
        return f"错误: {e}"
    except Exception as e:
        return f"错误: {e}"
