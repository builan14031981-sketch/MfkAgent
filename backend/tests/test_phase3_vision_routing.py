"""Phase 3: Vision Auto-Routing 智能路由与熔断兜底验收测试。

测试覆盖：
  1. Settings API vision_fallback 字段组读写
  2. 场景 A：主模型支持 Vision → 直接注入多模态消息
  3. 场景 B：主模型不支持 Vision + 未配置 fallback → 友好提示
  4. 场景 B：主模型不支持 Vision + 已配置 fallback → 调用备用模型
  5. 熔断兜底：fallback API 返回错误 → 优雅降级，不崩溃
  6. 熔断兜底：fallback API 超时 → 优雅降级
  7. _inject_fallback_text_into_messages 注入逻辑
  8. _vision_fallback_extract 配置读取
"""

import os
import sys
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

# 确保 backend 目录在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================================
# Test 1: Settings API — vision_fallback 字段组
# ============================================================================

class TestVisionFallbackSettings:
    """测试 vision_fallback 设置字段的读写与脱敏。"""

    def test_default_settings_include_vision_fallback(self):
        """DEFAULT_SETTINGS 应包含 vision_fallback 四个字段。"""
        from app.api.settings import DEFAULT_SETTINGS
        assert "vision_provider" in DEFAULT_SETTINGS
        assert "vision_api_key" in DEFAULT_SETTINGS
        assert "vision_model" in DEFAULT_SETTINGS
        assert "vision_base_url" in DEFAULT_SETTINGS
        assert DEFAULT_SETTINGS["vision_provider"] == ""
        assert DEFAULT_SETTINGS["vision_api_key"] == ""
        assert DEFAULT_SETTINGS["vision_model"] == ""
        assert DEFAULT_SETTINGS["vision_base_url"] == ""

    def test_mask_key_short(self):
        """短 Key（<=8 字符）脱敏为 ****。"""
        from app.api.settings import _mask_key
        assert _mask_key("short") == "****"
        assert _mask_key("12345678") == "****"

    def test_mask_key_long(self):
        """长 Key 脱敏为首3+****+尾4。"""
        from app.api.settings import _mask_key
        result = _mask_key("sk-abcdefghijklmnopqrstuvwxyz")
        assert result == "sk-****wxyz"

    def test_mask_key_empty(self):
        """空 Key 脱敏为空字符串。"""
        from app.api.settings import _mask_key
        assert _mask_key("") == ""
        assert _mask_key(None) == ""


# ============================================================================
# Test 2: _inject_fallback_text_into_messages
# ============================================================================

class TestInjectFallbackText:
    """测试 fallback 文本注入到消息列表的逻辑。"""

    def test_inject_into_str_content(self):
        """content 为 str 时，追加 fallback 文本。"""
        from app.services.model import _inject_fallback_text_into_messages

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "这张图片里有什么？"},
        ]
        result = _inject_fallback_text_into_messages(messages, "这是一张包含代码截图的图片。")

        assert len(result) == 2
        user_content = result[1]["content"]
        assert isinstance(user_content, str)
        assert "[图片解析文本说明]" in user_content
        assert "这是一张包含代码截图的图片。" in user_content
        assert "这张图片里有什么？" in user_content

    def test_inject_into_list_content(self):
        """content 为 list 时，追加 text 项。"""
        from app.services.model import _inject_fallback_text_into_messages

        messages = [
            {"role": "user", "content": [{"type": "text", "text": "描述这张图"}]},
        ]
        result = _inject_fallback_text_into_messages(messages, "图片描述文本")

        assert len(result) == 1
        content = result[0]["content"]
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "text"
        assert "[图片解析文本说明]" in content[1]["text"]

    def test_empty_fallback_text(self):
        """空 fallback 文本不修改消息。"""
        from app.services.model import _inject_fallback_text_into_messages

        messages = [{"role": "user", "content": "hello"}]
        result = _inject_fallback_text_into_messages(messages, "")
        assert result == messages  # 空文本不修改

    def test_no_user_message(self):
        """无 user 消息时，追加一条 user 消息。"""
        from app.services.model import _inject_fallback_text_into_messages

        messages = [{"role": "system", "content": "system"}]
        result = _inject_fallback_text_into_messages(messages, "fallback text")

        assert len(result) == 2
        assert result[1]["role"] == "user"
        assert "fallback text" in result[1]["content"]

    def test_preserves_original_messages(self):
        """原消息列表不被修改（深拷贝）。"""
        from app.services.model import _inject_fallback_text_into_messages

        messages = [{"role": "user", "content": "original"}]
        _ = _inject_fallback_text_into_messages(messages, "fallback")
        assert messages[0]["content"] == "original"  # 原列表未变


# ============================================================================
# Test 3: _vision_fallback_extract — 配置读取
# ============================================================================

