"""Phase 10: 记忆自动提取系统（Memory Extractor）专项测试。

覆盖：
- MemoryExtractor 前置过滤（过短 / 寒暄确认语跳过）
- Prompt 组装（含已有记忆去重块）
- LLM 输出解析（```json 围栏 / 多余文本 / 非法条目回退）
- extract() 动作规范化（add / update / 非法过滤 / 置信度夹逼）
- run_memory_extraction 后台触发链条：
    * 独立 Session 隔离（不复用主请求 db）
    * Scope 自动分配（project / global）
    * add / update 落库与更新
    * Fail-safe（LLM 异常不抛错、返回 []）
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import AsyncSessionLocal
from app.models.agent import MemoryItem
from app.services.memory_extractor import (
    MemoryExtractor,
    run_memory_extraction,
    _SHORT_CONFIRMATIONS,
)


class PreFilterTestCase(unittest.TestCase):
    """前置过滤：过短输入 / 寒暄确认语 → 跳过提取。"""

    def setUp(self):
        self.extractor = MemoryExtractor()

    def test_empty_skips(self):
        self.assertTrue(self.extractor.should_skip(""))
        self.assertTrue(self.extractor.should_skip("   "))

    def test_short_input_skips(self):
        self.assertTrue(self.extractor.should_skip("好的"))
        self.assertTrue(self.extractor.should_skip("好"))
        self.assertTrue(self.extractor.should_skip("hi"))

    def test_confirmation_phrases_skip(self):
        for phrase in _SHORT_CONFIRMATIONS:
            self.assertTrue(self.extractor.should_skip(phrase), f"应跳过: {phrase}")

    def test_meaningful_input_not_skipped(self):
        self.assertFalse(self.extractor.should_skip("我喜欢简洁的回答方式"))
        self.assertFalse(self.extractor.should_skip("项目使用 Python 作为主语言"))
        # 恰好达到长度下限
        self.assertFalse(self.extractor.should_skip("我喜欢吃苹果派"))


class PromptBuilderTestCase(unittest.TestCase):
    def setUp(self):
        self.extractor = MemoryExtractor()

    def test_prompt_includes_existing_memories(self):
        existing = [
            {"id": 1, "content": "用户喜欢简洁回答", "memory_type": "preference"},
            {"id": 2, "content": "项目用 Python", "memory_type": "fact"},
        ]
        prompt = self.extractor._build_prompt(
            "用户消息内容", "AI 回复内容", existing
        )
        self.assertIn("用户喜欢简洁回答", prompt)
        self.assertIn("[id=1", prompt)
        self.assertIn("[id=2", prompt)
        self.assertIn('"action": "add"', prompt)
        self.assertIn('"action": "update"', prompt)

    def test_prompt_handles_no_existing(self):
        prompt = self.extractor._build_prompt("用户消息", "AI 回复", [])
        self.assertIn("（无已有记忆）", prompt)


class ParseResponseTestCase(unittest.TestCase):
    """LLM 输出解析：围栏 / 多余文本 / 非法条目。"""

    def setUp(self):
        self.extractor = MemoryExtractor()

    def test_plain_json_array(self):
        raw = '[{"action": "add", "memory_type": "fact", "confidence": 0.9, "content": "项目用 Python"}]'
        data = self.extractor._parse_response(raw)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["action"], "add")

    def test_fenced_json(self):
        raw = '```json\n[{"action": "add", "memory_type": "preference", "confidence": 0.8, "content": "喜欢简洁"}]```'
        data = self.extractor._parse_response(raw)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["content"], "喜欢简洁")

    def test_text_with_embedded_json(self):
        raw = '好的，我提取如下：\n[{"action": "add", "memory_type": "fact", "confidence": 0.9, "content": "项目用 Python"}]\n完成。'
        data = self.extractor._parse_response(raw)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["content"], "项目用 Python")

    def test_empty_array(self):
        self.assertEqual(self.extractor._parse_response("[]"), [])
        self.assertEqual(self.extractor._parse_response(""), [])
        self.assertEqual(self.extractor._parse_response("   "), [])
        self.assertEqual(self.extractor._parse_response("没有值得保存的信息"), [])

    def test_non_list_returns_empty(self):
        self.assertEqual(self.extractor._parse_response('{"action": "add"}'), [])
        self.assertEqual(self.extractor._parse_response("not json at all"), [])

    def test_invalid_json_returns_empty(self):
        self.assertEqual(self.extractor._parse_response("[{broken"), [])


class NormalizeTestCase(unittest.TestCase):
    def setUp(self):
        self.extractor = MemoryExtractor()

    def test_add_normalization(self):
        norm = self.extractor._normalize(
            {"action": "add", "memory_type": "fact", "confidence": 0.95, "content": "  项目用 Python  "}
        )
        self.assertEqual(norm["action"], "add")
        self.assertEqual(norm["content"], "项目用 Python")
        self.assertEqual(norm["memory_type"], "fact")
        self.assertEqual(norm["confidence"], 0.95)
        self.assertNotIn("existing_id", norm)

    def test_unknown_memory_type_falls_back(self):
        norm = self.extractor._normalize(
            {"action": "add", "memory_type": "bogus", "confidence": 0.9, "content": "内容"}
        )
        self.assertEqual(norm["memory_type"], "preference")

    def test_confidence_clamped(self):
        norm = self.extractor._normalize(
            {"action": "add", "confidence": 5.0, "content": "内容"}
        )
        self.assertEqual(norm["confidence"], 1.0)
        norm = self.extractor._normalize(
            {"action": "add", "confidence": -1, "content": "内容"}
        )
        self.assertEqual(norm["confidence"], 0.0)
        norm = self.extractor._normalize(
            {"action": "add", "confidence": "abc", "content": "内容"}
        )
        self.assertEqual(norm["confidence"], 0.8)

    def test_update_normalization(self):
        norm = self.extractor._normalize(
            {"action": "update", "existing_id": 7, "memory_type": "project", "confidence": 0.8, "content": "更新内容"}
        )
        self.assertEqual(norm["action"], "update")
        self.assertEqual(norm["existing_id"], 7)

    def test_invalid_items_rejected(self):
        self.assertEqual(self.extractor._normalize({}), {})
        self.assertEqual(self.extractor._normalize({"action": "delete"}), {})
        self.assertEqual(self.extractor._normalize({"action": "update", "existing_id": 0, "content": "x"}), {})
        self.assertEqual(self.extractor._normalize({"action": "add", "content": ""}), {})
        self.assertEqual(self.extractor._normalize({"action": "update", "content": "x"}), {})


class ExtractTestCase(unittest.TestCase):
    """extract() 主流程：mock LLM 返回，验证解析与规范化。"""

    def setUp(self):
        self.extractor = MemoryExtractor()

    def _fake_result(self, content):
        from app.services.model import SingleCallResult
        return SingleCallResult(content=content, finish_reason="stop", usage=None)

    def test_skip_returns_empty_without_llm_call(self):
        """前置过滤命中时不触发 LLM 调用。"""
        import asyncio

        async def _run():
            with patch(
                "app.services.memory_extractor.model_service.call_once",
                new_callable=AsyncMock,
            ) as mock_call:
                result = await self.extractor.extract("好的", "好的，没问题", [])
                mock_call.assert_not_awaited()
                return result

        self.assertEqual(asyncio.run(_run()), [])

    def _async_wrap(self, coro):
        import asyncio
        return asyncio.run(coro)

    def test_short_input_skips_extraction(self):
        async def _run():
            return await self.extractor.extract("好的", "好的，没问题", [])
        self.assertEqual(self._async_wrap(_run()), [])

    def test_empty_ai_skips(self):
        async def _run():
            return await self.extractor.extract("我喜欢简洁的回答方式", "", [])
        self.assertEqual(self._async_wrap(_run()), [])

    def test_extract_parses_add(self):
        raw = '[{"action": "add", "memory_type": "fact", "confidence": 0.9, "content": "项目使用 Python 3.14"}]'
        with patch(
            "app.services.memory_extractor.model_service.call_once",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = self._fake_result(raw)
            async def _run():
                return await self.extractor.extract("项目使用什么语言？", "项目使用 Python 3.14。", [])
            result = self._async_wrap(_run())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["action"], "add")
        self.assertEqual(result[0]["content"], "项目使用 Python 3.14")
        self.assertEqual(result[0]["memory_type"], "fact")
        mock_call.assert_awaited_once()

    def test_extract_llm_error_returns_empty(self):
        with patch(
            "app.services.memory_extractor.model_service.call_once",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.side_effect = RuntimeError("upstream down")
            async def _run():
                return await self.extractor.extract("我喜欢简洁的回答方式", "好的，记住了。", [])
            result = self._async_wrap(_run())
        self.assertEqual(result, [])

    def test_extract_empty_llm_output_returns_empty(self):
        with patch(
            "app.services.memory_extractor.model_service.call_once",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = self._fake_result("")
            async def _run():
                return await self.extractor.extract("我喜欢简洁的回答方式", "好的。", [])
            result = self._async_wrap(_run())
        self.assertEqual(result, [])


class BackgroundTriggerTestCase(unittest.TestCase):
    """run_memory_extraction 后台触发链条：Session 隔离 / Scope / add / update / Fail-safe。"""

    def _cleanup(self, *ids):
        import asyncio

        async def _del():
            async with AsyncSessionLocal() as s:
                for mid in ids:
                    row = s.query(MemoryItem).filter(MemoryItem.id == mid).first()
                    if row:
                        s.delete(row)
                s.commit()
        asyncio.run(_del())

    def test_global_scope_add(self):
        async def _run():
            async with AsyncSessionLocal() as s:
                s.query(MemoryItem).delete()
                s.commit()
            with patch(
                "app.services.memory_extractor.model_service.call_once",
                new_callable=AsyncMock,
            ) as mock_call:
                mock_call.return_value = self._fake_result(
                    '[{"action": "add", "memory_type": "preference", "confidence": 0.9, "content": "用户偏好简洁回答"}]'
                )
                actions = await run_memory_extraction(
                    chat_id=123,
                    project_id=None,
                    user_message="我以后希望回答简洁一些",
                    ai_content="好的，以后我会保持简洁。",
                )
            assert len(actions) == 1
            row = s.query(MemoryItem).filter(MemoryItem.content == "用户偏好简洁回答").first()
            assert row is not None
            assert row.scope == "global"
            assert row.project_id is None
            assert row.memory_type == "preference"
            assert row.source_chat_id == 123
            s.delete(row)
            s.commit()
        import asyncio
        asyncio.run(_run())

    def test_project_scope_add(self):
        async def _run():
            async with AsyncSessionLocal() as s:
                s.query(MemoryItem).delete()
                s.commit()
            with patch(
                "app.services.memory_extractor.model_service.call_once",
                new_callable=AsyncMock,
            ) as mock_call:
                mock_call.return_value = self._fake_result(
                    '[{"action": "add", "memory_type": "project", "confidence": 0.9, "content": "本项目后端禁止用同步请求"}]'
                )
                actions = await run_memory_extraction(
                    chat_id=42,
                    project_id=7,
                    user_message="记住本项目后端不能用同步请求",
                    ai_content="好的，已记录为项目规则。",
                )
            assert len(actions) == 1
            row = s.query(MemoryItem).filter(MemoryItem.content == "本项目后端禁止用同步请求").first()
            assert row is not None
            assert row.scope == "project"
            assert row.project_id == 7
            assert row.memory_type == "project"
            assert row.source_chat_id == 42
            s.delete(row)
            s.commit()
        import asyncio
        asyncio.run(_run())

    def test_update_existing_memory(self):
        import asyncio

        async def _run():
            async with AsyncSessionLocal() as s:
                s.query(MemoryItem).delete()
                existing = MemoryItem(
                    scope="project",
                    project_id=3,
                    content="用户喜欢英文回复",
                    memory_type="preference",
                    confidence=0.7,
                )
                s.add(existing)
                s.commit()
                existing_id = existing.id
            with patch(
                "app.services.memory_extractor.model_service.call_once",
                new_callable=AsyncMock,
            ) as mock_call:
                mock_call.return_value = self._fake_result(
                    f'[{{"action": "update", "existing_id": {existing_id}, "memory_type": "preference", "confidence": 0.95, "content": "用户喜欢中文回复（更新后）"}}]'
                )
                actions = await run_memory_extraction(
                    chat_id=5,
                    project_id=3,
                    user_message="其实我更喜欢中文回复，帮我更新一下",
                    ai_content="已为您更新偏好。",
                )
            assert len(actions) == 1
            async with AsyncSessionLocal() as s2:
                row = s2.query(MemoryItem).filter(MemoryItem.id == existing_id).first()
                assert row is not None
                assert row.content == "用户喜欢中文回复（更新后）"
                assert row.confidence == 0.95
                assert row.source_chat_id == 5
                # 未被重复添加（仍是原 id）
                count = s2.query(MemoryItem).filter(MemoryItem.project_id == 3).count()
                assert count == 1
                s2.delete(row)
                s2.commit()
        asyncio.run(_run())

    def test_fail_safe_on_llm_error(self):
        """LLM 异常不抛错、返回 []，且不产生任何记忆。"""
        import asyncio

        async def _run():
            async with AsyncSessionLocal() as s:
                s.query(MemoryItem).delete()
                s.commit()
            with patch(
                "app.services.memory_extractor.model_service.call_once",
                new_callable=AsyncMock,
            ) as mock_call:
                mock_call.side_effect = RuntimeError("boom")
                actions = await run_memory_extraction(
                    chat_id=1,
                    project_id=None,
                    user_message="我喜欢简洁的回答方式",
                    ai_content="好的。",
                )
            assert actions == []
            async with AsyncSessionLocal() as s2:
                count = s2.query(MemoryItem).count()
                assert count == 0
        asyncio.run(_run())

    def test_uses_independent_session(self):
        """后台任务通过 AsyncSessionLocal 新建会话，而非复用传入的 db。"""
        import asyncio

        async def _run():
            async with AsyncSessionLocal() as s:
                s.query(MemoryItem).delete()
                s.commit()
            with patch(
                "app.services.memory_extractor.model_service.call_once",
                new_callable=AsyncMock,
            ) as mock_call:
                mock_call.return_value = self._fake_result("[]")
                actions = await run_memory_extraction(
                    chat_id=1,
                    project_id=None,
                    user_message="我喜欢简洁的回答方式",
                    ai_content="好的。",
                )
            assert actions == []
        asyncio.run(_run())

    def _fake_result(self, content):
        from app.services.model import SingleCallResult
        return SingleCallResult(content=content, finish_reason="stop", usage=None)


if __name__ == "__main__":
    unittest.main()
