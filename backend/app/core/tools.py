"""本地项目沙箱文件工具集 —— 供 LLM Function Calling 使用。

所有工具接收 `project_path` + `relative_path`，通过 realpath 沙箱校验，
确保读写范围严格限定在项目工作区内，防止越权访问项目外文件。
"""
from typing import Dict, List, Optional
import os


class ToolExecutionError(Exception):
    """工具执行失败（消息会原样返回给 LLM）"""


def _resolve_sandbox_path(project_path: str, relative_path: str = ".") -> str:
    """沙箱解析：将项目内相对路径解析为绝对路径，并校验位于 project_path 内。"""
    if not project_path:
        raise ToolExecutionError("project_path 不能为空")
    proj_real = os.path.realpath(project_path)
    if not os.path.isdir(proj_real):
        raise ToolExecutionError(f"项目目录不存在: {project_path}")

    target = os.path.realpath(os.path.join(proj_real, relative_path or "."))
    if target != proj_real and not target.startswith(proj_real + os.sep):
        raise ToolExecutionError(f"路径越权，禁止访问项目目录之外: {relative_path}")
    return target


def write_file(project_path: str, relative_path: str, content: str) -> str:
    """写入/覆写本地项目文件。若父目录不存在会自动创建。"""
    target = _resolve_sandbox_path(project_path, relative_path)
    parent = os.path.dirname(target)
    os.makedirs(parent, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return f"文件已写入: {relative_path} ({len(content)} 字符)"


def read_file(project_path: str, relative_path: str) -> str:
    """读取本地项目文件内容。"""
    target = _resolve_sandbox_path(project_path, relative_path)
    if not os.path.isfile(target):
        raise ToolExecutionError(f"文件不存在: {relative_path}")
    if os.path.getsize(target) > 100 * 1024:
        raise ToolExecutionError(f"文件过大（>100KB）: {relative_path}")
    with open(target, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def list_files(project_path: str, relative_path: str = ".") -> str:
    """查看本地项目目录结构。"""
    target = _resolve_sandbox_path(project_path, relative_path)
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
    except ToolExecutionError as e:
        return f"错误: {e}"
    except Exception as e:
        return f"错误: {e}"