class TestVisionFallbackExtract:
    """测试 _vision_fallback_extract 的配置读取与熔断逻辑。"""

    @pytest.mark.asyncio
    async def test_no_config_returns_hint(self):
        """未配置 vision_fallback 时返回友好提示。"""
        from app.services.model import _vision_fallback_extract

        vision_context = {"images": [{"path": "/tmp/test.png", "mime": "image/png"}]}

        with patch("app.core.database.SessionLocal") as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            # 模拟所有设置查询返回 None（未配置）
            mock_session.query.return_value.filter.return_value.first.return_value = None

            result = await _vision_fallback_extract(vision_context)
            assert "[图片解析提示]" in result
            assert "请在设置中配置备用识图模型" in result

    @pytest.mark.asyncio
    async def test_no_images_returns_empty(self):
        """无图片时返回空字符串（前提：已配置 fallback）。"""
        from app.services.model import _vision_fallback_extract

        vision_context = {"images": []}

        with patch("app.core.database.SessionLocal") as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            # 模拟配置存在（有 api_key + model）
            mock_session.query.return_value.filter.return_value.first.return_value = MagicMock(
                value="sk-fake"
            )

            result = await _vision_fallback_extract(vision_context)
            assert result == ""

    @pytest.mark.asyncio
    async def test_api_error_graceful(self):
        """fallback API 返回非 200 → 优雅降级，不抛异常。"""
        from app.services.model import _vision_fallback_extract
        import httpx

        vision_context = {"images": [{"path": "/tmp/test.png", "mime": "image/png"}]}

        with patch("app.core.database.SessionLocal") as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            # 模拟配置存在
            def mock_filter_first(key):
                m = MagicMock()
                if key == "vision_provider":
                    m.value = "siliconflow"
                elif key == "vision_api_key":
                    m.value = "sk-fake-key-12345678"
                elif key == "vision_model":
                    m.value = "Qwen/Qwen2.5-VL-7B-Instruct"
                elif key == "vision_base_url":
                    m.value = ""
                else:
                    m.value = None
                return m

            mock_session.query.return_value.filter.return_value.first.side_effect = (
                lambda: mock_filter_first("vision_provider")
            )

            # 模拟文件存在 + API 返回 500
            with patch("os.path.isfile", return_value=True):
                with patch("os.path.getsize", return_value=1024):
                    with patch(
                        "builtins.open",
                        MagicMock(),
                    ):
                        with patch("base64.b64encode", return_value=b"fakebase64"):
                            with patch("app.services.model._image_to_data_uri", return_value="data:image/png;base64,fake"):
                                mock_response = MagicMock()
                                mock_response.status_code = 500
                                mock_response.text = '{"error": "Internal Server Error"}'

                                mock_client = MagicMock()
                                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                                mock_client.__aexit__ = AsyncMock(return_value=None)
                                mock_client.post = AsyncMock(return_value=mock_response)

                                with patch("httpx.AsyncClient", return_value=mock_client):
                                    result = await _vision_fallback_extract(vision_context)
                                    assert "[图片解析失败" in result
                                    # 不抛异常

    @pytest.mark.asyncio
    async def test_timeout_graceful(self):
        """fallback API 超时 → 优雅降级，不抛异常。"""
        from app.services.model import _vision_fallback_extract
        import httpx

        vision_context = {"images": [{"path": "/tmp/test.png", "mime": "image/png"}]}

        with patch("app.core.database.SessionLocal") as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            # 模拟配置存在
            mock_session.query.return_value.filter.return_value.first.return_value = MagicMock(
                value="sk-fake"
            )

            with patch("os.path.isfile", return_value=True):
                with patch("os.path.getsize", return_value=1024):
                    with patch("builtins.open", MagicMock()):
                        with patch("base64.b64encode", return_value=b"fakebase64"):
                            with patch("app.services.model._image_to_data_uri", return_value="data:image/png;base64,fake"):
                                mock_client = MagicMock()
                                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                                mock_client.__aexit__ = AsyncMock(return_value=None)
                                mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

                                with patch("httpx.AsyncClient", return_value=mock_client):
                                    result = await _vision_fallback_extract(vision_context)
                                    assert "[图片解析失败" in result
                                    assert "超时" in result

    @pytest.mark.asyncio
    async def test_exception_graceful(self):
        """fallback API 任意异常 → 优雅降级，不抛异常。"""
        from app.services.model import _vision_fallback_extract

        vision_context = {"images": [{"path": "/tmp/test.png", "mime": "image/png"}]}

        with patch("app.core.database.SessionLocal") as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            mock_session.query.return_value.filter.return_value.first.return_value = MagicMock(
                value="sk-fake"
            )

            with patch("os.path.isfile", return_value=True):
                with patch("os.path.getsize", return_value=1024):
                    with patch("builtins.open", MagicMock()):
                        with patch("base64.b64encode", return_value=b"fakebase64"):
                            with patch("app.services.model._image_to_data_uri", return_value="data:image/png;base64,fake"):
                                mock_client = MagicMock()
                                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                                mock_client.__aexit__ = AsyncMock(return_value=None)
                                mock_client.post = AsyncMock(side_effect=RuntimeError("unexpected error"))

                                with patch("httpx.AsyncClient", return_value=mock_client):
                                    result = await _vision_fallback_extract(vision_context)
                                    assert "[图片解析失败" in result
                                    # 不抛异常

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        """fallback API 成功返回文本。"""
        from app.services.model import _vision_fallback_extract

        vision_context = {"images": [{"path": "/tmp/test.png", "mime": "image/png"}]}

        with patch("app.core.database.SessionLocal") as mock_db:
            mock_session = MagicMock()
            mock_db.return_value = mock_session

            mock_session.query.return_value.filter.return_value.first.return_value = MagicMock(
                value="sk-fake"
            )

            with patch("os.path.isfile", return_value=True):
                with patch("os.path.getsize", return_value=1024):
                    with patch("builtins.open", MagicMock()):
                        with patch("base64.b64encode", return_value=b"fakebase64"):
                            with patch("app.services.model._image_to_data_uri", return_value="data:image/png;base64,fake"):
                                mock_response = MagicMock()
                                mock_response.status_code = 200
                                mock_response.json.return_value = {
                                    "choices": [
                                        {
                                            "message": {
                                                "content": "这是一张包含代码截图的图片，显示了 Python 代码。"
                                            }
                                        }
                                    ]
                                }

                                mock_client = MagicMock()
                                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                                mock_client.__aexit__ = AsyncMock(return_value=None)
                                mock_client.post = AsyncMock(return_value=mock_response)

                                with patch("httpx.AsyncClient", return_value=mock_client):
                                    result = await _vision_fallback_extract(vision_context)
                                    assert "这是一张包含代码截图的图片" in result
                                    assert "[图片解析失败" not in result
                                    assert "[图片解析提示]" not in result


