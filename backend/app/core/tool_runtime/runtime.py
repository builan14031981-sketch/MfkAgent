"""Tool Decision Runtime V5 Final — 唯一入口

使用方法（chat.py 唯一允许的调用方式）：

    from app.core.tool_runtime import tool_runtime

    tool_context = tool_runtime.process(message=user_message, chat=chat)
    # → {"need_tools": bool, "tools": [...], "system_policy": "..."}

chat.py 不再需要知道 capabilities、command_tools、file_tools 等细节。
"""

from typing import Dict

from .intent import IntentAnalyzer
from .planner import ToolPlanner
from .selector import ToolSelector
from .permission import PermissionFilter
from .policy import build_policy


class ToolRuntime:
    """Tool Decision Runtime V5 Final — 统一工具决策运行时"""

    def __init__(self):
        self._intent = IntentAnalyzer()
        self._planner = ToolPlanner()
        self._selector = ToolSelector()
        self._permission = PermissionFilter()

    def process(self, message: str, chat) -> Dict:
        """唯一入口：接收用户消息和 Chat 对象，返回工具决策结果。

        Args:
            message: 用户消息文本
            chat: Chat ORM 对象，需包含以下属性：
                - project_path: str | None
                - mode: str ("build" | "plan")
                - agent_id: str
                - project_id: int | None

        Returns:
            {
                "need_tools": bool,           # 是否需要工具
                "tools": List[Dict],          # 工具定义列表（可直接传给 model_service）
                "system_policy": str,         # 全局工具策略（需注入 system prompt）
                "decision": {                 # 决策详情
                    "layer": str,
                    "reason": str,
                    "confidence": float,
                },
            }
        """
        # 1. 意图分析（三层判断）
        intent_result = self._intent.analyze(message)

        # 2. 工具规划
        tool_names = self._planner.plan(intent_result, chat)

        # 3. 权限过滤
        tool_names = self._permission.filter(tool_names, chat)

        # 4. 工具选择（获取定义）
        tools = self._selector.select(tool_names, chat)

        # 5. 构建全局策略
        policy = build_policy(chat)

        # 如果 Layer 3 触发了自检提示词，将其注入策略
        self_check = intent_result.get("self_check_prompt", "")
        if self_check:
            policy = policy + "\n\n" + self_check

        return {
            "need_tools": len(tools) > 0,
            "tools": tools,
            "system_policy": policy,
            "decision": {
                "layer": intent_result["layer"],
                "reason": intent_result["reason"],
                "confidence": intent_result["confidence"],
            },
        }