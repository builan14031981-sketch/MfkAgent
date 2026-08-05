"""工具选择器 — 将工具名称转换为 OpenAI Function Calling Schema。

封装所有工具定义的导入和组装，chat.py 不再需要知道具体工具定义来源。
"""

from typing import Dict, List, Optional

from app.core.command_tools import COMMAND_TOOLS_DEFINITIONS
from app.core.tools import FILE_TOOLS_DEFINITIONS
from app.core.git_tools import GIT_TOOLS_DEFINITIONS
from app.core.search_tools import SEARCH_TOOLS_DEFINITIONS
from app.services.tools import tool_registry


class ToolSelector:
    """工具选择器"""

    def __init__(self):
        # 构建工具定义速查表
        self._def_map: Dict[str, Dict] = {}

        # 命令工具
        for t in COMMAND_TOOLS_DEFINITIONS:
            self._def_map[t["function"]["name"]] = t

        # 文件工具
        for t in FILE_TOOLS_DEFINITIONS:
            self._def_map[t["function"]["name"]] = t

        # Git 工具
        for t in GIT_TOOLS_DEFINITIONS:
            self._def_map[t["function"]["name"]] = t

        # 搜索工具
        for t in SEARCH_TOOLS_DEFINITIONS:
            self._def_map[t["function"]["name"]] = t

        # 通用工具（来自 tool_registry）
        for t in tool_registry.get_definitions():
            self._def_map[t["function"]["name"]] = t

        # 需要项目路径的工具
        self._project_only_tools = {
            "read_file", "write_file", "list_files",
            "git_status", "git_diff", "git_log", "git_commit",
            "git_add", "git_reset", "git_push", "git_pull",
            "search_files",
        }

    def select(self, tool_names: List[str], chat) -> List[Dict]:
        """根据工具名称列表，返回对应的工具定义

        Args:
            tool_names: 工具名称列表
            chat: Chat ORM 对象

        Returns:
            工具定义列表（OpenAI Function Calling Schema）
        """
        if not tool_names:
            return []

        project_path = getattr(chat, "project_path", None)
        definitions = []

        for name in tool_names:
            definition = self._def_map.get(name)
            if definition is None:
                continue

            # 项目专有工具需要 project_path
            if name in self._project_only_tools and not project_path:
                continue

            definitions.append(definition)

        return definitions