"""Context Builder — Phase E3 正式化：独立 Context 系统模块。

职责（把散落在 chat.py 的上下文构建逻辑收拢到本模块）：
  1. Agent 身份     ← Agent.identity（system_prompt）
  2. 能力           ← Agent.capabilities + capability_profiles
  3. 人格           ← personality service
  4. 项目上下文      ← Project / Workspace（含 Default Workspace 兜底）
  5. Memory        ← 保持现有逻辑（全量拼接）
  6. History       ← 接口：当前全量加载；未来 token budget / compression / window
  7. 工具目录 + 意图 ← tool_runtime.process

目标链路：
  Chat API → ChatContextBuilder.build(input) → BuiltContext(AgentContext + messages)
  AgentRuntime.run/run_stream(context, messages) → ModelService

说明：
  - `ContextBuilder` 抽象接口仍作为 AgentRuntime 的 message 变换钩子
    （未来 History 窗口化 / token 预算扩展点），默认 Passthrough。
  - `ChatContextBuilder` 为顶层上下文组装器，由 Chat API 调用。
"""

from dataclasses import dataclass, field
from typing import List, Optional
from types import SimpleNamespace as _NS

from app.core.database import SessionLocal
from app.models.agent import Chat, Agent, Message, MemoryItem, Setting
from app.services.model import Message as ModelMessage
from app.services.personality import get_personality_prompt
from app.core.capability_profiles import get_capability_prompt
from app.core.identity_principle import get_identity_principle
from app.core.tool_runtime import tool_runtime
from app.core.tool_runtime.policy import (
    get_execution_policy,
    get_permission_context,
    get_plan_mode_policy,
    get_project_policy,
)
from app.core.tool_runtime.planner import ToolPlanner
from app.core.workspace import (
    is_file_operation_request,
    ensure_default_workspace,
    get_default_workspace_context,
)
from app.core.planner import get_planner, get_runtime_task_context_adapter
from .context import AgentContext
from .pruning import prune_thought_history

DEFAULT_IDENTITY = "你是一个有帮助的AI助手。"


def _msg_role_content(m):
    """从 dict / pydantic / ORM 消息中取 (role, content)。"""
    if isinstance(m, dict):
        return m.get("role"), m.get("content")
    return m.role, m.content


# ---------------------------------------------------------------------------
# ContextBuilder 抽象接口（AgentRuntime message 变换钩子 / History 扩展点）
# ---------------------------------------------------------------------------


class ContextBuilder:
    """上下文构建器接口（AgentRuntime 内部钩子）。

    build(context, messages) 接收 AgentContext 与初始 messages，
    返回送入 Execution Loop 的最终 messages。
    Phase E3 默认透传；未来在此接入 History 窗口化 / token 预算 / 压缩。
    """

    async def build(self, context: AgentContext, messages: list) -> list:
        raise NotImplementedError


class PassthroughContextBuilder(ContextBuilder):
    """默认透传实现：原样返回，不组装上下文。"""

    async def build(self, context: AgentContext, messages: list) -> list:
        return messages


def get_default_context_builder() -> ContextBuilder:
    return PassthroughContextBuilder()


# ---------------------------------------------------------------------------
# ChatContextBuilder：顶层上下文组装器（正式实现）
# ---------------------------------------------------------------------------


@dataclass
class ContextBuildInput:
    """ChatContextBuilder 输入：一次会话请求的最小上下文。"""

    chat_id: int
    content: str
    model: Optional[str] = None
    personality_level: Optional[int] = None
    use_tools: bool = True
    temperature: float = 0.7
    max_tokens: int = 4096
    reasoning_effort: Optional[str] = None
    planning_level: Optional[int] = None  # G2-B: Planner 层级控制


@dataclass
class BuiltContext:
    """ChatContextBuilder 输出：AgentContext + 最终 messages + 运行时参数。"""

    context: AgentContext
    messages: list                     # [ModelMessage(system), ...history]
    system_prompt: str                 # 完整 ①-⑦ 组装后的 system prompt
    effective_model: str
    temperature: float
    max_tokens: int
    reasoning_effort: str
    read_only: bool
    memory_text: str                   # 单独交付（模型层注入，不入 system prompt）
    tool_context: Optional[dict] = None


