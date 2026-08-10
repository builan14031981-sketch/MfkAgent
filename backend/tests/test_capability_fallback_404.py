"""Phase: 自定义动态模型能力适配与 API 404 熔断兜底 — 专项测试

测试覆盖：
  A 组：_detect_supports_vision 动态能力检测
  B 组：supports_tools 默认 True
  C 组：get_model_config 惰性 reload 兜底
  D 组：ModelService._check_model_not_found 404/400/422 熔断
  E 组：ModelNotFoundError 消息格式
  F 组：call_once 404 熔断
  G 组：stream_once 404 熔断
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from app.services.model import (
    ModelService,
    ModelNotFoundError,
    ModelConfig,
    ModelProvider,
    _detect_supports_vision,
)
from app.core.model_providers import PROVIDER_MAP


# ═══════════════════════════════════════════════════════════════════════
# A 组：_detect_supports_vision 动态能力检测
# ═══════════════════════════════════════════════════════════════════════

class TestDetectSupportsVision:
    """测试动态模型名 → supports_vision 推断。"""

    def test_vl_in_name_returns_true(self):
        """模型名含 'vl' → True（无论 provider 级配置）。"""
        assert _detect_supports_vision("qwen3-vl-32b", False) is True

    def test_vl_uppercase_in_name_returns_true(self):
        """模型名含 'VL'（大写）→ True。"""
        assert _detect_supports_vision("Model-VL-7B", False) is True

    def test_vision_in_name_returns_true(self):
        """模型名含 'vision' → True。"""
        assert _detect_supports_vision("my-vision-model", False) is True

    def test_vision_uppercase_in_name_returns_true(self):
        """模型名含 'Vision' → True。"""
        assert _detect_supports_vision("SomeVisionModel", False) is True

    def test_no_vision_keyword_provider_vision_true(self):
        """模型名无关键词 + provider 支持 vision → True（回退到 provider 级）。"""
        assert _detect_supports_vision("qwen-plus", True) is True

    def test_no_vision_keyword_provider_vision_false(self):
        """模型名无关键词 + provider 不支持 vision → False。"""
        assert _detect_supports_vision("deepseek-v4-flash", False) is False

    def test_empty_model_name_provider_false(self):
        """空模型名 + provider 不支持 → False。"""
        assert _detect_supports_vision("", False) is False

    def test_empty_model_name_provider_true(self):
        """空模型名 + provider 支持 → True（回退到 provider 级）。"""
        assert _detect_supports_vision("", True) is True

    def test_none_model_name_provider_false(self):
        """None 模型名 + provider 不支持 → False。"""
        assert _detect_supports_vision(None, False) is False


# ═══════════════════════════════════════════════════════════════════════
# B 组：supports_tools 默认 True
# ═══════════════════════════════════════════════════════════════════════

class TestSupportsToolsDefault:
    """测试自定义模型 supports_tools 默认为 True。"""

    def test_model_config_default_supports_tools_true(self):
        """ModelConfig 默认 supports_tools=True。"""
        config = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="custom-model",
            api_key="sk-test",
            api_base="https://api.example.com/v1",
        )
        assert config.supports_tools is True

    def test_model_config_explicit_supports_tools_false(self):
        """ModelConfig 可显式设 supports_tools=False。"""
        config = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="custom-model",
            api_key="sk-test",
            api_base="https://api.example.com/v1",
            supports_tools=False,
        )
        assert config.supports_tools is False


# ═══════════════════════════════════════════════════════════════════════
# C 组：get_model_config 惰性 reload 兜底
# ═══════════════════════════════════════════════════════════════════════

class TestGetModelConfigLazyReload:
    """测试 get_model_config 未找到时尝试 reload 兜底。"""

    def test_existing_model_no_reload(self):
        """已存在的模型不触发 reload。"""
        svc = ModelService()
        original_models = svc.models
        # 获取一个已存在的模型
        config = svc.get_model_config("deepseek-v4-flash")
        # models 字典不应变化（未 reload）
        assert svc.models is original_models
        assert config is not None
        assert config.model_name == "deepseek-v4-flash"

    def test_nonexistent_model_triggers_reload(self):
        """不存在的模型触发一次 reload，仍不存在则返回 None。"""
        svc = ModelService()
        reload_called = False
        original_reload = svc.reload_models

        def tracking_reload():
            nonlocal reload_called
            reload_called = True
            original_reload()

        svc.reload_models = tracking_reload
        try:
            config = svc.get_model_config("definitely-nonexistent-model-xyz")
            assert reload_called is True
            assert config is None
        finally:
            svc.reload_models = original_reload

    def test_reload_finds_newly_added_model(self):
        """reload 后能找到新添加的自定义模型。"""
        svc = ModelService()
        # 模拟 reload 后 models 字典中出现了新模型
        fake_config = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="my-custom-model",
            api_key="sk-custom",
            api_base="https://api.custom.com/v1",
            supports_vision=True,
            supports_tools=True,
        )
        original_reload = svc.reload_models

        def mock_reload():
            svc.models["my-custom-model"] = fake_config

        svc.reload_models = mock_reload
        try:
            config = svc.get_model_config("my-custom-model")
            assert config is not None
            assert config.model_name == "my-custom-model"
            assert config.supports_vision is True
            assert config.supports_tools is True
        finally:
            svc.reload_models = original_reload


# ═══════════════════════════════════════════════════════════════════════
# D 组：ModelService._check_model_not_found 404/400/422 熔断
# ═══════════════════════════════════════════════════════════════════════

class TestCheckModelNotFound:
    """测试 ModelService._check_model_not_found 对各类 HTTP 错误的判定。"""

    def test_404_raises_model_not_found(self):
        """HTTP 404 → 抛出 ModelNotFoundError。"""
        with pytest.raises(ModelNotFoundError) as exc_info:
            ModelService._check_model_not_found(404, "Not Found", "my-model")
        assert "服务商未找到模型 [my-model]" in str(exc_info.value)
        assert "请在设置中检查 Model ID 是否正确" in str(exc_info.value)

    def test_400_with_model_not_found_raises(self):
        """HTTP 400 + 'model not found' → 抛出 ModelNotFoundError。"""
        raw = '{"error": {"message": "model not found: my-model"}}'
        with pytest.raises(ModelNotFoundError) as exc_info:
            ModelService._check_model_not_found(400, raw, "my-model")
        assert "服务商未找到模型 [my-model]" in str(exc_info.value)

    def test_422_with_invalid_model_raises(self):
        """HTTP 422 + 'invalid model' → 抛出 ModelNotFoundError。"""
        raw = '{"error": {"message": "invalid model id"}}'
        with pytest.raises(ModelNotFoundError) as exc_info:
            ModelService._check_model_not_found(422, raw, "my-model")
        assert "服务商未找到模型 [my-model]" in str(exc_info.value)

    def test_400_with_does_not_exist_raises(self):
        """HTTP 400 + 'does not exist' → 抛出 ModelNotFoundError。"""
        raw = '{"error": {"message": "The model does not exist"}}'
        with pytest.raises(ModelNotFoundError):
            ModelService._check_model_not_found(400, raw, "my-model")

    def test_400_with_unknown_model_raises(self):
        """HTTP 400 + 'unknown model' → 抛出 ModelNotFoundError。"""
        raw = '{"error": {"message": "unknown model specified"}}'
        with pytest.raises(ModelNotFoundError):
            ModelService._check_model_not_found(400, raw, "my-model")

    def test_400_with_no_such_model_raises(self):
        """HTTP 400 + 'no such model' → 抛出 ModelNotFoundError。"""
        raw = '{"error": {"message": "no such model: my-model"}}'
        with pytest.raises(ModelNotFoundError):
            ModelService._check_model_not_found(400, raw, "my-model")

    def test_200_no_exception(self):
        """HTTP 200 → 不抛异常。"""
        ModelService._check_model_not_found(200, '{"ok": true}', "my-model")

    def test_500_no_exception(self):
        """HTTP 500 → 不抛 ModelNotFoundError（不是模型不存在错误）。"""
        ModelService._check_model_not_found(500, "Internal Server Error", "my-model")

    def test_429_no_exception(self):
        """HTTP 429 → 不抛 ModelNotFoundError（限流，非模型不存在）。"""
        ModelService._check_model_not_found(429, "Too Many Requests", "my-model")

    def test_400_without_model_keywords_no_exception(self):
        """HTTP 400 + 无模型关键词 → 不抛 ModelNotFoundError。"""
        raw = '{"error": {"message": "rate limit exceeded"}}'
        ModelService._check_model_not_found(400, raw, "my-model")


# ═══════════════════════════════════════════════════════════════════════
# E 组：ModelNotFoundError 消息格式
# ═══════════════════════════════════════════════════════════════════════

class TestModelNotFoundErrorFormat:
    """测试 ModelNotFoundError 的用户友好消息格式。"""

    def test_message_contains_model_name(self):
        """错误消息包含模型名。"""
        try:
            raise ModelNotFoundError("服务商未找到模型 [test-model-123]，请在设置中检查 Model ID 是否正确。")
        except ModelNotFoundError as e:
            assert "test-model-123" in str(e)

    def test_message_contains_guidance(self):
        """错误消息包含设置指引。"""
        try:
            raise ModelNotFoundError("服务商未找到模型 [test-model-123]，请在设置中检查 Model ID 是否正确。")
        except ModelNotFoundError as e:
            assert "请在设置中检查 Model ID" in str(e)

    def test_is_exception_subclass(self):
        """ModelNotFoundError 是 Exception 子类，可被 except Exception 捕获。"""
        with pytest.raises(Exception):
            raise ModelNotFoundError("test")


# ═══════════════════════════════════════════════════════════════════════
# F 组：call_once 404 熔断
# ═══════════════════════════════════════════════════════════════════════

class TestCallOnceModelNotFound:
    """测试 call_once 遇到 404 时抛出 ModelNotFoundError。"""

    @pytest.mark.asyncio
    async def test_call_once_404_raises_model_not_found(self):
        """call_once 收到 404 → 抛出 ModelNotFoundError（非通用 Exception）。"""
        svc = ModelService()

        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = '{"error": {"message": "model not found"}}'

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ModelNotFoundError) as exc_info:
                await svc.call_once(
                    model_id="deepseek-v4-flash",
                    messages=[{"role": "user", "content": "hi"}],
                )
            assert "服务商未找到模型" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_once_400_model_not_found_raises_model_not_found(self):
        """call_once 收到 400 + model not found → 抛出 ModelNotFoundError。"""
        svc = ModelService()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": {"message": "model not found: deepseek-v4-flash"}}'

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ModelNotFoundError):
                await svc.call_once(
                    model_id="deepseek-v4-flash",
                    messages=[{"role": "user", "content": "hi"}],
                )

    @pytest.mark.asyncio
    async def test_call_once_500_raises_generic_exception(self):
        """call_once 收到 500 → 抛出通用 Exception（非 ModelNotFoundError）。"""
        svc = ModelService()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception) as exc_info:
                await svc.call_once(
                    model_id="deepseek-v4-flash",
                    messages=[{"role": "user", "content": "hi"}],
                )
            # 不应是 ModelNotFoundError
            assert not isinstance(exc_info.value, ModelNotFoundError)


# ═══════════════════════════════════════════════════════════════════════
# G 组：stream_once 404 熔断
# ═══════════════════════════════════════════════════════════════════════

class TestStreamOnceModelNotFound:
    """测试 stream_once 遇到 404 时抛出 ModelNotFoundError。"""

    @pytest.mark.asyncio
    async def test_stream_once_404_raises_model_not_found(self):
        """stream_once 收到 404 → 抛出 ModelNotFoundError。"""
        svc = ModelService()

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.aread = AsyncMock(return_value=b'{"error": {"message": "model not found"}}')

        # Mock stream context manager
        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ModelNotFoundError) as exc_info:
                async for _ in svc.stream_once(
                    model_id="deepseek-v4-flash",
                    messages=[{"role": "user", "content": "hi"}],
                ):
                    pass
            assert "服务商未找到模型" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stream_once_400_invalid_model_raises_model_not_found(self):
        """stream_once 收到 400 + invalid model → 抛出 ModelNotFoundError。"""
        svc = ModelService()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.aread = AsyncMock(return_value=b'{"error": {"message": "invalid model id"}}')

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ModelNotFoundError):
                async for _ in svc.stream_once(
                    model_id="deepseek-v4-flash",
                    messages=[{"role": "user", "content": "hi"}],
                ):
                    pass


# ═══════════════════════════════════════════════════════════════════════
# H 组：Agent.py ModelNotFoundError 专项捕获（集成验证）
# ═══════════════════════════════════════════════════════════════════════

class TestAgentModelNotFoundErrorCatch:
    """验证 agent.py 能正确导入和捕获 ModelNotFoundError。"""

    def test_agent_imports_model_not_found_error(self):
        """agent.py 能正常导入 ModelNotFoundError。"""
        from app.core.agent_runtime.agent import ModelNotFoundError as ImportedError
        assert ImportedError is ModelNotFoundError

    def test_model_not_found_error_is_catchable_before_exception(self):
        """ModelNotFoundError 可被 except 捕获，优先于 except Exception。"""
        caught_specific = False

        try:
            raise ModelNotFoundError("test error")
        except ModelNotFoundError:
            caught_specific = True
        except Exception:
            caught_specific = False

        assert caught_specific is True
