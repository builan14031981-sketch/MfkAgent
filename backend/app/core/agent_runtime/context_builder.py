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
import os

from app.core.database import SessionLocal
from app.models.agent import Chat, Agent, Message, MemoryItem, Setting
from app.models.persona import PersonaTemplate
from app.services.model import Message as ModelMessage
from app.services.personality import get_personality_prompt
from app.core.capability_profiles import get_capability_prompt
from app.core.persona_engine import build_persona_context, load_expression_knowledge, PersonaContext
from app.core.identity_principle import get_identity_principle
from app.core.agent_base_instruction import get_agent_base_instruction
from app.core.skill_store import get_enabled_skills_prompt  # Phase 4 T3: Skill Prompt Fragment 加载
from app.core.tool_runtime import tool_runtime
from app.core.tool_runtime.guidance import get_tool_guidance
from app.core.tool_runtime.policy import (
    get_execution_policy,
    get_permission_context,
    get_plan_mode_policy,
    get_project_policy,
)
from app.core.tool_runtime.planner import ToolPlanner
from .expressions import get_expression_prompt
from app.core.workspace import (
    is_file_operation_request,
    ensure_default_workspace,
    get_default_workspace_context,
    extract_workspace_path,
    get_user_path_workspace_context,
)
from app.core.tool_runtime.permission import NO_PATH_TOOLS
from app.core.planner import get_planner, get_runtime_task_context_adapter
from .context import AgentContext
from .pruning import prune_thought_history

DEFAULT_IDENTITY = "你是一个有帮助的AI助手。"

# ──── Task 3: 普通聊天检测（轻量关键词匹配，避免为闲聊加载工具）────

_CHAT_GREETINGS = {
    "你好", "嗨", "hi", "hello", "hey", "早上好", "下午好", "晚上好", "晚安",
    "再见", "拜拜", "bye", "谢谢", "thanks", "thank", "不客气",
}

_CHAT_SMALL_TALK = {
    "今天怎么样", "今天如何", "今天好吗", "最近怎么样", "最近如何",
    "你怎么样", "你还好吗", "你是什么", "你是谁", "你能做什么",
    "介绍一下自己", "自我介绍",
}

_CHAT_KNOWLEDGE_PREFIXES = {
    "什么是", "解释", "介绍一下", "说说", "讲讲", "为什么", "怎么理解",
    "能否解释", "能不能解释", "请解释",
}

# 任务执行关键词 —— 如果命中，说明用户明确要求执行操作，不走聊天短路
_ACTION_TRIGGERS = {
    "帮我", "请帮我", "能不能帮我", "可以帮我", "你给我",
    "执行", "运行", "创建", "修改", "删除", "添加", "生成",
    "检查", "查看", "分析一下", "查一下", "搜索", "查找",
    "读取", "git", "编译", "构建", "测试", "调试", "部署",
    "修复", "改一下", "改下", "写一个", "写个", "新建",
}


def _is_casual_chat(message: str) -> bool:
    """轻量判断用户消息是否为纯聊天（不触发工具加载）。

    规则：
      1. 纯问候/告别 → True
      2. 闲聊 → True
      3. 知识性问题（什么是/解释/为什么）且无动作触发词 → True
      4. 包含动作触发词 → False
      5. 默认 → False（保守：不确定时走工具加载路径）
    """
    msg = message.strip()
    msg_lower = msg.lower()

    # 规则 1: 纯问候
    if msg_lower in _CHAT_GREETINGS:
        return True

    # 规则 2: 闲聊
    if msg_lower in _CHAT_SMALL_TALK:
        return True

    # 规则 4: 动作触发词（优先级最高 —— 只要包含动作词就不走聊天短路）
    for trigger in _ACTION_TRIGGERS:
        if trigger in msg_lower:
            return False

    # 规则 3: 知识性问题（以"什么是/解释/为什么"开头且不包含动作触发词）
    for prefix in _CHAT_KNOWLEDGE_PREFIXES:
        if msg_lower.startswith(prefix):
            return True

    return False


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
    attachments: list = field(default_factory=list)  # Phase 2: AttachmentItem 列表


