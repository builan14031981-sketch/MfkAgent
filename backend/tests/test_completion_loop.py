"""MfkAgent Autonomous Completion Loop V1 测试。

覆盖 4 个用例：
  Case 1: 成功完成   —— 执行工具 → 验证通过 → Agent 结束
  Case 2: 失败继续   —— 验证失败 → 生成反馈上下文 → 重新进入执行循环
  Case 3: 最大重试   —— 连续失败达到 max_completion_retry → 安全退出
  Case 4: TaskGraph —— TaskNode → Verification → 节点状态正确变化

全部通过 mock model_service.call_once / execute_tool 实现，无真实 LLM / 工具调用。
"""

import json
import sys
import os
import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from tests._t4_mock_adapter import stream_from_single_call  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.agent_runtime.completion.llm_judge import JUDGE_MARKER  # noqa: E402


# ──── Mock 数据类 ────


@dataclass
class MockSingleCallResult:
    content: str
    tool_calls: list = None
    finish_reason: str = "stop"
    usage: dict = None


class _MockModelMessage:
    """类 ModelMessage 对象（run() 中 messages[-1].content / _to_dict_messages 需要）。"""

    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


# ──── 辅助函数 ────


def make_tool_call(name: str, args: str, call_id: str = "call_1"):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": args}}


def make_tool_result(name: str, result: str, success: bool = True, call_id: str = "call_1"):
    return {
        "name": name,
        "tool": name,
        "path": "",
        "success": success,
        "status": "success" if success else "failed",
        "arguments": {},
        "result": result,
        "duration_ms": 10,
        "tool_call_id": call_id,
    }


def make_judge_result(completed: bool, reason: str = "", missing=None, suggestion: str = ""):
    payload = {"completed": completed, "reason": reason, "missing": missing or [], "suggestion": suggestion}
    return MockSingleCallResult(content=json.dumps(payload, ensure_ascii=False), tool_calls=None)


def _is_judge_call(messages) -> bool:
    """判断本次 call_once 是否来自 LLM Judge（消息含识别标记）。"""
    for m in messages or []:
        if isinstance(m, dict) and JUDGE_MARKER in str(m.get("content", "")):
            return True
        if hasattr(m, "content") and JUDGE_MARKER in str(getattr(m, "content", "")):
            return True
    return False


# ──── 测试用例 ────


