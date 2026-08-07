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

    def process(
        self,
        message: str,
        chat,
        agent_capabilities=None,
    ) -> Dict:
        """唯一入口：接收用户消息和 Chat 对象，返回工具决策结果。

        Phase B-2 架构：权限决定工具可见性，模型决定调用。
        工具目录由 PermissionFilter.resolve 根据 chat（模式/项目/capabilities）决定，
        与消息内容无关；意图只作为软提示注入 system prompt，不 gate 工具。

        Args:
            message: 用户消息文本
            chat: Chat ORM 对象，需包含以下属性：
                - project_path: str | None
                - mode: str ("build" | "plan")
                - agent_id: str
                - project_id: int | None
            agent_capabilities: Agent 的 capabilities（可选，仅控制高级能力）

        Returns:
            {
                "need_tools": bool,           # 会话是否可见工具（目录非空）
                "tools": List[Dict],          # 工具定义列表（可直接传给 model_service）
                "system_policy": str,         # 全局工具策略（需注入 system prompt）
                "decision": {                 # 决策详情
                    "layer": str,
                    "intent": str,
                    "reason": str,
                    "confidence": float,
                },
            }
        """
        # 1. 权限 → 会话可见工具全集（与消息内容无关）
        tool_names = self._permission.resolve(chat, agent_capabilities)

        # 2. 意图分析 → 供 decision 使用（soft_hint 由 chat.py 在 ⑦ 层自行注入）
        intent_result = self._intent.analyze(message)

        # 3. 工具选择（获取定义）
        tools = self._selector.select(tool_names, chat)

        # 4. 构建全局策略（兼容导出；chat.py 现自行按 ①-⑧ 组装，soft_hint 由调用方注入 ⑦ 层）
        policy = build_policy(chat)

        return {
            "need_tools": len(tools) > 0,
            "tools": tools,
            "system_policy": policy,
            "decision": {
                "layer": intent_result["layer"],
                "intent": intent_result.get("intent", "general_chat"),
                "reason": intent_result["reason"],
                "confidence": intent_result["confidence"],
            },
        }