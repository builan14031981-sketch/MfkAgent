"""TaskGraph Runtime Stabilization（Phase G4-C）测试。

覆盖：
- 正常 DAG：全部任务依次 completed，事件顺序正确，进度摘要收敛
- 中间节点失败：failed + 级联跳过依赖链后续节点（skipped）
- 后续节点 skipped：依赖失败的 pending 节点全部 skipped，无悬空
- 状态一致性：TaskNode.status / TaskGraphState / AgentRun / RuntimeEvent 保持一致
- 事件顺序：task_started → task_completed | task_failed → task_skipped
- current_step 追踪：current_task_id / step_index 同步（不修改 Plan）
"""

import os
import sys
import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

# 确保 backend 在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.planner.models import Plan, PlanStep
from app.core.task_graph.models import TaskNode, TaskNodeStatus, TaskEdge, TaskGraph
from app.core.agent_runtime.task_graph_state import TaskGraphState
from app.core.agent_runtime.context import AgentContext, AgentResult


def _msg(role, content):
    return SimpleNamespace(role=role, content=content)


def _async_gen(events):
    async def gen(*args, **kwargs):
        for e in events:
            yield e
    return gen


class _MockModelResult:
    def __init__(self, content="", tool_calls=None, usage=None, finish_reason="stop"):
        self.content = content
        self.tool_calls = tool_calls
        self.usage = usage
        self.finish_reason = finish_reason


class _RecordingRecorder:
    """捕获 AgentRuntime 事件调用（替代真实 DB recorder）。"""

    def __init__(self):
        self.events = []      # [(event_type, payload)]
        self.finished = None  # finish_run(status)

    def create_run(self, **kwargs):
        return 1

    def emit(self, run_id, event_type, payload=None):
        self.events.append((event_type, payload or {}))

    def transition(self, *args, **kwargs):
        pass

    def finish_run(self, run_id, status):
        self.finished = status

    def event_types(self):
        return [t for t, _ in self.events]


def _make_context(plan=None):
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
        plan=plan,
    )


# ---------------------------------------------------------------------------
# G4-C: TaskGraphState 失败级联 / 图中断 / 进度同步
# ---------------------------------------------------------------------------


class TestG4CStateCascade(unittest.TestCase):
    """mark_failed 级联跳过依赖链。"""

    def test_mark_failed_cascade_linear(self):
        """线性链：task_0 完成 → task_1 失败 → task_2 被跳过。"""
        plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B"), PlanStep(action="C")])
        state = TaskGraphState.from_plan(plan)
        state.update_task_status("task_0", "completed")
        state.update_task_status("task_1", "running")

        skipped = state.mark_failed("task_1", "boom")

        self.assertEqual(skipped, ["task_2"])
        self.assertEqual(state.get_task("task_1").status, TaskNodeStatus.FAILED)
        self.assertEqual(state.get_task("task_2").status, TaskNodeStatus.SKIPPED)
        self.assertTrue(state.is_all_done())
        self.assertTrue(state.has_failed())
        self.assertEqual(state.get_task("task_0").status, TaskNodeStatus.COMPLETED)
        self.assertIsNone(state.current_task_id)

    def test_mark_failed_unknown_task(self):
        """不存在的节点 → 返回空列表。"""
        state = TaskGraphState.from_plan(None)
        self.assertEqual(state.mark_failed("ghost"), [])

    def test_mark_failed_diamond(self):
        """菱形依赖：左支失败 → 汇合节点被跳过。"""
        graph = TaskGraph(
            nodes=[
                TaskNode(id="task_0", action="基础"),
                TaskNode(id="task_1", action="左支", depends_on=["task_0"]),
                TaskNode(id="task_2", action="右支", depends_on=["task_0"]),
                TaskNode(id="task_3", action="汇合", depends_on=["task_1", "task_2"]),
            ],
            edges=[
                TaskEdge(from_id="task_0", to_id="task_1"),
                TaskEdge(from_id="task_0", to_id="task_2"),
                TaskEdge(from_id="task_1", to_id="task_3"),
                TaskEdge(from_id="task_2", to_id="task_3"),
            ],
        )
        state = TaskGraphState(graph=graph)

        skipped = state.mark_failed("task_1")

        # 汇合节点依赖左支 → skipped；右支不受影响（仍 pending，可继续）
        self.assertIn("task_3", skipped)
        self.assertEqual(state.get_task("task_3").status, TaskNodeStatus.SKIPPED)
        self.assertEqual(state.get_task("task_2").status, TaskNodeStatus.PENDING)


