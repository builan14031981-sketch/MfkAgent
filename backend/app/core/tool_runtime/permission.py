"""权限控制 — 决定会话可见工具目录（Phase B-2）。

原则：权限决定工具可见性，模型决定调用。
- 第一阶段基础工具目录默认对所有 Agent 开放（不做意图相关的窄白名单）。
- plan 模式：移除写入/有副作用工具（动态派生自 risk_engine.TOOL_RISK_POLICY，
  与执行闸共用单一事实来源，避免两处清单漂移；外部 MCP 注入策略同样生效）。
- 无项目绑定：移除项目专有工具。
- capabilities 仅控制高级能力（第一阶段无高级工具，保留参数向前兼容，不缩减基础工具）。
- ComfyUI skill 启用时：移除内置 generate_image，强制走本地 ComfyUI。
- 外部 MCP 工具（T6）：mcp__<server>__<tool> 进入目录，取自会话冻结清单
  （core.mcp_client），启停/变更下个会话生效；风险判定仍在 risk_engine 单一来源。
"""

import time
from typing import List, Optional

from app.core.tool_runtime import risk_engine
from app.core.tool_runtime.risk_engine import PLAN_FORBIDDEN_TOOLS
from app.core.plugin_tools import get_enabled_plugin_tools  # 插件→工具集（DeepSeek Harness 范式）
from app.core import mcp_client  # 外部 MCP 工具清单（顶层仅依赖 stdlib，无循环导入）

# ComfyUI skill 启用状态缓存（TTL 10s）
_comfyui_cache = {"enabled": None, "ts": 0.0}
_COMFYUI_TTL = 10.0


def _is_comfyui_enabled() -> bool:
    """检查 comfyui-local skill 是否已安装并启用。带 10s 缓存。"""
    now = time.time()
    if _comfyui_cache["enabled"] is not None and (now - _comfyui_cache["ts"]) < _COMFYUI_TTL:
        return bool(_comfyui_cache["enabled"])
    try:
        from app.core.database import SessionLocal
        from app.models.agent import SkillDefinition
        db = SessionLocal()
        try:
            row = (
                db.query(SkillDefinition)
                .filter(SkillDefinition.name == "comfyui-local", SkillDefinition.enabled == True)  # noqa: E712
                .first()
            )
            enabled = row is not None
        finally:
            db.close()
    except Exception:
        enabled = False
    _comfyui_cache["enabled"] = enabled
    _comfyui_cache["ts"] = now
    return enabled


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

    # 写入/有副作用工具（plan 模式移除）— resolve() 内动态派生自 risk_engine.TOOL_RISK_POLICY
    #（单一事实来源，外部 MCP 注入的写入类策略同样生效）。
    # _plan_write_tools 保留为兼容镜像（phase E5 测试断言其与 PLAN_FORBIDDEN_TOOLS 一致）：
    # 可变 set，mcp_client 注册外部写入类工具时原地 add 保持同步。
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

        # 外部 MCP 工具入口（T6）：取会话冻结清单（启停/变更下个会话生效）。
        # 风险准入不在本层放宽——写入类外部工具在 plan 过滤中同样被移除。
        tools |= set(mcp_client.external_mcp_manager.frozen_external_tool_names(chat))

        chat_mode = getattr(chat, "mode", "build") or "build"
        if chat_mode == "plan":
            # 动态读取 TOOL_RISK_POLICY（= PLAN_FORBIDDEN_TOOLS 的实时等价），
            # 使外部 MCP 注入的写入类策略即时生效
            tools -= set(risk_engine.TOOL_RISK_POLICY.keys())

        project_path = getattr(chat, "project_path", None)
        if not project_path:
            tools -= self._project_only_tools

        # ComfyUI skill 启用时，禁用内置 generate_image，强制走本地 ComfyUI
        if _is_comfyui_enabled():
            tools.discard("generate_image")

        return sorted(tools)


# 无需工作目录即可执行的工具全集（无 project_path 时保留，供 context_builder 分级过滤）。
# 由 BASE_TOOLS - _project_only_tools 派生，单一事实来源，避免两处清单漂移。
# 注意：必须保持可变 set —— context_builder 在导入期捕获本对象引用，
# 外部 MCP 工具注册时原地 add（见 mcp_client._register_no_path），保证无项目会话可见外部工具。
NO_PATH_TOOLS = set(
    t for t in PermissionFilter.BASE_TOOLS if t not in PermissionFilter._project_only_tools
)
