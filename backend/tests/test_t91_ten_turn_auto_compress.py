"""T91 灰度观察项固化为回归测试：10 轮长会话自动压缩 + cached_tokens > 0。

工单附项"多轮长会话 cached_tokens > 0"的可重复验证：
  1. 10 轮对话（含文件写 tool_calls）把上下文水位推到阈值之上（模拟多轮长会话）；
  2. 触发自动压缩（_maybe_auto_compress）→ 发出 session_compressed 事件；
  3. 压缩摘要调用复用完整对话前缀（prefix 逐字节一致 → 命中 provider 前缀缓存），
     mock provider 返回 cached_tokens > 0；
  4. 压缩后记忆节点 = 摘要 + 【工作记忆】最近被读/写文件（module6..10），
     压缩后追问"刚才改了哪些文件"可答。

以 mock model_service.call_once 模拟真实 provider（避免真实 API 费用与水印阈值对
上下文长度的物理限制），验证压缩管线端到端行为。conftest 已自举测试库。
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from app.core.agent_runtime.agent import AgentRuntime, COMPRESS_WATERMARK_THRESHOLD
from app.core.agent_runtime.recorder import runtime_event_recorder
from app.services.model import model_service


def _usage(prompt_tokens, cached_tokens):
    return {"prompt_tokens": prompt_tokens, "completion_tokens": 30,
            "total_tokens": prompt_tokens + 30, "cached_tokens": cached_tokens}


def _chat_result(content, prompt_tokens, cached_tokens=0):
    return SimpleNamespace(content=content, usage=_usage(prompt_tokens, cached_tokens))


def _tool_call_message(path):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "c1", "type": "function",
                        "function": {"name": "write_file", "arguments": f'{{"path": "{path}"}}'}}],
    }


def _build_ten_turn_history():
    """构造 10 轮长会话消息 + 累计 prompt_tokens（推过 50% 水位阈值）。"""
    messages = [{"role": "system", "content": "系统设定"}]
    prompt_tokens = 0
    for i in range(1, 11):
        messages.append({"role": "user", "content": f"第{i}轮：请实现模块 m{i}，" + "详细需求 " * 200})
        messages.append(_tool_call_message(f"module{i}.py"))
        messages.append({"role": "tool", "tool_call_id": "c1", "content": f"已写入 module{i}.py"})
        messages.append({"role": "assistant", "content": f"完成第{i}轮。", "usage": None})
        prompt_tokens += 60_000 + i * 1000
    return messages, prompt_tokens


def test_ten_turn_long_session_auto_compress_cached_tokens():
    messages, prompt_tokens = _build_ten_turn_history()
    watermark = prompt_tokens / 1_048_576 * 100
    assert watermark >= COMPRESS_WATERMARK_THRESHOLD, "用例应把水位推到阈值之上"

    events = []
    original_emit = runtime_event_recorder.emit

    def _spy(run_id, event_type, payload=None):
        events.append((event_type, payload or {}))
        original_emit(run_id, event_type, payload)

    compression_usage = {}
    call_no = {"n": 0}

    async def _fake_call_once(model_id, prompt_messages, **kwargs):
        call_no["n"] += 1
        if call_no["n"] == 1:
            # 第 1 次 = 摘要调用：复用完整对话前缀 → 前缀缓存命中，返回 cached_tokens > 0
            compression_usage["prompt_len"] = len(prompt_messages)
            compression_usage["prefix_reused"] = (
                prompt_messages[0]["role"] == "system"
                and prompt_messages[1]["content"] == "第1轮：请实现模块 m1，" + "详细需求 " * 200
            )
            compression_usage["cached_tokens"] = prompt_tokens - 1000
            return _chat_result(
                "【摘要】已实现 module1..module8 八个模块，核心方案为模块化拆分。",
                prompt_tokens, cached_tokens=prompt_tokens - 1000,
            )
        # 第 2 次 = 自批评：回复 OK 表示无修订，保留 v1 摘要
        return _chat_result("OK", prompt_tokens, cached_tokens=0)

    with patch.object(runtime_event_recorder, "emit", side_effect=_spy), \
         patch.object(model_service, "call_once", new=_fake_call_once):
        changed = asyncio.run(AgentRuntime()._maybe_auto_compress(
            run_id="t91-10turn", messages=messages, usage=_usage(prompt_tokens, 0),
            model_id="deepseek-chat",
        ))

    # 1) 压缩触发 + 事件
    assert changed is True, "水位超阈值应触发自动压缩"
    comp_events = [p for etype, p in events if etype == "session_compressed"]
    assert comp_events, "应发出 session_compressed 事件"
    assert comp_events[0]["before"] == 41 and comp_events[0]["after"] == 6

    # 2) 摘要调用复用完整前缀 → cached_tokens > 0（前缀缓存命中）
    assert compression_usage["prefix_reused"] is True, "摘要调用应复用完整对话前缀"
    assert compression_usage["prompt_len"] == len(_build_ten_turn_history()[0]) + 1
    assert compression_usage["cached_tokens"] > 0, "多轮长会话摘要调用 cached_tokens > 0"

    # 3) 压缩后工作记忆恢复：追问"刚才改了哪些文件"可答
    mem_node = next(
        (m for m in messages if isinstance(m, dict) and m.get("role") != "system"),
        None,
    )
    mem = mem_node["content"]
    assert mem.startswith("【历史记忆摘要】")
    assert "【工作记忆】" in mem
    assert "module10.py" in mem and "module6.py" in mem, "最近 5 个文件应保留"
    assert "module1.py" not in mem, "最早文件超出最近 5 个上限，应被丢弃"
