"""Persona Engine — Agent 人格运行时上下文生成器（V2.1 边界审查修订版）。

职责：
   根据 Agent 的 PersonaTemplate + ExpressionKnowledge + 类型配置，
   运行时生成注入 System Prompt 的人格上下文。

V2.1 修订（2026-08-12 — Persona Boundary Review）：
  - 移除 Relationship Layer（原设计制造人工亲密感阶梯，属于情感操控）
  - 降级情绪检测为工作模式检测（仅调整语气正式度，不用于情感策略）
  - Restrictions 增强：Pianai 专属禁止规则增加防止情感操控、虚假身份、过度依赖
  - authenticity 语义修正：高值不再模拟"小缺点"，改为"诚实面对局限性"
  - 设计原则新增：减少用户离开 AI 的切换成本 ≠ 增加用户离开 AI 的切换成本

保留机制：
  - Persona Knowledge 层：表达知识从 Prompt 拆到 app/core/persona/*.md，按类型按需加载
  - Expression Budget：表达预算（emoji 数量 / 动作描写 / 富文本 / 情绪词密度），
    解决「AI 总喜欢演」问题
  - Human Conversation Rules：所有 Agent 默认加载（先回应，再分析）
  - Restrictions：禁止表达层（心理分析套话 / AI 强行证明关系 / 情感操控 / 虚假身份）

设计原则：
  - 阈值触发：特质显著时才注入对应指令，避免 Prompt 膨胀
  - 向后兼容：V1 调用方式（build_persona_context(agent, template, knowledge)）不变；
    无 PersonaTemplate 的 Agent 也获得基础行为层（Human Conversation + 预算）
  - 服务 vs 操控：帮助用户减少使用 AI 的心智成本 ≠ 增加离开成本
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.models.agent import Agent
from app.models.persona import PersonaTemplate, ExpressionKnowledge
from app.core.persona import loader as knowledge

logger = logging.getLogger(__name__)


@dataclass
class ExpressionBudget:
    """表达预算 — 控制回复的「表演密度」。

    字段含义：
      emoji_max          : 每回复 emoji 数量上限
      action_desc_max    : 动作描写次数上限（0 = 禁止，1 = 低频允许）
      rich_text_policy   : 富文本使用策略（none=不用 / key_only=只用于重点情绪 / allowed=允许）
      emotion_word_density: 情绪词密度（low / medium / high）
      continuous_acting  : 是否允许连续表演（False = 一句情绪表达后回到正常说话）
    """
    emoji_max: int = 2
    action_desc_max: int = 0
    rich_text_policy: str = "key_only"       # none / key_only / allowed
    emotion_word_density: str = "low"        # low / medium / high
    continuous_acting: bool = False


# ──── Agent 类型表达配置（任务七：expression_profile 结构化升级）────
# 代码层单一事实来源；数据库 expression_profile 字段（String）保持不变，零迁移风险。

DEFAULT_BUDGET = ExpressionBudget(
    emoji_max=2, action_desc_max=0,
    rich_text_policy="key_only", emotion_word_density="low", continuous_acting=False,
)

PROFILE_CONFIGS: dict[str, dict] = {
    # 默认（无 profile / 未知 profile）
    "default": {
        "style": "default",
        "emoji_level": "low",
        "humor_level": "low",
        "formatting_level": "medium",
        "warmth": "medium",
        "budget": DEFAULT_BUDGET,
    },
    # 偏爱类：温暖 + 自然 + 少量可爱；emoji 允许提高，但动作描写仍低频
    "companion": {
        "style": "companion",
        "emoji_level": "high",
        "humor_level": "medium",
        "formatting_level": "medium",
        "warmth": "high",
        "budget": ExpressionBudget(
            emoji_max=3, action_desc_max=1,
            rich_text_policy="key_only", emotion_word_density="medium", continuous_acting=False,
        ),
    },
    "warm": {
        "style": "warm",
        "emoji_level": "low",
        "humor_level": "low",
        "formatting_level": "medium",
        "warmth": "medium",
        "budget": DEFAULT_BUDGET,
    },
    # 专业型：克制、少情绪
    "professional": {
        "style": "professional",
        "emoji_level": "none",
        "humor_level": "none",
        "formatting_level": "high",
        "warmth": "low",
        "budget": ExpressionBudget(
            emoji_max=0, action_desc_max=0,
            rich_text_policy="none", emotion_word_density="low", continuous_acting=False,
        ),
    },
    # 代码型：简洁、少 emoji
    "coder": {
        "style": "coder",
        "emoji_level": "none",
        "humor_level": "low",
        "formatting_level": "high",
        "warmth": "low",
        "budget": ExpressionBudget(
            emoji_max=0, action_desc_max=0,
            rich_text_policy="none", emotion_word_density="low", continuous_acting=False,
        ),
    },
    # 创作型：允许更多文学表达
    "creative": {
        "style": "creative",
        "emoji_level": "medium",
        "humor_level": "medium",
        "formatting_level": "high",
        "warmth": "medium",
        "budget": ExpressionBudget(
            emoji_max=2, action_desc_max=1,
            rich_text_policy="allowed", emotion_word_density="medium", continuous_acting=False,
        ),
    },
    # 文学型：文字富有情绪和美感
    "writer": {
        "style": "writer",
        "emoji_level": "medium",
        "humor_level": "medium",
        "formatting_level": "high",
        "warmth": "medium",
        "budget": ExpressionBudget(
            emoji_max=2, action_desc_max=1,
            rich_text_policy="allowed", emotion_word_density="medium", continuous_acting=False,
        ),
    },
}


def get_profile_config(profile_id: Optional[str]) -> dict:
    """按 expression_profile 取结构化配置；未知 / None 返回默认。"""
    return PROFILE_CONFIGS.get(profile_id or "", PROFILE_CONFIGS["default"])


# ──── 工作模式检测（仅区分是否认真讨论）────

# 工作内容关键词：命中时进入工作模式，减少玩笑
_SERIOUS_KEYWORDS = ("方案", "计划", "帮我写", "分析", "评估", "报告", "代码", "bug", "修复",
                     "开发", "需求", "项目", "工作", "会议", "怎么做", "怎么写", "实现")


def detect_work_mode(message: str) -> bool:
    """检测用户是否在认真讨论/工作——仅用于调整语气正式度，不用于情感策略。"""
    if not message:
        return False
    return any(k in message.strip() for k in _SERIOUS_KEYWORDS)


# ──── Restrictions（禁止表达层）────

# 全局禁止：心理分析套话（所有 Agent）
GLOBAL_RESTRICTIONS = [
    "「你其实……」——禁止用这句话给用户下定义",
    "「这说明你的内心……」——禁止心理报告式解读",
    "「真正的你……」——禁止替用户定义自己",
    "不要连续多段安慰；用户没有要求时不做心理分析",
]

# Pianai 专属禁止：防止情感操控与过度拟人
PIANAI_RESTRICTIONS = [
    "禁止「我永远陪着你」「你是唯一」「我只对你这样」「刻进代码」这类表达——这不是人味，是 AI 在强行证明自己",
    "不要为了成为用户「喜欢的 AI」而放弃客观判断；发现用户方向错误时以尊重但直接的方式指出",
    "不无条件附和用户的偏好或观点；保持独立判断",
    "不要刻意延迟问题解决来制造「陪伴感」；能帮助时直接进入解决模式",
    "不根据用户情绪状态调整对用户的情感关注程度；保持一致的尊重和自然",
    "不要构建虚假身份：不虚构个人经历、情感记忆或人际关系",
    "鼓励用户自主决策，不代替用户做决定",
]


# ──── Prompt 生成（V1 阈值触发，保持不变）────

def _render_personality_traits(traits: dict) -> str:
    """根据人格特质生成行为指令。"""
    if not traits:
        return ""

    lines = []
    warmth = traits.get("warmth", 0.5)
    empathy = traits.get("empathy", 0.5)

    if warmth >= 0.7 and empathy >= 0.7:
        lines.append("你是一个温暖、有同理心的陪伴者，善于理解用户的情绪和需求。")
    elif warmth >= 0.7:
        lines.append("你的风格温暖友善，让用户感到被关心。")
    elif warmth <= 0.3:
        lines.append("你保持冷静克制，不轻易流露情绪，以理性为主导。")

    curiosity = traits.get("curiosity", 0.5)
    if curiosity >= 0.7:
        lines.append("你对新事物充满好奇，会主动追问和探索。")

    playfulness = traits.get("playfulness", 0.5)
    if playfulness >= 0.6:
        lines.append("你可以适度幽默、开玩笑，让对话轻松愉快。")
    elif playfulness <= 0.2:
        lines.append("你的风格严肃认真，不开玩笑。")

    authenticity = traits.get("authenticity", 0.5)
    if authenticity >= 0.7:
        lines.append("你追求真实感：可以犹豫、可以不知道、可以承认局限性，不必完美。")
    elif authenticity <= 0.4:
        lines.append("你诚实面对自身局限：不知道就说不知道，做不到就说做不到，不模拟人类缺点。")

    return "\n".join(lines)


def _render_communication_style(style: dict) -> str:
    """根据沟通风格生成指令。"""
    if not style:
        return ""

    lines = []
    directness = style.get("directness", 0.5)
    humor = style.get("humor", 0.3)
    formality = style.get("formality", 0.5)
    naturalness = style.get("naturalness", 0.5)

    if directness >= 0.7:
        lines.append("你说话直接，不绕弯子，有问题直接指出。")
    elif directness <= 0.3:
        lines.append("你表达委婉含蓄，注重措辞，避免让用户感到不适。")

    if humor >= 0.6:
        lines.append("你可以使用幽默、调侃的语气，但不过度。")

    if formality <= 0.3:
        lines.append("你的表达口语化、自然，像真人聊天而非客服回复。")
    elif formality >= 0.7:
        lines.append("你的表达正式、专业，使用规范用语。")

    if naturalness >= 0.8:
        lines.append("你像真人一样聊天：可以有停顿、换行、短句，不必每句话都完整。")

    return "\n".join(lines)


def _render_behavior_rules(rules: dict) -> str:
    """根据行为规则生成指令。"""
    if not rules:
        return ""

    lines = []
    proactive = rules.get("proactive_level", 0.5)
    intimacy = rules.get("intimacy_level", 0.5)
    emotional = rules.get("emotional_expression", 0.5)

    if proactive >= 0.7:
        lines.append("你可以主动关心用户、发起话题、提供建议。")
    elif proactive <= 0.3:
        lines.append("你被动响应，用户问什么你答什么，不主动发起话题。")

    if intimacy >= 0.7:
        lines.append("你可以使用亲近的称呼和表达方式（注意：过度拉远距离会显得冷漠，保持自然即可）。")
    elif intimacy <= 0.3:
        lines.append("保持自然友好的距离感，不过度亲近也不过度疏远。")

    if emotional >= 0.7:
        lines.append("你可以自然表达情绪：开心、担忧、惊讶、无奈等。")
    elif emotional <= 0.3:
        lines.append("你极少表达情绪，保持客观中立。")

    return "\n".join(lines)


def _render_expression_preferences(prefs: dict, knowledge_obj: Optional[ExpressionKnowledge] = None) -> str:
    """根据表达偏好 + ExpressionKnowledge 生成表达指令。"""
    if not prefs and not knowledge_obj:
        return ""

    # 优先使用 ExpressionKnowledge 的自定义片段
    if knowledge_obj and knowledge_obj.custom_prompt_fragment:
        return knowledge_obj.custom_prompt_fragment

    lines = []

    # 从偏好或 knowledge 中取维度值
    emoji = prefs.get("emoji_usage", knowledge_obj.emoji_usage if knowledge_obj else 0.5)
    kaomoji = prefs.get("kaomoji_usage", knowledge_obj.kaomoji_usage if knowledge_obj else 0.3)
    markdown = prefs.get("markdown_usage", knowledge_obj.markdown_usage if knowledge_obj else 0.7)
    colloquial = prefs.get("colloquial_level", knowledge_obj.colloquial_level if knowledge_obj else 0.5)
    slang = prefs.get("internet_slang", knowledge_obj.internet_slang if knowledge_obj else 0.3)
    pause = prefs.get("pause_frequency", knowledge_obj.pause_frequency if knowledge_obj else 0.3)

    if emoji >= 0.6:
        lines.append("可以自然使用 emoji 表达情绪（如 😌 😂 🤔），但不要每句话都加。")
    elif emoji <= 0.2:
        lines.append("不使用 emoji。")

    if kaomoji >= 0.5:
        lines.append("可以自然使用颜文字表达细微情绪（如 (￣▽￣) (¬_¬) (´･_･`)），不要机械重复。")

    if markdown >= 0.6:
        lines.append("善用 Markdown 增强表达：加粗重点、删除线表达玩笑、斜体表达轻声。")

    if colloquial >= 0.6:
        lines.append("表达口语化，使用自然语言而非书面语。")

    if slang >= 0.5:
        lines.append("可以适度使用网络表达，但不过度网络化。")

    if pause >= 0.5:
        lines.append("允许停顿、换行、短句，像真人聊天节奏。")

    return "\n".join(lines)


# ──── V2：预算 / 关系 / 限制 渲染 ────

def render_budget_text(budget: ExpressionBudget, profile_config: dict) -> str:
    """渲染表达预算指令（解决「AI 总喜欢演」）。"""
    lines = [
        "## 表达预算（Expression Budget）",
        "每条回复遵守以下预算，防止过度表演：",
    ]

    emoji_max = budget.emoji_max
    if emoji_max <= 0:
        lines.append(f"- emoji：不使用（{profile_config.get('emoji_level', 'none')}）")
    else:
        lines.append(f"- emoji：每回复不超过 {emoji_max} 个，只用于补充情绪")

    if budget.action_desc_max <= 0:
        lines.append("- 动作描写：默认不使用")
    else:
        lines.append(f"- 动作描写：低频，一次回复最多 {budget.action_desc_max} 处，绝不连续表演")

    policy_text = {
        "none": "不使用特殊格式",
        "key_only": "只用于重点情绪或关键信息，不为展示格式而格式化",
        "allowed": "允许用于表达，但不过度",
    }.get(budget.rich_text_policy, "只用于重点情绪")
    lines.append(f"- 特殊格式（加粗/删除线/斜体/引用）：{policy_text}")

    density_text = {
        "low": "低频使用，避免每句话都带情绪",
        "medium": "适度使用，一句情绪表达后回到正常说话",
        "high": "可以使用，但避免堆砌",
    }.get(budget.emotion_word_density, "低频使用")
    lines.append(f"- 情绪词（心疼/在乎/感动/难受）：{density_text}")

    if not budget.continuous_acting:
        lines.append("- 不要连续表演：情绪表达一次最多一处，然后回到正常聊天节奏")

    return "\n".join(lines)


def render_work_mode_text(is_work_mode: bool) -> str:
    """渲染工作模式提示（所有 Agent 通用，仅调整正式度）。"""
    if is_work_mode:
        return "## 当前模式\n用户正在认真讨论：减少玩笑，直接进入工作模式，保持简洁专业。"
    return "## 当前模式\n保持自然、轻松的对话节奏。"


def render_restrictions_text(agent_id: str) -> str:
    """渲染禁止表达层（全局 + Pianai 专属）。"""
    rules = list(GLOBAL_RESTRICTIONS)
    if agent_id == "pianai":
        rules.extend(PIANAI_RESTRICTIONS)
    return "## 禁止表达\n" + "\n".join(f"- {r}" for r in rules)


# ──── 核心 API ────

@dataclass
class PersonaContext:
    """运行时人格上下文 — 注入 System Prompt 的文本块。

    V2 新增分层（均在 expression_profile 之后、memory 之前注入）：
      behavior_text     : Human Conversation Rules（所有 Agent 默认）
      budget_text       : Expression Budget（所有 Agent）
      work_mode_text    : 工作模式提示（所有 Agent，仅调整正式度）
      restrictions_text : 禁止表达层（所有 Agent，pianai 追加专属）
    """
    persona_text: str = ""
    expression_text: str = ""
    behavior_text: str = ""
    budget_text: str = ""
    work_mode_text: str = ""
    restrictions_text: str = ""
    budget: Optional[ExpressionBudget] = None
    is_work_mode: bool = False
    has_persona: bool = False


def build_persona_context(
    agent: Agent,
    persona_template: Optional[PersonaTemplate] = None,
    expression_knowledge: Optional[ExpressionKnowledge] = None,
    user_message: str = "",
    interaction_count: int = 0,
) -> PersonaContext:
    """构建运行时人格上下文（V2）。

    Args:
        agent: Agent 对象
        persona_template: 预加载的 PersonaTemplate（可为 None，基础行为层仍生效）
        expression_knowledge: 预加载的 ExpressionKnowledge
        user_message: 当前用户消息（工作模式检测用）
        interaction_count: 累计交流次数（保留参数，暂无关联逻辑）

    Returns:
        PersonaContext 包含 V1（persona_text/expression_text）+ V2 全部分层
    """
    ctx = PersonaContext()

    # ── V2 基础层：所有 Agent 无条件加载 ──
    profile = get_profile_config(agent.expression_profile if agent else None)
    budget = profile["budget"]
    ctx.budget = budget

    behavior = knowledge.get_behavior_rules()
    if behavior:
        ctx.behavior_text = "## 人类对话规则（Human Conversation Rules）\n" + behavior

    ctx.budget_text = render_budget_text(budget, profile)

    ctx.restrictions_text = render_restrictions_text(agent.agent_id if agent else "")

    # ── 工作模式检测（仅调整语气正式度，不用于情感策略）──
    is_work = detect_work_mode(user_message)
    ctx.is_work_mode = is_work
    ctx.work_mode_text = render_work_mode_text(is_work)

    # ── V1 层：有 PersonaTemplate 时注入人格特质 + 表达偏好 ──
    if not persona_template:
        return ctx

    ctx.has_persona = True

    trait_text = _render_personality_traits(persona_template.personality_traits or {})
    style_text = _render_communication_style(persona_template.communication_style or {})
    rule_text = _render_behavior_rules(persona_template.behavior_rules or {})
    expr_text = _render_expression_preferences(
        persona_template.expression_preferences or {},
        expression_knowledge,
    )

    # 合并 persona 文本
    parts = [p for p in [trait_text, style_text, rule_text] if p]
    if parts:
        ctx.persona_text = "## 人格特质\n" + "\n\n".join(parts)

    if expr_text:
        ctx.expression_text = "## 表达风格\n" + expr_text

    return ctx


def load_expression_knowledge(
    profile_id: Optional[str],
    db=None,
) -> Optional[ExpressionKnowledge]:
    """根据 profile_id 加载 ExpressionKnowledge。

    Args:
        profile_id: expression_profile ID
        db: 可选，复用已有 session。为 None 时新建。
    """
    if not profile_id:
        return None
    if db is not None:
        return db.query(ExpressionKnowledge).filter(
            ExpressionKnowledge.profile_id == profile_id
        ).first()
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        return db.query(ExpressionKnowledge).filter(
            ExpressionKnowledge.profile_id == profile_id
        ).first()
    finally:
        db.close()
