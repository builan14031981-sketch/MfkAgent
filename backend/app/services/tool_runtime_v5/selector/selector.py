"""工具选择器 - 根据意图和上下文选择具体工具"""

from typing import List, Dict, Optional
from ..intent.analyzer import Intent


class ToolSelector:
    """工具选择器"""

    def __init__(self):
        # 意图到工具的映射
        self._intent_tool_mapping: Dict[Intent, List[str]] = {
            Intent.SYSTEM_DIAGNOSIS: ["run_command"],
            Intent.FILE_OPERATION: ["read_file", "write_file", "list_files"],
            Intent.PROJECT_DEBUG: ["run_command", "read_file", "git_status", "git_diff"],
            Intent.WEB_SEARCH: ["web_search", "fetch_url"],
            Intent.MEMORY_OPERATION: ["add_memory"],
        }

    def select(
        self,
        intent: Intent,
        available_tools: List[str],
        project_path: Optional[str] = None,
    ) -> List[str]:
        """根据意图选择工具

        Args:
            intent: 用户意图
            available_tools: 可用工具列表
            project_path: 项目路径（如果有）

        Returns:
            选中的工具列表
        """
        recommended = self._intent_tool_mapping.get(intent, [])

        # 过滤可用工具
        selected = [t for t in recommended if t in available_tools]

        # 如果没有项目路径，过滤掉文件工具
        if not project_path:
            file_tools = ["read_file", "write_file", "list_files", "git_status", "git_diff", "git_log"]
            selected = [t for t in selected if t not in file_tools]

        return selected
