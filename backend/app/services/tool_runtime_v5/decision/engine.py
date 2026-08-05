"""决策引擎 - 决定是否使用工具"""

from typing import Dict, List, Optional
from ..intent.analyzer import Intent, IntentAnalyzer


class DecisionEngine:
    """决策引擎"""

    def __init__(self):
        self._intent_analyzer = IntentAnalyzer()

    def decide(
        self,
        message: str,
        available_tools: List[str],
        project_path: Optional[str] = None,
    ) -> Dict:
        """做出工具决策

        Args:
            message: 用户消息
            available_tools: 可用工具列表
            project_path: 项目路径（如果有）

        Returns:
            {
                "need_tool": bool,
                "tools": List[str],
                "reason": str,
                "confidence": float
            }
        """
        # 1. 分析意图
        intent_result = self._intent_analyzer.analyze(message)
        intent = intent_result["intent"]
        confidence = intent_result["confidence"]
        need_tool = intent_result["need_tool"]

        # 2. 如果不需工具，直接返回
        if not need_tool:
            return {
                "need_tool": False,
                "tools": [],
                "reason": f"意图为 {intent.value}，不需要工具",
                "confidence": confidence,
            }

        # 3. 根据意图选择工具
        selected_tools = self._select_tools(intent, available_tools, project_path)

        if not selected_tools:
            return {
                "need_tool": False,
                "tools": [],
                "reason": f"意图为 {intent.value}，但没有可用工具",
                "confidence": confidence,
            }

        # 4. 生成决策原因
        reason = self._generate_reason(intent, selected_tools, project_path)

        return {
            "need_tool": True,
            "tools": selected_tools,
            "reason": reason,
            "confidence": confidence,
        }

    def _select_tools(
        self,
        intent: Intent,
        available_tools: List[str],
        project_path: Optional[str],
    ) -> List[str]:
        """根据意图选择工具"""

        # 意图到工具的映射
        intent_tool_mapping = {
            Intent.SYSTEM_DIAGNOSIS: ["run_command"],
            Intent.FILE_OPERATION: ["read_file", "write_file", "list_files"],
            Intent.PROJECT_DEBUG: ["run_command", "read_file", "git_status", "git_diff"],
            Intent.WEB_SEARCH: ["web_search", "fetch_url"],
            Intent.MEMORY_OPERATION: ["add_memory"],
        }

        recommended = intent_tool_mapping.get(intent, [])

        # 过滤可用工具
        selected = [t for t in recommended if t in available_tools]

        # 如果没有项目路径，过滤掉文件工具
        if not project_path:
            selected = [t for t in selected if t not in ["read_file", "write_file", "list_files", "git_status", "git_diff"]]

        return selected

    def _generate_reason(
        self,
        intent: Intent,
        tools: List[str],
        project_path: Optional[str],
    ) -> str:
        """生成决策原因"""
        intent_descriptions = {
            Intent.SYSTEM_DIAGNOSIS: "用户要求检查系统状态",
            Intent.FILE_OPERATION: "用户要求操作文件",
            Intent.PROJECT_DEBUG: "用户要求调试项目",
            Intent.WEB_SEARCH: "用户要求搜索信息",
            Intent.MEMORY_OPERATION: "用户要求保存记忆",
        }

        base_reason = intent_descriptions.get(intent, "未知意图")
        tool_names = ", ".join(tools)

        return f"{base_reason}，推荐使用工具：{tool_names}"