class TestG4CStateSkipAll(unittest.TestCase):
    """图中断兜底：mark_pending_skipped 收敛。"""

    def test_mark_pending_skipped_converges(self):
        """task_0 失败 → 剩余 pending 全部 skipped → is_all_done True。"""
        plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B"), PlanStep(action="C")])
        state = TaskGraphState.from_plan(plan)
        state.update_task_status("task_0", "failed")

        skipped = state.mark_pending_skipped()

        self.assertEqual(set(skipped), {"task_1", "task_2"})
        self.assertTrue(state.is_all_done())
        self.assertTrue(state.has_failed())

    def test_mark_pending_skipped_none_left(self):
        """全部已完成 → 无剩余跳过。"""
        plan = Plan(steps=[PlanStep(action="A")])
        state = TaskGraphState.from_plan(plan)
        state.update_task_status("task_0", "completed")
        self.assertEqual(state.mark_pending_skipped(), [])


class TestG4CStateProgress(unittest.TestCase):
    """current_step 追踪（不修改 Plan）。"""

    def test_current_task_tracking(self):
        """running 记录当前节点；终态清空。"""
        plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B")])
        state = TaskGraphState.from_plan(plan)

        self.assertIsNone(state.current_task_id)
        state.update_task_status("task_0", "running")
        self.assertEqual(state.current_task_id, "task_0")
        state.update_task_status("task_0", "completed")
        self.assertIsNone(state.current_task_id)

    def test_step_index(self):
        """节点执行顺序序号。"""
        plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B")])
        state = TaskGraphState.from_plan(plan)
        self.assertEqual(state.get_step_index("task_0"), 0)
        self.assertEqual(state.get_step_index("task_1"), 1)
        self.assertEqual(state.get_step_index("nonexistent"), -1)
        self.assertEqual(state.total_steps, 2)

    def test_get_progress_snapshot(self):
        """进度快照字段完整且一致。"""
        plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B"), PlanStep(action="C")])
        state = TaskGraphState.from_plan(plan)
        state.update_task_status("task_0", "completed")

        prog = state.get_progress()
        self.assertEqual(prog["total_steps"], 3)
        self.assertEqual(prog["completed"], 1)
        self.assertEqual(prog["pending"], 2)
        self.assertEqual(prog["failed"], 0)
        self.assertEqual(prog["skipped"], 0)
        self.assertEqual(prog["is_all_done"], False)
        self.assertEqual(prog["has_failed"], False)
        self.assertEqual(prog["current_task_id"], None)

    def test_mark_failed_clears_current_task(self):
        """失败时若为当前节点 → current_task_id 清空。"""
        plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B")])
        state = TaskGraphState.from_plan(plan)
        state.update_task_status("task_0", "running")
        state.mark_failed("task_0")
        self.assertIsNone(state.current_task_id)


# ---------------------------------------------------------------------------
# G4-C: run()（非流式）— 状态一致性 / 事件顺序 / AgentRun 收尾
# ---------------------------------------------------------------------------