# ============================================================================
# Test 4: _provider_supports_vision
# ============================================================================

class TestProviderSupportsVision:
    """测试 provider vision 支持查询。"""

    def test_qwen_provider_no_longer_supports_vision(self):
        """qwen provider 级不再默认支持 vision（粒度下沉到 Model 级）。"""
        from app.services.model import _provider_supports_vision
        assert _provider_supports_vision("qwen") is False

    def test_google_supports_vision(self):
        """google provider 全系支持 vision。"""
        from app.services.model import _provider_supports_vision
        assert _provider_supports_vision("google") is True

    def test_glm_provider_no_longer_supports_vision(self):
        """glm provider 级不再默认支持 vision（GLM-4 是纯文本模型）。"""
        from app.services.model import _provider_supports_vision
        assert _provider_supports_vision("glm") is False

    def test_deepseek_not_support_vision(self):
        """deepseek provider 不支持 vision。"""
        from app.services.model import _provider_supports_vision
        assert _provider_supports_vision("deepseek") is False

    def test_unknown_provider_not_support(self):
        """未知 provider 不支持 vision。"""
        from app.services.model import _provider_supports_vision
        assert _provider_supports_vision("unknown") is False


# ============================================================================
# Test 4.5: _detect_supports_vision — Model 级粒度判定（三级优先级）
# ============================================================================

