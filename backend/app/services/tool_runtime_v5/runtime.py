"""Tool Decision Runtime V5.0 - 主入口"""

from typing import Dict, List, Optional
from .intent.analyzer import IntentAnalyzer, Intent
from .decision.engine import DecisionEngine
from .permission.policy import PermissionPolicy, PermissionLevel
from .selector.selector import ToolSelector
from .observer.observer import ToolResultObserver
from .policies.default import (
    get_default_tool_policy,
    get_project_workflow_policy,
    get_plan_mode_policy,
)


class ToolRuntime:
    """工具运行时 - V5.0 统一入口"""

    def __init__(self):
        self._intent_analyzer = IntentAnalyzer()
        self._decision_engine = DecisionEngine()
        self._permission_policy = PermissionPolicy()
        self._tool_selector = ToolSelector()
        self._result_observer = ToolResultObserver()

    def handle(
        self,
        message: str,
        available_tools: List[str],
        project_path: Optional[str] = None,
        chat_mode: str = "build",
        agent_capabilities: Optional[List[str]] = None,
    ) -> Dict:
        """处理用户消息，返回工具决策结果

        Args:
            message: 用户消息
            available_tools: 可用工具列表
            project_path: 项目路径（如果有）
            chat_mode: 聊天模式（build/plan）
            agent_capabilities: Agent 的能力配置（已废弃，保留向后兼容）

        Returns:
            {
                "tools": List[Dict],  # 工具定义列表
                "policy": str,  # 工具策略提示词
                "decision": Dict,  # 决策详情
            }
        """
        # 1. 意图分析
        intent_result = self._intent_analyzer.analyze(message)
        intent = intent_result["intent"]
        need_tool = intent_result["need_tool"]

        # 2. 决策引擎
        decision = self._decision_engine.decide(
            message=message,
            available_tools=available_tools,
            project_path=project_path,
        )

        # 3. 权限过滤
        filtered_tools = self._permission_policy.filter_tools(
            agent_capabilities=agent_capabilities or [],
            available_tools=decision["tools"],
        )

        # 4. 构建策略提示词
        policy = self._build_policy(project_path, chat_mode)

        # 5. 返回结果
        return {
            "tools": filtered_tools,
            "policy": policy,
            "decision": {
                "intent": intent.value,
                "need_tool": need_tool,
                "confidence": intent_result["confidence"],
                "reason": decision["reason"],
            },
        }

    def _build_policy(self, project_path: Optional[str], chat_mode: str) -> str:
        """构建工具策略提示词"""
        policies = [get_default_tool_policy()]

        if project_path:
            policies.append(get_project_workflow_policy())

            if chat_mode == "plan":
                policies.append(get_plan_mode_policy())

        return "\n\n".join(policies)

    def observe_result(
        self,
        tool_name: str,
        tool_result: str,
        original_intent: str,
    ) -> Dict:
        """观察工具执行结果

        Args:
            tool_name: 工具名称
            tool_result: 工具执行结果
            original_intent: 原始意图

        Returns:
            {
                "should_continue": bool,
                "next_tools": List[str],
                "reason": str
            }
        """
        return self._result_observer.observe(
            tool_name=tool_name,
            tool_result=tool_result,
            original_intent=original_intent,
        )

    def get_permission_level(self, agent_capabilities: List[str]) -> PermissionLevel:
        """获取权限级别"""
        return self._permission_policy.get_permission_level(agent_capabilities)
