"""权限策略 - 控制工具访问权限"""

from typing import List, Set, Dict
from enum import IntEnum


class PermissionLevel(IntEnum):
    """权限级别"""
    NONE = 0  # 纯聊天，禁止工具
    READ_ONLY = 1  # 只读操作
    PROJECT_ASSISTANT = 2  # 项目助手
    DESKTOP_AGENT = 3  # 桌面 Agent


class PermissionPolicy:
    """权限策略"""

    def __init__(self):
        # 权限级别对应的工具白名单
        self._permission_tools: Dict[PermissionLevel, Set[str]] = {
            PermissionLevel.NONE: set(),
            PermissionLevel.READ_ONLY: {
                # 只读工具
                "read_file",
                "list_files",
                "search_files",
                "run_command",  # 只读命令
                "git_status",
                "git_diff",
                "git_log",
                "web_search",
                "fetch_url",
                "add_memory",
            },
            PermissionLevel.PROJECT_ASSISTANT: {
                # 项目助手工具（包含只读 + 写入）
                "read_file",
                "write_file",
                "list_files",
                "search_files",
                "run_command",
                "git_status",
                "git_diff",
                "git_log",
                "git_commit",
                "git_add",
                "git_reset",
                "web_search",
                "fetch_url",
                "add_memory",
            },
            PermissionLevel.DESKTOP_AGENT: {
                # 桌面 Agent 工具（所有工具）
                "read_file",
                "write_file",
                "list_files",
                "search_files",
                "run_command",
                "git_status",
                "git_diff",
                "git_log",
                "git_commit",
                "git_add",
                "git_reset",
                "git_push",
                "git_pull",
                "web_search",
                "fetch_url",
                "add_memory",
            },
        }

        # 默认权限级别（所有 Agent 默认具备）
        self._default_permission = PermissionLevel.READ_ONLY

    def filter_tools(
        self,
        agent_capabilities: List[str],
        available_tools: List[str],
        permission_level: PermissionLevel = None,
    ) -> List[str]:
        """根据权限过滤工具

        Args:
            agent_capabilities: Agent 的 capabilities 配置（已废弃，保留向后兼容）
            available_tools: 所有可用工具列表
            permission_level: 权限级别（如果为 None，使用默认级别）

        Returns:
            过滤后的工具列表
        """
        if permission_level is None:
            permission_level = self._default_permission

        # 获取权限级别允许的工具
        allowed_tools = self._permission_tools.get(permission_level, set())

        # 如果 Agent 有明确的 capabilities，使用 capabilities 作为额外限制
        if agent_capabilities:
            # capabilities 是白名单，只允许 capabilities 中的工具
            capability_set = set(agent_capabilities)
            allowed_tools = allowed_tools.intersection(capability_set)

        # 过滤可用工具
        filtered = [t for t in available_tools if t in allowed_tools]

        return filtered

    def get_permission_level(self, agent_capabilities: List[str]) -> PermissionLevel:
        """根据 Agent capabilities 推断权限级别

        Args:
            agent_capabilities: Agent 的 capabilities 配置

        Returns:
            推断的权限级别
        """
        if not agent_capabilities:
            return self._default_permission

        capability_set = set(agent_capabilities)

        # 检查是否有写入权限
        write_tools = {"write_file", "git_commit", "git_push"}
        if capability_set.intersection(write_tools):
            return PermissionLevel.PROJECT_ASSISTANT

        # 检查是否有桌面操作权限
        desktop_tools = {"git_push", "git_pull"}
        if capability_set.intersection(desktop_tools):
            return PermissionLevel.DESKTOP_AGENT

        # 默认只读
        return PermissionLevel.READ_ONLY