class TestDetectSupportsVisionModelLevel:
    """测试 _detect_supports_vision 的三级优先级判定逻辑。"""

    def test_qwen_flash_returns_false(self):
        """qwen-flash 纯文本模型 → False（无显式标记 + 命名不匹配 + provider 级 False）。"""
        from app.services.model import _detect_supports_vision
        assert _detect_supports_vision("qwen-flash", provider_vision=False) is False

    def test_qwen3_vl_235b_returns_true_by_name(self):
        """qwen3-vl-235b 模型名含 vl → True（命名推测优先级）。"""
        from app.services.model import _detect_supports_vision
        assert _detect_supports_vision("qwen3-vl-235b-a22b-thinking", provider_vision=False) is True

    def test_qwen3_vl_235b_returns_true_by_explicit(self):
        """qwen3-vl-235b 显式 model_vision=True → True（最高优先级）。"""
        from app.services.model import _detect_supports_vision
        assert _detect_supports_vision("qwen3-vl-235b-a22b-thinking", provider_vision=False, model_vision=True) is True

    def test_gemini_flash_returns_true_by_provider(self):
        """gemini-3.5-flash 无显式标记 + 命名不匹配 → 回退 provider 级 True。"""
        from app.services.model import _detect_supports_vision
        assert _detect_supports_vision("gemini-3.5-flash", provider_vision=True) is True

    def test_deepseek_v4_flash_returns_false(self):
        """deepseek-v4-flash 纯文本模型 → False。"""
        from app.services.model import _detect_supports_vision
        assert _detect_supports_vision("deepseek-v4-flash", provider_vision=False) is False

    def test_model_vision_explicit_overrides_name(self):
        """显式 model_vision=False 覆盖命名推测（防御性）。"""
        from app.services.model import _detect_supports_vision
        assert _detect_supports_vision("some-vl-model", provider_vision=False, model_vision=False) is False

    def test_model_vision_explicit_overrides_provider(self):
        """显式 model_vision=True 覆盖 provider 级 False。"""
        from app.services.model import _detect_supports_vision
        assert _detect_supports_vision("qwen-flash", provider_vision=False, model_vision=True) is True

    def test_backward_compat_no_model_vision(self):
        """不传 model_vision 参数时（旧代码兼容），行为与原来一致。"""
        from app.services.model import _detect_supports_vision
        # 旧行为：provider_vision=False → False
        assert _detect_supports_vision("qwen-flash", provider_vision=False) is False
        # 旧行为：provider_vision=True → True
        assert _detect_supports_vision("gemini-3.5-flash", provider_vision=True) is True


# ============================================================================
# Test 5: call_once 路由逻辑
# ============================================================================

class TestCallOnceRouting:
    """测试 call_once 中的 Vision Auto-Routing 逻辑。"""

    @pytest.mark.asyncio
    async def test_provider_supports_vision_direct_inject(self):
        """主模型支持 Vision → 直接注入多模态消息。"""
        from app.services.model import model_service, _inject_vision_into_messages
        from app.services.model import ModelProvider

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "描述这张图"},
        ]
        vision_context = {"images": [{"path": "/tmp/test.png", "mime": "image/png"}]}

        # 模拟 gemini 模型配置（支持 vision）
        with patch.object(model_service, "get_model_config") as mock_config:
            mock_config.return_value = MagicMock(
                provider=ModelProvider.GOOGLE,
                model_name="gemini-3.5-flash",
                api_key="sk-test",
                api_base="https://test/v1",
            )

            with patch("os.path.isfile", return_value=True):
                with patch("os.path.getsize", return_value=1024):
                    with patch("builtins.open", MagicMock()):
                        with patch("base64.b64encode", return_value=b"fake"):
                            with patch("app.services.model._image_to_data_uri", return_value="data:image/png;base64,fake"):
                                mock_response = MagicMock()
                                mock_response.status_code = 200
                                mock_response.json.return_value = {
                                    "choices": [{"message": {"content": "这是一张图"}, "finish_reason": "stop"}],
                                    "usage": {"total_tokens": 100},
                                }

                                mock_client = MagicMock()
                                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                                mock_client.__aexit__ = AsyncMock(return_value=None)
                                mock_client.post = AsyncMock(return_value=mock_response)

                                with patch("httpx.AsyncClient", return_value=mock_client):
                                    result = await model_service.call_once(
                                        model_id="gemini-3.5-flash",
                                        messages=messages,
                                        vision_context=vision_context,
                                    )
                                    # 调用成功，不抛异常
                                    assert result.content is not None

    @pytest.mark.asyncio
    async def test_deepseek_no_fallback_returns_hint(self):
        """DeepSeek 不支持 Vision + 未配置 fallback → 友好提示仍可调用。"""
        from app.services.model import model_service
        from app.services.model import ModelProvider

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "描述这张图"},
        ]
        vision_context = {"images": [{"path": "/tmp/test.png", "mime": "image/png"}]}

        with patch.object(model_service, "get_model_config") as mock_config:
            mock_config.return_value = MagicMock(
                provider=ModelProvider.DEEPSEEK,
                model_name="deepseek-v4-flash",
                api_key="sk-test",
                api_base="https://test/v1",
            )

            with patch("app.services.model._vision_fallback_extract") as mock_fallback:
                mock_fallback.return_value = (
                    "[图片解析提示] 当前主模型不支持识图，"
                    "请在设置中配置备用识图模型。"
                )

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "我无法看到图片，但你可以描述它。"}, "finish_reason": "stop"}],
                    "usage": {"total_tokens": 100},
                }

                mock_client = MagicMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.post = AsyncMock(return_value=mock_response)

                with patch("httpx.AsyncClient", return_value=mock_client):
                    result = await model_service.call_once(
                        model_id="deepseek-v4-flash",
                        messages=messages,
                        vision_context=vision_context,
                    )
                    assert result.content is not None
                    # 不崩溃，正常返回


# ============================================================================
# 运行入口
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])