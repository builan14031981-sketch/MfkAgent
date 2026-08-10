"""Phase 12 — 推理档位映射统一与 reasoning_content 双轨透传 单元测试

测试场景：
  1. _apply_reasoning_payload — 各 Provider 的 reasoning_effort 参数映射
  2. _apply_reasoning_payload — reasoning_effort=none 时剥离推理参数
  3. _apply_reasoning_payload — 不支持的 Provider 不发送推理参数
  4. stream_once — reasoning_content 多字段兼容提取
  5. stream_once — reasoning_content 通过 type:thinking 独立下发
  6. stream_once — reasoning_content 不与 content 混淆
  7. 向后兼容：旧客户端忽略 thinking 字段不崩溃
"""

import sys
import os
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.model import ModelService, ModelProvider, ModelConfig


# ══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════════════════════════════

def make_config(provider: ModelProvider, model_name: str = "test-model") -> ModelConfig:
    """构造测试用 ModelConfig"""
    return ModelConfig(
        provider=provider,
        model_name=model_name,
        api_key="test-key",
        api_base="https://test.api/v1",
        max_tokens=4096,
        temperature=0.7,
    )


def _payload_has_thinking_disabled(payload: dict) -> bool:
    """检查 payload 中 thinking 是否被禁用"""
    thinking = payload.get("thinking", {})
    return thinking.get("type") == "disabled"


def _payload_has_thinking_enabled(payload: dict) -> bool:
    """检查 payload 中 thinking 是否被启用"""
    thinking = payload.get("thinking", {})
    return thinking.get("type") == "enabled"


