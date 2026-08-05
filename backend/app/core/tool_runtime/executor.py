"""工具执行器 — 统一执行所有工具调用，从 model.py 迁移而来。

负责：
- 文件工具执行（read_file / write_file / list_files）
- Git 工具执行
- 搜索工具执行
- 命令工具执行（run_command）
- 通用工具执行（tool_registry）
- Plan 模式只读拦截
- ToolCallCard 格式化
"""

import json
import time
from typing import Callable, Dict, Any, Optional

from app.core.tools import execute_file_tool
from app.core.git_tools import GIT_TOOLS, execute_git_tool
from app.core.search_tools import SEARCH_TOOLS, execute_search_tool
from app.core.command_tools import COMMAND_TOOLS, execute_command_tool
from app.services.tools import tool_registry
from app.core.tool_runtime.events import make_tool_start, make_tool_result


async def execute_tool(
    tool_call: Dict,
    project_path: str | None,
    read_only: bool,
    ctx: Dict[str, Any] | None = None,
    emit: Optional[Callable[[Dict], None]] = None,
) -> Dict:
    """执行单个工具调用

    Args:
        tool_call: {"function": {"name": "...", "arguments": "..."}, "id": "..."}
        project_path: 项目路径（可为 None）
        read_only: 是否为只读模式
        ctx: 上下文（agent_id, project_id 等），供 add_memory 等工具使用
        emit: 可选事件发射器（接收 tool_start / tool_result 事件）。不传则静默（非流式路径零影响）。

    Returns:
        {
            "name": str,
            "tool": str,
            "path": str,
            "success": bool,
            "status": str,
            "arguments": dict,
            "result": str,
            "duration_ms": int,
            "tool_call_id": str,
        }
    """
    ctx = ctx or {}
    func_name = tool_call["function"]["name"]
    tool_call_id = tool_call.get("id", "")

    try:
        func_args = json.loads(tool_call["function"].get("arguments", "{}") or "{}")
    except Exception:
        func_args = {}

    # 工具开始事件：分发前发射
    if emit:
        emit(make_tool_start(tool_call_id=tool_call_id, tool=func_name, input_args=func_args))
    _start_time = time.monotonic()

    result_text = ""

    # 文件工具
    if func_name in ("write_file", "read_file", "list_files"):
        if not project_path:
            result_text = "错误: 文件操作需要绑定项目"
        elif read_only and func_name == "write_file":
            result_text = "错误: 当前为 plan 只读模式，禁止写入或修改项目文件。如需修改请切换到 build 模式。"
        else:
            result_text = execute_file_tool(func_name, project_path=project_path, **func_args)

    # Git 工具
    elif func_name in GIT_TOOLS:
        if not project_path:
            result_text = "错误: Git 操作需要绑定项目"
        elif read_only:
            result_text = "错误: 当前为 plan 只读模式，git 提交/回滚类操作被禁止。查看状态可先切换到 build 模式。"
        else:
            result_text = execute_git_tool(func_name, project_path=project_path, **func_args)

    # 搜索工具
    elif func_name in SEARCH_TOOLS:
        if not project_path:
            result_text = "错误: 搜索操作需要绑定项目"
        else:
            result_text = execute_search_tool(func_name, project_path=project_path, **func_args)

    # 命令工具
    elif func_name in COMMAND_TOOLS:
        if read_only:
            result_text = "错误: 当前为 plan 只读模式，禁止执行命令。查看状态可先切换到 build 模式。"
        else:
            result_text = execute_command_tool(func_name, project_path=project_path or "", **func_args)

    # 通用工具（web_search, fetch_url, add_memory 等）
    else:
        r = await tool_registry.execute(func_name, **{**ctx, **func_args})
        result_text = r.output if r.success else f"Error: {r.error}"

    # ToolCallCard 格式化
    rel_path = str(func_args.get("relative_path", ""))
    success = not result_text.startswith("错误")
    duration_ms = round((time.monotonic() - _start_time) * 1000)

    record = {
        "name": func_name,
        "tool": func_name,
        "path": rel_path,
        "success": success,
        "status": "success" if success else "failed",
        "arguments": func_args,
        "result": result_text,
        "duration_ms": duration_ms,
        "tool_call_id": tool_call_id,
    }

    # 工具结束事件：构造 record 前发射
    if emit:
        emit(make_tool_result(
            tool_call_id=tool_call_id,
            tool=func_name,
            success=success,
            result=result_text,
            duration_ms=duration_ms,
        ))

    return record