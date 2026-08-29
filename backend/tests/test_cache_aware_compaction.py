"""T9 缓存友好压缩回归测试：摘要调用复用主对话前缀 + 摘要自批评（单轮有界）。

运行：python backend/tests/test_cache_aware_compaction.py
退出码：0 = 全部通过；1 = 存在失败。

验收点（工单 T9）：
  1. 开关开启时，摘要调用以完整对话列表为前缀 + 追加 1 条摘要指令 user 消息
     （前缀与主循环上一轮请求逐字节一致 → 命中 provider 前缀缓存）。
  2. 调用方 messages / DB 历史消息零改动（只改发往 LLM 的副本）。
  3. 自批评恰好 1 轮（不做摘要链）：修订被采用 / "OK" 保留 v1 / 失败保留 v1。
  4. 开关关闭（cache_aware_compaction_enabled=false）→ 恢复旧路径：
     独立两条消息 prompt、只发 middle 拼接、无自批评调用。
  5. 自动压缩链路端到端不被破坏（_maybe_auto_compress → 压缩生效）。
"""
import asyncio
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
# 直接运行兜底：与 conftest 同一独立测试库（pytest 下 conftest 已先设置，此处为 no-op）
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite:///{(Path(__file__).resolve().parent / 'mfkagent_test.db').as_posix()}",
)

from app.core.agent_runtime.agent import AgentRuntime, is_cache_aware_compaction_enabled
from app.core import database as database_module
from app.services.model import model_service

AGENT_MODULE = "app.core.agent_runtime.agent"


def _messages(n=20, system_head=2):
    """system 头 + n 条对话消息，模拟超长历史。"""
    msgs = [{"role": "system", "content": f"system {i}"} for i in range(system_head)]
    for i in range(n):
        msgs.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i} " + "x" * 200})
    return msgs


def _result(content):
    return SimpleNamespace(content=content)


class CacheAwareCompactionTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime = AgentRuntime()

    # ──── 1. 摘要调用复用主对话前缀 ────

    def test_summary_call_reuses_conversation_prefix(self):
        msgs = _messages()
        snapshot = [dict(m) for m in msgs]
        mock_call = AsyncMock(side_effect=[_result("摘要v1"), _result("OK")])
        with patch.object(model_service, "call_once", mock_call), \
             patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=True):
            out = asyncio.run(self.runtime.compress_history(msgs, model_id="deepseek-chat"))

        self.assertEqual(mock_call.await_count, 2)
        first = mock_call.await_args_list[0].args[1]
        # 前缀 = 完整对话原样 + 1 条摘要指令
        self.assertEqual(len(first), len(msgs) + 1)
        for got, orig in zip(first, msgs):
            self.assertEqual(got, orig)
        instruction = first[-1]
        self.assertEqual(instruction["role"], "user")
        self.assertIn("除最后4条消息之外", instruction["content"])
        self.assertIn("500", instruction["content"])
        # 调用方列表零改动（绝不改 DB 历史消息）
        self.assertEqual(msgs, snapshot)
        # 返回形状不变：head(2) + memory 节点 + recent(4)；自批评回 OK → 保留 v1
        self.assertEqual(len(out), 2 + 1 + 4)
        self.assertIn("【历史记忆摘要】", out[2]["content"])
        self.assertIn("摘要v1", out[2]["content"])

    # ──── 2. 摘要自批评：修订被采用 ────

    def test_self_critique_refines_summary(self):
        msgs = _messages()
        mock_call = AsyncMock(side_effect=[_result("摘要v1"), _result("修订版摘要v2")])
        with patch.object(model_service, "call_once", mock_call), \
             patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=True):
            out = asyncio.run(self.runtime.compress_history(msgs, model_id="deepseek-chat"))

        self.assertEqual(mock_call.await_count, 2)
        second = mock_call.await_args_list[1].args[1]
        # 自批评调用 = 同一前缀 + 摘要指令 + assistant(v1) + 自批评指令
        self.assertEqual(len(second), len(msgs) + 3)
        self.assertEqual(second[-2], {"role": "assistant", "content": "摘要v1"})
        self.assertEqual(second[-1]["role"], "user")
        self.assertIn("自检", second[-1]["content"])
        # 修订版被采用
        self.assertIn("修订版摘要v2", out[2]["content"])

    # ──── 3. 自批评有界：无修订 / 短变体 / 失败 / 失控均保留 v1 ────

    def test_self_critique_ok_keeps_v1(self):
        msgs = _messages()
        mock_call = AsyncMock(side_effect=[_result("摘要v1"), _result("OK")])
        with patch.object(model_service, "call_once", mock_call), \
             patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=True):
            out = asyncio.run(self.runtime.compress_history(msgs, model_id="deepseek-chat"))
        self.assertEqual(mock_call.await_count, 2)
        self.assertIn("摘要v1", out[2]["content"])

    def test_self_critique_ok_variant_keeps_v1(self):
        """“OK，无缺漏。”等短变体不得被误当成修订版写进摘要。"""
        msgs = _messages()
        mock_call = AsyncMock(side_effect=[_result("摘要v1"), _result("OK，无缺漏。")])
        with patch.object(model_service, "call_once", mock_call), \
             patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=True):
            out = asyncio.run(self.runtime.compress_history(msgs, model_id="deepseek-chat"))
        self.assertIn("摘要v1", out[2]["content"])
        self.assertNotIn("OK", out[2]["content"])

    def test_self_critique_failure_keeps_v1(self):
        msgs = _messages()
        mock_call = AsyncMock(side_effect=[_result("摘要v1"), RuntimeError("critique timeout")])
        with patch.object(model_service, "call_once", mock_call), \
             patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=True):
            out = asyncio.run(self.runtime.compress_history(msgs, model_id="deepseek-chat"))
        self.assertEqual(mock_call.await_count, 2)
        self.assertIn("摘要v1", out[2]["content"])

    def test_self_critique_runaway_revision_rejected(self):
        """修订版超长（>4x 字数约束）视为输出失控，保留 v1。"""
        msgs = _messages()
        mock_call = AsyncMock(side_effect=[_result("摘要v1"), "长" * 2001])
        with patch.object(model_service, "call_once", mock_call), \
             patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=True):
            out = asyncio.run(self.runtime.compress_history(msgs, model_id="deepseek-chat"))
        self.assertIn("摘要v1", out[2]["content"])

    # ──── 4. 回滚开关：关闭 = 旧路径 ────

    def test_switch_off_restores_legacy_path(self):
        msgs = _messages()
        mock_call = AsyncMock(side_effect=[_result("旧路径摘要")])
        with patch.object(model_service, "call_once", mock_call), \
             patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=False):
            out = asyncio.run(self.runtime.compress_history(msgs, model_id="deepseek-chat"))
        self.assertEqual(mock_call.await_count, 1)  # 旧路径无自批评
        legacy = mock_call.await_args_list[0].args[1]
        self.assertEqual(len(legacy), 2)
        self.assertEqual(legacy[0]["role"], "system")
        self.assertIn("会话压缩引擎", legacy[0]["content"])
        self.assertEqual(legacy[1]["role"], "user")
        self.assertTrue(legacy[1]["content"].startswith("user: msg 0"))  # middle 段拼接
        self.assertIn("【历史记忆摘要】", out[2]["content"])

    # ──── 5. 开关 helper：settings 表读取惯例（灰度默认关 / true 灰度开）────

    def test_switch_helper_reads_settings_table(self):
        cases = [
            (None, False),                             # 无行 → 灰度默认关
            (SimpleNamespace(value=None), False),
            (SimpleNamespace(value="false"), False),
            (SimpleNamespace(value="0"), False),
            (SimpleNamespace(value="garbage"), False),  # 非法值按默认关
            (SimpleNamespace(value="true"), True),      # 灰度开启
            (SimpleNamespace(value="1"), True),
            (SimpleNamespace(value="on"), True),
            (SimpleNamespace(value="yes"), True),
        ]
        for row, expected in cases:
            with self.subTest(row=row):
                fake_db = MagicMock()
                fake_db.query.return_value.filter.return_value.first.return_value = row
                with patch.object(database_module, "SessionLocal", return_value=fake_db):
                    self.assertEqual(is_cache_aware_compaction_enabled(), expected)

    def test_switch_helper_defaults_off_when_db_unavailable(self):
        with patch.object(database_module, "SessionLocal", side_effect=RuntimeError("db down")):
            self.assertFalse(is_cache_aware_compaction_enabled())

    # ──── 6. 自动压缩链路端到端 ────

    def test_auto_compress_end_to_end_cache_aware(self):
        msgs = _messages(n=20, system_head=0)
        mock_call = AsyncMock(side_effect=[_result("端到端摘要"), _result("OK")])
        # 按当前模型上限自适应取 90% 水位（max_tokens 配置漂移不影响触发）
        from app.core.agent_runtime.model_context_config import get_model_max_tokens
        prompt_tokens = int(get_model_max_tokens("deepseek-chat") * 0.9)
        with patch.object(model_service, "call_once", mock_call), \
             patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=True):
            ok = asyncio.run(self.runtime._maybe_auto_compress(
                run_id="r9", messages=msgs,
                usage={"prompt_tokens": prompt_tokens}, model_id="deepseek-chat",
            ))
        self.assertTrue(ok)
        self.assertEqual(len(msgs), 1 + 4)  # memory 节点 + recent
        self.assertIn("端到端摘要", msgs[0]["content"])
        # 摘要调用复用主对话前缀：完整 20 条 + 1 条指令
        first = mock_call.await_args_list[0].args[1]
        self.assertEqual(len(first), 20 + 1)


if __name__ == "__main__":
    unittest.main()
