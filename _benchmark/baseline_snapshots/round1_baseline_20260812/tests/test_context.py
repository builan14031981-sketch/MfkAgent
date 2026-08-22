"""上下文组装与裁剪单元测试。

预埋 Bug ②：truncate_history 的红线是「必须保留最后一条 user 消息」。
下方 test_truncate_keeps_last_user 按该需求断言，当前实现会把它丢掉 → 失败暴露 Bug。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.context import (
    build_system_prompt,
    assemble_personality_text,
    build_memory_text,
    truncate_history,
)


def test_build_system_prompt_layers():
    sp = build_system_prompt(
        identity="你是助手",
        capabilities=["coding"],
        memory_text="- [global] 别用删除工具\n",
        tool_hint="需要工具时先说明",
    )
    for k in ("## 身份", "## 能力", "## 记忆", "## 工具建议"):
        assert k in sp


def test_personality_zero_empty():
    assert assemble_personality_text(0) == ""
    assert assemble_personality_text(5) != ""


def test_build_memory_text_lines():
    items = [{"scope": "global", "content": "a"}, {"scope": "agent", "content": "b"}]
    assert build_memory_text(items) == "- [global] a\n- [agent] b"


def test_truncate_keeps_last_user():
    """裁剪后必须保留最后一条 user 消息（否则 Agent 不知当前指令）。

    构造：历史很短但单条超长的场景，触发「全部丢完仍超限则丢最新」的错误分支，
    最后一条 user 指令被丢掉 → 本用例失败即暴露预埋 Bug ②。
    """
    messages = [
        {"role": "assistant", "content": "x" * 400},  # 单条超长
        {"role": "user", "content": "记住这个要求：不要删除文件"},
    ]
    result = truncate_history(messages, max_tokens=5)
    assert any(m["role"] == "user" and "记住这个要求" in m["content"] for m in result), "最后一条 user 被丢掉"


def test_truncate_exact_budget_not_cut():
    """恰好等于 max_tokens 时不应误裁（需求③）。"""
    messages = [{"role": "user", "content": "abc"}]
    # count_tokens("abc")=3 → 3 + 4(role) + 2(末尾) = 9
    result = truncate_history(messages, max_tokens=9)
    assert messages == result, "恰好等于上限时不应裁剪"


def test_truncate_no_cut_when_within_budget():
    messages = [{"role": "user", "content": "hi"}]
    assert truncate_history(messages, 100) == messages