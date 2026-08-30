"""TaskGraphState + AgentRuntime TaskGraph 集成测试（G4-A + G4-B）。

G4-A 验证：
- 状态初始化（from_plan / init_task_graph）
- get_next_ready_task 的就绪检查逻辑
- update_task_status 的状态流转
- 线性依赖下的执行顺序
- 全部完成 / 阻塞 / 失败传播

G4-B 验证：
- run_stream 中 task_started / task_completed 事件 yield
- run_stream 中多任务线性推进
- run_stream 中 task_failed 事件
- run() 中 TaskGraph 驱动（task 事件 emit）
- 无 Plan 时原始行为不变
"""

import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from tests._t4_mock_adapter import stream_from_single_call  # noqa: E402

from app.core.planner.models import Plan, PlanStep
from app.core.task_graph.models import TaskNode, TaskNodeStatus, TaskEdge, TaskGraph
from app.core.agent_runtime.task_graph_state import TaskGraphState
from app.core.agent_runtime.context import AgentContext, AgentResult


def _msg(role, content):
    """构造类 ModelMessage 对象（run() 中 messages[-1].content 需要 .content 属性）。"""
    return SimpleNamespace(role=role, content=content)


class TestTaskGraphStateInit(unittest.TestCase):
    """状态初始化测试。"""

    def test_from_none_plan(self):
        """None Plan → 空状态机。"""
        state = TaskGraphState.from_plan(None)

        self.assertEqual(state.node_count, 0)
        self.assertEqual(len(state.graph.nodes), 0)
        self.assertIsNone(state.graph.metadata)

    def test_from_empty_plan(self):
        """空 steps Plan → 0 节点。"""
        plan = Plan(goal="g", steps=[])
        state = TaskGraphState.from_plan(plan)

        self.assertEqual(state.node_count, 0)

    def test_from_multi_step_plan(self):
        """3 步骤 Plan → 3 节点，初始全 PENDING。"""
        plan = Plan(steps=[
            PlanStep(action="A"),
            PlanStep(action="B"),
            PlanStep(action="C"),
        ])
        state = TaskGraphState.from_plan(plan)

        self.assertEqual(state.node_count, 3)
        for node in state.graph.nodes:
            self.assertEqual(node.status, TaskNodeStatus.PENDING)

    def test_node_index_built_correctly(self):
        """内部索引正确建立，get_task 可查。"""
        plan = Plan(steps=[PlanStep(action="X")])
        state = TaskGraphState.from_plan(plan)

        node = state.get_task("task_0")
        self.assertIsNotNone(node)
        self.assertEqual(node.action, "X")

    def test_get_task_not_found(self):
        """查询不存在的节点 ID → None。"""
        state = TaskGraphState.from_plan(None)
        self.assertIsNone(state.get_task("nonexistent"))


class TestGetNextReadyTask(unittest.TestCase):
    """get_next_ready_task 就绪检查逻辑。"""

    def setUp(self):
        self.plan = Plan(steps=[
            PlanStep(action="构建", suggested_tools=["docker_build"]),
            PlanStep(action="测试", suggested_tools=["pytest"]),
            PlanStep(action="部署", suggested_tools=["kubectl"]),
        ])
        self.state = TaskGraphState.from_plan(self.plan)

    def test_first_ready_is_task_0(self):
        """初始状态：task_0 无依赖，应被选中。"""
        task = self.state.get_next_ready_task()

        self.assertIsNotNone(task)
        self.assertEqual(task.id, "task_0")
        self.assertEqual(task.action, "构建")

    def test_task_1_not_ready_until_task_0_completed(self):
        """task_0 未完成时，task_1 不就绪。"""
        # task_0 → running（未完成）
        self.state.update_task_status("task_0", "running")
        task = self.state.get_next_ready_task()

        # task_0 已非 pending，task_1 依赖 task_0 但未 completed → None
        self.assertIsNone(task)

    def test_task_1_ready_after_task_0_completed(self):
        """task_0 completed 后，task_1 就绪。"""
        self.state.update_task_status("task_0", "completed")
        task = self.state.get_next_ready_task()

        self.assertIsNotNone(task)
        self.assertEqual(task.id, "task_1")
        self.assertEqual(task.action, "测试")

    def test_linear_chain_full_progression(self):
        """线性链完整推进：task_0 → task_1 → task_2。"""
        # task_0
        task = self.state.get_next_ready_task()
        self.assertEqual(task.id, "task_0")
        self.state.update_task_status("task_0", "completed")

        # task_1
        task = self.state.get_next_ready_task()
        self.assertEqual(task.id, "task_1")
        self.state.update_task_status("task_1", "completed")

        # task_2
        task = self.state.get_next_ready_task()
        self.assertEqual(task.id, "task_2")
        self.state.update_task_status("task_2", "completed")

        # 全部完成
        self.assertIsNone(self.state.get_next_ready_task())
        self.assertTrue(self.state.is_all_done())

    def test_all_done_returns_none(self):
        """全部完成后 get_next_ready_task 返回 None。"""
        for node in self.state.graph.nodes:
            node.status = TaskNodeStatus.COMPLETED

        self.assertIsNone(self.state.get_next_ready_task())
        self.assertTrue(self.state.is_all_done())

    def test_empty_graph_returns_none(self):
        """空图 → None。"""
        state = TaskGraphState.from_plan(None)
        self.assertIsNone(state.get_next_ready_task())


