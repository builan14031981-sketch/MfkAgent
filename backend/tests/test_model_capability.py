"""自定义动态模型能力适配与 API 404 熔断兜底 专项测试。

覆盖：
- _detect_supports_vision：模型名含 vl/vision → True，否则回退 provider 级
- ModelConfig.supports_vision / supports_tools 字段正确填充
- _check_model_not_found：404 / 400+关键词 → ModelNotFoundError
- _upstream_error_message：友好错误消息
- run_stream yield error 事件验证
- 完整流程：自定义模型 → API 404 → 友好错误提示
"""
import sys
import os
import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.model import (
    ModelConfig,
    ModelNotFoundError,
    ModelProvider,
    ModelService,
    _detect_supports_vision,
    _provider_supports_vision,
)
from app.core.model_providers import PROVIDER_MAP


# ──── _detect_supports_vision 单元测试 ────

class TestDetectSupportsVision(unittest.TestCase):
    """模型名启发式能力检测。"""

    def test_vl_in_name(self):
        """模型名含 'vl' → True。"""
        self.assertTrue(_detect_supports_vision("qwen3-vl-32b-thinking", False))
        self.assertTrue(_detect_supports_vision("Qwen3-VL-235B", False))
        self.assertTrue(_detect_supports_vision("llava-vl-7b", False))

    def test_vision_in_name(self):
        """模型名含 'vision' → True。"""
        self.assertTrue(_detect_supports_vision("gpt-4-vision-preview", False))
        self.assertTrue(_detect_supports_vision("VisionModel", False))
        self.assertTrue(_detect_supports_vision("my-vision-model", False))

    def test_no_vision_keyword_fallback_false(self):
        """无关键词 + provider 不支持 → False。"""
        self.assertFalse(_detect_supports_vision("qwen-flash", False))
        self.assertFalse(_detect_supports_vision("deepseek-chat", False))
        self.assertFalse(_detect_supports_vision("mimo-v2.5", False))

    def test_no_vision_keyword_fallback_true(self):
        """无关键词 + provider 支持 → True（provider 级回退）。"""
        self.assertTrue(_detect_supports_vision("qwen-flash", True))
        self.assertTrue(_detect_supports_vision("some-model", True))

    def test_empty_name(self):
        """空模型名 → 回退到 provider 级。"""
        self.assertFalse(_detect_supports_vision("", False))
        self.assertTrue(_detect_supports_vision("", True))


# ──── ModelConfig 能力字段测试 ────

class TestModelConfigCapabilities(unittest.TestCase):
    """ModelConfig 的 supports_vision / supports_tools 字段。"""

    def test_default_values(self):
        """ModelConfig 默认值：supports_vision=False, supports_tools=True。"""
        cfg = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="test-model",
            api_key="sk-test",
            api_base="https://api.example.com/v1",
        )
        self.assertFalse(cfg.supports_vision)
        self.assertTrue(cfg.supports_tools)

    def test_explicit_vision_true(self):
        """显式设置 supports_vision=True。"""
        cfg = ModelConfig(
            provider=ModelProvider.QWEN,
            model_name="qwen3-vl-32b",
            api_key="sk-test",
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            supports_vision=True,
        )
        self.assertTrue(cfg.supports_vision)

    def test_explicit_tools_false(self):
        """显式设置 supports_tools=False。"""
        cfg = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="no-tools-model",
            api_key="sk-test",
            api_base="https://api.example.com/v1",
            supports_tools=False,
        )
        self.assertFalse(cfg.supports_tools)


# ──── _init_models 能力填充测试 ────

class TestInitModelsCapabilities(unittest.TestCase):
    """_init_models 正确填充能力字段。"""

    def setUp(self):
        from app.core.database import SessionLocal, engine, Base
        Base.metadata.create_all(bind=engine)

    def test_vl_model_gets_vision(self):
        """VL 模型自动识别 supports_vision=True。"""
        from app.services.model import model_service
        cfg = model_service.get_model_config("qwen3-vl-32b-thinking")
        if cfg:
            self.assertTrue(cfg.supports_vision)
            self.assertTrue(cfg.supports_tools)

    def test_non_vl_model_no_vision(self):
        """非 VL 模型 supports_vision=False（除非 provider 支持）。"""
        from app.services.model import model_service
        cfg = model_service.get_model_config("mimo-v2.5")
        if cfg:
            self.assertFalse(cfg.supports_vision)
            self.assertTrue(cfg.supports_tools)

    def test_qwen_provider_models_vision_inheritance(self):
        """Qwen provider supports_vision=False（粒度下沉到 Model 级），
        非 VL 模型 qwen-flash → supports_vision=False。
        
        注意：_detect_supports_vision 三级优先级：
        1. 模型级显式指定（非 None）→ 直接使用
        2. 命名推测（含 vl/vision）→ True
        3. 回退 provider 级 → 当前 qwen=False
        qwen-flash 无显式标记 + 命名不匹配 + provider 级 False → False
        """
        from app.services.model import model_service
        cfg = model_service.get_model_config("qwen-flash")
        if cfg:
            # qwen provider supports_vision=False，qwen-flash 不含 vl/vision → 回退 False
            self.assertFalse(cfg.supports_vision)

    def test_all_models_have_tools_true(self):
        """所有模型 supports_tools 默认 True。"""
        from app.services.model import model_service
        for model_id, cfg in model_service.models.items():
            self.assertTrue(
                cfg.supports_tools,
                f"模型 {model_id} 的 supports_tools 应为 True",
            )


