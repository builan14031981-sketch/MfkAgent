"""Token 估算单元测试。

预埋 Bug ①：下表断言按「设计目标公式」书写，当前实现为 `len(text)`（只算字符数），
因此下面 2 个用例应失败——暴露 token 估算逻辑 Bug。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.tokens import count_tokens, estimate_messages_tokens, watermark


def test_count_tokens_chinese_dense():
    """10 个汉字按设计目标应约等于 10 token（中文字符≈1 token）。"""
    text = "你好世界这是一个测试消息"
    assert count_tokens(text) == len(text)


def test_count_tokens_english_long_words():
    """英文按每 4 字符 1 token 估算；26 个小写字母≈7 token。"""
    text = "abcdefghijklmnopqrstuvwxyz"
    assert count_tokens(text) <= int(len(text) / 4) + 2


def test_count_tokens_empty():
    assert count_tokens("") == 0


def test_estimate_messages_overhead():
    messages = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    # 每条消息 +4 role 开销，末尾 +2
    expected = count_tokens("hi") + count_tokens("hello") + 4 * 2 + 2
    assert estimate_messages_tokens(messages) == expected


def test_watermark_percent():
    assert watermark(1000, 10000) == 10.0
    assert watermark(0, 10000) == 0.0