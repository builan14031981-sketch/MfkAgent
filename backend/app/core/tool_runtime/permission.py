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
from app.core.plugin_tools import get_enabled_plugin_tools  # 插件→工具集（DeepSeek Harness 范式）


class PermissionFilter:
    """权限过滤器 — resolve() 返回某会话可见的工具全集（与消息内容无关）"""

    # 第一阶段工具目录（基础工具，默认开放）
    BASE_TOOLS = [
        "run_command", "execute_command",
        "read_file", "write_file", "list_files",
        "find_files", "edit_file", "apply_patch",
        "git_status", "git_diff", "git_log", "git_branch_list", "git_remote",
        "git_commit", "git_restore", "git_clone", "git_pull", "git_push", "git_fetch",
        "github_create_pr",
        # Phase 4 T2: GitHub 只读工具（自动 ALLOW，无需审批）
        "github_list_issues", "github_read_issue",
        "github_list_pull_requests", "github_read_pull_request",
        "search_files",
        "web_search", "fetch_url", "github_search",
        "add_memory", "manage_todos", "ask_user_choice", "get_datetime", "format_json",
        # Phase SubAgent: 委派子任务给专门化子代理（子代理自身工具集被收窄）
        "delegate_sub_agent",
        # Phase Orchestration: 复杂任务拆解 + 并行 spawn 子代理编排
        "spawn_orchestration",
        # UI 自检工具（前端 Agent 交付前自检）
        "probe_ui", "capture_screenshot", "analyze_screenshot",
        # 文生图（万相 API，外部付费服务，需审批）
        "generate_image",
        # 飞书多维表格（只读：list_bases / query_records；写入：write_records / create_base）
        "feishu_list_bases", "feishu_query_records",
        "feishu_write_records", "feishu_create_base",
        # 飞书 IM（P1：发文本 / 图片 / 文件；列群只读）
        "feishu_send_message", "feishu_send_image", "feishu_send_file",
        "feishu_list_chats",
    ]

    # 写入/有副作用工具（plan 模式移除；派生自 risk_engine，与执行闸保持同步）
    _plan_write_tools = set(PLAN_FORBIDDEN_TOOLS)

    # 必须绑定项目才可使用的写入与环境专有工具（无 project_path 时移除；只读文件工具如 read_file/list_files/find_files/search_files 全局可用）
    _project_only_tools = {
        "write_file", "edit_file", "apply_patch",
        "git_status", "git_diff", "git_log", "git_branch_list", "git_remote",
        "git_commit", "git_restore", "git_clone", "git_pull", "git_push", "git_fetch",
        "probe_ui", "capture_screenshot", "analyze_screenshot",
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
        # 插件→工具集：工具可见 = 基础工具 ∩ 启用的插件工具。
        # 默认无插件记录=全启用 → 交集=全集（零回归）；仅显式停用某插件才扣除其工具。
        tools = set(self.BASE_TOOLS) & get_enabled_plugin_tools()

        chat_mode = getattr(chat, "mode", "build") or "build"
        if chat_mode == "plan":
            tools -= self._plan_write_tools

        project_path = getattr(chat, "project_path", None)
        if not project_path:
            tools -= self._project_only_tools

        return sorted(tools)


# 无需工作目录即可执行的工具全集（无 project_path 时保留，供 context_builder 分级过滤）。
# 由 BASE_TOOLS - _project_only_tools 派生，单一事实来源，避免两处清单漂移。
NO_PATH_TOOLS = frozenset(
    t for t in PermissionFilter.BASE_TOOLS if t not in PermissionFilter._project_only_tools
)