class TestG4CRunNonStreaming(unittest.TestCase):
    """run() 非流式路径：任务失败不使 AgentRun failed，事件完整。"""

    def setUp(self):
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context_builder import PassthroughContextBuilder
        self.runtime = AgentRuntime(context_builder=PassthroughContextBuilder())

    def test_normal_dag_all_completed(self):
        """正常 DAG：全部任务 completed，进度摘要收敛，事件顺序正确。"""
        plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B"), PlanStep(action="C")])
        context = _make_context(plan=plan)
        messages = [_msg("user", "执行")]

        recorder = _RecordingRecorder()
        mock_result = _MockModelResult(content="ok")
        mock_call = AsyncMock(return_value=mock_result)

        with patch("app.services.model.model_service.call_once", mock_call), \
             patch("app.core.agent_runtime.agent.runtime_event_recorder", recorder):
            result = asyncio.run(self.runtime.run(context, messages))

        self.assertIsInstance(result, AgentResult)
        self.assertTrue(self.runtime.task_graph_state.is_all_done())
        self.assertFalse(self.runtime.task_graph_state.has_failed())

        # 事件顺序：3× task_started + 3× task_completed（交替）
        task_events = [
            (t, p["task_id"], p.get("step_index"))
            for t, p in recorder.events if t in ("task_started", "task_completed")
        ]
        self.assertEqual(
            task_events,
            [
                ("task_started", "task_0", 0),
                ("task_completed", "task_0", 0),
                ("task_started", "task_1", 1),
                ("task_completed", "task_1", 1),
                ("task_started", "task_2", 2),
                ("task_completed", "task_2", 2),
            ],
        )

        # AgentRun 正常收尾 completed
        self.assertEqual(recorder.finished, "completed")

        # 进度摘要：3 completed
        summary = result.metadata["task_graph"]
        self.assertEqual(summary["completed"], 3)
        self.assertEqual(summary["total_steps"], 3)
        self.assertTrue(summary["is_all_done"])

    def test_middle_task_failure(self):
        """中间节点失败：failed + 级联 skipped，run 正常收尾 completed。"""
        plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B"), PlanStep(action="C")])
        context = _make_context(plan=plan)
        messages = [_msg("user", "执行")]

        recorder = _RecordingRecorder()

        async def fake_call(**kwargs):
            # task_0 成功；task_1 抛异常
            raise RuntimeError("LLM 服务不可用")

        call_count = [0]

        async def side_effect_call(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _MockModelResult(content="完成A")
            raise RuntimeError("LLM 服务不可用")

        with patch("app.services.model.model_service.call_once", side_effect_call), \
             patch("app.core.agent_runtime.agent.runtime_event_recorder", recorder):
            result = asyncio.run(self.runtime.run(context, messages))

        self.assertIsInstance(result, AgentResult)
        # 运行正常收尾（任务失败不使 AgentRun failed）
        self.assertEqual(recorder.finished, "completed")

        # 事件顺序：task_0 completed → task_1 failed → task_2 skipped
        task_events = [
            (t, p["task_id"], p.get("status"), p.get("error"))
            for t, p in recorder.events if t in ("task_started", "task_completed", "task_failed", "task_skipped")
        ]
        types = [e[0] for e in task_events]
        self.assertEqual(types[0], "task_started")
        self.assertEqual(types[1], "task_completed")
        self.assertIn("task_failed", types)
        self.assertIn("task_skipped", types)
        # task_failed 在 task_skipped 之前
        self.assertLess(types.index("task_failed"), types.index("task_skipped"))
        # failed 的是 task_1，skipped 的是 task_2
        failed_events = [p for t, p in recorder.events if t == "task_failed"]
        skipped_events = [p for t, p in recorder.events if t == "task_skipped"]
        self.assertEqual([p["task_id"] for p in failed_events], ["task_1"])
        self.assertEqual([p["task_id"] for p in skipped_events], ["task_2"])
        # task_skipped 携带 error 之外的状态
        self.assertEqual(skipped_events[0]["status"], "skipped")

        # 状态一致性：TaskNode / TaskGraphState 一致
        state = self.runtime.task_graph_state
        self.assertEqual(state.get_task("task_0").status, TaskNodeStatus.COMPLETED)
        self.assertEqual(state.get_task("task_1").status, TaskNodeStatus.FAILED)
        self.assertEqual(state.get_task("task_2").status, TaskNodeStatus.SKIPPED)
        self.assertTrue(state.is_all_done())
        self.assertTrue(state.has_failed())

        # 进度摘要透传
        summary = result.metadata["task_graph"]
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["skipped"], 1)
        self.assertTrue(summary["is_all_done"])
        self.assertTrue(summary["has_failed"])

    def test_no_plan_original_behavior(self):
        """无 Plan：无 task 事件，行为不变。"""
        context = _make_context(plan=None)
        messages = [_msg("user", "hello")]

        recorder = _RecordingRecorder()
        mock_result = _MockModelResult(content="hi")
        mock_call = AsyncMock(return_value=mock_result)

        with patch("app.services.model.model_service.call_once", mock_call), \
             patch("app.core.agent_runtime.agent.runtime_event_recorder", recorder):
            result = asyncio.run(self.runtime.run(context, messages))

        task_types = {"task_started", "task_completed", "task_failed", "task_skipped"}
        self.assertFalse(any(t in task_types for t in recorder.event_types()))
        self.assertIsNone(result.metadata.get("task_graph"))


