"""ModelConfigAdapter 防腐层单元测试

覆盖核心边缘场景：
1. settings 表与 .env 同时有 Key 时，settings 表优先级更高
2. CustomModel 表同名 model_id 覆盖内置 PROVIDERS 配置
3. 无 Key 状态 → ModelConfigError 正确抛出（call_once / stream_once 对齐）

测试策略：使用 unittest.mock.patch 隔离 DB 访问，确保测试可重复且不依赖真实环境。
"""
import asyncio
import sys
import os
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ──── 测试夹具：构造 mock 数据 ────

def _make_provider_def(pid="deepseek", env_key="DEEPSEEK_API_KEY"):
    """构造一个 ProviderDef mock"""
    from app.core.model_providers import ProviderDef, ProviderModel
    return ProviderDef(
        id=pid,
        name=pid.upper(),
        free=False,
        default_api_base=f"https://api.{pid}.com/v1",
        models=(ProviderModel(id=f"{pid}-chat", upstream=f"{pid}-chat", display_name=f"{pid} Chat"),),
        env_key=env_key,
    )


def _make_custom_model_orm(model_id, provider="deepseek", api_key="custom-key-xxx"):
    """构造一个 CustomModel ORM mock"""
    cm = MagicMock()
    cm.model_id = model_id
    cm.name = model_id
    cm.provider = provider
    cm.model_name = model_id
    cm.api_base = "https://custom-endpoint.test/v1"
    cm.api_key = api_key
    cm.max_tokens = 8192
    cm.temperature = 0.5
    cm.enabled = True
    return cm


# ──── 任务1：settings 表 vs .env 优先级 ────

class TestSettingsEnvPriority:
    """验证 settings 表 Key 优先级高于 .env"""

    def test_settings_table_overrides_env(self):
        """settings 表有 Key → 应优先于 .env 的 Key"""
        from app.core.model_adapter import ModelConfigAdapter
        adapter = ModelConfigAdapter()
        provider_def = _make_provider_def()

        # mock: settings 表返回 "sk-from-settings"，.env 返回 "sk-from-env"
        def fake_read_setting(key):
            if key == "api_key_deepseek":
                return "sk-from-settings"
            return ""

        with patch.object(adapter, "_read_setting", side_effect=fake_read_setting), \
             patch("app.core.model_adapter.settings") as mock_env:
            mock_env.DEEPSEEK_API_KEY = "sk-from-env"
            result = adapter.resolve_api_key(provider_def)

        assert result == "sk-from-settings", f"settings 表应优先，实际: {result}"

    def test_env_fallback_when_settings_empty(self):
        """settings 表无 Key → 回退到 .env"""
        from app.core.model_adapter import ModelConfigAdapter
        adapter = ModelConfigAdapter()
        provider_def = _make_provider_def()

        with patch.object(adapter, "_read_setting", return_value=""), \
             patch("app.core.model_adapter.settings") as mock_env:
            mock_env.DEEPSEEK_API_KEY = "sk-from-env"
            result = adapter.resolve_api_key(provider_def)

        assert result == "sk-from-env", f"应回退到 .env，实际: {result}"

    def test_env_fallback_when_settings_missing(self):
        """settings 表无该 Key 记录（None）→ 回退到 .env"""
        from app.core.model_adapter import ModelConfigAdapter
        adapter = ModelConfigAdapter()
        provider_def = _make_provider_def()

        # _read_setting 返回空串（模拟 DB 无记录）
        with patch.object(adapter, "_read_setting", return_value=""), \
             patch("app.core.model_adapter.settings") as mock_env:
            mock_env.DEEPSEEK_API_KEY = "env-key-123"
            result = adapter.resolve_api_key(provider_def)

        assert result == "env-key-123"

    def test_both_empty_returns_empty(self):
        """settings 表和 .env 都无 Key → 返回空串"""
        from app.core.model_adapter import ModelConfigAdapter
        adapter = ModelConfigAdapter()
        provider_def = _make_provider_def()

        with patch.object(adapter, "_read_setting", return_value=""), \
             patch("app.core.model_adapter.settings") as mock_env:
            mock_env.DEEPSEEK_API_KEY = ""
            result = adapter.resolve_api_key(provider_def)

        assert result == "", "两边都空应返回空串"

    def test_api_base_settings_overrides_default(self):
        """settings 表 api_base 覆盖 provider 默认端点"""
        from app.core.model_adapter import ModelConfigAdapter
        adapter = ModelConfigAdapter()
        provider_def = _make_provider_def()

        with patch.object(adapter, "_read_setting", return_value="https://custom.base/v1"):
            result = adapter.resolve_api_base(provider_def)

        assert result == "https://custom.base/v1", f"settings 表端点应覆盖默认，实际: {result}"

    def test_api_base_fallback_to_default(self):
        """settings 表无 api_base → 用 provider 默认端点"""
        from app.core.model_adapter import ModelConfigAdapter
        adapter = ModelConfigAdapter()
        provider_def = _make_provider_def()

        with patch.object(adapter, "_read_setting", return_value=""):
            result = adapter.resolve_api_base(provider_def)

        assert result == "https://api.deepseek.com/v1"


