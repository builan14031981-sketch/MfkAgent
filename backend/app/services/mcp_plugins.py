"""MCP 外部插件注册器 — 将浏览器自动化、系统控制等真实能力注册为 MCP 插件。

使用方式：
  - 在 main.py 启动时调用 register_all_external_plugins() 即可。
  - 各插件注册后，其工具会出现在 MCPServer 工具列表中，可在前端插件管理

设计原则：
  - 每个外部插件 = 一组工具 + 一个执行器（executor）。
  - 执行器接收 (tool_name, args) 返回结果。
  - 插件注册后，其工具状态由 PluginManager 控制（启用/停用）。
"""

import logging
import asyncio
from typing import Any, Dict

from app.services.mcp import mcp_server
from app.services.plugin import register_mcp_plugin

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 1. 浏览器自动化插件 (Browser Automation)
# ═══════════════════════════════════════════════════════════════

_BROWSER_TOOLS = [
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_screenshot",
    "browser_back",
    "browser_forward",
    "browser_reload",
    "browser_state",
    "browser_scroll",
    "browser_evaluate",
]

_BROWSER_TOOL_SCHEMAS = {
    "browser_navigate": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "目标 URL（仅允许本机地址）"},
            "wait_for": {"type": "string", "description": "等待条件，默认 domcontentloaded"},
        },
        "required": ["url"],
    },
    "browser_click": {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS 选择器"},
        },
        "required": ["selector"],
    },
    "browser_type": {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS 选择器"},
            "text": {"type": "string", "description": "要输入的文本"},
        },
        "required": ["selector", "text"],
    },
    "browser_screenshot": {
        "type": "object",
        "properties": {
            "full_page": {"type": "boolean", "description": "是否截取完整页面"},
            "timeout": {"type": "integer", "description": "截图超时时间(毫秒)，默认15000"},
        },
    },
    "browser_back": {"type": "object", "properties": {}},
    "browser_forward": {"type": "object", "properties": {}},
    "browser_reload": {"type": "object", "properties": {}},
    "browser_state": {"type": "object", "properties": {}},
    "browser_scroll": {
        "type": "object",
        "properties": {
            "delta_x": {"type": "integer", "description": "水平滚动像素"},
            "delta_y": {"type": "integer", "description": "垂直滚动像素"},
        },
    },
    "browser_evaluate": {
        "type": "object",
        "properties": {
            "script": {"type": "string", "description": "要在页面中执行的 JavaScript 代码"},
        },
        "required": ["script"],
    },
}


async def _browser_executor(tool_name: str, args: Dict[str, Any]) -> Any:
    """浏览器自动化工具执行器。

    委托给 app.core.browser_session 的 browser_manager 执行。
    chat_id 固定为 0（全局会话），前端可通过 session_id 区分。
    """
    from app.core.browser_session import browser_manager

    chat_id = args.pop("chat_id", 0)

    action_map = {
        "browser_navigate": "navigate",
        "browser_click": "click",
        "browser_type": "type",
        "browser_screenshot": "screenshot",
        "browser_back": "back",
        "browser_forward": "forward",
        "browser_reload": "reload",
        "browser_state": "state",
        "browser_scroll": "scroll",
        "browser_evaluate": "evaluate",
    }

    action = action_map.get(tool_name)
    if not action:
        raise ValueError(f"Unknown browser tool: {tool_name}")

    result = await browser_manager.run(action, chat_id, **args)
    return result


# ═══════════════════════════════════════════════════════════════
# 2. 系统控制插件 (System Control)
# ═══════════════════════════════════════════════════════════════

_SYSTEM_TOOLS = [
    "system_info",
    "list_processes",
    "get_env",
    "open_file",
    "open_folder",
    "notify",
]

_SYSTEM_TOOL_SCHEMAS = {
    "system_info": {
        "type": "object",
        "properties": {
            "info_type": {
                "type": "string",
                "enum": ["os", "cpu", "memory", "disk", "all"],
                "description": "要获取的系统信息类型",
            },
        },
    },
    "list_processes": {
        "type": "object",
        "properties": {
            "filter": {"type": "string", "description": "进程名过滤关键字"},
        },
    },
    "get_env": {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "环境变量名"},
        },
        "required": ["key"],
    },
    "open_file": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
        },
        "required": ["path"],
    },
    "open_folder": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件夹路径"},
        },
        "required": ["path"],
    },
    "notify": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "通知标题"},
            "message": {"type": "string", "description": "通知正文"},
        },
        "required": ["title", "message"],
    },
}