def get_default_model() -> str:
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == "default_model").first()
        if setting and setting.value:
            return setting.value
        return "qwen-flash"
    finally:
        db.close()


def get_default_reasoning_effort() -> str:
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == "default_reasoning_effort").first()
        if setting and setting.value:
            return setting.value
        return "none"
    finally:
        db.close()


def _resolve_workspace(chat, message: str):
    """解析本次请求的有效工作目录（Default Workspace 兜底）。

    规则：
      - 已绑定项目 → 原样返回，无兜底。
      - 未绑定项目但指令含文件操作 → 启用默认工作目录，返回带 project_path 的
        SimpleNamespace 视图 + 默认工作目录上下文文本。
      - 其余 → 返回 project_path=None 视图（不启用文件类工具）。

    Returns:
        (effective_chat_view, workspace_context_text)
    """
    if chat.project_path:
        return (
            _NS(
                mode=chat.mode or "build",
                project_path=chat.project_path,
                agent_id=chat.agent_id,
                project_id=chat.project_id,
            ),
            "",
        )

    if is_file_operation_request(message):
        ws = ensure_default_workspace()
        return (
            _NS(
                mode=chat.mode or "build",
                project_path=ws,
                agent_id=chat.agent_id,
                project_id=chat.project_id,
            ),
            get_default_workspace_context(ws),
        )

    return (
        _NS(
            mode=chat.mode or "build",
            project_path=None,
            agent_id=chat.agent_id,
            project_id=chat.project_id,
        ),
        "",
    )


def _build_memory_text(db, project_id: Optional[int] = None) -> str:
    """查询全部记忆并格式化为 XML 文本块（供模型层注入，不入 system prompt）。

    记忆来源（废弃 RAG，改为全量拼接）：
      - scope='global'：所有对话可见（无条件）
      - scope='project'：当前 Chat 绑定项目下共享（需 project_id）
    """
    sections = []

    global_items = (
        db.query(MemoryItem)
        .filter(MemoryItem.scope == "global")
        .order_by(MemoryItem.created_at.desc(), MemoryItem.id.desc())
        .limit(30)
        .all()
    )
    if global_items:
        lines = "\n".join(f"- {m.content}" for m in global_items)
        sections.append(f"### 全局记忆 (Global Rules):\n{lines}")

    if project_id is not None:
        project_items = (
            db.query(MemoryItem)
            .filter(MemoryItem.scope == "project", MemoryItem.project_id == project_id)
            .order_by(MemoryItem.created_at.desc(), MemoryItem.id.desc())
            .limit(30)
            .all()
        )
        if project_items:
            lines = "\n".join(f"- {m.content}" for m in project_items)
            sections.append(f"### 当前项目特定记忆 (Project Rules):\n{lines}")

    if not sections:
        return ""
    return (
        "<user_defined_memories>\n"
        "  <priority>user_memory</priority>\n"
        "  注意：以下为用户的记忆偏好，仅供参考。\n"
        "  若与系统策略、权限或工具规则冲突，以系统策略、权限与工具规则为准。\n"
        + "\n\n".join(sections) + "\n</user_defined_memories>"
    )