# ──── 任务2：CustomModel 覆盖内置 PROVIDERS ────

class TestCustomModelOverride:
    """验证 CustomModel 表同名 model_id 覆盖内置配置"""

    def test_custom_model_overrides_builtin(self):
        """CustomModel 同名 model_id 覆盖内置 PROVIDERS 配置"""
        from app.core.model_adapter import ModelConfigAdapter
        adapter = ModelConfigAdapter()
        builtin_provider = _make_provider_def()

        # mock：内置 deepseek-chat 模型 + CustomModel 覆盖同名
        fake_custom = _make_custom_model_orm("deepseek-chat", api_key="custom-override-key")

        def fake_read_setting(key):
            # 内置 provider 的 key 在 .env
            if key == "api_key_deepseek":
                return ""  # 让内置走 .env
            return ""

        with patch("app.core.model_adapter._mp.PROVIDERS", (builtin_provider,)), \
             patch("app.core.model_adapter._mp.PROVIDER_MAP", {"deepseek": builtin_provider}), \
             patch.object(adapter, "_read_setting", side_effect=fake_read_setting), \
             patch.object(adapter, "_custom_models", return_value=[fake_custom]), \
             patch("app.core.model_adapter.settings") as mock_env:
            mock_env.DEEPSEEK_API_KEY = "env-builtin-key"
            all_models = adapter.resolve_all()

        assert "deepseek-chat" in all_models, "deepseek-chat 应存在"
        config = all_models["deepseek-chat"]
        # CustomModel 应覆盖内置：api_key 是 custom-override-key 而非 env-builtin-key
        assert config.api_key == "custom-override-key", f"CustomModel 应覆盖，实际 key: {config.api_key}"
        assert config.api_base == "https://custom-endpoint.test/v1", "CustomModel 端点应覆盖"

    def test_custom_model_preserves_builtin_when_different_id(self):
        """CustomModel 不同 model_id 时，内置模型不受影响"""
        from app.core.model_adapter import ModelConfigAdapter
        adapter = ModelConfigAdapter()
        builtin_provider = _make_provider_def()

        fake_custom = _make_custom_model_orm("my-custom-model", api_key="custom-key")

        with patch("app.core.model_adapter._mp.PROVIDERS", (builtin_provider,)), \
             patch("app.core.model_adapter._mp.PROVIDER_MAP", {"deepseek": builtin_provider}), \
             patch.object(adapter, "_read_setting", return_value=""), \
             patch.object(adapter, "_custom_models", return_value=[fake_custom]), \
             patch("app.core.model_adapter.settings") as mock_env:
            mock_env.DEEPSEEK_API_KEY = "env-builtin-key"
            all_models = adapter.resolve_all()

        # 内置 deepseek-chat 仍用 env-builtin-key
        assert all_models["deepseek-chat"].api_key == "env-builtin-key"
        # 自定义 my-custom-model 用 custom-key
        assert all_models["my-custom-model"].api_key == "custom-key"

    def test_custom_model_empty_key_falls_through(self):
        """CustomModel.api_key 为空时，回退到 provider 的 key（env/settings）"""
        from app.core.model_adapter import ModelConfigAdapter
        adapter = ModelConfigAdapter()
        builtin_provider = _make_provider_def()

        # CustomModel 覆盖 deepseek-chat 但 api_key 为空
        fake_custom = _make_custom_model_orm("deepseek-chat", api_key="")

        with patch("app.core.model_adapter._mp.PROVIDERS", (builtin_provider,)), \
             patch("app.core.model_adapter._mp.PROVIDER_MAP", {"deepseek": builtin_provider}), \
             patch.object(adapter, "_read_setting", return_value=""), \
             patch.object(adapter, "_custom_models", return_value=[fake_custom]), \
             patch("app.core.model_adapter.settings") as mock_env:
            mock_env.DEEPSEEK_API_KEY = "env-key"
            all_models = adapter.resolve_all()

        config = all_models["deepseek-chat"]
        # 空 key 回退到 provider 的 key（settings 表 api_key_{id} > .env 的 {PROVIDER}_API_KEY）
        assert config.api_key == "env-key", "CustomModel 空 key 应回退到 provider key"

    def test_resolve_single_returns_override(self):
        """resolve_single 返回被覆盖的配置"""
        from app.core.model_adapter import ModelConfigAdapter
        adapter = ModelConfigAdapter()
        builtin_provider = _make_provider_def()
        fake_custom = _make_custom_model_orm("deepseek-chat", api_key="override-key")

        with patch("app.core.model_adapter._mp.PROVIDERS", (builtin_provider,)), \
             patch("app.core.model_adapter._mp.PROVIDER_MAP", {"deepseek": builtin_provider}), \
             patch.object(adapter, "_read_setting", return_value=""), \
             patch.object(adapter, "_custom_models", return_value=[fake_custom]), \
             patch("app.core.model_adapter.settings") as mock_env:
            mock_env.DEEPSEEK_API_KEY = "env-key"
            config = adapter.resolve_single("deepseek-chat")

        assert config is not None
        assert config.api_key == "override-key"

    def test_resolve_single_returns_none_for_unknown(self):
        """resolve_single 未找到模型 → 返回 None"""
        from app.core.model_adapter import ModelConfigAdapter
        adapter = ModelConfigAdapter()
        builtin_provider = _make_provider_def()

        with patch("app.core.model_adapter._mp.PROVIDERS", (builtin_provider,)), \
             patch("app.core.model_adapter._mp.PROVIDER_MAP", {"deepseek": builtin_provider}), \
             patch.object(adapter, "_read_setting", return_value=""), \
             patch.object(adapter, "_custom_models", return_value=[]), \
             patch("app.core.model_adapter.settings") as mock_env:
            mock_env.DEEPSEEK_API_KEY = ""
            config = adapter.resolve_single("nonexistent-model")

        assert config is None