# ──── _check_model_not_found 测试 ────

class TestCheckModelNotFound(unittest.TestCase):
    """404 / Model Not Found 熔断检测。"""

    def test_404_raises_model_not_found(self):
        """HTTP 404 → ModelNotFoundError。"""
        with self.assertRaises(ModelNotFoundError) as ctx:
            ModelService._check_model_not_found(404, '{"error": "not found"}', "my-model")
        self.assertIn("my-model", str(ctx.exception))
        self.assertIn("请在设置中检查", str(ctx.exception))

    def test_400_with_model_not_found_keyword(self):
        """HTTP 400 + 'model not found' → ModelNotFoundError。"""
        with self.assertRaises(ModelNotFoundError):
            ModelService._check_model_not_found(400, '{"error": "Model not found"}', "test-model")

    def test_400_with_invalid_model_keyword(self):
        """HTTP 400 + 'invalid model' → ModelNotFoundError。"""
        with self.assertRaises(ModelNotFoundError):
            ModelService._check_model_not_found(400, '{"error": "Invalid model ID"}', "bad-model")

    def test_422_with_does_not_exist(self):
        """HTTP 422 + 'does not exist' → ModelNotFoundError。"""
        with self.assertRaises(ModelNotFoundError):
            ModelService._check_model_not_found(422, '{"error": "Model does not exist"}', "no-model")

    def test_500_does_not_raise_model_not_found(self):
        """HTTP 500 → 不触发 ModelNotFoundError（不 raise）。"""
        # 不应抛出任何异常
        ModelService._check_model_not_found(500, "Internal Server Error", "my-model")

    def test_400_without_keyword_does_not_raise(self):
        """HTTP 400 但无关键词 → 不触发 ModelNotFoundError。"""
        ModelService._check_model_not_found(400, '{"error": "Rate limit exceeded"}', "my-model")

    def test_200_does_not_raise(self):
        """HTTP 200 → 不触发。"""
        ModelService._check_model_not_found(200, "", "my-model")

    def test_friendly_message_format(self):
        """ModelNotFoundError 消息格式正确。"""
        with self.assertRaises(ModelNotFoundError) as ctx:
            ModelService._check_model_not_found(404, "", "qwen-max")
        msg = str(ctx.exception)
        self.assertIn("qwen-max", msg)
        self.assertIn("服务商未找到模型", msg)
        self.assertIn("请在设置中检查 Model ID 是否正确", msg)


# ──── _upstream_error_message 测试 ────

class TestUpstreamErrorMessage(unittest.TestCase):
    """_upstream_error_message 友好化。"""

    def test_extract_error_message(self):
        """从 JSON 中提取 error.message。"""
        raw = '{"error": {"message": "Rate limit exceeded", "type": "rate_limit"}}'
        msg = ModelService._upstream_error_message(429, raw)
        self.assertIn("429", msg)
        self.assertIn("Rate limit exceeded", msg)

    def test_503_queue_full_hint(self):
        """503 队列满附加中文提示。"""
        raw = '{"error": {"message": "upstream queue is full"}}'
        msg = ModelService._upstream_error_message(503, raw)
        self.assertIn("上游队列繁忙", msg)

    def test_non_json_fallback(self):
        """非 JSON 响应 → 截断原文。"""
        raw = "Internal Server Error - Something went wrong"
        msg = ModelService._upstream_error_message(500, raw)
        self.assertIn("500", msg)
        self.assertIn(raw[:50], msg)


# ──── run_stream yield error 事件测试 ────

class TestRunStreamErrorYield(unittest.TestCase):
    """run_stream 在异常时 yield error 事件。"""

    def test_error_event_yielded_on_exception(self):
        """run_stream 捕获异常时 yield {"type": "error", ...} 事件。"""
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context import AgentContext

        # Mock context
        ctx = MagicMock(spec=AgentContext)
        ctx.chat_id = 1
        ctx.agent_id = 1
        ctx.model_id = "test-model"
        ctx.metadata = {}

        runtime = AgentRuntime()

        # Mock _run_stream_events to raise an exception
        async def _mock_events(*args, **kwargs):
            yield {"type": "text", "content": "partial"}
            raise RuntimeError("LLM service unavailable")
            yield  # never reached

        with patch.object(runtime, "_run_stream_events", _mock_events):
            events = []

            async def _collect():
                try:
                    async for event in runtime.run_stream(
                        context=ctx,
                        messages=[{"role": "user", "content": "test"}],
                    ):
                        events.append(event)
                except RuntimeError:
                    pass  # run_stream re-raises after yield

            asyncio.run(_collect())

        # Should have: text event, then error event
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["type"], "text")
        self.assertEqual(events[1]["type"], "error")
        self.assertIn("LLM service unavailable", events[1]["message"])

    def test_model_not_found_error_yielded(self):
        """ModelNotFoundError 被正确 yield 为 error 事件。"""
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context import AgentContext

        ctx = MagicMock(spec=AgentContext)
        ctx.chat_id = 2
        ctx.agent_id = 1
        ctx.model_id = "nonexistent-model"
        ctx.metadata = {}

        runtime = AgentRuntime()

        async def _mock_events(*args, **kwargs):
            raise ModelNotFoundError(
                "服务商未找到模型 [nonexistent-model]，请在设置中检查 Model ID 是否正确。"
            )
            yield  # never reached, but needed for async generator

        with patch.object(runtime, "_run_stream_events", _mock_events):
            events = []

            async def _collect():
                try:
                    async for event in runtime.run_stream(
                        context=ctx,
                        messages=[{"role": "user", "content": "test"}],
                    ):
                        events.append(event)
                except ModelNotFoundError:
                    pass

            asyncio.run(_collect())

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "error")
        self.assertIn("nonexistent-model", events[0]["message"])
        self.assertIn("请在设置中检查", events[0]["message"])


