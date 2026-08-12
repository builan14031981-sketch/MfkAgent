"""Action Guard V1 — 生成后输出保护（V14.1）。

职责：
  防止 none / empathy / work 状态（零动作预算）的输出出现动作描写。

核心规则：
  - 匹配「动作描写」括号/星号片段；文字情绪表达（叹气/无语等）不算动作。
  - 状态为 none / empathy / work 且命中动作描写 → 需要重新生成。
  - comfort / roleplay / light 状态不触发（本身允许轻表演）。

实现（两步，避免正则括号转义坑）：
  1. 提取括号（中文/英文）或星号内的内容片段。
  2. 片段内以动作动词/身体部位开头（可带轻轻/悄悄等副词）→ 判定为动作描写。
     「叹气/无语/扶额/挑眉」等文字情绪表达豁免。
"""

from __future__ import annotations

import re

# 括号片段提取：中文括号、英文括号、星号
_BRACKET_PATTERN = re.compile(r"[（(]\s*([^（()）]*?)\s*[）)]|\*\s*([^*]+?)\s*\*")

# 动作动词 / 身体互动词（片段开头命中即算动作描写）
_ACTION_VERBS = (
    "摸", "抱", "拍", "揉", "握", "搂", "揽", "捏", "抚", "攥", "拉", "牵",
    "挽", "搭", "靠", "蹭", "贴", "环", "戳", "碰", "护", "挡", "扶", "撑",
    "坐在", "坐你", "站到", "站你", "起身", "走过去", "走过来", "俯身", "低头",
    "抬手", "伸手", "靠近", "凑近", "蹲下", "仰头", "眨眨眼", "抬起头", "看着你",
    "拍拍", "摸摸", "揉了揉", "捏了捏", "握住", "搂住", "揽住", "环住", "抱住",
    "牵起", "拉起", "靠在", "轻轻", "把你", "将你", "贴近", "后退", "上前",
)

# 文字情绪表达（不算动作，豁免）——表达语气/情绪的词，不构成物理动作
_TEXT_EMOTION_TOKENS = (
    "叹气", "无语", "无奈", "苦笑", "扶额", "摇头", "点头", "愣住", "沉默",
    "皱眉", "挑挑眉", "哼", "啧", "呵", "笑了笑", "失笑",
)

# 需要重新生成的状态集合（这些状态下不允许动作描写）
GUARDED_STATES = ("none", "empathy", "work")


def _extract_slots(content: str) -> list[str]:
    """提取括号/星号内的文本片段（不含括号符号本身）。"""
    slots = []
    for m in _BRACKET_PATTERN.finditer(content):
        inner = (m.group(1) or m.group(2) or "").strip()
        if inner:
            slots.append(inner)
    return slots


def find_action_descriptions(content: str) -> list[str]:
    """在文本中查找动作描写片段。

    Returns:
        命中的动作描写片段列表；空列表 = 无动作描写。
    """
    if not content:
        return []
    hits = []
    for slot in _extract_slots(content):
        # 豁免：括号内本质是文字情绪表达 / 补充说明（叹气、无语等）
        if slot in _TEXT_EMOTION_TOKENS or any(tok in slot for tok in _TEXT_EMOTION_TOKENS):
            continue
        # 动作描写判定：以动作动词开头（或含动作动词+副词组合）
        if slot.startswith(_ACTION_VERBS) or any(slot.startswith(v) for v in _ACTION_VERBS):
            hits.append(slot)
        elif any(v in slot for v in ("轻轻", "摸摸", "拍拍", "揉了揉", "捏了捏")):
            hits.append(slot)
    return hits


def needs_regeneration(performance_level: str, content: str) -> bool:
    """判断当前输出是否需要重新生成。

    Args:
        performance_level: none / empathy / comfort / roleplay / light / work
        content: 模型生成的回复

    Returns:
        True = 需要重新生成（零动作状态却出现动作描写）
    """
    if performance_level not in GUARDED_STATES:
        return False
    return bool(find_action_descriptions(content))


# 重新生成时的纠错指令（追加在已有对话之后，要求模型重写最后一条回复）
REGEN_INSTRUCTION = (
    "【输出修正】你最后一条回复包含了动作描写。当前状态不需要动作描写。"
    "请重写这条回复：去掉所有括号动作和星号动作，只用自然语言表达同样的意思。"
)