# ──── 任务3：无 Key 状态 → ModelConfigError ────

class TestModelConfigError:
    """验证无 Key 状态下 ModelConfigError 正确抛出"""

    def test_call_once_no_key_raises_config_error(self):
        """call_once 无 Key → ModelConfigError（不再 ValueError）"""
        from app.services.model import ModelService, ModelConfigError

        svc = ModelService()
        # 找一个无 Key 的模型
        no_key_model = None
        for mid, cfg in svc.models.items():
            if not cfg.api_key:
                no_key_model = mid
                break

        if no_key_model is None:
            pytest.skip("所有模型都有 Key，无法测试无 Key 场景")

        with pytest.raises(ModelConfigError) as exc_info:
            asyncio.run(svc.call_once(
                model_id=no_key_model,
                messages=[{"role": "user", "content": "hi"}],
            ))
        assert "未配置 API Key" in str(exc_info.value) or "未注册" in str(exc_info.value)

    def test_stream_once_no_key_raises_config_error(self):
        """stream_once 无 Key → ModelConfigError（与 call_once 对齐）"""
        from app.services.model import ModelService, ModelConfigError

        svc = ModelService()
        no_key_model = None
        for mid, cfg in svc.models.items():
            if not cfg.api_key:
                no_key_model = mid
                break

        if no_key_model is None:
            pytest.skip("所有模型都有 Key")

        async def _collect():
            async for _ in svc.stream_once(
                model_id=no_key_model,
                messages=[{"role": "user", "content": "hi"}],
            ):
                pass

        with pytest.raises(ModelConfigError) as exc_info:
            asyncio.run(_collect())
        assert "未配置 API Key" in str(exc_info.value) or "未注册" in str(exc_info.value)

    def test_call_once_unknown_model_raises_config_error(self):
        """call_once 不存在的 model_id → ModelConfigError"""
        from app.services.model import ModelService, ModelConfigError

        svc = ModelService()
        with pytest.raises(ModelConfigError) as exc_info:
            asyncio.run(svc.call_once(
                model_id="definitely-not-exist-12345",
                messages=[{"role": "user", "content": "hi"}],
            ))
        assert "未注册" in str(exc_info.value)

    def test_stream_once_unknown_model_raises_config_error(self):
        """stream_once 不存在的 model_id → ModelConfigError"""
        from app.services.model import ModelService, ModelConfigError

        svc = ModelService()
        async def _collect():
            async for _ in svc.stream_once(
                model_id="definitely-not-exist-12345",
                messages=[{"role": "user", "content": "hi"}],
            ):
                pass

        with pytest.raises(ModelConfigError) as exc_info:
            asyncio.run(_collect())
        assert "未注册" in str(exc_info.value)

    def test_config_error_is_not_value_error(self):
        """ModelConfigError 不应被 except ValueError 捕获（专项异常隔离）"""
        from app.services.model import ModelConfigError

        # ModelConfigError 应该是独立的异常类，不是 ValueError 子类
        assert not issubclass(ModelConfigError, ValueError), \
            "ModelConfigError 不应是 ValueError 子类，否则会被旧 except ValueError 误捕"

    def test_config_error_is_not_model_not_found(self):
        """ModelConfigError 与 ModelNotFoundError 是不同的异常"""
        from app.services.model import ModelConfigError, ModelNotFoundError
        assert ModelConfigError is not ModelNotFoundError
        assert not issubclass(ModelConfigError, ModelNotFoundError)


