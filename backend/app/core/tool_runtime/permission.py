"""权限控制 — 根据 chat mode 和 Agent capabilities 做最终过滤。"""

from typing import List, Optional


class PermissionFilter:
    """权限过滤器"""

    # 写入类工具（plan 模式禁止）
    _write_tools = {
        "write_file", "git_commit", "git_add",
        "git_reset", "git_push", "git_pull",
    }

    # 基础只读工具（所有 Agent 默认具备）
    _default_tools = {
        "run_command", "web_search", "fetch_url",
        "add_memory", "get_datetime", "format_json",
    }

    def filter(
        self,
        tool_names: List[str],
        chat,
        agent_capabilities: Optional[List[str]] = None,
    ) -> List[str]:
        """根据权限过滤工具

        Args:
            tool_names: 待过滤的工具名称列表
            chat: Chat ORM 对象
            agent_capabilities: Agent 的 capabilities 白名单（可选，向后兼容）

        Returns:
            过滤后的工具名称列表
        """
        if not tool_names:
            return []

        chat_mode = getattr(chat, "mode", "build") or "build"

        filtered = list(tool_names)

        # Plan 模式：过滤写入类工具
        if chat_mode == "plan":
            filtered = [t for t in filtered if t not in self._write_tools]

        # Agent capabilities 白名单（向后兼容）
        if agent_capabilities and len(agent_capabilities) > 0:
            capability_set = set(agent_capabilities)
            # 基础工具始终保留
            allowed = capability_set.union(self._default_tools)
            filtered = [t for t in filtered if t in allowed]

        return filtered