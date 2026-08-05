"""工具规划器 — 根据意图分析结果决定需要哪些工具。"""

from typing import Dict, List, Optional


class ToolPlanner:
    """工具规划器"""

    def __init__(self):
        # 意图到工具名称的映射
        self._intent_tool_map: Dict[str, List[str]] = {
            "system_diagnosis": ["run_command"],
            "file_operation": ["read_file", "write_file", "list_files"],
            "project_debug": ["run_command", "read_file", "git_status", "git_diff"],
            "git_operation": ["run_command", "git_status", "git_diff", "git_log"],
            "web_search": ["web_search", "fetch_url"],
            "memory_operation": ["add_memory"],
        }

        # 需要项目路径的工具（无项目绑定时自动过滤）
        self._project_only_tools = {
            "read_file", "write_file", "list_files",
            "git_status", "git_diff", "git_log",
            "search_files",
        }

    def plan(self, intent_result: Dict, chat) -> List[str]:
        """根据意图分析结果规划工具

        Args:
            intent_result: 意图分析结果（来自 intent.py）
            chat: Chat ORM 对象

        Returns:
            工具名称列表
        """
        if not intent_result.get("need_tools"):
            return []

        intent = intent_result.get("intent", "")
        tool_names = self._intent_tool_map.get(intent, [])

        if not tool_names:
            return []

        # 无项目路径时过滤掉项目专有工具
        project_path = getattr(chat, "project_path", None)
        if not project_path:
            tool_names = [t for t in tool_names if t not in self._project_only_tools]

        return tool_names