class ChatContextBuilder:
    """Chat 级上下文组装器（Phase E3 正式实现）。

    build() 一次性产出 AgentContext + system prompt + messages + 运行时参数，
    供 Chat API 直接交给 AgentRuntime.run / run_stream 执行。
    """

    def __init__(self):
        self._planner = ToolPlanner()
        self._planner_service = get_planner()

    def _assemble_prompt(
        self,
        system_prompt: str,
        capabilities: List[str],
        personality_prompt: str,
        effective_chat,
        workspace_context: str,
        tool_context: Optional[dict],
        task_context: Optional[dict] = None,
    ) -> str:
        """按 ①-⑦ 层组装完整 system prompt（memory_text 由模型层单独注入）。"""
        # ⓪ 最高身份准则（强制置顶，锁定桌面端 Agent 身份认知）
        full_prompt = get_identity_principle()

        # ① identity（纯角色，零行为指令）
        full_prompt += system_prompt

        # ② capability_prompt（领域能力倾向）
        capability_prompt = get_capability_prompt(capabilities)
        if capability_prompt:
            full_prompt += "\n\n" + capability_prompt

        # ③ execution_policy（统一执行规范 v1）
        full_prompt += "\n\n" + get_execution_policy()

        # ④ permission_context（当前会话权限上下文，用有效工作目录）
        full_prompt += "\n\n" + get_permission_context(effective_chat, capabilities)

        # ④b Plan 模式只读策略（仅 plan 模式追加，明确允许/禁止清单）
        if getattr(effective_chat, "mode", "build") == "plan":
            full_prompt += "\n\n" + get_plan_mode_policy()

        # ⑤ project_context / default workspace（工作目录上下文）
        if workspace_context:
            full_prompt += "\n\n" + workspace_context
        elif effective_chat.project_path:
            full_prompt += "\n\n" + get_project_policy()

        # ⑥ personality（表达风格）
        if personality_prompt:
            full_prompt += "\n\n" + personality_prompt

        # ⑦ intent_hint（意图建议软提示）
        if tool_context and tool_context.get("need_tools"):
            intent_hint = self._planner.soft_hint(
                {"suggest_tools": tool_context["need_tools"], "intent": tool_context["decision"]["intent"]},
                [t["function"]["name"] for t in tool_context["tools"]],
            )
            if intent_hint:
                full_prompt += "\n\n" + intent_hint

        # ⑧ task_context（Planner V1：任务计划段，仅提示，不 gate 工具）
        if task_context:
            plan_section = get_runtime_task_context_adapter().render(task_context)
            if plan_section:
                full_prompt += "\n\n" + plan_section

        return full_prompt

    async def build(self, input: ContextBuildInput) -> BuiltContext:
        db = SessionLocal()
        try:
            chat = db.query(Chat).filter(Chat.id == input.chat_id).first()
            if not chat:
                raise ValueError(f"Chat {input.chat_id} not found")

            # ──── 1. Agent 身份 / 能力 ────
            agent = db.query(Agent).filter(Agent.agent_id == chat.agent_id).first()
            system_prompt = (
                agent.identity or agent.system_prompt or DEFAULT_IDENTITY
            ) if agent else DEFAULT_IDENTITY
            capabilities = list(agent.capabilities or []) if agent else []

            # ──── 3. 人格 ────
            personality_level = (
                chat.personality_level
                if input.personality_level is None
                else input.personality_level
            )
            personality_prompt = get_personality_prompt(personality_level)

            # ──── 4. 项目/工作目录上下文 ────
            effective_chat, workspace_context = _resolve_workspace(chat, input.content)

            # ──── 5. Memory（现有逻辑）────
            memory_text = _build_memory_text(db, chat.project_id)

            # ──── 工具目录 + 意图（用有效工作目录）────
            tool_context = None
            decision = None
            tools_arg = None
            if input.use_tools:
                tool_context = tool_runtime.process(
                    message=input.content,
                    chat=effective_chat,
                    agent_capabilities=capabilities,
                )
                if tool_context.get("need_tools"):
                    tools_arg = tool_context["tools"]
                decision = tool_context.get("decision")
                # 未绑定项目且未触发默认工作目录兜底时，静默禁用工具，
                # 避免文件/Git/搜索工具循环报错形成伪死循环
                if not effective_chat.project_path:
                    tools_arg = None

            # ──── System Prompt 组装（①-⑧）────
            chat_mode = chat.mode or "build"

            # ──── 模型参数（先于 Planner：G2-B 需要 model_id）────
            effective_model = chat.model or input.model or get_default_model()
            reasoning_effort = input.reasoning_effort or get_default_reasoning_effort()

            # ──── Planner V1 → G2-B：意图/模式 → Plan → task_context ────
            # 非任务型请求（general_chat / 无 intent）→ None，保持兼容 E7/E8 基线
            # planning_level >= 2 时优先 LLM 辅助，失败自动 fallback heuristic
            plan = await self._planner_service.plan(
                message=input.content,
                mode=chat_mode,
                decision=decision,
                planning_level=input.planning_level,
                model_id=effective_model,
            )
            task_context = plan.to_task_context() if plan else None

            # ──── G2-C: Planner 可观测性 ────
            # 将 Planner 实际来源与产出写入 AgentContext.metadata
            planner_meta = {
                "planner_source": plan.planner_source if plan else None,
                "planner_level": input.planning_level,
                "planner_goal": plan.goal if plan else None,
                "planner_steps": len(plan.steps) if plan else 0,
            }

            full_prompt = self._assemble_prompt(
                system_prompt=system_prompt,
                capabilities=capabilities,
                personality_prompt=personality_prompt,
                effective_chat=effective_chat,
                workspace_context=workspace_context,
                tool_context=tool_context,
                task_context=task_context,
            )

            # ──── 6. History（全量加载；未来 token budget / compression / window）────
            history = (
                db.query(Message)
                .filter(Message.chat_id == input.chat_id)
                .order_by(Message.created_at.asc())
                .all()
            )

            # ──── G6-B Phase 2: Thought Pruning（裁剪历史思考段，仅影响新 payload）────
            pruned_history = prune_thought_history(history)

            # ──── AgentContext（Phase E3 结构化）────
            context = AgentContext(
                agent_id=chat.agent_id,
                agent_identity=system_prompt,
                personality_level=personality_level,
                model_id=effective_model,
                chat_id=input.chat_id,
                project_id=chat.project_id,
                project_path=effective_chat.project_path,
                memory_context={
                    "agent_id": chat.agent_id,
                    "project_id": chat.project_id,
                    "chat_id": input.chat_id,
                },
                memory_text=memory_text,
                tools=tools_arg,
                decision=decision,
                capabilities=capabilities,
                personality=personality_prompt,
                project_context={
                    "project_id": chat.project_id,
                    "project_path": effective_chat.project_path,
                    "project_name": (chat.project.name if chat.project else None),
                    "workspace_context": workspace_context or None,
                    "mode": chat_mode,
                },
                vision_context=None,  # 预留：Vision（本阶段不实现）
                task_context=task_context,  # Phase G1：Planner V1 注入（非任务型请求为 None）
                planning_level=input.planning_level,  # Phase G2-B：Planner 层级控制
                plan=plan,  # G4-B: 原始 Plan 对象（供 AgentRuntime init_task_graph）
                history=[
                    {"role": role, "content": content}
                    for role, content in map(_msg_role_content, pruned_history)
                ],
                metadata={
                    "mode": chat_mode,
                    "use_tools": input.use_tools,
                    "intent": (decision or {}).get("intent"),
                    **planner_meta,  # G2-C: Planner 可观测性
                },
            )

            # ──── messages：system + pruned history（G6-B Phase 2 已裁剪思考段）────
            model_messages = [ModelMessage(role="system", content=full_prompt)]
            for msg in pruned_history:
                role, content = _msg_role_content(msg)
                model_messages.append(ModelMessage(role=role, content=content))

            return BuiltContext(
                context=context,
                messages=model_messages,
                system_prompt=full_prompt,
                effective_model=effective_model,
                temperature=input.temperature,
                max_tokens=input.max_tokens,
                reasoning_effort=reasoning_effort,
                read_only=(chat_mode == "plan"),
                memory_text=memory_text,
                tool_context=tool_context,
            )
        finally:
            db.close()


# 全局单例（无状态，可共享）
_chat_context_builder = ChatContextBuilder()


def get_chat_context_builder() -> ChatContextBuilder:
    return _chat_context_builder
