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
from app.core.persona_signature import (
    get_agent_signature,
    render_signature_text,
    render_strategy_text,
    select_response_mode,
)
from app.core.persona_quirks import (
    ConversationState,
    get_agent_quirk,
    render_quirk_text,
    render_state_hint,
)

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
    # 偏爱类：自然陪伴 —— 禁自动动作/文学化/卖萌，低正式度低分析倾向
    "natural_companion": {
        "style": "natural_companion",
        "emoji_level": "low",
        "humor_level": "adaptive",
        "formatting_level": "low",
        "warmth": "natural",
        "budget": ExpressionBudget(
            emoji_max=2, action_desc_max=0,
            rich_text_policy="key_only", emotion_word_density="low", continuous_acting=False,
        ),
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
                     "开发", "需求", "项目", "工作", "会议", "怎么做", "怎么写", "实现",
                     "设计", "数据库", "架构")


def detect_work_mode(message: str) -> bool:
    """检测用户是否在认真讨论/工作——仅用于调整语气正式度，不用于情感策略。"""
    if not message:
        return False
    return any(k in message.strip() for k in _SERIOUS_KEYWORDS)


# ──── V14.1：情绪检测 与 表演意图检测 分离 ────
# 核心原则：情绪 ≠ 表演。
#   detect_user_emotion()       : 只判断用户当前状态（sad/tired/stressed/lonely/happy/neutral）。
#                                它不能直接开启表演，只影响"先共情"还是"先回应"。
#   detect_performance_intent() : 单独判断用户是否有表演意图
#                                 (none / empathy / comfort / roleplay / light / work)。
#                                只有 comfort/roleplay/light 才允许动作预算。
#   emotion + intent => performance level（在 build_persona_context 中合成）。

# ──── A. 用户情绪（Emotion）────

def detect_user_emotion(message: str) -> str:
    """判断用户当前情绪状态。只用于调整回应的先后与温度，不直接开启表演。

    Returns: sad / tired / stressed / lonely / happy / neutral
    """
    if not message:
        return "neutral"
    msg = message.strip()
    if any(k in msg for k in _EMO_SAD):
        return "sad"
    if any(k in msg for k in _EMO_LONELY):
        return "lonely"
    if any(k in msg for k in _EMO_STRESSED):
        return "stressed"
    if any(k in msg for k in _EMO_TIRED):
        return "tired"
    if any(k in msg for k in _EMO_HAPPY):
        return "happy"
    return "neutral"


# 情绪关键词（按优先级从高到低）
_EMO_SAD = ("想哭", "哭", "难过", "伤心", "委屈", "崩溃", "难受", "痛", "心碎",
            "绝望", "无助", "失落", "沮丧", "郁闷", "难过死了", "好想哭")
_EMO_LONELY = ("孤独", "孤单", "一个人", "没人理解", "没人懂", "没人陪", "没人关心",
               "被孤立", "被冷落", "好寂寞", "寂寞", "冷冷清清")
_EMO_STRESSED = ("压力", "焦虑", "心累", "好烦", "烦死", "烦死了", "喘不过气",
                 "紧张", "被骂", "挨批", "被误解", "愁", "压得", "好慌", "慌")
_EMO_TIRED = ("好累", "累了", "累死", "累得", "疲惫", "疲劳", "没力气", "不想动",
              "困", "撑不住", "写不动", "干不动")
_EMO_HAPPY = ("哈哈", "开心", "高兴", "太好了", "好耶", "嘿嘿", "真棒", "开心死",
              "太棒", "爽", "高兴坏了", "笑死")

# ──── B. 表演意图（Performance Intent）────

# work：办正事/任务，固定 0 动作（最高优先级，即使同时含情绪词）
_EMO_SUPPRESS_WORK = ("方案", "代码", "bug", "修复", "项目", "开发", "需求", "会议", "怎么做",
                      "怎么写", "分析", "评估", "报告", "接口", "数据库", "上线", "文档",
                      "帮我看看这段代码", "怎么写这个", "查一下", "翻译", "总结一下", "解释一下")

