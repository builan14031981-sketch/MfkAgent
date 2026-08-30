"""Phase H 自动压缩自动化验证：50% 水位触发 / LLM 摘要优先 / 降级规则截断。

运行：python backend/tests/test_auto_compress_phase_h.py
退出码：0 = 全部通过；1 = 存在失败。
"""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.agent_runtime.agent import (
    AgentRuntime,
    COMPRESS_WATERMARK_THRESHOLD,
    MAX_STREAM_ROUNDS,
)
from app.core.agent_runtime.model_context_config import compute_watermark


def _messages(n=20):
    """n 条对话消息（无 system），模拟超长历史。"""
    msgs = []
    for i in range(n):
        msgs.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i} " + "x" * 200})
    return msgs


class AutoCompressPhaseHTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime = AgentRuntime()

    # ──── 阈值与水位计算 ────

    def test_threshold_is_50(self):
        """Phase H 决策：压缩水位阈值 = 50%（非 60%）。"""
        self.assertEqual(COMPRESS_WATERMARK_THRESHOLD, 50.0)

    def test_watermark_below(self):
        self.assertLess(compute_watermark(5000, "deepseek-chat"), 50.0)

    def test_watermark_above(self):
        # deepseek 系当前 context_window=1048576（model_context_config → model_providers
        # ProviderModel.context_window），50% 阈值 ≈ 524288；600000 已越过 50%。
        self.assertGreater(compute_watermark(600000, "deepseek-chat"), 50.0)

    # ──── 触发 / 不触发 ────

    def test_below_threshold_no_compress(self):
        async def go():
            msgs = _messages(3)
            ok = await self.runtime._maybe_auto_compress(
                run_id="r1", messages=msgs, usage={"prompt_tokens": 5000}, model_id="deepseek-chat"
            )
            return ok, msgs

        ok, msgs = asyncio.run(go())
        self.assertFalse(ok)
        self.assertEqual(len(msgs), 3)

    def test_above_threshold_compresses_llm_path(self):
        async def go():
            msgs = _messages(20)
            compressed = _messages(4)
            self.runtime.compress_history = AsyncMock(return_value=compressed)
            ok = await self.runtime._maybe_auto_compress(
                run_id="r1", messages=msgs, usage={"prompt_tokens": 600000}, model_id="deepseek-chat"
            )
            return ok, msgs

        ok, msgs = asyncio.run(go())
        self.assertTrue(ok)
        self.assertEqual(len(msgs), 4)

    def test_llm_fails_falls_back_to_truncate(self):
        async def go():
            msgs = _messages(20)
            self.runtime.compress_history = AsyncMock(return_value=msgs)  # 未生效 → 降级
            ok = await self.runtime._maybe_auto_compress(
                run_id="r1", messages=msgs, usage={"prompt_tokens": 600000}, model_id="deepseek-chat"
            )
            return ok, msgs

        ok, msgs = asyncio.run(go())
        self.assertTrue(ok)
        self.assertLess(len(msgs), 20)  # 降级截断生效
        self.assertIn("历史截断摘要", msgs[0]["content"])

    def test_both_fail_no_compress(self):
        async def go():
            msgs = _messages(3)  # 仅 3 条，降级也拒绝（rest<=keep_recent 或 middle<4）
            self.runtime.compress_history = AsyncMock(return_value=msgs)
            ok = await self.runtime._maybe_auto_compress(
                run_id="r1", messages=msgs, usage={"prompt_tokens": 150000}, model_id="deepseek-chat"
            )
            return ok, msgs

        ok, msgs = asyncio.run(go())
        self.assertFalse(ok)
        self.assertEqual(len(msgs), 3)

    def test_no_usage_no_compress(self):
        async def go():
            msgs = _messages(5)
            ok = await self.runtime._maybe_auto_compress(
                run_id="r1", messages=msgs, usage=None, model_id="deepseek-chat"
            )
            return ok

        self.assertFalse(asyncio.run(go()))

    # ──── 规则截断 fallback 细节 ────

    def test_truncate_fallback_preserves_system_and_recent(self):
        msgs = [{"role": "system", "content": "SYS"}] + _messages(12)
        out = self.runtime._truncate_history_fallback(msgs)
        self.assertEqual(out[0]["role"], "system")
        self.assertIn("历史截断摘要", out[1]["content"])
        self.assertIn("msg 11", out[-1]["content"])  # 最近消息保留
        self.assertEqual(len(out), 2 + 4)  # system + 摘要 + keep_recent=4

    def test_truncate_fallback_short_history_unchanged(self):
        msgs = _messages(4)
        self.assertIs(self.runtime._truncate_history_fallback(msgs), msgs)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AutoCompressPhaseHTestCase)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
