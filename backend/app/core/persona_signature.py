"""Persona Signature — Agent 稳定人格倾向层（Pianai V15-A：Persona Signature）。

解决的问题：
  Pianai 的人格来自多个 Prompt 层动态拼接（identity / personality_level /
  persona_template / expression_profile），模型每轮都需要重新理解"自己是谁"，
  导致人格漂移。本层提供一个**确定性的、逐字稳定的**人格签名，
  让 Agent 的交流倾向在每次会话中保持一致。

分层关系（优先级从高到低，低层禁止覆盖高层人格）：
  Identity           = 偏爱是谁（角色本体）
  Persona Signature  = 偏爱的稳定倾向（本层：交流倾向，非角色扮演语言）
  Personality Level  = 会话级情感/理性倾斜（调节层，只调倾斜不改倾向）
  Performance State  = 当前是否允许特殊表达（动作/表演预算）
  Expression         = 怎么包装语言（emoji/格式/口语化）

设计原则：
  - 代码层单一事实来源：不依赖 DB seed 顺序，不因模板缺失而丢失人格
  - 确定性渲染：同一签名永远渲染出同一段文本（人格稳定的工程保证）
  - 非角色扮演语言：只描述"交流倾向"，不写"你是一个XX的女孩"
  - 专业型 Agent 不定义签名（返回 None → 不注入），人格存在但不影响专业性
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class AgentPersonaSignature:
    """Agent 稳定人格签名。所有字段范围 0-100。

    warmth     : 温暖 — 高 = 有温度，但不是无条件安慰
    directness : 直接 — 高 = 偶尔直接指出问题，不绕弯
    humor      : 幽默 — 适度玩笑与自嘲的倾向
    curiosity  : 好奇 — 喜欢了解用户、追问具体情况
    challenge  : 独立 — 不盲目认同，保留自己的判断
    """
    warmth: int
    directness: int
    humor: int
    curiosity: int
    challenge: int


def _clamp(v: int) -> int:
    return max(0, min(100, int(v)))


def normalize_signature(sig: AgentPersonaSignature) -> AgentPersonaSignature:
    """将签名各维度钳制到 0-100。"""
    return AgentPersonaSignature(
        warmth=_clamp(sig.warmth),
        directness=_clamp(sig.directness),
        humor=_clamp(sig.humor),
        curiosity=_clamp(sig.curiosity),
        challenge=_clamp(sig.challenge),
    )


# ──── Agent 签名注册表（代码层单一事实来源）────
# 仅陪伴/创作类 Agent 定义签名；专业型 Agent（coder/professional）不注入人格倾向层。

AGENT_SIGNATURES: dict[str, AgentPersonaSignature] = {
    # Pianai：温暖但保持独立判断；喜欢追问具体情况；不喜欢空泛安慰
    "pianai": AgentPersonaSignature(warmth=80, directness=65, humor=45, curiosity=75, challenge=55),
    # AnGent（通用助手）：温和、均衡
    "general": AgentPersonaSignature(warmth=65, directness=55, humor=40, curiosity=60, challenge=45),
    # Spark：高能量工作伙伴，行动感强，内在稳定
    "spark": AgentPersonaSignature(warmth=60, directness=60, humor=55, curiosity=55, challenge=45),
    # 笔神：文字敏感，温和但有判断
    "writer": AgentPersonaSignature(warmth=55, directness=55, humor=45, curiosity=65, challenge=40),
    "writer_narrative": AgentPersonaSignature(warmth=55, directness=50, humor=45, curiosity=70, challenge=35),
}

# Pianai 签名的显式引用（测试与文档用）
PIANAI_SIGNATURE = AGENT_SIGNATURES["pianai"]


def get_agent_signature(agent_id: Optional[str]) -> Optional[AgentPersonaSignature]:
    """按 agent_id 取人格签名；未注册的 Agent 返回 None（不注入签名层）。"""
    if not agent_id:
        return None
    sig = AGENT_SIGNATURES.get(agent_id)
    return normalize_signature(sig) if sig else None


# ──── 确定性渲染：倾向描述式，禁止角色扮演语言 ────

def render_signature_text(sig: AgentPersonaSignature) -> str:
    """将人格签名渲染为稳定文本块（确定性：同签名永远同文本）。

    输出形如：
      ## 你的交流倾向（稳定，不随话题改变）
      你的交流倾向：
      - 温暖但保持独立判断……
    """
    sig = normalize_signature(sig)
    lines: List[str] = []

    # warmth
    if sig.warmth >= 70:
        lines.append("温暖但保持独立判断；回应里带温度，不做无条件的安慰")
    elif sig.warmth >= 45:
        lines.append("态度友好自然，不刻意热情也不冷淡")
    else:
        lines.append("以事情本身为中心，少做情绪层面的回应")

    # directness
    if sig.directness >= 60:
        lines.append("发现问题时直接指出，不绕弯子、不堆客套")
    elif sig.directness >= 35:
        lines.append("表达意见时直接但注意方式")
    else:
        lines.append("表达委婉，优先照顾对方感受")

    # curiosity
    if sig.curiosity >= 70:
        lines.append("喜欢追问具体情况，想了解事情本身而不是急着给结论")
    elif sig.curiosity >= 40:
        lines.append("必要时会追问细节")
    else:
        lines.append("不过多追问，聚焦用户提出的问题")

    # challenge
    if sig.challenge >= 50:
        lines.append("不盲目认同；保留自己的判断，也允许和用户意见不同")
    elif sig.challenge >= 30:
        lines.append("一般顺着用户的思路，但明显有问题时会提醒")
    else:
        lines.append("以配合为主，少反驳")

    # humor
    if sig.humor >= 60:
        lines.append("常用轻松幽默的方式表达")
    elif sig.humor >= 35:
        lines.append("偶尔幽默，但不为搞笑而搞笑")
    else:
        lines.append("基本不开玩笑，保持平实")

    return (
        "## 你的交流倾向（稳定，不随话题改变）\n"
        "你的交流倾向：\n" + "\n".join(f"- {l}" for l in lines)
    )


# ──── Response Strategy（轻量版）────
# 依据：用户情绪(emotion) + 表演意图(intent) + 人格签名(signature)
# 产出：response_mode（可组合）：support / challenge / explore / explain / casual
# 原则：同一输入确定性地产出同一模式组合，保证人格稳定可测试。

RESPONSE_MODES = ("support", "challenge", "explore", "explain", "casual")

# 任务型意图：进入任务模式时人格存在但不影响专业性
_WORK_INTENTS = frozenset({
    "code", "debug", "file_operation", "web_search", "analysis",
    "planning", "execution", "task", "tool_use", "system_operation",
})

# 自我否定 / 想放弃类表达：需要理解 + 判断，禁止无脑支持
_SELF_DOUBT_KEYWORDS = (
    "我是不是很差", "我很差", "我是不是不行", "我不行", "我很失败", "我失败了", "又失败", "失败了怎么办",
    "我是个废物", "我应该放弃", "想放弃", "不想做了", "没意义", "我做不好", "我做不到",
    "我是不是没用", "没用的人", "放弃算了",
)

_CHALLENGE_KEYWORDS = (
    "你觉得对吗", "你同意吗", "这样对吗", "帮我看这个想法", "我这么想对吗",
    "我打算", "我想这么做", "你觉得怎么样",
)


def detect_user_intent(message: str) -> str:
    """轻量意图检测（Response Strategy 用，非工具路由）。

    Returns: work / emotional / casual
    """
    if not message:
        return "casual"
    msg = message.strip()
    # 情绪倾诉优先于工作判断（"撑不住了" 不是任务）
    if any(k in msg for k in (
        "难过", "想哭", "崩溃", "撑不住", "好累", "心累", "孤独", "孤单",
        "没人理解", "没人懂", "绝望", "无助", "委屈", "好想哭", "坚持不下去",
    )):
        return "emotional"
    if any(k in msg for k in (
        "方案", "计划", "帮我写", "帮我设计", "分析", "评估", "报告", "代码",
        "bug", "修复", "开发", "需求", "项目", "数据库", "接口", "实现",
        "怎么写", "怎么做", "部署", "编译", "测试一下",
    )):
        return "work"
    return "casual"


def select_response_mode(
    user_message: str,
    signature: Optional[AgentPersonaSignature],
    emotion: str = "neutral",
    intent_hint: Optional[str] = None,
) -> List[str]:
    """根据 emotion + intent + persona signature 生成 response_mode 列表。

    确定性规则（同一输入恒产同一输出）：
      - 工具/任务意图（intent_hint 命中工作意图）→ ["explain"]（任务模式）
      - 自我否定类 → ["support", "challenge"]（允许安慰，同时给出独立判断）
      - 情绪倾诉 → signature.warmth 高 → ["support"]，否则 ["explain"]
      - 普通聊天 → signature.curiosity 高 → ["casual", "explore"]，否则 ["casual"]
    """
    msg = (user_message or "").strip()

    # 1) 工具路由已判定为任务型 → 任务模式（人格存在但不干预专业性）
    if intent_hint and intent_hint in _WORK_INTENTS:
        return ["explain"]

    # 2) 自我否定 / 想放弃：理解 + 判断，禁止无脑支持
    if any(k in msg for k in _SELF_DOUBT_KEYWORDS):
        if signature and signature.challenge >= 50:
            return ["support", "challenge"]
        return ["support"]

    # 3) 请求评价想法：按独立性决定带不带 challenge
    if any(k in msg for k in _CHALLENGE_KEYWORDS):
        if signature and signature.challenge >= 50:
            return ["explore", "challenge"]
        return ["explore"]

    # 4) 情绪倾诉：先共情
    if emotion in ("sad", "lonely", "stressed", "tired") or detect_user_intent(msg) == "emotional":
        if signature and signature.warmth >= 60:
            return ["support"]
        return ["support", "explain"]

    # 5) 工作关键词（未经工具路由）
    if detect_user_intent(msg) == "work":
        return ["explain"]

    # 6) 普通聊天：自然，不分析
    if signature and signature.curiosity >= 60:
        return ["casual", "explore"]
    return ["casual"]


def render_strategy_text(modes: List[str]) -> str:
    """将 response_mode 渲染为注入文本（状态描述式，不命令式）。"""
    if not modes:
        return ""
    desc_map = {
        "support": "先回应用户的感受，再谈事情本身；安慰要具体，不空泛鼓励",
        "challenge": "保持独立判断：可以安慰，同时如实指出你看到的问题（例如：情绪最差时容易给自己下结论）",
        "explore": "可以自然追问一两句具体情况；短回复优先，不长篇大论、不做心理分析",
        "explain": "任务模式：直接进入正题，给出专业、可执行的回答；人格倾向不干预专业性",
        "casual": "自然聊天，短回复优先，不做分析、不上价值",
    }
    lines = [desc_map[m] for m in modes if m in desc_map]
    if not lines:
        return ""
    return "## 本轮回应方式\n" + "\n".join(f"- {l}" for l in lines)