@dataclass
class BuiltContext:
    """ChatContextBuilder 输出：AgentContext + 最终 messages + 运行时参数。"""

    context: AgentContext
    messages: list                     # [ModelMessage(system), ...history]
    system_prompt: str                 # 完整 ①-⑩ 组装后的 system prompt
    effective_model: str
    temperature: float
    max_tokens: int
    reasoning_effort: str
    read_only: bool
    memory_text: str                   # 单独交付（模型层注入，不入 system prompt）
    tool_context: Optional[dict] = None
    persona_context: Optional[PersonaContext] = None  # Persona 运行时上下文


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
    """解析本次请求的有效工作目录（用户指定路径 > Default Workspace 兜底）。

    规则：
      - 已绑定项目 → 原样返回，无兜底。
      - 未绑定项目但消息含已存在的绝对路径 → 以该路径（文件则取其父目录）
        作为本次工作目录，返回带 project_path 的视图 + 用户路径上下文文本。
      - 未绑定项目但指令含文件操作 → 启用默认工作目录兜底。
      - 其余 → 返回 project_path=None 视图（仅保留无路径工具）。

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

    # 2026-08-11：用户消息中直接给出存在的绝对路径 → 优先作为本次工作目录
    user_path = extract_workspace_path(message)
    if user_path:
        return (
            _NS(
                mode=chat.mode or "build",
                project_path=user_path,
                agent_id=chat.agent_id,
                project_id=chat.project_id,
            ),
            get_user_path_workspace_context(user_path),
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


# 文本附件最大读取字节数（约 256KB，防止超大文件撑爆 Prompt）
_MAX_TEXT_ATTACHMENT_BYTES = 256 * 1024


def _is_path_within(base_dir: str, file_path: str) -> bool:
    """校验 file_path 是否位于 base_dir 目录内（含自身），防附件路径越权。"""
    if not base_dir or not file_path:
        return False
    base_real = os.path.realpath(base_dir)
    file_real = os.path.realpath(file_path)
    return file_real == base_real or file_real.startswith(base_real + os.sep)


def _read_text_attachment_ladder(abs_path: str) -> Optional[str]:
    """阶梯容错解码读取文本附件：UTF-8 → GBK → errors='replace' 兜底。

    严禁因编码问题抛出 UnicodeDecodeError：
      1. 优先 UTF-8 解码（现代文件主流）
      2. UTF-8 失败 → 尝试 GBK（Windows 中文文件常见编码）
      3. GBK 失败 → UTF-8 + errors='replace'（用替换符兜底，保证不抛异常）

    读取上限 _MAX_TEXT_ATTACHMENT_BYTES 字节，防撑爆 Prompt。
    任何 OSError（文件不存在/无权限）返回 None。
    """
    try:
        # 先按字节读取（限定上限），再做解码尝试
        with open(abs_path, "rb") as f:
            raw = f.read(_MAX_TEXT_ATTACHMENT_BYTES)
    except OSError:
        return None

    # 阶梯解码：UTF-8 → GBK → replace 兜底
    for encoding in ("utf-8", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    # 兜底：UTF-8 + replace（不会抛异常，无法识别的字节用 替换符）
    return raw.decode("utf-8", errors="replace")


def _build_attachment_prompt(attachments: list, project_path: Optional[str]) -> str:
    """将附件列表组装为 system prompt 第 ⑨ 层文本块（严密版格式）。

    注入格式（按 Phase 2 严密版规范）：
      - text  : [附件上下文]\n[文件: {name}] ({path})\n{file_content}
      - image : [图片附件: {name}] ({path})
      - binary: [二进制/压缩包附件: {name}] (大小: {size}B, 类型: {mime})

    安全：
      - text 附件读取仅限 project_path 内文件（_is_path_within 防越权）
      - text 附件阶梯解码（UTF-8 → GBK → replace），严禁 UnicodeDecodeError
      - 读取失败注入"无法读取"说明，不中断整体组装

    attachments 元素为 Pydantic AttachmentItem 或 dict（兼容测试构造）。
    """
    text_blocks = []
    binary_meta = []
    image_lines = []

    for att in attachments:
        # 兼容 Pydantic model 与 dict
        if hasattr(att, "model_dump"):
            a = att.model_dump()
        elif isinstance(att, dict):
            a = att
        else:
            continue

        kind = a.get("kind", "text")
        name = a.get("name", "unknown")
        rel_path = a.get("path")
        size = a.get("size", 0)
        mime = a.get("mime", "application/octet-stream")

        if kind == "image":
            # image 不入 system prompt 内容（由 build() 写入 vision_context），
            # 仅写入名称+路径提示，让 Agent 知道有图片附件已传入视觉通道
            path_hint = rel_path if rel_path else "(无路径)"
            image_lines.append(f"[图片附件: {name}] ({path_hint})")
            continue

        if kind == "binary":
            # binary：注入元数据说明，提示 Agent 必要时用工具命令读取
            binary_meta.append(
                f"[二进制/压缩包附件: {name}] (大小: {size}B, 类型: {mime})"
            )
            continue

        # kind == "text"：阶梯解码读取内容
        content_text = None
        used_path = rel_path
        if rel_path and project_path:
            abs_path = os.path.join(project_path, rel_path)
            if _is_path_within(project_path, abs_path) and os.path.isfile(abs_path):
                content_text = _read_text_attachment_ladder(abs_path)

        path_hint = used_path if used_path else "(无路径)"
        if content_text is None:
            text_blocks.append(
                f"[附件上下文]\n[文件: {name}] ({path_hint})\n（无法读取文件内容）"
            )
        else:
            text_blocks.append(
                f"[附件上下文]\n[文件: {name}] ({path_hint})\n{content_text}"
            )

    sections = []
    if text_blocks:
        sections.append("\n\n".join(text_blocks))
    if binary_meta:
        sections.append("\n".join(binary_meta))
    if image_lines:
        sections.append("\n".join(image_lines))

    if not sections:
        return ""
    preamble = (
        "<!-- ATTACHMENT_CONTEXT_NOTICE: 以下内容已由前端读取并注入内存，"
        "请直接基于此内容回答，无需调用任何文件读取工具，也绝对不需要项目路径。 -->"
    )
    return preamble + "\n<attachments>\n" + "\n\n".join(sections) + "\n</attachments>"


def _build_vision_context(attachments: list, project_path: Optional[str]) -> Optional[dict]:
    """从附件列表提取 image 附件，构造 vision_context（供 AgentContext.vision_context）。

    返回 None 表示无图片附件。结构：
        {
            "images": [
                {"name": ..., "path": 绝对路径, "rel_path": 相对路径, "mime": ..., "size": ...},
                ...
            ]
        }
    """
    import logging
    logger = logging.getLogger(__name__)
    images = []
    for att in attachments:
        if hasattr(att, "model_dump"):
            a = att.model_dump()
        elif isinstance(att, dict):
            a = att
        else:
            continue
        if a.get("kind") != "image":
            continue
        rel_path = a.get("path")
        abs_path = None
        if rel_path and project_path:
            candidate = os.path.join(project_path, rel_path)
            if _is_path_within(project_path, candidate) and os.path.isfile(candidate):
                abs_path = candidate
            else:
                logger.warning(
                    "vision_context: 图片路径解析失败 rel_path=%s project_path=%s candidate=%s isfile=%s",
                    rel_path, project_path, candidate, os.path.isfile(candidate) if candidate else False,
                )
        elif rel_path and not project_path:
            # 无项目关联：rel_path 可能是绝对路径或 .mfkagent/uploads/ 相对路径
            if os.path.isabs(rel_path) and os.path.isfile(rel_path):
                abs_path = rel_path
            else:
                logger.warning(
                    "vision_context: 无项目关联且路径非绝对路径 rel_path=%s", rel_path,
                )
        images.append({
            "name": a.get("name", "unknown"),
            "path": abs_path,  # 绝对路径，供模型层/工具读取
            "rel_path": rel_path,
            "mime": a.get("mime", "application/octet-stream"),
            "size": a.get("size", 0),
        })
    if not images:
        return None
    logger.info(
        "vision_context: 构建完成 images=%d, 有效路径=%d",
        len(images), sum(1 for i in images if i["path"]),
    )
    return {"images": images}


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
        attachments: Optional[list] = None,
        tool_guidance: Optional[str] = None,
        expression_profile: Optional[str] = None,
        persona_context: Optional[PersonaContext] = None,
    ) -> str:
        """按 ①-⑩+ 层组装完整 system prompt（memory_text 由模型层单独注入）。"""
        # ⓪ 最高身份准则（强制置顶，锁定桌面端 Agent 身份认知）
        full_prompt = get_identity_principle()

        # ⓪b Agent Base Instruction（所有 Agent 共享的基础行为规则）
        full_prompt += get_agent_base_instruction()

        # ① identity（纯角色，零行为指令）
        full_prompt += system_prompt

        # ② capability_prompt（领域能力倾向）
        capability_prompt = get_capability_prompt(capabilities)
        if capability_prompt:
            full_prompt += "\n\n" + capability_prompt

        # ②b Skill Prompt Fragment（Phase 4 T3: 能力增强层，注入位置在 capability 之后、execution_policy 之前）
        # Skill = Prompt Fragment，仅文本，无 Tool/Code/Executor 能力
        # 加载失败/无 Skill 时返回空串，不影响 prompt 结构
        skills_prompt = get_enabled_skills_prompt()
        if skills_prompt:
            full_prompt += "\n\n" + skills_prompt

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

        # ⑥b expression_profile（表达风格层 — Expression Profile V1）
        expression_prompt = get_expression_prompt(expression_profile)
        if expression_prompt:
            full_prompt += "\n\n" + expression_prompt

        # ⑥c persona_traits（Persona System V1 — 人格特质层）
        if persona_context and persona_context.persona_text:
            full_prompt += "\n\n" + persona_context.persona_text

        # ⑥d persona_expression（Persona System V1 — 表达风格层）
        if persona_context and persona_context.expression_text:
            full_prompt += "\n\n" + persona_context.expression_text

        # ⑥e persona_behavior（Persona System V2 — 人类对话规则，全 Agent 默认）
        if persona_context and persona_context.behavior_text:
            full_prompt += "\n\n" + persona_context.behavior_text

        # ⑥f persona_budget（Persona System V2 — 表达预算，控制表演密度）
        if persona_context and persona_context.budget_text:
            full_prompt += "\n\n" + persona_context.budget_text

        # ⑥g persona_work_mode（Persona System V2 — 工作模式提示，仅调整正式度）
        if persona_context and persona_context.work_mode_text:
            full_prompt += "\n\n" + persona_context.work_mode_text

        # ⑥h persona_restrictions（Persona System V2 — 禁止表达层）
        if persona_context and persona_context.restrictions_text:
            full_prompt += "\n\n" + persona_context.restrictions_text

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

        # ⑨ tool_guidance（Tool Guidance V1：动态工具使用指导）
        if tool_guidance:
            full_prompt += "\n\n" + tool_guidance

        # ⑩ attachments（Phase 2：附件上下文层）
        # - text 附件：读取文件内容注入 Prompt（仅 project_path 内文件，防越权）
        # - image 附件：不注入 system prompt，由 build() 写入 vision_context
        # - binary 附件：注入元数据说明，提示 Agent 用工具自行读取
        if attachments:
            attachment_section = _build_attachment_prompt(
                attachments, getattr(effective_chat, "project_path", None)
            )
            if attachment_section:
                full_prompt += "\n\n" + attachment_section

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
            # Task 3: 普通聊天检测 —— 闲聊消息跳过工具加载，避免误触发工具调用
            is_chat = _is_casual_chat(input.content)
            if input.use_tools and not is_chat:
                tool_context = tool_runtime.process(
                    message=input.content,
                    chat=effective_chat,
                    agent_capabilities=capabilities,
                )
                if tool_context.get("need_tools"):
                    tools_arg = tool_context["tools"]
                decision = tool_context.get("decision")
                # 未绑定项目：PermissionFilter 已移除项目专有工具；
                # 此处按无路径白名单二次过滤，保留 add_memory/web_search 等无需路径的工具，
                # 不再一棒子打死（2026-08-11：修复普通聊天工具全禁问题）
                if not effective_chat.project_path and tools_arg:
                    tools_arg = [
                        t for t in tools_arg
                        if t.get("function", {}).get("name") in NO_PATH_TOOLS
                    ]
                    if not tools_arg:
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

            # ──── Persona System V2: 加载人格运行时上下文 ────
            # 所有 Agent 默认注入 Human Conversation Rules + Expression Budget；
            # 有 PersonaTemplate 时叠加人格特质层；Pianai 追加 Relationship Layer
            persona_ctx: Optional[PersonaContext] = None
            if agent:
                persona_tmpl = db.query(PersonaTemplate).filter(
                    PersonaTemplate.agent_id == agent.agent_id
                ).first()
                # 交流次数：当前会话的 user 消息数（轻量查询，JOIN 全表 COUNT 性能差）
                interaction_count = (
                    db.query(Message)
                    .filter(Message.chat_id == input.chat_id, Message.role == "user")
                    .count()
                )
                expr_knowledge = load_expression_knowledge(agent.expression_profile, db=db)
                persona_ctx = build_persona_context(
                    agent, persona_tmpl, expr_knowledge,
                    user_message=input.content,
                    interaction_count=interaction_count,
                )

            full_prompt = self._assemble_prompt(
                system_prompt=system_prompt,
                capabilities=capabilities,
                personality_prompt=personality_prompt,
                effective_chat=effective_chat,
                workspace_context=workspace_context,
                tool_context=tool_context,
                task_context=task_context,
                attachments=input.attachments,
                tool_guidance=get_tool_guidance(
                    intent=(decision or {}).get("intent", "general_chat"),
                    project_bound=bool(effective_chat.project_path),
                    message=input.content,
                ),
                expression_profile=agent.expression_profile if agent else None,
                persona_context=persona_ctx,
            )

            # ──── Phase 2: image 附件 → vision_context ────
            vision_ctx = _build_vision_context(
                input.attachments, effective_chat.project_path
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
                vision_context=vision_ctx,  # Phase 2: image 附件视觉上下文（无图片为 None）
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
                persona_context=persona_ctx,
            )
        finally:
            db.close()


# 全局单例（无状态，可共享）
_chat_context_builder = ChatContextBuilder()


def get_chat_context_builder() -> ChatContextBuilder:
    return _chat_context_builder
