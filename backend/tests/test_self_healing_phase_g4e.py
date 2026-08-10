"""TaskGraph 动态自愈与反思（Phase G4-E）专项测试。

覆盖：
- TaskGraphState.get_heal_depth / can_heal：自愈深度上限追踪
- dynamic_append_task：失败父节点 → COMPLETED + 注入 heal_N 节点
- _reflect_and_heal：成功注入 / 空方案降级 / LLM 异常降级 / 触达上限阻断
- 非流式 run：连续失败触达 max_heal_depth → 阻断反思，走 failed + 级联降级
- 流式 run_stream：连续失败触达上限 → 阻断；修复事件 current_task_id 对齐 heal_N
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
from app.core.task_graph.models import TaskNode, TaskNodeStatus, TaskGraph
from app.core.agent_runtime.task_graph_state import TaskGraphState
from app.core.agent_runtime.context import AgentContext, AgentResult

REFLECTION_MODEL = "qwen-flash"  # 与 AgentRuntime.REFLECTION_MODEL 保持一致


def _msg(role, content):
    return SimpleNamespace(role=role, content=content)


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


class _MockModelResult:
    def __init__(self, content="", tool_calls=None, usage=None, finish_reason="stop"):
        self.content = content
        self.tool_calls = tool_calls
        self.usage = usage
        self.finish_reason = finish_reason


class _RecordingRecorder:
    """捕获 AgentRuntime 事件（替换 agent.py 命名空间内的 recorder 单例）。"""

    def __init__(self):
        self.events = []      # [(event_type, payload)]
        self.finished = None

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


class _ExecFailReflectOkCallOnce:
    """call_once mock：执行调用（test-model）抛错，反思调用（qwen-flash）返回修复 JSON。

    用于模拟"任务反复失败但反思总能给出方案"的自愈循环场景。
    """

    def __init__(self, reflection_json=None, execution_error="执行调用失败"):
        self.reflection_json = reflection_json or (
            '{"analysis":"根因分析","fix_action":"重试修复","suggested_tools":["write_file"]}'
        )
        self.execution_error = execution_error
        self.execution_calls = 0
        self.reflection_calls = 0

    async def __call__(self, **kwargs):
        if kwargs.get("model_id") == REFLECTION_MODEL:
            self.reflection_calls += 1
            return _MockModelResult(content=self.reflection_json)
        self.execution_calls += 1
        raise RuntimeError(self.execution_error)


def _make_runtime():
    from app.core.agent_runtime.agent import AgentRuntime
    from app.core.agent_runtime.context_builder import PassthroughContextBuilder
    return AgentRuntime(context_builder=PassthroughContextBuilder())


# ---------------------------------------------------------------------------
# G4-E: TaskGraphState 自愈深度上限
# ---------------------------------------------------------------------------


class TestHealDepthTracking(unittest.TestCase):
    """get_heal_depth / can_heal 深度上限语义。"""

    def _chain(self, depth=3):
        state = TaskGraphState(max_heal_depth=3)
        nodes = [TaskNode(id="task_0", action="原始")]
        for i in range(1, depth + 1):
            nodes.append(TaskNode(id=f"heal_{i}", action=f"修复{i}", depends_on=[f"heal_{i - 1}" if i > 1 else "task_0"]))
        state.set_graph(TaskGraph(nodes=nodes))
        return state

    def test_get_heal_depth_original_is_zero(self):
        state = self._chain()
        self.assertEqual(state.get_heal_depth("task_0"), 0)

    def test_get_heal_depth_increments(self):
        state = self._chain()
        self.assertEqual(state.get_heal_depth("heal_1"), 1)
        self.assertEqual(state.get_heal_depth("heal_2"), 2)
        self.assertEqual(state.get_heal_depth("heal_3"), 3)

    def test_get_heal_depth_unknown(self):
        state = self._chain()
        self.assertEqual(state.get_heal_depth("ghost"), 0)

    def test_can_heal_under_limit(self):
        state = self._chain()
        self.assertTrue(state.can_heal("task_0"))
        self.assertTrue(state.can_heal("heal_2"))

    def test_can_heal_blocked_at_limit(self):
        state = self._chain()
        # depth 3 >= max 3 → 阻断
        self.assertFalse(state.can_heal("heal_3"))

    def test_custom_max_heal_depth(self):
        state = TaskGraphState(max_heal_depth=1)
        state.set_graph(TaskGraph(nodes=[
            TaskNode(id="task_0", action="原始"),
            TaskNode(id="heal_1", action="修复", depends_on=["task_0"]),
        ]))
        self.assertTrue(state.can_heal("task_0"))
        self.assertFalse(state.can_heal("heal_1"))

    def test_dynamic_append_marks_parent_completed(self):
        state = TaskGraphState()
        state.set_graph(TaskGraph(nodes=[TaskNode(id="task_0", action="原始")]))
        state.update_task_status("task_0", "running")
        state.mark_failed("task_0")

        new_node = state.dynamic_append_task("重试修复", "task_0")

        self.assertIsNotNone(new_node)
        self.assertEqual(new_node.id, "heal_1")
        self.assertEqual(new_node.depends_on, ["task_0"])
        self.assertEqual(new_node.status, TaskNodeStatus.PENDING)
        # 失败父节点被标记为 COMPLETED，让修复节点成为后继
        self.assertEqual(state.get_task("task_0").status, TaskNodeStatus.COMPLETED)
        self.assertTrue(state.can_heal("heal_1"))


# ---------------------------------------------------------------------------
# G4-E: _reflect_and_heal 单点行为
# ---------------------------------------------------------------------------


class TestReflectAndHeal(unittest.TestCase):
    def setUp(self):
        self.runtime = _make_runtime()
        plan = Plan(steps=[PlanStep(action="原始任务")])
        self.state = self.runtime.init_task_graph(plan)
        self.state.update_task_status("task_0", "running")

    def _heal(self, json_text=None, raise_on_llm=False):
        async def mock_call(**kwargs):
            if raise_on_llm:
                raise RuntimeError("LLM 挂了")
            return _MockModelResult(content=json_text or (
                '{"analysis":"a","fix_action":"重试修复","suggested_tools":["write_file"]}'
            ))

        async def do():
            with patch("app.services.model.model_service.call_once", mock_call):
                return await self.runtime._reflect_and_heal(
                    self.state.get_task("task_0"), "boom", run_id=None
                )
        return asyncio.run(do())

    def test_success_injects_heal_node(self):
        node = self._heal()
        self.assertIsNotNone(node)
        self.assertEqual(node.id, "heal_1")
        self.assertEqual(node.action, "重试修复")
        self.assertEqual(node.depends_on, ["task_0"])
        self.assertEqual(self.state.get_task("task_0").status, TaskNodeStatus.COMPLETED)

    def test_empty_fix_action_degrades(self):
        node = self._heal(json_text='{"analysis":"a","fix_action":"","suggested_tools":[]}')
        self.assertIsNone(node)

    def test_llm_failure_degrades(self):
        node = self._heal(raise_on_llm=True)
        self.assertIsNone(node)

    def test_blocked_at_heal_limit_no_llm_call(self):
        async def mock_call(**kwargs):
            raise AssertionError("触达上限后不应再调用反思 LLM")

        async def do():
            with patch("app.services.model.model_service.call_once", mock_call):
                cur = self.state.get_task("task_0")
                # 前 3 次成功注入（需要真实反思响应）
                for expected in ("heal_1", "heal_2", "heal_3"):
                    with patch(
                        "app.services.model.model_service.call_once",
                        _ExecFailReflectOkCallOnce(),
                    ):
                        node = await self.runtime._reflect_and_heal(cur, "boom", run_id=None)
                    self.assertIsNotNone(node)
                    self.assertEqual(node.id, expected)
                    cur = node
                # 第 4 次：深度 3 已达上限 → 阻断（不应触发任何 LLM 调用）
                node = await self.runtime._reflect_and_heal(cur, "boom", run_id=None)
                self.assertIsNone(node)
        asyncio.run(do())


# ---------------------------------------------------------------------------
# G4-E: 非流式 run — 触达上限后降级（failed + 级联跳过）
# ---------------------------------------------------------------------------


class TestRunSelfHealLimit(unittest.TestCase):
    def setUp(self):
        self.runtime = _make_runtime()
        self.recorder = _RecordingRecorder()

    def test_run_degrades_after_max_heal_depth(self):
        plan = Plan(steps=[PlanStep(action="危险操作")])
        context = _make_context(plan=plan)
        messages = [_msg("user", "执行")]

        mock_call = _ExecFailReflectOkCallOnce()
        with patch("app.services.model.model_service.call_once", mock_call), \
             patch("app.core.agent_runtime.agent.runtime_event_recorder", self.recorder):
            result = asyncio.run(self.runtime.run(context, messages))

        self.assertIsInstance(result, AgentResult)
        summary = result.metadata["task_graph"]
        # task_0 / heal_1 / heal_2 被标记 COMPLETED，heal_3 最终 FAILED
        self.assertEqual(summary["completed"], 3)
        self.assertEqual(summary["failed"], 1)
        self.assertTrue(summary["is_all_done"])

        # 反思仅调用 3 次，第 4 次被深度上限阻断
        self.assertEqual(mock_call.reflection_calls, 3)

        # 反思开始事件 3 次，自愈上限阻断事件 1 次
        reflection = [p for t, p in self.recorder.events
                      if t == "agent_state_update"
                      and p.get("action_detail") == "触发自我反思，分析错误原因..."]
        limit = [p for t, p in self.recorder.events
                 if t == "agent_state_update"
                 and p.get("action_detail", "").startswith("已到达自愈上限")]
        self.assertEqual(len(reflection), 3)
        self.assertEqual(len(limit), 1)
        # 最终只有一个 task_failed（heal_3）
        self.assertEqual(self.recorder.event_types().count("task_failed"), 1)


# ---------------------------------------------------------------------------
# G4-E: 流式 run_stream — 触达上限降级 + 修复事件 current_task_id 对齐 heal_N
# ---------------------------------------------------------------------------


class TestRunStreamSelfHealLimit(unittest.TestCase):
    def setUp(self):
        self.runtime = _make_runtime()

    def _collect(self, context, messages, mock_call, mock_stream):
        events = []
        with patch("app.services.model.model_service.call_once", mock_call), \
             patch("app.services.model.model_service.stream_once", mock_stream):
            async def collect():
                async for e in self.runtime.run_stream(context, messages):
                    events.append(e)
            asyncio.run(collect())
        return events

    def test_stream_heal_then_degrade_with_heal_id(self):
        plan = Plan(steps=[PlanStep(action="危险操作")])
        context = _make_context(plan=plan)
        messages = [_msg("user", "执行")]

        mock_call = _ExecFailReflectOkCallOnce()

        async def boom_stream(*args, **kwargs):
            raise RuntimeError("流式执行调用失败")
            yield  # noqa: unreachable

        events = self._collect(context, messages, mock_call, boom_stream)

        types = [e["type"] for e in events]
        self.assertIn("task_failed", types)
        self.assertIn("finish", types)

        # 反思开始事件 3 次，自愈上限阻断事件 1 次
        reflection = [e for e in events
                      if e.get("action_detail") == "触发自我反思，分析错误原因..."]
        limit = [e for e in events
                 if e.get("action_detail", "").startswith("已到达自愈上限")]
        self.assertEqual(len(reflection), 3)
        self.assertEqual(len(limit), 1)

        # BUG FIX 验证：修复事件 current_task_id 必须使用新注入的 heal_N
        fix_events = [e for e in events
                      if e.get("action_detail", "").startswith("动态生成修复计划")]
        self.assertEqual([e["current_task_id"] for e in fix_events],
                         ["heal_1", "heal_2", "heal_3"])

        # 最终失败节点为最后一次注入的 heal_3
        failed = [e for e in events if e["type"] == "task_failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["task_id"], "heal_3")

    def test_stream_single_heal_success_path(self):
        """任务先失败、修复节点成功 → 事件链 task_failed 不出现，全部 completed。"""
        plan = Plan(steps=[PlanStep(action="任务A")])
        context = _make_context(plan=plan)
        messages = [_msg("user", "执行")]

        # 第一次 stream 抛错（task_0），之后 heal_1 正常输出文本
        call_count = {"n": 0}

        async def flaky_stream(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("第一次执行失败")
            yield {"type": "text", "content": "修复成功"}
            yield {"type": "finish", "finish_reason": "stop"}

        mock_call = _ExecFailReflectOkCallOnce()

        events = self._collect(context, messages, mock_call, flaky_stream)

        types = [e["type"] for e in events]
        self.assertNotIn("task_failed", types)
        self.assertIn("task_completed", types)
        completed = [e for e in events if e["type"] == "task_completed"]
        self.assertEqual(completed[0]["task_id"], "heal_1")
        # 修复事件指向 heal_1
        fix = [e for e in events
               if e.get("action_detail", "").startswith("动态生成修复计划")]
        self.assertEqual(fix[0]["current_task_id"], "heal_1")


if __name__ == "__main__":
    unittest.main()