class TestCompletionLoop:
    """Completion Loop V1 执行流测试。"""

    def _make_context(self, tools=None, completion_verification=True, max_completion_retry=None, plan=None):
        from app.core.agent_runtime.agent import AgentContext
        return AgentContext(
            agent_id="test_agent",
            agent_identity="You are a helpful assistant.",
            personality_level=None,
            model_id="test-model-qwen",  # 不依赖真实模型；真实调用全部被 mock
            project_path=None,
            tools=tools,
            plan=plan,
            memory_context={},
            chat_id=None,
            completion_verification=completion_verification,
            max_completion_retry=max_completion_retry,
        )

    @staticmethod
    def _make_messages(user_text="hello"):
        return [
            _MockModelMessage(role="system", content="You are a helpful assistant."),
            _MockModelMessage(role="user", content=user_text),
        ]

    def _run(self, runtime, context, messages, mock_model_service):
        return asyncio.run(runtime.run(context=context, messages=messages))

    # ──── Case 1: 成功完成 ────

    @patch("app.core.tool_runtime.executor.execute_tool")
    @patch("app.core.agent_runtime.agent.runtime_event_recorder")
    @patch("app.services.model.model_service")
    def test_case1_success_completion(self, mock_model_service, mock_recorder, mock_execute_tool):
        """工具执行 → 完成验证通过 → Agent 结束（judge completed=true）。"""
        from app.core.agent_runtime.agent import AgentRuntime

        call_count = 0

        async def side_effect(model_id, messages, tools=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if _is_judge_call(messages):
                return make_judge_result(True, reason="判定完成")
            if call_count == 1:
                return MockSingleCallResult(
                    content="",
                    tool_calls=[make_tool_call("read_file", '{"relative_path": "a.py"}', "call_1")],
                    finish_reason="tool_calls",
                    usage={"total_tokens": 100},
                )
            return MockSingleCallResult(
                content="已完成任务，验证通过。",
                tool_calls=None,
                finish_reason="stop",
                usage={"total_tokens": 200},
            )

        mock_model_service.call_once = AsyncMock(side_effect=side_effect)  # judge/反思/压缩等内部单次调用仍走 call_once
        mock_model_service.stream_once = stream_from_single_call(AsyncMock(side_effect=side_effect))
        mock_execute_tool.return_value = make_tool_result("read_file", "ok", call_id="call_1")

        context = self._make_context(
            tools=[{"type": "function", "function": {"name": "read_file", "description": "", "parameters": {}}}]
        )
        messages = self._make_messages("读取文件")

        runtime = AgentRuntime()
        result = self._run(runtime, context, messages, mock_model_service)

        assert result.content == "已完成任务，验证通过。", f"预期最终内容，实际: {result.content}"
        assert result.finish_reason == "stop", f"预期 stop，实际: {result.finish_reason}"
        assert result.metadata["completion"]["verified"] is True, "预期 completion.verified=True"
        assert len(result.tool_calls) == 1, "预期 1 个工具调用"

        # judge 至少调用 1 次
        emits = [c.args for c in mock_recorder.emit.call_args_list]
        assert any(e[1] == "completion_verify_started" for e in emits), "缺少 completion_verify_started 事件"
        assert any(e[1] == "completion_verify_passed" for e in emits), "缺少 completion_verify_passed 事件"

    # ──── Case 2: 失败继续 ────

    @patch("app.core.agent_runtime.agent.runtime_event_recorder")
    @patch("app.services.model.model_service")
    def test_case2_failure_then_continue(self, mock_model_service, mock_recorder):
        """验证失败 → 注入反馈 → 重新进入执行循环 → 最终完成。"""
        from app.core.agent_runtime.agent import AgentRuntime

        call_count = 0
        judge_calls = 0

        async def side_effect(model_id, messages, tools=None, **kwargs):
            nonlocal call_count, judge_calls
            call_count += 1
            if _is_judge_call(messages):
                judge_calls += 1
                if judge_calls == 1:
                    # 注意：reason/missing 必须避开写/测试关键字——Round 2 完成验证会把
                    # 失败反馈（含 reason）以 user 角色回注入 messages，_extract_task_goal
                    # 未跳过该反馈节点，会将其当作重试轮的任务目标；若含"生成/测试"等字样，
                    # 规则层（rule_write_detected / rule_test_scope_guard）会先于 judge 拦截。
                    return make_judge_result(False, reason="回答不够完整", missing=["缺少必要的细节说明"], suggestion="补充说明")
                return make_judge_result(True, reason="回答完整")
            # 主循环：每轮直接输出最终内容（无工具）
            return MockSingleCallResult(
                content="实现完成。",
                tool_calls=None,
                finish_reason="stop",
                usage={"total_tokens": 100 + call_count},
            )

        mock_model_service.call_once = AsyncMock(side_effect=side_effect)  # judge/反思/压缩等内部单次调用仍走 call_once
        mock_model_service.stream_once = stream_from_single_call(AsyncMock(side_effect=side_effect))

        # 中性任务文本：不含写/测试意图，避免规则层在首轮就拦截（规则层在 judge 之前）。
        context = self._make_context(tools=None)
        messages = self._make_messages("解释什么是 MfkAgent")

        runtime = AgentRuntime()
        result = self._run(runtime, context, messages, mock_model_service)

        # 主循环最多允许 DEFAULT_MAX_COMPLETION_RETRY 次失败后仍只跑一轮；失败后应继续
        emits = [c.args for c in mock_recorder.emit.call_args_list]
        failed_events = [e for e in emits if e[1] == "completion_verify_failed"]
        passed_events = [e for e in emits if e[1] == "completion_verify_passed"]
        assert len(failed_events) >= 1, "预期至少 1 次 completion_verify_failed"
        assert len(passed_events) >= 1, "预期最终 completion_verify_passed"
        assert result.metadata["completion"]["verified"] is True, "重试后应最终验证通过"
        assert judge_calls >= 2, f"预期 judge 至少调 2 次, 实际 {judge_calls}"
        assert call_count >= 4, f"预期多轮 call_once, 实际 {call_count}"

    # ──── Case 3: 最大重试保护 ────

    @patch("app.core.agent_runtime.agent.runtime_event_recorder")
    @patch("app.services.model.model_service")
    def test_case3_max_retry_safe_exit(self, mock_model_service, mock_recorder):
        """连续验证失败达到 max_completion_retry → 安全退出，保留未完成原因。

        Round 2 完成验证契约：重试轮规则层（防逃逸）先于 judge 拦截，重试主要靠规则层
        判定（judge 仅首轮被调用）；耗尽后以结构化失败汇报（【任务未完全完成】…）收尾，
        不再返回主循环文本。
        """
        from app.core.agent_runtime.agent import AgentRuntime

        judge_calls = 0

        async def side_effect(model_id, messages, tools=None, **kwargs):
            nonlocal judge_calls
            if _is_judge_call(messages):
                judge_calls += 1
                return make_judge_result(False, reason="回答不够完整", missing=["缺乏结论"], suggestion="补充结论")
            return MockSingleCallResult(
                content="只能做到这里了。",
                tool_calls=None,
                finish_reason="stop",
                usage={"total_tokens": 100},
            )

        mock_model_service.call_once = AsyncMock(side_effect=side_effect)  # judge/反思/压缩等内部单次调用仍走 call_once
        mock_model_service.stream_once = stream_from_single_call(AsyncMock(side_effect=side_effect))

        context = self._make_context(tools=None, max_completion_retry=3)
        # 中性任务文本：不含写/测试意图，保证首轮进入 judge 层而非规则层。
        messages = self._make_messages("解释一个概念")

        runtime = AgentRuntime()
        result = self._run(runtime, context, messages, mock_model_service)

        # 安全退出：finish=completion_failed + verified=False + 结构化失败汇报 + 记录原因
        assert result.finish_reason == "completion_failed", f"预期 completion_failed, 实际 {result.finish_reason}"
        assert "【任务未完全完成】" in result.content, "验证耗尽应以结构化失败汇报收尾"
        completion_meta = result.metadata["completion"]
        assert completion_meta is not None and completion_meta["verified"] is False, "预期 verified=False"
        assert completion_meta["retry_count"] == 3, f"预期 retry_count=3, 实际 {completion_meta['retry_count']}"
        assert completion_meta["reason"], "预期记录了未完成原因"
        assert judge_calls >= 1, f"预期 judge 至少调用 1 次, 实际 {judge_calls}"

    # ──── Case 4: TaskGraph 节点状态 ────

    @patch("app.core.agent_runtime.agent.runtime_event_recorder")
    @patch("app.services.model.model_service")
    def test_case4_taskgraph_node_completion(self, mock_model_service, mock_recorder):
        """单节点 TaskGraph → 验证通过 → 节点 completed，事件与状态正确。"""
        from app.core.planner.models import Plan, PlanStep
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context_builder import PassthroughContextBuilder
        from app.core.task_graph.models import TaskNodeStatus

        # 注：任务 action 不可含写文件关键字（"生成/创建/写入/修改"），
        #     否则 rule_write_detected 规则会要求写工具调用，导致验证失败。
        plan = Plan(steps=[PlanStep(action="回答用户问题")])

        async def side_effect(model_id, messages, tools=None, **kwargs):
            # plan 路径的 LLM 调用本轮为主循环 call（judge 也走同一 call_once，靠标记区分）
            if _is_judge_call(messages):
                return make_judge_result(True, reason="已完整回答")
            return MockSingleCallResult(content="用户问题的答案。", finish_reason="stop", usage={"total_tokens": 20})

        mock_model_service.call_once = AsyncMock(side_effect=side_effect)  # judge/反思/压缩等内部单次调用仍走 call_once
        mock_model_service.stream_once = stream_from_single_call(AsyncMock(side_effect=side_effect))

        context = self._make_context(tools=None, plan=plan)
        messages = [SimpleNamespace(role="user", content="什么是 MfkAgent")]

        runtime = AgentRuntime(context_builder=PassthroughContextBuilder())
        result = self._run(runtime, context, messages, mock_model_service)

        # 节点 completed + completion.verified=True
        node = runtime.task_graph_state.get_task("task_0")
        assert node is not None, "task_0 应存在"
        assert node.status == TaskNodeStatus.COMPLETED, f"节点应 completed, 实际 {node.status}"
        assert runtime.task_graph_state.is_all_done(), "全图应 done"
        assert result.metadata["completion"]["verified"] is True, "预期 completion.verified=True"

        # task_completed 事件携带 completion_verified
        emits = [c.args for c in mock_recorder.emit.call_args_list]
        task_done = [e for e in emits if e[1] == "task_completed"]
        assert len(task_done) == 1, "预期 1 次 task_completed"
        assert task_done[0][2].get("completion_verified") is True, "预期 task_completed 携带 completion_verified=True"