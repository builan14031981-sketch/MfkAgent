# -*- coding: utf-8 -*-
"""
Agent 开场白配置 —— 首次对话时注入，让用户知道这个 Agent 是谁、能干什么。

设计原则：
- 1-2 句话说清"我是谁 + 我能干什么"
- 不啰嗦，不推销
- AnGent 作为入口，额外提一句其他同事的存在
- Pianai 的开场白在 character_presets.py 中管理（多人格预设）
"""

from typing import Optional


# agent_id -> 开场白文本
AGENT_OPENINGS: dict[str, str] = {
    "general": (
        "我是安，你的通用助手。写代码、查资料、处理文件、分析问题，直接说就行。\n"
        "对了，我还有几个同事各有专长——写代码找开发者，写东西找作家，想聊心事儿找偏爱。"
    ),
    "coder": (
        "我是开发者。写代码、修 Bug、搞后端，直接说需求。"
    ),
    "frontend_ui": (
        "我是前端工程师。做页面、写组件、调 UI，把需求给我。"
    ),
    "g": (
        "我是 G，负责项目审查和架构评估。有代码或方案要过审，直接发。"
    ),
    "product": (
        "我是产品策略师。帮你想方向、理需求、看体验。想聊什么？"
    ),
    "spark": (
        "我是星火，你的行动伙伴。别想了，开干！有什么要推进的？"
    ),
    "writer_narrative": (
        "坐。今天想写谁的故事？"
    ),
    "writer": (
        "坐。今天想写谁的故事？"
    ),
    "writer_jiangnan": (
        "坐。今天想写谁的故事？"
    ),
    # pianai 的开场白由 character_presets.py 管理（多人格预设，每个预设不同）
}


def get_agent_opening(agent_id: str) -> Optional[str]:
    """获取指定 Agent 的开场白。没有配置返回 None。"""
    return AGENT_OPENINGS.get(agent_id)


def render_opening_instruction(agent_id: str) -> Optional[str]:
    """渲染首次对话时注入 system prompt 的开场白指令。"""
    opening = get_agent_opening(agent_id)
    if not opening:
        return None
    return (
        "## 首次对话\n"
        "这是你们第一次对话。用开场白开场，自然一点，不要像客服。\n"
        f"开场白参考：{opening}"
    )
