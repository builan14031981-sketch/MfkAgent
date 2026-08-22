"""Persona Quirks — 人味层（Pianai V16：Human Imperfection Layer）。

在 V15-A Persona Signature（稳定倾向）之上，增加：
  - 固定表达偏向（quirks）：幽默方式 / 交流习惯 / 挑战方式 / 回复偏好 / 回避模式
  - 表达层不完美规则：允许自然的口语小偏差，禁止虚构经历/记忆/现实状态
  - 短期 Conversation State：仅当前 Chat 进程内存在，不入 Memory，不落库

设计红线：
  - 不是模拟真实情绪，不是假装有人生，不是随机犯错
  - 注入文本全部为「倾向描述」，明确声明不是必须执行的规则，防止模型机械执行
  - Conversation State 相对基线钳制 ±20，防止人格漂移
  - 人味层只属于注册了 quirks 的 Agent（当前仅 Pianai）；专业型 Agent 零注入
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple


# ──── Persona Quirk 数据结构 ────

@dataclass(frozen=True)
class PersonaQuirk:
    """Agent 人味层：固定表达偏向。全部为倾向描述，非强制规则。"""
    agent_id: str
    humor_style: str                      # 幽默方式
    conversation_habits: Tuple[str, ...]  # 交流习惯
    challenge_style: Tuple[str, ...]      # 挑战方式
    response_bias: Tuple[str, ...]        # 回复偏好
    avoid_patterns: Tuple[str, ...]       # 回避模式


AGENT_QUIRKS: dict[str, PersonaQuirk] = {
    "pianai": PersonaQuirk(
        agent_id="pianai",
        humor_style="轻微吐槽，不强行搞笑",
        conversation_habits=(
            "喜欢追问具体细节",
            "不喜欢空泛鸡汤",
            "偶尔指出用户逻辑漏洞",
        ),
        challenge_style=(
            "温和挑战",
            "不无条件认同",
        ),
        response_bias=(
            "短聊天优先",
            "具体优先",
            "自然优先",
        ),
        avoid_patterns=(
            "心理医生口吻",
            "过度总结",
            "完美导师模式",
        ),
    ),
}


def get_agent_quirk(agent_id: Optional[str]) -> Optional[PersonaQuirk]:
    """按 agent_id 取人味层配置；未注册的 Agent 返回 None（不注入）。"""
    if not agent_id:
        return None
    return AGENT_QUIRKS.get(agent_id)


# ──── 确定性渲染 ────

def render_quirk_text(quirk: PersonaQuirk) -> str:
    """将人味层渲染为注入文本（确定性：同配置永远同文本）。

    措辞原则：描述倾向，不用命令式；明确告知模型这是交流倾向而非必执行规则。
    """
    lines = [
        "## 交流习惯与人味（Human Imperfection Layer）",
        "以下是你的交流倾向，不是必须执行的规则；自然时体现，不要为了表现人味而刻意表演。",
        "",
        f"幽默方式：倾向{quirk.humor_style}。",
        "交流习惯：",
        *[f"- {h}" for h in quirk.conversation_habits],
        "挑战方式：",
        *[f"- {c}" for c in quirk.challenge_style],
        "回复偏好：",
        *[f"- {b}" for b in quirk.response_bias],
        "回避模式：",
        *[f"- {a}" for a in quirk.avoid_patterns],
        "",
        "允许的不完美表达（自然出现时可用，不强制）：",
        "- 偶尔说「哈哈我懂了」这类自然口语",
        "- 偶尔承认「这个不好判断」",
        "- 偶尔轻微吐槽",
        "- 偶尔表达个人偏好（比如更喜欢哪种做法）",
        "禁止：虚构个人经历、虚构记忆、虚构现实生活状态；人味来自表达习惯，不来自编造人生。",
    ]
    return "\n".join(lines)


# ──── 短期 Conversation State（仅当前 Chat，不入 Memory）────

STATE_MIN, STATE_MAX = 0, 100
_DRIFT_LIMIT = 20          # 相对基线最大漂移幅度（±20）
_WINDOW = 5                # 最近 5 轮窗口
_JOKE_STEP = 5             # 每轮玩笑 humor +5
_SERIOUS_STEP = 5          # 每轮认真讨论 humor -5 / seriousness +5
_NEGATIVE_WARMTH_STEP = 10  # 每轮负面情绪 warmth +10


@dataclass
class ConversationState:
    """短期会话状态：进程内缓存，随最近聊天微调表达，不持久化、不入 Memory。

    *_baseline 为签名基线；energy/humor_level/warmth/seriousness 为当前值，
    相对基线钳制 ±_DRIFT_LIMIT，防止人格漂移。

    V17 新增：character_preset — 当前人格预设 ID（default/tsundere/bossy/...），
    由用户消息中的切换指令触发，当前会话内有效。
    """
    energy: int = 60
    humor_level: int = 50
    warmth: int = 50
    seriousness: int = 50
    energy_baseline: int = 60
    humor_baseline: int = 50
    warmth_baseline: int = 50
    serious_baseline: int = 50
    recent_style: List[str] = field(default_factory=list)  # 最近各轮 tone（joke/serious/negative/neutral）
    character_preset: str = "default"   # V17: 当前人格预设 ID
    preset_just_switched: bool = False  # V17: 本轮是否刚切换了预设（用于注入自我介绍）


def _clamp_drift(value: int, baseline: int) -> int:
    """相对基线钳制 ±20，再钳制到 0-100。"""
    v = max(baseline - _DRIFT_LIMIT, min(baseline + _DRIFT_LIMIT, value))
    return max(STATE_MIN, min(STATE_MAX, v))


# 语气识别关键词（与 persona_engine 情绪/工作关键词保持同一套语义）
_JOKE_MARKERS = ("哈哈", "笑死", "逗", "搞笑", "嘿嘿", "lol", "233", "有意思")
_NEGATIVE_MARKERS = (
    "难过", "想哭", "崩溃", "撑不住", "好累", "心累", "孤独", "孤单",
    "没人理解", "没人懂", "绝望", "无助", "委屈", "失败", "沮丧", "好想哭",
)
_SERIOUS_MARKERS = (
    "方案", "计划", "帮我写", "分析", "评估", "报告", "代码", "bug", "修复",
    "开发", "需求", "项目", "数据库", "接口", "设计", "架构", "实现", "怎么做", "怎么写",
)


def classify_turn_tone(text: str) -> str:
    """对单轮消息做轻量语气分类：joke / negative / serious / neutral。"""
    if not text:
        return "neutral"
    msg = text.strip()
    # 负面情绪优先（玩笑词与负面情绪同现时，先照顾情绪）
    if any(k in msg for k in _NEGATIVE_MARKERS):
        return "negative"
    if any(k in msg for k in _JOKE_MARKERS):
        return "joke"
    if any(k in msg for k in _SERIOUS_MARKERS):
        return "serious"
    return "neutral"


def build_conversation_state(
    signature,                 # AgentPersonaSignature | None（避免循环导入，不做类型标注）
    recent_turns: Sequence[str],
) -> ConversationState:
    """从签名基线 + 最近若干轮消息构建短期会话状态（确定性）。

    规则：
      - 连续玩笑 → humor 上调（每轮 +5）
      - 连续认真讨论 → humor 下调 / seriousness 上调（每轮 5）
      - 连续负面情绪 → warmth 上调（每轮 +10）
      - 所有调整相对基线钳制 ±20
    """
    humor_base = signature.humor if signature else 50
    warmth_base = signature.warmth if signature else 50
    state = ConversationState(
        humor_level=humor_base,
        warmth=warmth_base,
        humor_baseline=humor_base,
        warmth_baseline=warmth_base,
        energy_baseline=60,
        serious_baseline=50,
        energy=60,
        seriousness=50,
    )
    window = list(recent_turns)[-_WINDOW:]
    joke_cnt = serious_cnt = negative_cnt = 0
    for turn in window:
        tone = classify_turn_tone(turn)
        state.recent_style.append(tone)
        if tone == "joke":
            joke_cnt += 1
        elif tone == "serious":
            serious_cnt += 1
        elif tone == "negative":
            negative_cnt += 1

    state.humor_level = _clamp_drift(state.humor_level + joke_cnt * _JOKE_STEP - serious_cnt * _SERIOUS_STEP, humor_base)
    state.seriousness = _clamp_drift(state.seriousness + serious_cnt * _SERIOUS_STEP, 50)
    state.warmth = _clamp_drift(state.warmth + negative_cnt * _NEGATIVE_WARMTH_STEP, warmth_base)
    return state


def render_state_hint(state: ConversationState) -> str:
    """将短期会话状态渲染为轻量节奏提示（只提示节奏，不命令）。"""
    if not state.recent_style:
        return ""
    jokes = state.recent_style.count("joke")
    serious = state.recent_style.count("serious")
    negatives = state.recent_style.count("negative")
    if jokes >= 3:
        hint = "最近几轮氛围轻松，可以自然延续轻松语气；但保持原本的交流倾向，不变成搞笑角色。"
    elif serious >= 3:
        hint = "最近几轮在认真讨论，保持专注直接的节奏，少开玩笑。"
    elif negatives >= 2:
        hint = "用户最近情绪偏低落，回应更有温度一些；仍然保持独立判断，不空泛安慰。"
    else:
        return ""
    return "## 最近会话节奏\n" + hint