# ---------------------------------------------------------------------------
# G4-C: run_stream()（流式）— 失败级联 / 事件顺序
# ---------------------------------------------------------------------------


class TestG4CRunStream(unittest.TestCase):
    """run_stream() 流式路径：task_failed → task_skipped 级联。"""

    def setUp(self):
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context_builder import PassthroughContextBuilder
        self.runtime = AgentRuntime(context_builder=PassthroughContextBuilder())

    def test_middle_task_failure_cascades(self):
        """中间节点失败 → task_failed + 后续 task_skipped。"""
        plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B"), PlanStep(action="C")])
        context = _make_context(plan=plan)
        messages = [{"role": "user", "content": "执行"}]

        call_count = [0]

        def fake_stream(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # task_0 成功
                return _async_gen([
                    {"type": "text", "content": "完成A"},
                    {"type": "finish", "finish_reason": "stop"},
                ])()
            # task_1 抛异常
            raise RuntimeError("stream 中断")

        async def boom_reflection(*args, **kwargs):
            # 反思 LLM 失败 → 自愈降级，走原始 failed + 级联 skip 路径
            raise RuntimeError("反思调用失败")
            yield  # noqa: unreachable

        events = []
        with patch("app.services.model.model_service.stream_once", fake_stream), \
             patch("app.services.model.model_service.call_once", boom_reflection), \
             patch("app.core.agent_runtime.agent.runtime_event_recorder", _RecordingRecorder()):
            async def collect():
                async for event in self.runtime.run_stream(context, messages):
                    events.append(event)
            asyncio.run(collect())

        task_types = [e["type"] for e in events if e["type"].startswith("task_")]
        self.assertIn("task_failed", task_types)
        self.assertIn("task_skipped", task_types)
        # task_failed 在 task_skipped 之前
        self.assertLess(task_types.index("task_failed"), task_types.index("task_skipped"))

        failed = [e for e in events if e["type"] == "task_failed"][0]
        self.assertEqual(failed["task_id"], "task_1")
        skipped = [e for e in events if e["type"] == "task_skipped"][0]
        self.assertEqual(skipped["task_id"], "task_2")
        self.assertEqual(skipped["status"], "skipped")

        # 状态一致性
        state = self.runtime.task_graph_state
        self.assertEqual(state.get_task("task_1").status, TaskNodeStatus.FAILED)
        self.assertEqual(state.get_task("task_2").status, TaskNodeStatus.SKIPPED)
        self.assertTrue(state.is_all_done())
        self.assertTrue(state.has_failed())

    def test_normal_dag_event_order(self):
        """正常 DAG：task_started/completed 交替 + finish 收尾。"""
        plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B")])
        context = _make_context(plan=plan)
        messages = [{"role": "user", "content": "执行"}]

        mock_stream = _async_gen([
            {"type": "text", "content": "ok"},
            {"type": "finish", "finish_reason": "stop"},
        ])

        events = []
        with patch("app.services.model.model_service.stream_once", mock_stream), \
             patch("app.core.agent_runtime.agent.runtime_event_recorder", _RecordingRecorder()):
            async def collect():
                async for event in self.runtime.run_stream(context, messages):
                    events.append(event)
            asyncio.run(collect())

        task_events = [
            (e["type"], e["task_id"]) for e in events if e["type"].startswith("task_")
        ]
        self.assertEqual(
            task_events,
            [
                ("task_started", "task_0"),
                ("task_completed", "task_0"),
                ("task_started", "task_1"),
                ("task_completed", "task_1"),
            ],
        )
        finishes = [e for e in events if e["type"] == "finish"]
        self.assertEqual(len(finishes), 1)
        self.assertTrue(self.runtime.task_graph_state.is_all_done())


class TestG4CRegistry(unittest.TestCase):
    """G4-C：事件注册表包含 task_skipped。"""

    def test_task_skipped_registered(self):
        from app.core.agent_runtime.states import is_registered_event_type
        self.assertTrue(is_registered_event_type("task_skipped"))


if __name__ == "__main__":
    unittest.main()