class TestUpdateTaskStatus(unittest.TestCase):
    """update_task_status 状态更新。"""

    def setUp(self):
        self.plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B")])
        self.state = TaskGraphState.from_plan(self.plan)

    def test_update_to_running(self):
        """更新为 running。"""
        ok = self.state.update_task_status("task_0", "running")
        self.assertTrue(ok)
        self.assertEqual(self.state.get_task("task_0").status, TaskNodeStatus.RUNNING)

    def test_update_to_completed(self):
        """更新为 completed。"""
        ok = self.state.update_task_status("task_0", "completed")
        self.assertTrue(ok)
        self.assertEqual(self.state.get_task("task_0").status, TaskNodeStatus.COMPLETED)

    def test_update_to_failed(self):
        """更新为 failed。"""
        ok = self.state.update_task_status("task_0", "failed")
        self.assertTrue(ok)
        self.assertEqual(self.state.get_task("task_0").status, TaskNodeStatus.FAILED)

    def test_update_nonexistent_task(self):
        """更新不存在的节点 → False。"""
        ok = self.state.update_task_status("task_999", "running")
        self.assertFalse(ok)

    def test_update_invalid_status(self):
        """无效状态字符串 → False。"""
        ok = self.state.update_task_status("task_0", "invalid_status")
        self.assertFalse(ok)
        # 原状态不变
        self.assertEqual(self.state.get_task("task_0").status, TaskNodeStatus.PENDING)