def _payload_has_no_reasoning_field(payload: dict) -> bool:
    """检查 payload 中是否没有任何推理相关字段"""
    return (
        "thinking" not in payload
        and "reasoning_effort" not in payload
        and "enable_thinking" not in payload
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: _apply_reasoning_payload — 各 Provider 的 reasoning_effort 映射
# ══════════════════════════════════════════════════════════════════════════════

class TestApplyReasoningPayload:
    """测试 _apply_reasoning_payload 对各个 Provider 的参数映射"""

    def test_deepseek_none_disables_thinking(self):
        """DeepSeek reasoning_effort=none → thinking.type=disabled"""
        svc = ModelService()
        config = make_config(ModelProvider.DEEPSEEK, "deepseek-v4-pro")
        payload = {}
        svc._apply_reasoning_payload(payload, config, "none")
        assert _payload_has_thinking_disabled(payload), (
            f"DeepSeek none 应发送 thinking.type=disabled，实际 payload={payload}"
        )
        assert "reasoning_effort" not in payload.get("thinking", {}), (
            "none 档位不应携带 reasoning_effort 值"
        )

    def test_deepseek_high_enables_thinking(self):
        """DeepSeek reasoning_effort=high → thinking.type=enabled + reasoning_effort=high"""
        svc = ModelService()
        config = make_config(ModelProvider.DEEPSEEK, "deepseek-v4-pro")
        payload = {}
        svc._apply_reasoning_payload(payload, config, "high")
        assert _payload_has_thinking_enabled(payload)
        assert payload["thinking"]["reasoning_effort"] == "high"

    def test_deepseek_max_enables_thinking(self):
        """DeepSeek reasoning_effort=max → thinking.type=enabled + reasoning_effort=max"""
        svc = ModelService()
        config = make_config(ModelProvider.DEEPSEEK, "deepseek-v4-pro")
        payload = {}
        svc._apply_reasoning_payload(payload, config, "max")
        assert _payload_has_thinking_enabled(payload)
        assert payload["thinking"]["reasoning_effort"] == "max"

    def test_siliconflow_none_disables_thinking(self):
        """SiliconFlow reasoning_effort=none → thinking.type=disabled"""
        svc = ModelService()
        config = make_config(ModelProvider.SILICONFLOW, "deepseek-ai/DeepSeek-V4-Pro")
        payload = {}
        svc._apply_reasoning_payload(payload, config, "none")
        assert _payload_has_thinking_disabled(payload), (
            f"SiliconFlow none 应发送 thinking.type=disabled，实际 payload={payload}"
        )

    def test_siliconflow_high_enables_thinking(self):
        """SiliconFlow reasoning_effort=high → thinking.type=enabled + reasoning_effort=high"""
        svc = ModelService()
        config = make_config(ModelProvider.SILICONFLOW, "deepseek-ai/DeepSeek-V4-Pro")
        payload = {}
        svc._apply_reasoning_payload(payload, config, "high")
        assert _payload_has_thinking_enabled(payload)
        assert payload["thinking"]["reasoning_effort"] == "high"

    def test_glm_none_disables_thinking(self):
        """GLM reasoning_effort=none → thinking.type=disabled"""
        svc = ModelService()
        config = make_config(ModelProvider.GLM, "glm-4")
        payload = {}
        svc._apply_reasoning_payload(payload, config, "none")
        assert _payload_has_thinking_disabled(payload), (
            f"GLM none 应发送 thinking.type=disabled，实际 payload={payload}"
        )
        # GLM 的 reasoning_effort 是顶层字段，none 时不应存在
        assert "reasoning_effort" not in payload, (
            "GLM none 档位不应在顶层携带 reasoning_effort"
        )

    def test_glm_high_enables_thinking(self):
        """GLM reasoning_effort=high → thinking.type=enabled + reasoning_effort"""
        svc = ModelService()
        config = make_config(ModelProvider.GLM, "glm-4")
        payload = {}
        svc._apply_reasoning_payload(payload, config, "high")
        assert _payload_has_thinking_enabled(payload)
        assert payload["reasoning_effort"] == "high"

    def test_qwen_none_disables_thinking(self):
        """QWEN reasoning_effort=none → enable_thinking=False"""
        svc = ModelService()
        config = make_config(ModelProvider.QWEN, "qwen-flash")
        payload = {}
        svc._apply_reasoning_payload(payload, config, "none")
        assert payload.get("enable_thinking") is False, (
            f"QWEN none 应设置 enable_thinking=False，实际 payload={payload}"
        )

    def test_qwen_high_enables_thinking(self):
        """QWEN reasoning_effort=high → enable_thinking=True"""
        svc = ModelService()
        config = make_config(ModelProvider.QWEN, "qwen-flash")
        payload = {}
        svc._apply_reasoning_payload(payload, config, "high")
        assert payload.get("enable_thinking") is True

    def test_openai_none_strips_reasoning(self):
        """OPENAI reasoning_effort=none → 不发送任何推理字段"""
        svc = ModelService()
        config = make_config(ModelProvider.OPENAI, "custom-model")
        payload = {}
        svc._apply_reasoning_payload(payload, config, "none")
        assert _payload_has_no_reasoning_field(payload), (
            f"OPENAI none 应剥离所有推理参数，实际 payload={payload}"
        )

    def test_openai_high_sets_reasoning_effort(self):
        """OPENAI reasoning_effort=high → reasoning_effort=high"""
        svc = ModelService()
        config = make_config(ModelProvider.OPENAI, "custom-model")
        payload = {}
        svc._apply_reasoning_payload(payload, config, "high")
        assert payload["reasoning_effort"] == "high"

    def test_unsupported_provider_skips(self):
        """不支持的 Provider（MIMO/MOONSHOT 等）不发送推理参数"""
        svc = ModelService()
        for provider in [ModelProvider.MIMO, ModelProvider.MOONSHOT, ModelProvider.WENXIN]:
            config = make_config(provider, "test")
            payload = {}
            svc._apply_reasoning_payload(payload, config, "none")
            assert _payload_has_no_reasoning_field(payload), (
                f"{provider.value} 不支持推理，不应发送推理参数，实际 payload={payload}"
            )
            payload2 = {}
            svc._apply_reasoning_payload(payload2, config, "high")
            assert _payload_has_no_reasoning_field(payload2), (
                f"{provider.value} 不支持推理，high 档位也不应发送推理参数"
            )

    def test_empty_reasoning_effort_noop(self):
        """reasoning_effort 为空/None 时不修改 payload"""
        svc = ModelService()
        config = make_config(ModelProvider.DEEPSEEK)
        for empty_val in [None, ""]:
            payload = {"model": "test"}
            svc._apply_reasoning_payload(payload, config, empty_val)
            assert payload == {"model": "test"}, (
                f"reasoning_effort={empty_val!r} 不应修改 payload"
            )

    def test_unknown_reasoning_effort_falls_back_to_high(self):
        """未知档位值回退为 high"""
        svc = ModelService()
        config = make_config(ModelProvider.DEEPSEEK, "deepseek-v4-pro")
        payload = {}
        svc._apply_reasoning_payload(payload, config, "unknown")
        assert _payload_has_thinking_enabled(payload)
        assert payload["thinking"]["reasoning_effort"] == "high", (
            "未知档位应回退为 high"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: reasoning_effort=none 时剥离推理参数 — 验收标准核心
# ══════════════════════════════════════════════════════════════════════════════

class TestReasoningNoneStripsParams:
    """验收标准：配置档位为 none 时，模型 API 请求报文中无推理指令"""

    def test_deepseek_none_payload_has_no_enable(self):
        """DeepSeek none → payload 中 thinking.type=disabled，无 reasoning_effort"""
        svc = ModelService()
        config = make_config(ModelProvider.DEEPSEEK)
        payload = {}
        svc._apply_reasoning_payload(payload, config, "none")
        thinking = payload.get("thinking", {})
        assert thinking.get("type") == "disabled"
        assert "reasoning_effort" not in thinking, (
            "disabled 时不应携带 reasoning_effort"
        )

    def test_glm_none_payload_has_no_reasoning_effort(self):
        """GLM none → thinking.type=disabled，顶层无 reasoning_effort"""
        svc = ModelService()
        config = make_config(ModelProvider.GLM)
        payload = {}
        svc._apply_reasoning_payload(payload, config, "none")
        assert payload.get("thinking", {}).get("type") == "disabled"
        assert "reasoning_effort" not in payload

    def test_qwen_none_payload_enable_thinking_false(self):
        """QWEN none → enable_thinking=False"""
        svc = ModelService()
        config = make_config(ModelProvider.QWEN)
        payload = {}
        svc._apply_reasoning_payload(payload, config, "none")
        assert payload["enable_thinking"] is False

    def test_openai_none_payload_stripped(self):
        """OPENAI none → 无任何推理字段"""
        svc = ModelService()
        config = make_config(ModelProvider.OPENAI)
        payload = {"model": "test"}
        svc._apply_reasoning_payload(payload, config, "none")
        # 应只有原有字段，无新增推理字段
        assert "thinking" not in payload
        assert "reasoning_effort" not in payload
        assert "enable_thinking" not in payload


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: stream_once — reasoning_content 多字段兼容提取
# ══════════════════════════════════════════════════════════════════════════════

class TestStreamOnceReasoningContent:
    """测试 stream_once 对 reasoning_content 的多字段兼容提取"""

    @pytest.mark.asyncio
    async def test_reasoning_content_standard_field(self):
        """标准字段 reasoning_content 能正确提取"""
        chunk = "data: " + json.dumps({
            "choices": [{
                "delta": {
                    "content": "",
                    "reasoning_content": "Let me think about this...",
                },
                "finish_reason": None,
            }],
        }) + "\n\n"
        events = await _collect_stream_events(chunk)
        thinking_events = [e for e in events if e["type"] == "thinking"]
        assert len(thinking_events) == 1
        assert thinking_events[0]["content"] == "Let me think about this..."

    @pytest.mark.asyncio
    async def test_reasoning_details_field(self):
        """兼容字段 reasoning_details.text 能正确提取"""
        chunk = "data: " + json.dumps({
            "choices": [{
                "delta": {
                    "content": "",
                    "reasoning_details": {"text": "Analyzing the problem..."},
                },
                "finish_reason": None,
            }],
        }) + "\n\n"
        events = await _collect_stream_events(chunk)
        thinking_events = [e for e in events if e["type"] == "thinking"]
        assert len(thinking_events) == 1
        assert thinking_events[0]["content"] == "Analyzing the problem..."

    @pytest.mark.asyncio
    async def test_thoughts_field(self):
        """兼容字段 thoughts 能正确提取"""
        chunk = "data: " + json.dumps({
            "choices": [{
                "delta": {
                    "content": "",
                    "thoughts": "Hmm, let me consider...",
                },
                "finish_reason": None,
            }],
        }) + "\n\n"
        events = await _collect_stream_events(chunk)
        thinking_events = [e for e in events if e["type"] == "thinking"]
        assert len(thinking_events) == 1
        assert thinking_events[0]["content"] == "Hmm, let me consider..."

    @pytest.mark.asyncio
    async def test_think_field(self):
        """兼容字段 think 能正确提取"""
        chunk = "data: " + json.dumps({
            "choices": [{
                "delta": {
                    "content": "",
                    "think": "Thinking...",
                },
                "finish_reason": None,
            }],
        }) + "\n\n"
        events = await _collect_stream_events(chunk)
        thinking_events = [e for e in events if e["type"] == "thinking"]
        assert len(thinking_events) == 1
        assert thinking_events[0]["content"] == "Thinking..."

    @pytest.mark.asyncio
    async def test_reasoning_content_priority_over_fallback(self):
        """reasoning_content 标准字段优先级高于 fallback 字段"""
        chunk = "data: " + json.dumps({
            "choices": [{
                "delta": {
                    "content": "",
                    "reasoning_content": "Primary reasoning",
                    "think": "Should be ignored",
                },
                "finish_reason": None,
            }],
        }) + "\n\n"
        events = await _collect_stream_events(chunk)
        thinking_events = [e for e in events if e["type"] == "thinking"]
        assert len(thinking_events) == 1
        assert thinking_events[0]["content"] == "Primary reasoning"


# ══════════════════════════════════════════════════════════════════════════════
# Test 4: stream_once — reasoning_content 通过 type:thinking 独立下发
# ══════════════════════════════════════════════════════════════════════════════

class TestReasoningContentSeparation:
    """验收标准：思考内容通过 type:thinking 单独下发，不与 content 混淆"""

    @pytest.mark.asyncio
    async def test_reasoning_separate_from_text(self):
        """reasoning_content 和 content 分别通过不同 type 下发"""
        chunks = [
            "data: " + json.dumps({
                "choices": [{
                    "delta": {"content": "", "reasoning_content": "Step 1: analyze"},
                    "finish_reason": None,
                }],
            }) + "\n\n",
            "data: " + json.dumps({
                "choices": [{
                    "delta": {"content": "Now I will answer", "reasoning_content": ""},
                    "finish_reason": None,
                }],
            }) + "\n\n",
        ]
        events = await _collect_stream_events_multiple(chunks)
        # 检查事件类型
        types = [e["type"] for e in events if e["type"] in ("text", "thinking")]
        assert "thinking" in types, "应包含 thinking 事件"
        assert "text" in types, "应包含 text 事件"
        # thinking 内容不应出现在 text 中
        text_contents = "".join(e["content"] for e in events if e["type"] == "text")
        assert "Step 1: analyze" not in text_contents, (
            "思考内容不应混入 text 事件"
        )

    @pytest.mark.asyncio
    async def test_no_reasoning_when_none(self):
        """无 reasoning_content 时不应产生 thinking 事件"""
        chunk = json.dumps({
            "choices": [{
                "delta": {"content": "Hello world", "reasoning_content": ""},
                "finish_reason": None,
            }],
        })
        events = await _collect_stream_events(chunk)
        thinking_events = [e for e in events if e["type"] == "thinking"]
        assert len(thinking_events) == 0, "无 reasoning_content 不应产生 thinking 事件"

    @pytest.mark.asyncio
    async def test_reasoning_not_sent_during_tool_calls(self):
        """工具调用期间不发送 reasoning 事件"""
        chunk = json.dumps({
            "choices": [{
                "delta": {
                    "content": "",
                    "reasoning_content": "I need to use a tool",
                    "tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                                    "function": {"name": "read_file", "arguments": '{"path":'}}],
                },
                "finish_reason": None,
            }],
        })
        events = await _collect_stream_events(chunk)
        thinking_events = [e for e in events if e["type"] == "thinking"]
        assert len(thinking_events) == 0, (
            "工具调用期间不应发送 reasoning 事件"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Test 5: 向后兼容 — 旧客户端忽略 thinking 字段不崩溃
# ══════════════════════════════════════════════════════════════════════════════

class TestBackwardCompatibility:
    """验证向后兼容：旧客户端忽略 thinking 字段不崩溃"""

    @pytest.mark.asyncio
    async def test_text_events_unchanged(self):
        """text 事件格式不变"""
        chunk = "data: " + json.dumps({
            "choices": [{
                "delta": {"content": "Hello", "reasoning_content": ""},
                "finish_reason": None,
            }],
        }) + "\n\n"
        events = await _collect_stream_events(chunk)
        text_events = [e for e in events if e["type"] == "text"]
        assert len(text_events) == 1
        assert text_events[0]["content"] == "Hello"
        assert "reasoning_content" not in text_events[0], (
            "text 事件不应包含 reasoning_content 字段"
        )

    @pytest.mark.asyncio
    async def test_finish_event_unchanged(self):
        """finish 事件格式不变，仍含 finish_reason 和 usage"""
        chunk = "data: " + json.dumps({
            "choices": [{
                "delta": {"content": ""},
                "finish_reason": "stop",
            }],
            "usage": {"total_tokens": 100},
        }) + "\n\n"
        events = await _collect_stream_events(chunk)
        finish_events = [e for e in events if e["type"] == "finish"]
        assert len(finish_events) == 1
        assert finish_events[0]["finish_reason"] == "stop"
        assert finish_events[0]["usage"] is not None

    @pytest.mark.asyncio
    async def test_old_client_ignores_thinking(self):
        """旧客户端可以安全忽略 thinking 事件"""
        # 模拟：旧客户端只处理 type=text 和 type=finish
        chunk = json.dumps({
            "choices": [{
                "delta": {"content": "", "reasoning_content": "thinking..."},
                "finish_reason": None,
            }],
        })
        events = await _collect_stream_events(chunk)
        # 旧客户端过滤逻辑
        old_client_events = [e for e in events if e["type"] not in ("thinking",)]
        # 应该只有 finish 事件（thinking 被过滤，text 无内容）
        types = [e["type"] for e in old_client_events]
        assert "thinking" not in types, "旧客户端过滤后不应有 thinking 事件"
        assert "finish" in types, "finish 事件应正常保留"


# ══════════════════════════════════════════════════════════════════════════════
# 辅助：模拟 stream_once 事件收集
# ══════════════════════════════════════════════════════════════════════════════

async def _collect_stream_events(sse_chunk: str) -> list:
    """通过真实 stream_once 的内部逻辑收集事件（模拟单个 SSE chunk）"""
    from app.services.model import model_service, ModelConfig, ModelProvider

    # 用简单的 async context manager 类替代 mock
    class MockResponse:
        def __init__(self, chunk_data):
            self.status_code = 200
            self._chunk_data = chunk_data

        async def aiter_text(self):
            yield self._chunk_data

        async def aread(self):
            return b""

    class MockStreamCtx:
        def __init__(self, response):
            self._response = response

        async def __aenter__(self):
            return self._response

        async def __aexit__(self, *args):
            pass

    class MockClient:
        def __init__(self, response):
            self._response = response

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url, **kwargs):
            return MockStreamCtx(self._response)

    mock_response = MockResponse(sse_chunk)
    mock_client = MockClient(mock_response)

    config = ModelConfig(
        provider=ModelProvider.DEEPSEEK,
        model_name="test-model",
        api_key="test-key",
        api_base="https://test.api/v1",
    )

    with patch.object(model_service, "get_model_config", return_value=config):
        with patch("httpx.AsyncClient", return_value=mock_client):
            events = []
            async for event in model_service.stream_once(
                model_id="test-model",
                messages=[{"role": "user", "content": "Hello"}],
            ):
                events.append(event)
            return events


async def _collect_stream_events_multiple(sse_chunks: list) -> list:
    """通过真实 stream_once 内部逻辑收集多个 SSE chunk 的事件"""
    from app.services.model import model_service, ModelConfig, ModelProvider

    class MockResponse:
        def __init__(self, chunks):
            self.status_code = 200
            self._chunks = chunks

        async def aiter_text(self):
            for c in self._chunks:
                yield c

        async def aread(self):
            return b""

    class MockStreamCtx:
        def __init__(self, response):
            self._response = response

        async def __aenter__(self):
            return self._response

        async def __aexit__(self, *args):
            pass

    class MockClient:
        def __init__(self, response):
            self._response = response

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def stream(self, method, url, **kwargs):
            return MockStreamCtx(self._response)

    mock_response = MockResponse(sse_chunks)
    mock_client = MockClient(mock_response)

    config = ModelConfig(
        provider=ModelProvider.DEEPSEEK,
        model_name="test-model",
        api_key="test-key",
        api_base="https://test.api/v1",
    )

    with patch.object(model_service, "get_model_config", return_value=config):
        with patch("httpx.AsyncClient", return_value=mock_client):
            events = []
            async for event in model_service.stream_once(
                model_id="test-model",
                messages=[{"role": "user", "content": "Hello"}],
            ):
                events.append(event)
            return events


async def _async_iter(items):
    """将列表转为异步迭代器"""
    for item in items:
        yield item


# ══════════════════════════════════════════════════════════════════════════════
# 直接运行
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])