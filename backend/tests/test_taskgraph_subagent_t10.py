"""T10 任务图 × 子代理委托 回归测试（分支 feat/t10-taskgraph-subagent）。

运行：python backend/tests/test_taskgraph_subagent_t10.py
退出码：0 = 全部通过；1 = 存在失败。

验收点（工单 T10）：
  1. 委托后主上下文不含子任务完整输出（只含 runtime_context 回注的摘要，
     子代理完整输出中的尾部哨兵标记不得出现在主循环任何消息中）。
  2. 并行模式：无依赖就绪节点并发执行（in-flight 峰值 ≥ 2）；
     有依赖节点等待上游 completed 后才启动。
  3. 默认串行（开关缺省关闭）行为与现状一致：不委托、逐节点主循环执行。
  4. 失败语义不变：委托失败 → failed + 级联 skip，不吞错。
  5. 开关 helper：settings 表读取（默认关 / true 灰度开）。
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

from app.core.agent_runtime.agent import AgentRuntime
from app.core.agent_runtime.context import AgentContext
from app.core.agent_runtime.context_builder import PassthroughContextBuilder
from app.core.planner.models import Plan
from app.core.task_graph.models import TaskGraph, TaskNode
from app.services.sub_agent import (
    SubAgentError,
    is_sub_agent_id,
    is_task_graph_subagent_enabled,
)

SUB_AGENT_MODULE = "app.services.sub_agent"
_SUB_AGENT_KEYS = {"sub_x", "sub_a", "sub_b", "sub_c"}


def _make_graph(specs):
    """specs: [(id, action, assigned_agent, depends_on), ...] → TaskGraph（绕过线性 builder）。"""
    nodes = [
        TaskNode(id=nid, action=action, assigned_agent=agent, depends_on=deps)
        for nid, action, agent, deps in specs
    ]
    return TaskGraph(nodes=nodes, edges=[], metadata={})


def _async_gen(events):
    async def gen(*args, **kwargs):
        for e in events:
            yield e
    return gen


class TaskGraphSubAgentT10TestCase(unittest.TestCase):
    def setUp(self):
        self.runtime = AgentRuntime(context_builder=PassthroughContextBuilder())

    def _make_context(self):
        return AgentContext(
            agent_id="test",
            agent_identity="test",
            personality_level=None,
            model_id="test-model",
            chat_id=1,
            project_path=None,
            memory_context={},
            memory_text=None,
            tools=None,
            plan=Plan(goal="T10 测试", steps=[]),
        )

    def _run(self, context, messages, stream_calls=None):
        events = []

        async def collect():
            async for event in self.runtime.run_stream(context, messages):
                events.append(event)

        asyncio.run(collect())
        return events

    # ──── 1. 委托后主上下文只含摘要 ────

    def test_delegation_injects_summary_only_into_main_context(self):
        """子代理完整输出不进主上下文；只经 runtime_context 回注 500 字内摘要。"""
        full_output = "HEAD_RESULT_" + "X" * 3000 + " TAIL_ONLY_MARKER"
        sub_mock = AsyncMock(return_value=full_output)
        stream_calls = []

        async def stream_once(*args, **kwargs):
            stream_calls.append(kwargs.get("messages"))
            yield {"type": "text", "content": "主循环产出"}
            yield {"type": "finish", "finish_reason": "stop"}

        graph = _make_graph([
            ("task_0", "子任务动作", "sub_x", []),
            ("task_1", "汇总动作", "default_agent", ["task_0"]),
        ])
        with patch("app.core.task_graph.builder.TaskGraphBuilder.build", new=lambda plan: graph), \
             patch(f"{SUB_AGENT_MODULE}.is_task_graph_subagent_enabled", return_value=True), \
             patch(f"{SUB_AGENT_MODULE}.is_sub_agent_id", side_effect=lambda k: k in _SUB_AGENT_KEYS), \
             patch(f"{SUB_AGENT_MODULE}.run_sub_agent", new=sub_mock), \
             patch("app.services.model.model_service.stream_once", new=stream_once), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            events = self._run(self._make_context(), [{"role": "user", "content": "执行"}])

        # 委托参数：只带任务文本（独立上下文，不含主会话历史）
        sub_mock.assert_awaited_once()
        args, kwargs = sub_mock.await_args
        self.assertEqual(args[0], "sub_x")
        self.assertEqual(args[1], "子任务动作")
        self.assertNotIn("messages", kwargs)

        # task_0 委托完成、task_1 主循环完成
        types = [e["type"] for e in events]
        self.assertIn("task_completed", types)
        self.assertIn("finish", types)
        completed = {e["task_id"]: e["status"] for e in events if e["type"] == "task_completed"}
        self.assertEqual(completed.get("task_0"), "completed")
        self.assertEqual(completed.get("task_1"), "completed")

        # 主循环只在 task_1 阶段调用一次模型（task_0 由子代理执行）
        self.assertEqual(len(stream_calls), 1)
        # 主上下文含 runtime_context 回注的摘要；完整输出的尾部哨兵不得出现
        joined = "\n".join(
            str(m.get("content", "")) for m in stream_calls[0] if isinstance(m, dict)
        )
        self.assertIn("【任务结果】", joined)
        self.assertIn("HEAD_RESULT_", joined)
        self.assertNotIn("TAIL_ONLY_MARKER", joined)
        # 摘要截断在 500 字内（HEAD + X 填充共 500 字符，尾部被截掉）
        self.assertNotIn("X" * 489, joined)

    # ──── 2. 并行并发 + 依赖等待 ────

    def test_parallel_independent_nodes_and_dependency_wait(self):
        """无依赖节点并发（in-flight 峰值 2）；依赖节点等上游 completed 后才启动。"""
        in_flight = 0
        max_in_flight = 0
        timeline = []

        async def fake_run_sub_agent(sub_agent_id, task, **kwargs):
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            timeline.append(("start", task))
            await asyncio.sleep(0.05)
            timeline.append(("end", task))
            in_flight -= 1
            return f"{task}的摘要"

        stream_calls = []

        async def stream_once(*args, **kwargs):
            stream_calls.append(kwargs.get("messages"))
            yield {"type": "text", "content": "不该被调用"}
            yield {"type": "finish", "finish_reason": "stop"}

        graph = _make_graph([
            ("task_0", "任务A", "sub_a", []),
            ("task_1", "任务B", "sub_b", []),
            ("task_2", "任务C依赖A", "sub_c", ["task_0"]),
        ])
        with patch("app.core.task_graph.builder.TaskGraphBuilder.build", new=lambda plan: graph), \
             patch(f"{SUB_AGENT_MODULE}.is_task_graph_subagent_enabled", return_value=True), \
             patch(f"{SUB_AGENT_MODULE}.is_sub_agent_id", side_effect=lambda k: k in _SUB_AGENT_KEYS), \
             patch(f"{SUB_AGENT_MODULE}.run_sub_agent", new=fake_run_sub_agent), \
             patch("app.services.model.model_service.stream_once", new=stream_once), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            events = self._run(self._make_context(), [{"role": "user", "content": "执行"}])

        # 并发证明：A 与 B 同时 in-flight
        self.assertEqual(max_in_flight, 2)
        # 依赖等待：A 结束早于 C 启动（时间线顺序）
        self.assertLess(timeline.index(("end", "任务A")), timeline.index(("start", "任务C依赖A")))
        # 全部委托完成，主循环模型零调用
        completed = {e["task_id"] for e in events if e["type"] == "task_completed"}
        self.assertEqual(completed, {"task_0", "task_1", "task_2"})
        self.assertEqual(len(stream_calls), 0)
        # 事件顺序：C 的 task_started 晚于 A 的 task_completed
        order = [(e["type"], e.get("task_id")) for e in events
                 if e["type"] in ("task_started", "task_completed")]
        self.assertGreater(order.index(("task_started", "task_2")),
                           order.index(("task_completed", "task_0")))

    # ──── 3. 失败语义不变：failed + 级联 skip ────

    def test_delegation_failure_cascades_skip(self):
        """委托失败 → task_failed + 依赖节点级联 task_skipped，主循环不执行。"""
        stream_calls = []

        async def stream_once(*args, **kwargs):
            stream_calls.append(kwargs.get("messages"))
            yield {"type": "text", "content": "不该被调用"}
            yield {"type": "finish", "finish_reason": "stop"}

        async def fake_run_sub_agent(sub_agent_id, task, **kwargs):
            raise SubAgentError("子代理执行失败")

        graph = _make_graph([
            ("task_0", "任务A", "sub_a", []),
            ("task_1", "任务B依赖A", "sub_b", ["task_0"]),
        ])
        with patch("app.core.task_graph.builder.TaskGraphBuilder.build", new=lambda plan: graph), \
             patch(f"{SUB_AGENT_MODULE}.is_task_graph_subagent_enabled", return_value=True), \
             patch(f"{SUB_AGENT_MODULE}.is_sub_agent_id", side_effect=lambda k: k in _SUB_AGENT_KEYS), \
             patch(f"{SUB_AGENT_MODULE}.run_sub_agent", new=fake_run_sub_agent), \
             patch("app.services.model.model_service.stream_once", new=stream_once), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            events = self._run(self._make_context(), [{"role": "user", "content": "执行"}])

        failed = [e for e in events if e["type"] == "task_failed"]
        skipped = [e for e in events if e["type"] == "task_skipped"]
        self.assertEqual([e["task_id"] for e in failed], ["task_0"])
        self.assertIn("子代理执行失败", failed[0]["error"])
        self.assertEqual([e["task_id"] for e in skipped], ["task_1"])
        # 失败不吞：主循环模型零调用（节点未进入主循环执行）
        self.assertEqual(len(stream_calls), 0)
        # 正常收尾（finish 事件仍在）
        self.assertIn("finish", [e["type"] for e in events])

    # ──── 4. 默认串行：开关关闭行为与现状一致 ────

    def test_switch_off_keeps_serial_behavior(self):
        """开关关闭（默认）→ 不委托，节点逐个走主循环，事件与现状一致。"""
        sub_mock = AsyncMock(return_value="不应被调用")
        stream_calls = []

        async def stream_once(*args, **kwargs):
            stream_calls.append(kwargs.get("messages"))
            yield {"type": "text", "content": "主循环产出"}
            yield {"type": "finish", "finish_reason": "stop"}

        graph = _make_graph([
            ("task_0", "任务A", "sub_a", []),
            ("task_1", "任务B", "sub_b", []),
        ])
        with patch("app.core.task_graph.builder.TaskGraphBuilder.build", new=lambda plan: graph), \
             patch(f"{SUB_AGENT_MODULE}.is_task_graph_subagent_enabled", return_value=False), \
             patch(f"{SUB_AGENT_MODULE}.is_sub_agent_id", side_effect=lambda k: k in _SUB_AGENT_KEYS), \
             patch(f"{SUB_AGENT_MODULE}.run_sub_agent", new=sub_mock), \
             patch("app.services.model.model_service.stream_once", new=stream_once), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            events = self._run(self._make_context(), [{"role": "user", "content": "执行"}])

        sub_mock.assert_not_awaited()
        # 两个节点都走主循环（逐个串行）
        self.assertEqual(len(stream_calls), 2)
        completed = {e["task_id"]: e["status"] for e in events if e["type"] == "task_completed"}
        self.assertEqual(completed, {"task_0": "completed", "task_1": "completed"})
        # 无摘要回注节点（未开启委托，主上下文与现状一致）
        for msgs in stream_calls:
            for m in msgs:
                if isinstance(m, dict):
                    self.assertNotIn("【任务结果】", str(m.get("content", "")))

    # ──── 5. 非子代理节点不委托 ────

    def test_switch_on_non_subagent_node_still_main_loop(self):
        """开关开启但 assigned_agent 非子代理 → 照旧主循环执行。"""
        sub_mock = AsyncMock(return_value="不应被调用")
        stream_calls = []

        async def stream_once(*args, **kwargs):
            stream_calls.append(kwargs.get("messages"))
            yield {"type": "text", "content": "主循环产出"}
            yield {"type": "finish", "finish_reason": "stop"}

        graph = _make_graph([("task_0", "普通动作", "default_agent", [])])
        with patch("app.core.task_graph.builder.TaskGraphBuilder.build", new=lambda plan: graph), \
             patch(f"{SUB_AGENT_MODULE}.is_task_graph_subagent_enabled", return_value=True), \
             patch(f"{SUB_AGENT_MODULE}.is_sub_agent_id", side_effect=lambda k: k in _SUB_AGENT_KEYS), \
             patch(f"{SUB_AGENT_MODULE}.run_sub_agent", new=sub_mock), \
             patch("app.services.model.model_service.stream_once", new=stream_once), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            events = self._run(self._make_context(), [{"role": "user", "content": "执行"}])

        sub_mock.assert_not_awaited()
        self.assertEqual(len(stream_calls), 1)
        completed = {e["task_id"]: e["status"] for e in events if e["type"] == "task_completed"}
        self.assertEqual(completed, {"task_0": "completed"})

    # ──── 6. 开关 helper：settings 表读取（默认关 / true 灰度开）────

    def test_switch_helper_reads_settings_table(self):
        cases = [
            (None, False),                              # 无行 → 默认关
            (SimpleNamespace(value=None), False),
            (SimpleNamespace(value="false"), False),
            (SimpleNamespace(value="0"), False),
            (SimpleNamespace(value="garbage"), False),  # 非法值按默认关
            (SimpleNamespace(value="true"), True),      # 灰度开启
            (SimpleNamespace(value="1"), True),
            (SimpleNamespace(value="on"), True),
        ]
        for row, expected in cases:
            with self.subTest(row=row):
                fake_db = MagicMock()
                fake_db.query.return_value.filter.return_value.first.return_value = row
                with patch(f"{SUB_AGENT_MODULE}.SessionLocal", return_value=fake_db):
                    self.assertEqual(is_task_graph_subagent_enabled(), expected)

    def test_switch_helper_defaults_off_when_db_unavailable(self):
        with patch(f"{SUB_AGENT_MODULE}.SessionLocal", side_effect=RuntimeError("db down")):
            self.assertFalse(is_task_graph_subagent_enabled())

    # ──── 7. 委托判定 helper ────

    def test_is_sub_agent_id_lookup(self):
        sub_agent_row = SimpleNamespace(is_sub_agent=True)
        normal_row = SimpleNamespace(is_sub_agent=False)
        cases = [
            (sub_agent_row, "sub_x", True),
            (normal_row, "coding_agent", False),
            (None, "ghost", False),
        ]
        for row, key, expected in cases:
            with self.subTest(key=key):
                fake_db = MagicMock()
                fake_db.query.return_value.filter.return_value.first.return_value = row
                with patch(f"{SUB_AGENT_MODULE}.SessionLocal", return_value=fake_db):
                    self.assertEqual(is_sub_agent_id(key), expected)

    def test_is_sub_agent_id_empty_and_db_error(self):
        self.assertFalse(is_sub_agent_id(""))
        self.assertFalse(is_sub_agent_id(None))
        with patch(f"{SUB_AGENT_MODULE}.SessionLocal", side_effect=RuntimeError("db down")):
            self.assertFalse(is_sub_agent_id("sub_x"))


if __name__ == "__main__":
    unittest.main()