# ──── call_once 404 熔断集成测试 ────

class TestCallOnceModelNotFound(unittest.TestCase):
    """call_once 遇到 404 → ModelNotFoundError。"""

    def test_call_once_404_raises_model_not_found(self):
        """call_once 遇到 HTTP 404 → 抛出 ModelNotFoundError。"""
        from app.services.model import model_service

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = '{"error": {"message": "Model not found"}}'

        with patch("app.services.model.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with self.assertRaises(ModelNotFoundError) as ctx:
                asyncio.run(model_service.call_once(
                    model_id="qwen-flash",
                    messages=[{"role": "user", "content": "hi"}],
                ))

            self.assertIn("qwen-flash", str(ctx.exception))

    def test_stream_once_404_raises_model_not_found(self):
        """stream_once 遇到 HTTP 404 → 抛出 ModelNotFoundError。"""
        from app.services.model import model_service

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.aread = AsyncMock(return_value=b'{"error": "not found"}')

        # stream_once uses client.stream() context manager
        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        mock_client.stream = MagicMock(return_value=mock_stream_ctx)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("app.services.model.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value = mock_client

            with self.assertRaises(ModelNotFoundError) as ctx:
                async def _collect():
                    async for _ in model_service.stream_once(
                        model_id="qwen-flash",
                        messages=[{"role": "user", "content": "hi"}],
                    ):
                        pass
                asyncio.run(_collect())

            self.assertIn("qwen-flash", str(ctx.exception))


# ──── 自定义模型平滑发起请求测试 ────

class TestCustomModelSmoothRequest(unittest.TestCase):
    """自定义 Model ID 能平滑发起 API 请求（不因能力缺失而报错）。"""

    def test_custom_model_config_has_capabilities(self):
        """自定义模型 ModelConfig 有能力字段。"""
        from app.core.database import SessionLocal, engine, Base
        from app.models.agent import CustomModel
        Base.metadata.create_all(bind=engine)

        db = SessionLocal()
        try:
            # 清理可能存在的测试数据
            existing = db.query(CustomModel).filter(CustomModel.model_id == "test-custom-vl").first()
            if existing:
                db.delete(existing)
                db.commit()

            cm = CustomModel(
                model_id="test-custom-vl",
                name="Test Custom VL",
                provider="openai",
                model_name="test-custom-vl",
                api_base="https://api.example.com/v1",
                api_key="sk-test",
                max_tokens=4096,
                temperature=0.7,
                enabled=True,
            )
            db.add(cm)
            db.commit()

            from app.services.model import ModelService
            ms = ModelService()
            cfg = ms.get_model_config("test-custom-vl")
            self.assertIsNotNone(cfg)
            # VL 在模型名中 → supports_vision=True
            self.assertTrue(cfg.supports_vision)
            self.assertTrue(cfg.supports_tools)

            # 清理
            db.delete(cm)
            db.commit()
        finally:
            db.close()

    def test_non_vl_custom_model(self):
        """非 VL 自定义模型 → supports_vision=False。"""
        from app.core.database import SessionLocal, engine, Base
        from app.models.agent import CustomModel
        Base.metadata.create_all(bind=engine)

        db = SessionLocal()
        try:
            existing = db.query(CustomModel).filter(CustomModel.model_id == "test-plain-model").first()
            if existing:
                db.delete(existing)
                db.commit()

            cm = CustomModel(
                model_id="test-plain-model",
                name="Test Plain",
                provider="openai",
                model_name="test-plain-model",
                api_base="https://api.example.com/v1",
                api_key="sk-test",
                max_tokens=4096,
                temperature=0.7,
                enabled=True,
            )
            db.add(cm)
            db.commit()

            from app.services.model import ModelService
            ms = ModelService()
            cfg = ms.get_model_config("test-plain-model")
            self.assertIsNotNone(cfg)
            self.assertFalse(cfg.supports_vision)
            self.assertTrue(cfg.supports_tools)

            db.delete(cm)
            db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