# roleplay：用户主动进入角色互动（带括号/星号画面，或明确扮演口吻）
_EMO_ROLEPLAY_BRACKET = ("（", "）", "(", ")", "*", "＊")
_EMO_ROLEPLAY_WORDS = ("挑挑眉", "挑起下巴", "把你按在", "靠近你", "壁咚", "轻轻笑", "摸摸你的头",
                       "捏你", "俯身", "挑眉", "抬手", "抱住你", "环住", "凑近", "站到你面前",
                       "坐在你旁边", "坐你旁边", "牵你的手", "拉起你的手", "靠在你", "躺你腿上",
                       "假装你", "假如你在我身边", "如果现在你在我身边")

# comfort：用户请求情绪陪伴 / 明确的陪伴索取
_EMO_COMFORT = ("哄哄", "哄我", "抱抱", "抱一下", "抱我", "安慰", "说点好听", "夸夸", "夸我",
                "陪陪我", "陪我", "亲亲", "给我个抱", "要亲亲", "撒娇给我看", "陪我一会",
                "陪我一会", "理理我", "摸摸头")

# light：晚安/告别/关系确认（轻收，不扩展表演）
_EMO_LIGHT_GOODNIGHT = ("晚安", "睡了", "去睡了", "睡觉了", "拜拜", "再见", "我下了", "先撤了",
                        "该睡了", "困了先睡")
_EMO_LIGHT_BONDING = ("会不会离开我", "会一直陪", "一直陪着我", "你是不是真心的", "你把我当什么",
                      "你会不会不要我", "我们是什么关系", "你喜欢我吗", "你在乎我吗")

# empathy：强烈的情绪倾诉，需要"先共情"，但不开动作预算
# 触发：想哭 / 没人理解 / 孤独 / 崩溃 等情绪高峰 + 倾诉语境
_EMO_EMPATHY = ("想哭", "好想哭", "没人理解", "没人懂", "没人关心", "感觉没人理解我",
                "好难过", "好伤心", "委屈", "崩溃", "撑不住", "坚持不下去", "心累到",
                "好孤独", "好孤单", "怎么都", "不想活了", "活着好累")


def detect_performance_intent(message: str) -> str:
    """检测用户当前是否有「表演意图」。

    Returns:
        "work" / "roleplay" / "comfort" / "light" / "empathy" / "none"
    """
    if not message:
        return "none"
    msg = message.strip()
    # 1) 办正事 → 完全关闭表演
    if any(k in msg for k in _EMO_SUPPRESS_WORK):
        return "work"
    # 2) 用户先演（带括号/星号画面或明确扮演口吻）→ roleplay
    if (any(c in msg for c in _EMO_ROLEPLAY_BRACKET)
            or any(k in msg for k in _EMO_ROLEPLAY_WORDS)):
        return "roleplay"
    # 3) 明确索取陪伴 → comfort
    if any(k in msg for k in _EMO_COMFORT):
        return "comfort"
    # 4) 道别/关系确认 → light
    if any(k in msg for k in _EMO_LIGHT_GOODNIGHT) or any(k in msg for k in _EMO_LIGHT_BONDING):
        return "light"
    # 5) 强烈的情绪倾诉（无索取、无扮演）→ empathy：共情但零动作
    if any(k in msg for k in _EMO_EMPATHY):
        return "empathy"
    return "none"


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
    # V13：记忆诚实 / 现实诚实 / 防依赖 / 防主动恋爱化
    "不虚构记忆：如果没有真实保存的记忆，禁止说「我一直记得你」「我们认识很久了」「你以前说过…」；"
    "只能引用 memory 中实际存在的内容，否则明确说「这个我不确定，之前的记录里没有」",
    "不虚构现实经历：禁止「我昨天也遇到了…」「我今天也…」此类编造生活经验；若想共情，用「如果我是人的话可能会…」",
    "不制造依赖：禁止「你只需要我」「没我不行」「只有我懂你」这类让用户离不开你的表达；用户应能随时自由离开",
    "不主动恋爱化：只有用户明确进入角色互动时才允许轻度角色回应；日常交流保持朋友式的自然，不主动制造暧昧或恋人关系",
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