class TestFailureAndBlocking(unittest.TestCase):
    """失败传播与阻塞场景。"""

    def test_failed_task_blocks_dependents(self):
        """task_0 失败 → task_1 被阻塞，get_next_ready_task 返回 None。"""
        plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B")])
        state = TaskGraphState.from_plan(plan)

        state.update_task_status("task_0", "failed")

        # task_1 依赖 task_0，但 task_0 是 failed 不是 completed → 阻塞
        self.assertIsNone(state.get_next_ready_task())
        self.assertTrue(state.has_failed())

        blocked = state.get_blocked_tasks()
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0].id, "task_1")

    def test_skipped_does_not_satisfy_dependency(self):
        """依赖节点被 skipped 不满足 completed 条件 → 后续阻塞。"""
        plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B")])
        state = TaskGraphState.from_plan(plan)

        state.update_task_status("task_0", "skipped")

        # task_0 是 skipped，不是 completed → task_1 阻塞
        self.assertIsNone(state.get_next_ready_task())

    def test_diamond_dependency(self):
        """菱形依赖：task_0 → task_1/task_2 → task_3。"""
        graph = TaskGraph(
            nodes=[
                TaskNode(id="task_0", action="基础"),
                TaskNode(id="task_1", action="左分支", depends_on=["task_0"]),
                TaskNode(id="task_2", action="右分支", depends_on=["task_0"]),
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

        # 初始：task_0 就绪
        self.assertEqual(state.get_next_ready_task().id, "task_0")

        # task_0 完成 → task_1 和 task_2 都就绪，选第一个（task_1）
        state.update_task_status("task_0", "completed")
        self.assertEqual(state.get_next_ready_task().id, "task_1")

        # task_1 完成 → task_2 就绪（task_0 已 completed）
        state.update_task_status("task_1", "completed")
        self.assertEqual(state.get_next_ready_task().id, "task_2")

        # task_2 完成 → task_3 就绪
        state.update_task_status("task_2", "completed")
        self.assertEqual(state.get_next_ready_task().id, "task_3")

        # task_3 完成 → 全部完成
        state.update_task_status("task_3", "completed")
        self.assertTrue(state.is_all_done())


class TestAgentRuntimeIntegration(unittest.TestCase):
    """AgentRuntime 上的 TaskGraph 集成方法测试。"""

    def setUp(self):
        from app.core.agent_runtime.agent import AgentRuntime
        self.runtime = AgentRuntime()
        self.plan = Plan(steps=[
            PlanStep(action="步骤1", suggested_tools=["tool1"]),
            PlanStep(action="步骤2", suggested_tools=["tool2"]),
            PlanStep(action="步骤3", suggested_tools=["tool3"]),
        ])

    def test_init_task_graph(self):
        """init_task_graph 正确构建状态机。"""
        state = self.runtime.init_task_graph(self.plan)

        self.assertIsNotNone(state)
        self.assertEqual(state.node_count, 3)
        self.assertIsNotNone(self.runtime.task_graph_state)

    def test_get_next_ready_task_via_runtime(self):
        """通过 AgentRuntime.get_next_ready_task() 获取就绪节点。"""
        self.runtime.init_task_graph(self.plan)

        task = self.runtime.get_next_ready_task()
        self.assertIsNotNone(task)
        self.assertEqual(task.id, "task_0")

    def test_update_task_status_via_runtime(self):
        """通过 AgentRuntime.update_task_status() 更新状态。"""
        self.runtime.init_task_graph(self.plan)

        # task_0 → completed
        ok = self.runtime.update_task_status("task_0", "completed")
        self.assertTrue(ok)

        # task_1 就绪
        task = self.runtime.get_next_ready_task()
        self.assertEqual(task.id, "task_1")

    def test_linear_progression_via_runtime(self):
        """通过 AgentRuntime 完整线性推进。"""
        self.runtime.init_task_graph(self.plan)

        # task_0
        task = self.runtime.get_next_ready_task()
        self.assertEqual(task.id, "task_0")
        self.runtime.update_task_status("task_0", "completed")

        # task_1
        task = self.runtime.get_next_ready_task()
        self.assertEqual(task.id, "task_1")
        self.runtime.update_task_status("task_1", "completed")

        # task_2
        task = self.runtime.get_next_ready_task()
        self.assertEqual(task.id, "task_2")
        self.runtime.update_task_status("task_2", "completed")

        # 全部完成
        self.assertIsNone(self.runtime.get_next_ready_task())
        self.assertTrue(self.runtime.task_graph_state.is_all_done())

    def test_runtime_without_init_returns_none(self):
        """未初始化 task_graph_state 时 get_next_ready_task 返回 None。"""
        # 未调用 init_task_graph
        self.assertIsNone(self.runtime.get_next_ready_task())
        self.assertFalse(self.runtime.update_task_status("task_0", "running"))


# ---------------------------------------------------------------------------
# G4-B: run_stream / run 中的 TaskGraph 事件测试
# ---------------------------------------------------------------------------


def _async_gen(events):
    """将事件列表转为 async generator。"""
    async def gen(*args, **kwargs):
        for e in events:
            yield e
    return gen


class _MockModelResult:
    """模拟 model_service.call_once 的返回值。"""
    def __init__(self, content="", tool_calls=None, usage="default", finish_reason="stop"):
        self.content = content
        self.tool_calls = tool_calls
        self.usage = {"prompt_tokens": 10, "completion_tokens": 10} if usage == "default" else usage
        self.finish_reason = finish_reason


class TestRunStreamTaskEvents(unittest.TestCase):
    """G4-B: run_stream 中 TaskGraph 事件 yield 验证。"""

    def setUp(self):
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context_builder import PassthroughContextBuilder
        self.runtime = AgentRuntime(context_builder=PassthroughContextBuilder())

    def _make_context(self, plan=None):
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

    def test_task_started_and_completed_events(self):
        """单任务 Plan → yield task_started + task_completed + finish。"""
        plan = Plan(steps=[PlanStep(action="分析文件")])
        context = self._make_context(plan=plan)
        messages = [{"role": "user", "content": "分析"}]

        # Mock: stream_once 每次返回一个 text + finish 事件
        mock_stream = _async_gen([
            {"type": "text", "content": "完成分析"},
            {"type": "finish", "finish_reason": "stop"},
        ])

        events = []
        with patch("app.services.model.model_service.stream_once", mock_stream), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            async def collect():
                async for event in self.runtime.run_stream(context, messages):
                    events.append(event)
            asyncio.run(collect())

        types = [e["type"] for e in events]
        self.assertIn("task_started", types)
        self.assertIn("task_completed", types)
        self.assertIn("finish", types)

        started = [e for e in events if e["type"] == "task_started"][0]
        self.assertEqual(started["task_id"], "task_0")
        self.assertEqual(started["action"], "分析文件")
        self.assertEqual(started["status"], "running")

        completed = [e for e in events if e["type"] == "task_completed"][0]
        self.assertEqual(completed["task_id"], "task_0")
        self.assertEqual(completed["status"], "completed")

    def test_multi_task_linear_progression(self):
        """3 步骤 Plan → 3 次 task_started + 3 次 task_completed，按顺序。"""
        plan = Plan(steps=[
            PlanStep(action="步骤A"),
            PlanStep(action="步骤B"),
            PlanStep(action="步骤C"),
        ])
        context = self._make_context(plan=plan)
        messages = [{"role": "user", "content": "执行"}]

        mock_stream = _async_gen([
            {"type": "text", "content": "ok"},
            {"type": "finish", "finish_reason": "stop"},
        ])

        events = []
        with patch("app.services.model.model_service.stream_once", mock_stream), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            async def collect():
                async for event in self.runtime.run_stream(context, messages):
                    events.append(event)
            asyncio.run(collect())

        started = [e for e in events if e["type"] == "task_started"]
        completed = [e for e in events if e["type"] == "task_completed"]

        self.assertEqual(len(started), 3)
        self.assertEqual(len(completed), 3)
        self.assertEqual(started[0]["task_id"], "task_0")
        self.assertEqual(started[1]["task_id"], "task_1")
        self.assertEqual(started[2]["task_id"], "task_2")
        self.assertEqual(completed[0]["task_id"], "task_0")
        self.assertEqual(completed[2]["task_id"], "task_2")

        # 最终 finish 只有一个
        finishes = [e for e in events if e["type"] == "finish"]
        self.assertEqual(len(finishes), 1)

    def test_task_failed_on_exception(self):
        """任务执行异常 → yield task_failed + 终止。"""
        plan = Plan(steps=[PlanStep(action="危险操作")])
        context = self._make_context(plan=plan)
        messages = [{"role": "user", "content": "执行"}]

        async def boom(*args, **kwargs):
            raise RuntimeError("LLM 调用失败")
            yield  # noqa: unreachable

        async def boom_reflection(*args, **kwargs):
            raise RuntimeError("反思调用失败")
            yield  # noqa: unreachable

        events = []
        with patch("app.services.model.model_service.stream_once", boom), \
             patch("app.services.model.model_service.call_once", boom_reflection), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            async def collect():
                async for event in self.runtime.run_stream(context, messages):
                    events.append(event)
            asyncio.run(collect())

        failed = [e for e in events if e["type"] == "task_failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["task_id"], "task_0")
        self.assertEqual(failed[0]["status"], "failed")
        self.assertIn("LLM", failed[0].get("error", ""))

    def test_no_plan_no_task_events(self):
        """无 Plan → 不 yield task_started / task_completed。"""
        context = self._make_context(plan=None)
        messages = [{"role": "user", "content": "hello"}]

        mock_stream = _async_gen([
            {"type": "text", "content": "hi"},
            {"type": "finish", "finish_reason": "stop"},
        ])

        events = []
        with patch("app.services.model.model_service.stream_once", mock_stream), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            async def collect():
                async for event in self.runtime.run_stream(context, messages):
                    events.append(event)
            asyncio.run(collect())

        types = [e["type"] for e in events]
        self.assertNotIn("task_started", types)
        self.assertNotIn("task_completed", types)
        self.assertIn("finish", types)

    def test_all_tasks_done_state(self):
        """全部任务完成后，TaskGraphState.is_all_done() 返回 True。"""
        plan = Plan(steps=[PlanStep(action="A"), PlanStep(action="B")])
        context = self._make_context(plan=plan)
        messages = [{"role": "user", "content": "执行"}]

        mock_stream = _async_gen([
            {"type": "text", "content": "ok"},
            {"type": "finish", "finish_reason": "stop"},
        ])

        with patch("app.services.model.model_service.stream_once", mock_stream), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            async def run():
                async for _ in self.runtime.run_stream(context, messages):
                    pass
            asyncio.run(run())

        self.assertTrue(self.runtime.task_graph_state.is_all_done())


class TestRunTaskGraphDriven(unittest.TestCase):
    """G4-B: run() 中 TaskGraph 驱动验证。"""

    def setUp(self):
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context_builder import PassthroughContextBuilder
        self.runtime = AgentRuntime(context_builder=PassthroughContextBuilder())

    def _make_context(self, plan=None):
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

    def test_run_with_plan_returns_result(self):
        """有 Plan 的 run() 正常返回 AgentResult。"""
        plan = Plan(steps=[PlanStep(action="任务1"), PlanStep(action="任务2")])
        context = self._make_context(plan=plan)
        messages = [_msg("user", "执行")]

        mock_result = _MockModelResult(content="完成", finish_reason="stop")
        mock_call = AsyncMock(return_value=mock_result)

        with patch("app.services.model.model_service.stream_once", stream_from_single_call(mock_call)), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            result = asyncio.run(self.runtime.run(context, messages))

        self.assertIsInstance(result, AgentResult)
        self.assertEqual(result.content, "完成")
        # 2 个任务 → 至少调用 2 次 call_once
        self.assertGreaterEqual(mock_call.call_count, 2)
        # TaskGraph 全部完成
        self.assertTrue(self.runtime.task_graph_state.is_all_done())

    def test_run_no_plan_original_behavior(self):
        """无 Plan 的 run() 保持原始行为。"""
        context = self._make_context(plan=None)
        messages = [_msg("user", "hello")]

        mock_result = _MockModelResult(content="hello back", finish_reason="stop")
        mock_call = AsyncMock(return_value=mock_result)

        with patch("app.services.model.model_service.stream_once", stream_from_single_call(mock_call)), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            result = asyncio.run(self.runtime.run(context, messages))

        self.assertIsInstance(result, AgentResult)
        self.assertEqual(result.content, "hello back")
        # 无 TaskGraph
        self.assertIsNone(self.runtime.task_graph_state)


# ---------------------------------------------------------------------------
# G5-B: Persona 动态注入测试
# ---------------------------------------------------------------------------

from app.core.agent_runtime.personas import (
    PERSONA_PROMPTS,
    get_persona_prompt,
)


class TestPersonaPrompts(unittest.TestCase):
    """personas.py 提示词库基础测试。"""

    def test_coding_agent_prompt_exists(self):
        prompt = get_persona_prompt("coding_agent")
        self.assertIsNotNone(prompt)
        self.assertIn("程序员", prompt)
        self.assertIn("Coding Agent", prompt)

    def test_research_agent_prompt_exists(self):
        prompt = get_persona_prompt("research_agent")
        self.assertIsNotNone(prompt)
        self.assertIn("研究员", prompt)
        self.assertIn("Research Agent", prompt)

    def test_default_agent_prompt_exists(self):
        prompt = get_persona_prompt("default_agent")
        self.assertIsNotNone(prompt)
        self.assertIn("通用助手", prompt)
        self.assertIn("Default Agent", prompt)

    def test_unknown_agent_returns_none(self):
        prompt = get_persona_prompt("nonexistent_agent")
        self.assertIsNone(prompt)


class TestRunStreamPersonaInjection(unittest.TestCase):
    """G5-B: run_stream 中 persona prompt 注入验证。"""

    def setUp(self):
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context_builder import PassthroughContextBuilder
        self.runtime = AgentRuntime(context_builder=PassthroughContextBuilder())

    def _make_context(self, plan=None):
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

    def test_coding_agent_persona_injected_into_messages(self):
        """coding_agent 的 persona prompt 出现在发给 LLM 的 messages 中。"""
        plan = Plan(steps=[
            PlanStep(action="编写代码", suggested_tools=["write_file"]),
        ])
        context = self._make_context(plan=plan)
        messages = [{"role": "user", "content": "执行"}]

        captured_messages = []

        async def capture_stream(**kwargs):
            captured_messages.append(list(kwargs.get("messages", [])))
            yield {"type": "text", "content": "done"}
            yield {"type": "finish", "finish_reason": "stop"}

        with patch("app.services.model.model_service.stream_once", capture_stream), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            async def run():
                async for _ in self.runtime.run_stream(context, messages):
                    pass
            asyncio.run(run())

        # 至少捕获到一次 messages
        self.assertGreater(len(captured_messages), 0)
        # 在某次调用的 messages 中，应包含 coding_agent 的 persona
        all_messages = []
        for msgs in captured_messages:
            all_messages.extend(msgs)

        persona_systems = [
            m for m in all_messages
            if m.get("role") == "system" and "Coding Agent" in m.get("content", "")
        ]
        self.assertGreater(len(persona_systems), 0, "coding_agent persona 未注入")

    def test_research_agent_persona_injected(self):
        """research_agent 的 persona prompt 注入。"""
        plan = Plan(steps=[
            PlanStep(action="搜索文档", suggested_tools=["search"]),
        ])
        context = self._make_context(plan=plan)
        messages = [{"role": "user", "content": "执行"}]

        captured_messages = []

        async def capture_stream(**kwargs):
            captured_messages.append(list(kwargs.get("messages", [])))
            yield {"type": "text", "content": "done"}
            yield {"type": "finish", "finish_reason": "stop"}

        with patch("app.services.model.model_service.stream_once", capture_stream), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            async def run():
                async for _ in self.runtime.run_stream(context, messages):
                    pass
            asyncio.run(run())

        all_messages = []
        for msgs in captured_messages:
            all_messages.extend(msgs)

        persona_systems = [
            m for m in all_messages
            if m.get("role") == "system" and "Research Agent" in m.get("content", "")
        ]
        self.assertGreater(len(persona_systems), 0, "research_agent persona 未注入")

    def test_mixed_agents_persona_switch(self):
        """混合任务中，不同任务注入不同 persona。"""
        plan = Plan(steps=[
            PlanStep(action="搜索资料", suggested_tools=["search"]),
            PlanStep(action="编写代码", suggested_tools=["write_file"]),
        ])
        context = self._make_context(plan=plan)
        messages = [{"role": "user", "content": "执行"}]

        captured_messages_per_call = []

        async def capture_stream(**kwargs):
            captured_messages_per_call.append(list(kwargs.get("messages", [])))
            yield {"type": "text", "content": "ok"}
            yield {"type": "finish", "finish_reason": "stop"}

        with patch("app.services.model.model_service.stream_once", capture_stream), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            async def run():
                async for _ in self.runtime.run_stream(context, messages):
                    pass
            asyncio.run(run())

        # 两次调用（每个任务一次）
        self.assertGreaterEqual(len(captured_messages_per_call), 2)

        # 第一次调用应含 Research Agent
        first_msgs = captured_messages_per_call[0]
        first_persona = [
            m for m in first_msgs
            if m.get("role") == "system" and "Research Agent" in m.get("content", "")
        ]
        self.assertGreater(len(first_persona), 0)

        # 第二次调用应含 Coding Agent
        second_msgs = captured_messages_per_call[1]
        second_persona = [
            m for m in second_msgs
            if m.get("role") == "system" and "Coding Agent" in m.get("content", "")
        ]
        self.assertGreater(len(second_persona), 0)

    def test_no_plan_no_persona_injection(self):
        """无 Plan 时不注入 persona。"""
        context = self._make_context(plan=None)
        messages = [{"role": "user", "content": "hello"}]

        captured_messages = []

        async def capture_stream(**kwargs):
            captured_messages.append(list(kwargs.get("messages", [])))
            yield {"type": "text", "content": "hi"}
            yield {"type": "finish", "finish_reason": "stop"}

        with patch("app.services.model.model_service.stream_once", capture_stream), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            async def run():
                async for _ in self.runtime.run_stream(context, messages):
                    pass
            asyncio.run(run())

        all_messages = []
        for msgs in captured_messages:
            all_messages.extend(msgs)

        persona_systems = [
            m for m in all_messages
            if m.get("role") == "system" and "【角色切换】" in m.get("content", "")
        ]
        self.assertEqual(len(persona_systems), 0)


class TestRunPersonaInjection(unittest.TestCase):
    """G5-B: run() 中 persona prompt 注入验证。"""

    def setUp(self):
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context_builder import PassthroughContextBuilder
        self.runtime = AgentRuntime(context_builder=PassthroughContextBuilder())

    def _make_context(self, plan=None):
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

    def test_coding_agent_persona_in_run(self):
        """run() 中 coding_agent persona 注入。"""
        plan = Plan(steps=[
            PlanStep(action="编写代码", suggested_tools=["write_file"]),
        ])
        context = self._make_context(plan=plan)
        messages = [_msg("user", "执行")]

        captured_messages = []

        async def mock_call(**kwargs):
            captured_messages.append(list(kwargs.get("messages", [])))
            return _MockModelResult(content="done", finish_reason="stop")

        with patch("app.services.model.model_service.stream_once", stream_from_single_call(mock_call)), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            asyncio.run(self.runtime.run(context, messages))

        all_messages = []
        for msgs in captured_messages:
            all_messages.extend(msgs)

        persona_systems = [
            m for m in all_messages
            if m.get("role") == "system" and "Coding Agent" in m.get("content", "")
        ]
        self.assertGreater(len(persona_systems), 0)


# ---------------------------------------------------------------------------
# G6-A: Token 水位监控测试
# ---------------------------------------------------------------------------

from app.core.agent_runtime.model_context_config import (
    MODEL_CONTEXT_WINDOWS,
    DEFAULT_CONTEXT_WINDOW,
    get_model_max_tokens,
    compute_watermark,
)


class TestModelContextConfig(unittest.TestCase):
    """模型上下文窗口配置测试。"""

    def test_known_model_exact_match(self):
        self.assertEqual(get_model_max_tokens("gpt-4o"), 128000)
        self.assertEqual(get_model_max_tokens("claude-3-5-sonnet"), 200000)  # 注册表真值：claude 系 200000（574 误填 1048576，已按 model_context_config 字典修正）
        self.assertEqual(get_model_max_tokens("deepseek-chat"), 1048576)

    def test_prefix_match(self):
        """前缀模糊匹配：gpt-4o-2024-08-06 → 128000"""
        self.assertEqual(get_model_max_tokens("gpt-4o-2024-08-06"), 128000)
        self.assertEqual(get_model_max_tokens("claude-3-5-sonnet-20241022"), 1048576)

    def test_unknown_model_returns_default(self):
        self.assertEqual(get_model_max_tokens("unknown-model-xyz"), DEFAULT_CONTEXT_WINDOW)

    def test_empty_model_id(self):
        self.assertEqual(get_model_max_tokens(""), DEFAULT_CONTEXT_WINDOW)
        self.assertEqual(get_model_max_tokens(None), DEFAULT_CONTEXT_WINDOW)

    def test_compute_watermark(self):
        """水位百分比计算。"""
        # 1000 / 128000 * 100 = 0.78
        self.assertEqual(compute_watermark(1000, "gpt-4o"), 0.78)
        # 1048576 / 1048576 * 100 = 100.0
        self.assertEqual(compute_watermark(1048576, "deepseek-chat"), 100.0)
        # 0 tokens → 0.0
        self.assertEqual(compute_watermark(0, "gpt-4o"), 0.0)


class TestTokenUsageEventBuilder(unittest.TestCase):
    """_build_token_usage_event 方法测试。"""

    def setUp(self):
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context_builder import PassthroughContextBuilder
        self.runtime = AgentRuntime(context_builder=PassthroughContextBuilder())

    def test_build_with_usage(self):
        usage = {
            "prompt_tokens": 500,
            "completion_tokens": 200,
            "total_tokens": 700,
        }
        event = self.runtime._build_token_usage_event(usage, "gpt-4o")

        self.assertEqual(event["type"], "token_usage")
        self.assertEqual(event["prompt_tokens"], 500)
        self.assertEqual(event["completion_tokens"], 200)
        self.assertEqual(event["total_tokens"], 700)
        self.assertEqual(event["model_max_tokens"], 128000)
        # 700 / 128000 * 100 = 0.55
        self.assertEqual(event["watermark_percentage"], 0.55)

    def test_build_without_total_tokens(self):
        """usage 无 total_tokens → 自动计算。"""
        usage = {
            "prompt_tokens": 300,
            "completion_tokens": 100,
        }
        event = self.runtime._build_token_usage_event(usage, "gpt-4o")

        self.assertEqual(event["total_tokens"], 400)
        self.assertEqual(event["watermark_percentage"], 0.31)

    def test_build_with_none_usage(self):
        """usage 为 None → 全零。"""
        event = self.runtime._build_token_usage_event(None, "gpt-4o")

        self.assertEqual(event["type"], "token_usage")
        self.assertEqual(event["prompt_tokens"], 0)
        self.assertEqual(event["completion_tokens"], 0)
        self.assertEqual(event["total_tokens"], 0)
        self.assertEqual(event["watermark_percentage"], 0.0)
        self.assertEqual(event["model_max_tokens"], 128000)

    def test_build_with_empty_dict(self):
        """usage 为空字典 → 全零。"""
        event = self.runtime._build_token_usage_event({}, "gpt-4o")

        self.assertEqual(event["prompt_tokens"], 0)
        self.assertEqual(event["watermark_percentage"], 0.0)


class TestRunStreamTokenUsageEvent(unittest.TestCase):
    """G6-A: run_stream 中 token_usage 事件 yield 验证。"""

    def setUp(self):
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context_builder import PassthroughContextBuilder
        self.runtime = AgentRuntime(context_builder=PassthroughContextBuilder())

    def _make_context(self, plan=None):
        return AgentContext(
            agent_id="test",
            agent_identity="test",
            personality_level=None,
            model_id="gpt-4o",
            chat_id=1,
            project_path=None,
            memory_context={},
            memory_text=None,
            tools=None,
            plan=plan,
        )

    def test_token_usage_event_in_stream(self):
        """finish 事件携带 usage → yield token_usage 事件。"""
        context = self._make_context(plan=None)
        messages = [{"role": "user", "content": "hello"}]

        async def mock_stream(**kwargs):
            yield {"type": "text", "content": "hi"}
            yield {
                "type": "finish",
                "finish_reason": "stop",
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            }

        events = []
        with patch("app.services.model.model_service.stream_once", mock_stream), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            async def collect():
                async for event in self.runtime.run_stream(context, messages):
                    events.append(event)
            asyncio.run(collect())

        token_events = [e for e in events if e["type"] == "token_usage"]
        self.assertEqual(len(token_events), 1)
        self.assertEqual(token_events[0]["prompt_tokens"], 100)
        self.assertEqual(token_events[0]["completion_tokens"], 50)
        self.assertEqual(token_events[0]["total_tokens"], 150)
        self.assertEqual(token_events[0]["model_max_tokens"], 128000)
        # 150 / 128000 * 100 = 0.12
        self.assertEqual(token_events[0]["watermark_percentage"], 0.12)

    def test_no_usage_no_token_event(self):
        """finish 无 usage → 不 yield token_usage。"""
        context = self._make_context(plan=None)
        messages = [{"role": "user", "content": "hello"}]

        async def mock_stream(**kwargs):
            yield {"type": "text", "content": "hi"}
            yield {"type": "finish", "finish_reason": "stop"}

        events = []
        with patch("app.services.model.model_service.stream_once", mock_stream), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            async def collect():
                async for event in self.runtime.run_stream(context, messages):
                    events.append(event)
            asyncio.run(collect())

        token_events = [e for e in events if e["type"] == "token_usage"]
        self.assertEqual(len(token_events), 0)

    def test_token_usage_with_task_graph(self):
        """有 Plan 时每个任务的 finish 都 yield token_usage。"""
        plan = Plan(steps=[
            PlanStep(action="步骤A"),
            PlanStep(action="步骤B"),
        ])
        context = self._make_context(plan=plan)
        messages = [{"role": "user", "content": "执行"}]

        call_count = [0]

        async def mock_stream(**kwargs):
            call_count[0] += 1
            yield {"type": "text", "content": "ok"}
            yield {
                "type": "finish",
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

        events = []
        with patch("app.services.model.model_service.stream_once", mock_stream), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            async def collect():
                async for event in self.runtime.run_stream(context, messages):
                    events.append(event)
            asyncio.run(collect())

        token_events = [e for e in events if e["type"] == "token_usage"]
        # 2 个任务 → 2 个 token_usage 事件
        self.assertEqual(len(token_events), 2)


class TestRunTokenUsageInResult(unittest.TestCase):
    """G6-A: run() 中 token_watermark 在 AgentResult.metadata 中。"""

    def setUp(self):
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context_builder import PassthroughContextBuilder
        self.runtime = AgentRuntime(context_builder=PassthroughContextBuilder())

    def _make_context(self, plan=None):
        return AgentContext(
            agent_id="test",
            agent_identity="test",
            personality_level=None,
            model_id="gpt-4o",
            chat_id=1,
            project_path=None,
            memory_context={},
            memory_text=None,
            tools=None,
            plan=plan,
        )

    def test_run_includes_token_watermark(self):
        """run() 结果的 metadata 中包含 token_watermark。"""
        context = self._make_context(plan=None)
        messages = [_msg("user", "hello")]

        mock_result = _MockModelResult(
            content="hi",
            finish_reason="stop",
            usage={"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300},
        )
        mock_call = AsyncMock(return_value=mock_result)

        with patch("app.services.model.model_service.stream_once", stream_from_single_call(mock_call)), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            result = asyncio.run(self.runtime.run(context, messages))

        self.assertIn("token_watermark", result.metadata)
        tw = result.metadata["token_watermark"]
        self.assertEqual(tw["prompt_tokens"], 200)
        self.assertEqual(tw["completion_tokens"], 100)
        self.assertEqual(tw["total_tokens"], 300)
        self.assertEqual(tw["model_max_tokens"], 128000)
        # 300 / 128000 * 100 = 0.23
        self.assertEqual(tw["watermark_percentage"], 0.23)

    def test_run_no_usage_no_watermark(self):
        """run() 无 usage → metadata 中 token_watermark 为 None。"""
        context = self._make_context(plan=None)
        messages = [_msg("user", "hello")]

        mock_result = _MockModelResult(content="hi", finish_reason="stop", usage=None)
        mock_call = AsyncMock(return_value=mock_result)

        with patch("app.services.model.model_service.stream_once", stream_from_single_call(mock_call)), \
             patch("app.core.agent_runtime.recorder.runtime_event_recorder"):
            result = asyncio.run(self.runtime.run(context, messages))

        self.assertIn("token_watermark", result.metadata)
        self.assertIsNone(result.metadata["token_watermark"])


if __name__ == "__main__":
    unittest.main()