async def _system_executor(tool_name: str, args: Dict[str, Any]) -> Any:
    """系统控制工具执行器。"""
    import os
    import platform
    import subprocess

    if tool_name == "system_info":
        info_type = args.get("info_type", "all")
        result = {}
        if info_type in ("os", "all"):
            result["os"] = platform.system()
            result["os_version"] = platform.version()
            result["arch"] = platform.machine()
        if info_type in ("cpu", "all"):
            result["cpu_count"] = os.cpu_count()
            try:
                import psutil
                result["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            except ImportError:
                result["cpu_percent"] = "N/A (psutil not installed)"
        if info_type in ("memory", "all"):
            try:
                import psutil
                mem = psutil.virtual_memory()
                result["memory_total"] = mem.total
                result["memory_available"] = mem.available
                result["memory_percent"] = mem.percent
            except ImportError:
                result["memory"] = "N/A (psutil not installed)"
        if info_type in ("disk", "all"):
            try:
                import psutil
                disk = psutil.disk_usage("/")
                result["disk_total"] = disk.total
                result["disk_free"] = disk.free
                result["disk_percent"] = disk.percent
            except ImportError:
                result["disk"] = "N/A (psutil not installed)"
        return result

    if tool_name == "list_processes":
        filter_keyword = args.get("filter", "")
        try:
            import psutil
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                if filter_keyword and filter_keyword.lower() not in p.info["name"].lower():
                    continue
                procs.append(p.info)
            return procs[:50]
        except ImportError:
            return "N/A (psutil not installed)"

    if tool_name == "get_env":
        key = args.get("key", "")
        return os.environ.get(key, f"环境变量 {key} 未设置")

    if tool_name == "open_file":
        path = args.get("path", "")
        if os.path.isfile(path):
            import subprocess
            subprocess.Popen(["start", "", path], shell=True)
            return f"已打开文件: {path}"
        return f"文件不存在: {path}"

    if tool_name == "open_folder":
        path = args.get("path", "")
        if os.path.isdir(path):
            subprocess.Popen(["explorer", path], shell=True)
            return f"已打开文件夹: {path}"
        return f"文件夹不存在: {path}"

    if tool_name == "notify":
        title = args.get("title", "MfkAgent")
        message = args.get("message", "")
        try:
            from plyer import notification
            notification.notify(title=title, message=message, timeout=5)
        except ImportError:
            pass
        return f"通知已发送: [{title}] {message}"

    raise ValueError(f"Unknown system tool: {tool_name}")


# ═══════════════════════════════════════════════════════════════
# 3. 注册所有外部插件
# ═══════════════════════════════════════════════════════════════

def register_all_external_plugins():
    """注册所有外部 MCP 插件。

    在 main.py 启动时调用一次。
    """
    # 注册前先为每个工具注册带 input_schema 的 MCPTool
    _register_tool_schemas(_BROWSER_TOOLS, _BROWSER_TOOL_SCHEMAS, "浏览器自动化")
    _register_tool_schemas(_SYSTEM_TOOLS, _SYSTEM_TOOL_SCHEMAS, "系统控制")

    # 注册浏览器自动化插件（执行器 + 插件状态管理）
    register_mcp_plugin(_BROWSER_TOOLS, _browser_executor)

    # 注册系统控制插件
    register_mcp_plugin(_SYSTEM_TOOLS, _system_executor)

    logger.info(
        "MCP 外部插件已注册: %d 个浏览器工具, %d 个系统工具",
        len(_BROWSER_TOOLS),
        len(_SYSTEM_TOOLS),
    )


def _register_tool_schemas(tools: list, schemas: dict, group_name: str):
    """为工具注册带 input_schema 的 MCPTool。"""
    from app.services.mcp import MCPTool

    for tool_name in tools:
        schema = schemas.get(tool_name, {"type": "object", "properties": {}})
        if tool_name not in mcp_server.tools:
            mcp_server.add_tool(
                MCPTool(
                    name=tool_name,
                    description=f"{group_name} 工具: {tool_name}",
                    input_schema=schema,
                )
            )
        else:
            # 已有注册（来自 plugin_tools），更新 schema
            existing = mcp_server.tools[tool_name]
            existing.input_schema = schema


def register_plugin_tool(name: str, description: str, input_schema: dict):
    """注册单个插件工具到 MCPServer（供外部使用）。"""
    from app.services.mcp import MCPTool

    if name not in mcp_server.tools:
        mcp_server.add_tool(
            MCPTool(
                name=name,
                description=description,
                input_schema=input_schema,
            )
        )