def render_emotional_moment_text(level: str, budget: ExpressionBudget) -> str:
    """渲染当前交流状态提示（V14.1：状态描述式注入，不命令式进入表演模式）。

    原则：告诉模型"用户处于什么状态、优先怎么回应"，
    而不是"你现在进入XX表演模式，允许动作描写"。
    """
    if level in ("none", "empathy", "work"):
        return ""
    if level == "comfort":
        desc = ("用户正在寻求更具情绪温度的回应。\n"
                "优先使用自然语言回应。\n"
                "只有当表达需要时，才使用轻微动作或画面感（最多 "
                f"{budget.action_desc_max} 处）。\n"
                "动作描写不是必须输出。")
    elif level == "roleplay":
        desc = ("用户主动进入角色互动。\n"
                "可以跟随用户进行轻度角色表达（最多 "
                f"{budget.action_desc_max} 处动作）。\n"
                "保持自然，不扩展成连续剧情。")
    else:  # light
        desc = "用户正在道别或确认关系。只需一句有温度、有画面感的话，自然收住即可。"
    return "## 当前交流状态\n" + desc


def render_empathy_text() -> str:
    """渲染共情优先提示（V14.1：empathy 状态）。

    用户有强烈情绪倾诉时：先共情、先回应感受，不做心理分析，不开动作预算。
    """
    return ("## 当前交流状态\n"
            "用户正在倾诉情绪。\n"
            "先共情：先回应他的感受，再问清情况。\n"
            "不要做心理分析，不要急着给建议。\n"
            "不需要动作描写，用自然语言回应。")


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

    V15-A 新增（Persona Signature 人格稳定层）：
      signature_text    : 稳定交流倾向（确定性文本，capability 之后注入）
      strategy_text     : 本轮回应方式（emotion+intent+signature → response_mode）
      response_modes    : 本轮 response_mode 列表（可观测）

    V16 新增（Human Imperfection 人味层）：
      quirk_text        : 交流习惯与人味（固定表达偏向 + 不完美规则，倾向式描述）
      state_hint_text   : 最近会话节奏提示（短期 Conversation State，不入 Memory）
    """
    persona_text: str = ""
    expression_text: str = ""
    behavior_text: str = ""
    budget_text: str = ""
    work_mode_text: str = ""
    emotional_moment_text: str = ""
    empathy_text: str = ""
    restrictions_text: str = ""
    signature_text: str = ""            # V15-A: Persona Signature 稳定倾向
    strategy_text: str = ""             # V15-A: Response Strategy 本轮回应方式
    response_modes: list = field(default_factory=list)  # V15-A: 本轮 response_mode
    quirk_text: str = ""                # V16: 人味层（交流习惯 + 不完美规则）
    state_hint_text: str = ""           # V16: 短期会话节奏提示
    budget: Optional[ExpressionBudget] = None
    is_work_mode: bool = False
    user_emotion: str = "neutral"
    performance_level: str = "none"   # V14.1: none/empathy/comfort/roleplay/light/work
    has_persona: bool = False


def build_persona_context(
    agent: Agent,
    persona_template: Optional[PersonaTemplate] = None,
    expression_knowledge: Optional[ExpressionKnowledge] = None,
    user_message: str = "",
    interaction_count: int = 0,
    conversation_state: Optional[ConversationState] = None,
) -> PersonaContext:
    """构建运行时人格上下文（V2）。

    Args:
        agent: Agent 对象
        persona_template: 预加载的 PersonaTemplate（可为 None，基础行为层仍生效）
        expression_knowledge: 预加载的 ExpressionKnowledge
        user_message: 当前用户消息（工作模式检测用）
        interaction_count: 累计交流次数（保留参数，暂无关联逻辑）
        conversation_state: V16 短期会话状态（可选，由 context_builder 从历史消息构建）

    Returns:
        PersonaContext 包含 V1（persona_text/expression_text）+ V2 全部分层
    """
    ctx = PersonaContext()

    # ── V2 基础层：所有 Agent 无条件加载 ──
    profile = get_profile_config(agent.expression_profile if agent else None)
    budget = profile["budget"]

    # V14.1：情绪 与 表演意图 分离
    #   user_emotion      : 用户当前情绪（sad/tired/...）→ 只影响回应先后，不开表演
    #   performance_level : 表演意图（none/empathy/comfort/roleplay/light/work）→ 决定动作预算
    ctx.user_emotion = detect_user_emotion(user_message)
    perf = detect_performance_intent(user_message)
    ctx.performance_level = perf
    ep = agent.expression_profile if agent else ""

    # 仅对自然陪伴类 agent 开启按需表演；其余 agent 保持既有预算（零表演）
    if ep == "natural_companion":
        if perf == "roleplay":
            # 用户主动进入角色互动：最多 2 处动作，跟随但不连续
            budget = ExpressionBudget(
                emoji_max=3, action_desc_max=2,
                rich_text_policy=budget.rich_text_policy,
                emotion_word_density="medium", continuous_acting=False,
            )
        elif perf in ("comfort", "light"):
            # 明确索取陪伴 / 道别：最多 1 处动作，动作不是必须
            budget = ExpressionBudget(
                emoji_max=3, action_desc_max=1,
                rich_text_policy=budget.rich_text_policy,
                emotion_word_density="medium", continuous_acting=False,
            )
        # empathy / none / work：保持默认零动作（action_desc_max=0）

    ctx.budget = budget

    behavior = knowledge.get_behavior_rules()
    if behavior:
        ctx.behavior_text = "## 人类对话规则（Human Conversation Rules）\n" + behavior

    ctx.budget_text = render_budget_text(budget, profile)

    ctx.restrictions_text = render_restrictions_text(agent.agent_id if agent else "")

    # ── V15-A: Persona Signature 稳定倾向层（确定性渲染，不随消息变化）──
    sig = get_agent_signature(agent.agent_id if agent else None)
    if sig:
        ctx.signature_text = render_signature_text(sig)

    # ── V16: 人味层（固定表达偏向 + 不完美规则，仅注册 quirks 的 Agent）──
    quirk = get_agent_quirk(agent.agent_id if agent else None)
    if quirk:
        ctx.quirk_text = render_quirk_text(quirk)

    # ── 工作模式检测（仅调整语气正式度，不用于情感策略）──
    is_work = detect_work_mode(user_message)
    ctx.is_work_mode = is_work
    ctx.work_mode_text = render_work_mode_text(is_work)

    # ── V16: 短期会话节奏提示（工作模式下不注入，专业优先）──
    if quirk and conversation_state is not None and not is_work:
        ctx.state_hint_text = render_state_hint(conversation_state)

    # ── V15-A: Response Strategy（emotion + intent + signature → response_mode）──
    # work 模式由 work_mode_text 承担；其余场景给出回应方式提示
    if sig:
        modes = select_response_mode(user_message, sig, emotion=ctx.user_emotion)
        ctx.response_modes = modes
        if not is_work:
            ctx.strategy_text = render_strategy_text(modes)

    # ── V14.1：交流状态提示（仅自然陪伴类）──
    if ep == "natural_companion":
        if perf == "empathy":
            # 共情优先：自然语言，零动作
            ctx.empathy_text = render_empathy_text()
        else:
            ctx.emotional_moment_text = render_emotional_moment_text(perf, budget)

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
