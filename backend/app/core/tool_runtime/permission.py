"""权限控制 — 决定会话可见工具目录（Phase B-2）。

原则：权限决定工具可见性，模型决定调用。
- 第一阶段基础工具目录默认对所有 Agent 开放（不做意图相关的窄白名单）。
- plan 模式：移除写入/有副作用工具（清单派生自 risk_engine.TOOL_RISK_POLICY，
  与执行闸共用单一事实来源，避免两处清单漂移）。
- 无项目绑定：移除项目专有工具。
- capabilities 仅控制高级能力（第一阶段无高级工具，保留参数向前兼容，不缩减基础工具）。
"""

from typing import List, Optional

from app.core.tool_runtime.risk_engine import PLAN_FORBIDDEN_TOOLS


class PermissionFilter:
    """权限过滤器 — resolve() 返回某会话可见的工具全集（与消息内容无关）"""

    # 第一阶段工具目录（基础工具，默认开放）
    BASE_TOOLS = [
        "run_command", "execute_command",
        "read_file", "write_file", "list_files",
        "git_status", "git_diff", "git_log", "git_branch_list", "git_remote",
        "git_commit", "git_restore", "git_clone", "git_pull", "git_push", "git_fetch",
        "github_create_pr",
        # Phase 4 T2: GitHub 只读工具（自动 ALLOW，无需审批）
        "github_list_issues", "github_read_issue",
        "github_list_pull_requests", "github_read_pull_request",
        "search_files",
        "web_search", "fetch_url", "github_search",
        "add_memory", "manage_todos", "get_datetime", "format_json",
    ]

    # 写入/有副作用工具（plan 模式移除；派生自 risk_engine，与执行闸保持同步）
    _plan_write_tools = set(PLAN_FORBIDDEN_TOOLS)

    # 项目专有工具（无 project_path 时移除）
    _project_only_tools = {
        "read_file", "write_file", "list_files", "search_files",
        "git_status", "git_diff", "git_log", "git_branch_list", "git_remote",
        "git_commit", "git_restore", "git_clone", "git_pull", "git_push", "git_fetch",
    }

    def resolve(
        self,
        chat,
        agent_capabilities: Optional[List[str]] = None,
    ) -> List[str]:
        """返回会话可见工具全集。

        Args:
            chat: Chat ORM 对象（需含 mode / project_path）
            agent_capabilities: Agent 的 capabilities（第一阶段仅控制高级能力，
                不缩减基础工具；保留参数向前兼容）

        Returns:
            工具名称列表
        """
        tools = set(self.BASE_TOOLS)

        chat_mode = getattr(chat, "mode", "build") or "build"
        if chat_mode == "plan":
            tools -= self._plan_write_tools

        project_path = getattr(chat, "project_path", None)
        if not project_path:
            tools -= self._project_only_tools

        return sorted(tools)
