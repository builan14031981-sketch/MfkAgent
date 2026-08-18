"""MCP 桥接层 — 将插件工具注册到 MCPServer 并统一调用执行。

对外暴露三个函数：
  - register_plugin_tools_to_mcp()：把 PLUGIN_TOOL_MAP 中所有插件的工具注册到 MCPServer
  - call_mcp_tool(plugin_id, tool_name, args)：调用指定插件工具
  - get_mcp_tools(plugin_id)：获取某插件的工具列表
"""

from typing import Any, Dict, List
import json

from app.services.mcp import mcp_server, MCPTool
from app.core.plugin_tools import PLUGIN_TOOL_MAP


def register_plugin_tools_to_mcp():
    """把 PLUGIN_TOOL_MAP 中所有插件的工具注册到 MCPServer。

    遍历每个插件及其工具集，对尚未注册的工具创建 MCPTool 并注册到 mcp_server。
    在 main.py 启动时调用一次完成初始化。
    """
    for plugin_id, tool_names in PLUGIN_TOOL_MAP.items():
        for tool_name in tool_names:
            if tool_name not in mcp_server.tools:
                mcp_server.add_tool(
                    MCPTool(
                        name=tool_name,
                        description=f"插件 {plugin_id} 的工具: {tool_name}",
                        input_schema={
                            "type": "object",
                            "properties": {},
                        },
                    )
                )


async def call_mcp_tool(plugin_id: str, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """调用指定插件工具。

    将工具调用委托给 executor.execute_tool 流水线，返回统一格式的结果。

    Args:
        plugin_id: 插件标识
        tool_name: 工具名
        args: 工具参数字典

    Returns:
        {"status": "ok", "result": ...} 或 {"status": "error", "error": "..."}
    """
    from app.core.tool_runtime.executor import execute_tool

    tool_call = {
        "function": {"name": tool_name, "arguments": json.dumps(args)},
        "id": f"mcp-{plugin_id}-{tool_name}",
    }
    try:
        record = await execute_tool(
            tool_call=tool_call,
            project_path=None,
            read_only=False,
            ctx={},
            emit=None,
            auto_approve=False,
        )
        return {
            "status": "ok",
            "result": record.get("result", ""),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


def get_mcp_tools(plugin_id: str) -> List[Dict[str, Any]]:
    """获取某插件的工具列表（已在 MCPServer 注册的工具）。"""
    tool_names = PLUGIN_TOOL_MAP.get(plugin_id, set())
    return [
        mcp_server.tools[name].to_dict()
        for name in tool_names
        if name in mcp_server.tools
    ]