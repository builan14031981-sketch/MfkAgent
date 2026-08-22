"""插件 → 工具集的映射层（DeepSeek Harness「工具即作用域能力」的落地）。

语义：
  每个 Plugin = 一组真实工具。启用该插件，其工具进入会话工具可见集；
  停用则移除。这是把原先「死壳」PluginManager 变成真能力层的关键。

默认全开、只认「显式停用」（无回归）：
  - `get_enabled_plugin_tools()` 默认返回全部插件工具的并集（= PermissionFilter.BASE_TOOLS 全集）；
  - 仅在 plugins 表存在某插件记录且 status != "active" 时，才把该插件的工具扣除；
  - 表缺失 / 无记录 / 查询异常时一律回退全量，绝不因插件表状态损坏而收窄 agent 工具，
    保证不影响现有用户任何能力。

流程必需工具（core/ask_user_choice）恒在：审批/选择是环控制器必需，即使关闭 core 插件也保留。
"""
from __future__ import annotations

from typing import Set


# 每个插件包含的工具（覆盖 PermissionFilter.BASE_TOOLS 全集，保证默认全开与现状一致）
PLUGIN_TOOL_MAP: dict[str, Set[str]] = {
    "web_search": {"web_search", "fetch_url", "github_search"},
    "code_execution": {"run_command", "execute_command"},
    "file_operations": {"read_file", "write_file", "list_files", "search_files", "find_files", "edit_file", "apply_patch"},
    "git": {
        "git_status", "git_diff", "git_log", "git_branch_list", "git_remote",
        "git_commit", "git_restore", "git_clone", "git_pull", "git_push", "git_fetch",
        "github_create_pr",
        "github_list_issues", "github_read_issue",
        "github_list_pull_requests", "github_read_pull_request",
    },
    "browser_ui": {"probe_ui", "capture_screenshot", "analyze_screenshot"},
    # 文生图（万相 API 外部付费服务，需审批）
    "image_generation": {"generate_image"},
    # 飞书集成（多维表格读写 + IM 消息/图片/文件；发送类需审批）
    "feishu": {
        "feishu_list_bases", "feishu_query_records",
        "feishu_write_records", "feishu_create_base",
        "feishu_send_message", "feishu_send_image", "feishu_send_file",
        "feishu_list_chats",
    },
    "orchestration": {"delegate_sub_agent", "spawn_orchestration"},
    "core": {"ask_user_choice", "get_datetime", "format_json", "add_memory", "manage_todos"},
    # 外部插件（真实 MCP 能力）
    "browser_automation": {
        "browser_navigate", "browser_click", "browser_type",
        "browser_screenshot", "browser_back", "browser_forward",
        "browser_reload", "browser_state", "browser_scroll",
        "browser_evaluate",
    },
    "system_control": {
        "system_info", "list_processes", "get_env",
        "open_file", "open_folder", "notify",
    },
}

# 流程环控制器必需，任何情况下都保留（即使 core 插件被停用）
CORE_ALWAYS_TOOLS: Set[str] = {"ask_user_choice"}


def _all_plugin_tools() -> Set[str]:
    s: Set[str] = set()
    for tools in PLUGIN_TOOL_MAP.values():
        s |= tools
    return s


def get_enabled_plugin_tools() -> Set[str]:
    """返回当前生效（启用插件）的工具集合。只扣除「显式停用」的插件工具。

    Returns:
        set[str] — 工具名集合；任何异常时回退全量。
    """
    enabled = _all_plugin_tools()
    try:
        from app.core.database import SessionLocal
        from app.models.agent import PluginItem

        db = SessionLocal()
        try:
            rows = db.query(PluginItem).all()
            for row in rows:
                # 没有 DB 记录 = 未显式配置 → 视为启用（默认全开）
                pid = getattr(row, "plugin_id", None)
                if pid is None:
                    continue
                status = getattr(row, "status", None)
                if pid in PLUGIN_TOOL_MAP and status != "active":
                    enabled -= PLUGIN_TOOL_MAP[pid]
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception:
        # 插件表不可读 → 回退全量，绝不影响 agent 现有能力
        return _all_plugin_tools()

    # 流程必需工具恒在
    enabled |= CORE_ALWAYS_TOOLS
    return enabled


def get_plugin_summary() -> list[dict]:
    """返回插件+工具摘要（供调试 / 状态查询，可选）。"""
    status_map: dict[str, str] = {}
    try:
        from app.core.database import SessionLocal
        from app.models.agent import PluginItem

        db = SessionLocal()
        try:
            for row in db.query(PluginItem).all():
                if getattr(row, "plugin_id", None):
                    status_map[row.plugin_id] = row.status
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception:
        pass

    result = []
    for pid, tools in PLUGIN_TOOL_MAP.items():
        result.append({
            "plugin_id": pid,
            "active": status_map.get(pid, "active") == "active",
            "tools": sorted(tools),
        })
    return result