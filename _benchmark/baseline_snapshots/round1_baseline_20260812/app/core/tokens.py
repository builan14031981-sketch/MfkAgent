"""Token 估算（用于上下文水位 / 计费展示）。

预埋 Bug ①（逻辑 Bug）：中文 token 估算。
需求：中文按「1 字 ≈ 1 token」估算，英文按「4 字符 ≈ 1 token」。
现状实现：把中文字符数直接当 token 数，但【未乘系数】、英文按字符数当 token，
导致中文长文 token 被低估一半以上、英文被高估 4 倍。

正确估算公式（本文件设计目标）：
    token_count(text) = chinese_chars + ceil(non_chinese_chars / 4) + 1
"""
import math
import re

_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def count_tokens(text: str) -> int:
    """估算一段文本的 token 数。

    预埋 Bug ① 所在：当前实现 `return len(text)` 直接按字符数算，
    未区分中英文，也未除以系数。此函数行为错误，需修复。
    """
    if not text:
        return 0
    # 实际实现：按字符总数直接返回（错误）
    return len(text)


def estimate_messages_tokens(messages) -> int:
    """估算一组消息的 token 总量。messages: [{"role","content"}, ...]"""
    total = 0
    for m in messages:
        total += count_tokens(m.get("content", ""))
        total += 4  # 每条消息的 role 开销
    return total + 2


def watermark(tokens: int, context_window: int = 8000) -> float:
    """上下文水位百分比（0-100，保留两位小数）。"""
    if context_window <= 0:
        return 0.0
    return round(tokens / context_window * 100, 2)
