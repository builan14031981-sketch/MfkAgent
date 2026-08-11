"""Persona Knowledge 加载器 — 把表达知识从 Prompt 拆到 md 文件，按 Agent 类型按需加载。

设计原则：
  - 知识文件是「知识源」，运行时由 persona_engine 按需加载，不全部塞进 system prompt
  - 所有 Agent 默认加载 behavior/（Human Conversation + Anti-AI）
  - profiles/ 按 Agent 的 expression_profile 类型加载（companion / professional / coder / creative）
  - expression/ 由预算渲染逻辑引用（emoji / 网络语言 / 排版 / 情绪表达）
  - 文件读取失败返回空串，绝不影响主链路
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

PERSONA_DIR = Path(__file__).resolve().parent

# 支持的 profile 类型（与 Agent.expression_profile 取值对齐）
PROFILE_NAMES = ("companion", "professional", "coder", "creative")

# 表达知识分节（expression/ 目录下文件名）
EXPRESSION_SECTIONS = ("emoji", "internet_language", "typography", "emotional_expression")


@lru_cache(maxsize=32)
def load_md(relative_path: str) -> str:
    """读取 persona 知识 md 文件（UTF-8）。失败返回空串并告警。"""
    path = PERSONA_DIR / relative_path
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        logger.warning("persona knowledge load failed: %s (%s)", relative_path, exc)
        return ""


def get_profile_text(style: str | None) -> str:
    """按 Agent 类型加载 profiles/ 知识文本。未知类型返回空串。"""
    if not style or style not in PROFILE_NAMES:
        return ""
    return load_md(f"profiles/{style}.md")


def get_behavior_rules() -> str:
    """加载所有 Agent 默认行为规则（Human Conversation + Anti-AI）。"""
    parts = [
        load_md("behavior/human_conversation.md"),
        load_md("behavior/anti_ai.md"),
    ]
    return "\n\n".join(p for p in parts if p)


def get_expression_section(section: str) -> str:
    """加载 expression/ 单节知识（emoji / internet_language / typography / emotional_expression）。"""
    if section not in EXPRESSION_SECTIONS:
        return ""
    return load_md(f"expression/{section}.md")


def get_expression_bundle() -> str:
    """加载全部表达知识分节（预算指令渲染时引用关键规则）。"""
    parts = [get_expression_section(s) for s in EXPRESSION_SECTIONS]
    return "\n\n".join(p for p in parts if p)