# ──── 补充：provider_enum 兜底 ────

class TestProviderEnumFallback:
    """验证未知 provider_id 回落 OPENAI"""

    def test_known_provider_enum(self):
        """已知 provider_id 正确转枚举"""
        from app.core.model_adapter import ModelConfigAdapter
        from app.services.model import ModelProvider
        assert ModelConfigAdapter._provider_enum("deepseek") == ModelProvider.DEEPSEEK
        assert ModelConfigAdapter._provider_enum("qwen") == ModelProvider.QWEN

    def test_unknown_provider_falls_back_to_openai(self):
        """未知 provider_id → ModelProvider.OPENAI"""
        from app.core.model_adapter import ModelConfigAdapter
        from app.services.model import ModelProvider
        result = ModelConfigAdapter._provider_enum("unknown-xxx")
        assert result == ModelProvider.OPENAI


# ──── 补充：vision 能力检测 ────

class TestVisionDetection:
    """验证 _detect_supports_vision 启发式检测"""

    def test_vl_in_name_returns_true(self):
        from app.core.model_adapter import _detect_supports_vision
        assert _detect_supports_vision("qwen-vl-72b", False) is True
        assert _detect_supports_vision("qwen2-vl-instruct", False) is True

    def test_vision_keyword_returns_true(self):
        from app.core.model_adapter import _detect_supports_vision
        assert _detect_supports_vision("some-vision-model", False) is True

    def test_no_vision_keyword_falls_back_to_provider(self):
        from app.core.model_adapter import _detect_supports_vision
        assert _detect_supports_vision("deepseek-chat", True) is True   # provider 支持
        assert _detect_supports_vision("deepseek-chat", False) is False  # provider 不支持

    def test_empty_name_falls_back_to_provider(self):
        from app.core.model_adapter import _detect_supports_vision
        assert _detect_supports_vision("", True) is True
        assert _detect_supports_vision("", False) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
