"""Tool Decision Runtime V5 Final — 统一工具决策运行时

使用方式：
    from app.core.tool_runtime import tool_runtime

    tool_context = tool_runtime.process(message=user_message, chat=chat)
"""

from .runtime import ToolRuntime

# 模块级单例
tool_runtime = ToolRuntime()

__all__ = ["tool_runtime", "ToolRuntime"]