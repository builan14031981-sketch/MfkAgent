# -*- coding: utf-8 -*-
"""T4 双循环合一测试。

验收项：
  A. 非流式审批契约：run() 遇 tool_approval 立即返回 pending_approval（不同步
     await 审批，5s 超时兜底），审批条目保留在 approval_registry（不再像旧实现
     那样 resolve cancelled + remove）；经 approval_registry.resolve（等价于
     POST /{chat_id}/approve 的动作）后后台续跑收尾，on_complete 交付完整结果。
  B. turn_reminder 无重复包裹：合一后包裹点只在统一实现（run_stream）一处，
     run() 作为消费者不再包裹 —— 断言标记在发往 LLM 的 messages 中恰好出现 1 次。
  C. TaskRouter 双路统一：路由仅在统一实现中调用 1 次，决策仅写入 metadata，
     不改变执行路径。
  D. 聚合兼容：run() drain 事件流重建的 AgentResult 与旧返回结构逐字段兼容。
  E. 抉择卡沿用旧契约：非流式自动采纳推荐项，不挂起。
  F. 结构断言：agent.py 不再存在第二套工具轮次循环（旧实现归档于 _legacy_run.py）。

全部 mock，无真实 LLM / 工具调用（asyncio.run 同步包装，与本仓测试基建一致）。
"""
import asyncio
import sys
import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.agent_runtime.agent import AgentRuntime, AgentResult  # noqa: E402
from app.core.agent_runtime.context import AgentContext  # noqa: E402
from app.core.agent_runtime.context_builder import PassthroughContextBuilder  # noqa: E402
from app.core.tool_runtime.approval import approval_registry  # noqa: E402
from app.core.tool_runtime.choice import choice_registry  # noqa: E402

TURN_REMINDER_MARK = "【T4-REMINDER-MARK】收尾提醒"


def _stream_events(*events):
    """把事件序列包装成 stream_once 型 async generator 工厂。"""
    async def _gen(*args, **kwargs):
        for e in events:
            yield dict(e)
    return _gen


def _make_recorder():
    """捕获 runtime_event_recorder 调用（替代真实 DB recorder）。"""
    rec = MagicMock()
    rec.create_run.return_value = 1
    rec.events = []
    rec.emit.side_effect = lambda run_id, t, p=None: rec.events.append((t, p or {}))
    return rec


def _make_context(tools=None, metadata=None, chat_id=1):
    return AgentContext(
        agent_id="test",
        agent_identity="test identity",
        personality_level=None,
        model_id="test-model",
        chat_id=chat_id,
        project_path=None,
        memory_context={},
        memory_text=None,
        tools=tools,
        plan=None,
        metadata=metadata,
    )


def _make_runtime():
    return AgentRuntime(context_builder=PassthroughContextBuilder())


def _stub_run_stream(runtime, *events):
    """把 runtime.run_stream 替换为按 yield 协议（现状文档 3.5）发事件的原样实现。

    run() 消费的正是 run_stream 的 yield 协议；协议级测试直接喂协议事件，
    不经 _run_stream_events 内部（其模型事件分支会吞掉 tool_approval 等非
    模型事件类型——那些事件真实路径由 _exec_tool_calls 产出）。
    """
    runtime.run_stream = lambda **kwargs: _stream_events(*events)()


def _approval_event(approval_id):
    return {
        "type": "tool_approval",
        "approval_id": approval_id,
        "tool_call_id": "call_1",
        "tool": "run_command",
        "command": "npm test",
        "risk_level": "high",
        "risk_reason": "命令执行需审批",
        "chat_id": 1,
    }


class TestNonStreamApprovalContract(unittest.TestCase):
    """A: 非流式审批契约 pending_approval → /approve（registry.resolve）→ 后台续跑闭环。"""

    def test_run_returns_pending_approval_immediately(self):
        """遇 tool_approval 立即返回（不挂 300s）；审批条目保留待 /approve。"""
        runtime = _make_runtime()
        with patch("app.core.agent_runtime.agent.runtime_event_recorder", _make_recorder()):
            async def _main():
                # 5s 超时兜底：若 run() 同步 await 审批（旧行为 300s 挂起）则此处失败
                approval_id, _info = approval_registry.register(
                    tool_call_id="call_1", chat_id=1, tool="run_command",
                    command="npm test", risk_level="high", risk_reason="命令执行需审批",
                )
                def _bind_stream(_aid=approval_id):
                    return lambda **kwargs: _stream_events(
                        {"type": "text", "content": "先看看"},
                        _approval_event(_aid),
                        {"type": "finish", "finish_reason": "stop"},
                    )()
                runtime.run_stream = _bind_stream()
                try:
                    result = await asyncio.wait_for(
                        runtime.run(context=_make_context(), messages=[{"role": "user", "content": "跑测试"}]),
                        timeout=5,
                    )
                    # 关键行为差异（vs 旧实现）：审批条目未被 resolve cancelled / remove，
                    # 留在注册表中等待前端 POST /{chat_id}/approve
                    assert approval_registry.get(approval_id) is not None, "审批应保留挂起而非被取消"
                    return result, approval_id
                finally:
                    approval_registry.resolve(approval_id, "cancelled")
                    approval_registry.remove(approval_id)

            result, approval_id = asyncio.run(_main())

        self.assertIsInstance(result, AgentResult)
        self.assertEqual(result.finish_reason, "pending_approval")
        pa = result.metadata.get("pending_approval") or {}
        self.assertEqual(pa.get("approval_id"), approval_id)
        self.assertEqual(pa.get("tool"), "run_command")
        self.assertEqual(pa.get("command"), "npm test")

    def test_pending_continuation_delivers_final_result_via_on_complete(self):
        """approve 后后台续跑至收尾，完整结果经 on_complete 回调交付。"""
        delivered = []

        async def on_complete(final_result):
            delivered.append(final_result)

        runtime = _make_runtime()
        with patch("app.core.agent_runtime.agent.runtime_event_recorder", _make_recorder()):
            async def _main():
                approval_id, _info = approval_registry.register(
                    tool_call_id="call_1", chat_id=1, tool="run_command",
                    command="npm test", risk_level="high", risk_reason="命令执行需审批",
                )
                def _bind_stream(_aid=approval_id):
                    return lambda **kwargs: _stream_events(
                        _approval_event(_aid),
                        {"type": "text", "content": "续跑完成"},
                        {"type": "token_usage", "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                        {"type": "finish", "finish_reason": "stop"},
                        {"type": "tool_calls", "calls": [{"tool": "run_command", "success": True, "result": "ok"}]},
                    )()
                runtime.run_stream = _bind_stream()
                try:
                    result = await asyncio.wait_for(
                        runtime.run(
                            context=_make_context(), messages=[{"role": "user", "content": "跑测试"}],
                            on_complete=on_complete,
                        ),
                        timeout=5,
                    )
                    self.assertEqual(result.finish_reason, "pending_approval")
                    # 等价于前端 POST /approve → approval_registry.resolve
                    self.assertTrue(approval_registry.resolve(approval_id, "approve"))
                    # 等待后台续跑交付完整结果
                    for _ in range(100):
                        if delivered:
                            return
                        await asyncio.sleep(0.05)
                    self.fail("on_complete 未在 5s 内收到续跑完整结果")
                finally:
                    approval_registry.resolve(approval_id, "approve")
                    approval_registry.remove(approval_id)

            asyncio.run(_main())

            self.assertEqual(len(delivered), 1)
            final = delivered[0]
            self.assertIsInstance(final, AgentResult)
            self.assertEqual(final.content, "续跑完成")
            self.assertEqual(final.finish_reason, "stop")
            self.assertEqual(final.usage.get("total_tokens"), 15)
            self.assertEqual(final.tool_calls, [{"tool": "run_command", "success": True, "result": "ok"}])


class TestTurnReminderSingleWrap(unittest.TestCase):
    """B: turn_reminder 只在统一实现中包裹一次（run/run_stream 同一实现）。"""

    def _capture_stream(self):
        captured = []

        def stream(model_id, messages, **kwargs):
            captured.append([dict(m) for m in messages])
            return _stream_events(
                {"type": "text", "content": "ok"},
                {"type": "finish", "finish_reason": "stop"},
            )()

        return stream, captured

    def _count_mark(self, messages):
        return sum(
            1 for m in messages
            if isinstance(m, dict) and TURN_REMINDER_MARK in str(m.get("content", ""))
        )

    def test_run_wraps_turn_reminder_exactly_once(self):
        stream, captured = self._capture_stream()
        runtime = _make_runtime()
        context = _make_context(metadata={"turn_reminder": TURN_REMINDER_MARK})
        with patch("app.services.model.model_service", MagicMock(stream_once=stream)), \
             patch("app.core.agent_runtime.agent.runtime_event_recorder", _make_recorder()):
            result = asyncio.run(runtime.run(context=context, messages=[
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "hello"},
            ]))
        self.assertEqual(len(captured), 1)
        self.assertEqual(self._count_mark(captured[0]), 1, "turn_reminder 应恰好包裹 1 次（禁止双路径重复包裹）")
        self.assertEqual(result.content, "ok")

    def test_run_stream_wraps_turn_reminder_exactly_once(self):
        stream, captured = self._capture_stream()
        runtime = _make_runtime()
        context = _make_context(metadata={"turn_reminder": TURN_REMINDER_MARK})
        with patch("app.services.model.model_service", MagicMock(stream_once=stream)), \
             patch("app.core.agent_runtime.agent.runtime_event_recorder", _make_recorder()):
            async def collect():
                async for _ in runtime.run_stream(context=context, messages=[
                    {"role": "system", "content": "sys"},
                    {"role": "user", "content": "hello"},
                ]):
                    pass

            asyncio.run(collect())
        self.assertEqual(len(captured), 1)
        self.assertEqual(self._count_mark(captured[0]), 1)


class TestTaskRouterUnified(unittest.TestCase):
    """C: TaskRouter 两路统一 —— 仅在统一实现中调用 1 次，决策仅写 metadata。"""

    def test_router_called_once_and_decision_only_in_metadata(self):
        stream = _stream_events(
            {"type": "text", "content": "done"},
            {"type": "finish", "finish_reason": "stop"},
        )
        runtime = _make_runtime()
        orig_route = runtime.router.route
        route_calls = []

        def spy_route(**kwargs):
            route_calls.append(kwargs)
            return orig_route(**kwargs)

        runtime.router.route = spy_route
        tools = [{"type": "function", "function": {"name": "read_file", "description": "", "parameters": {}}}]
        with patch("app.services.model.model_service", MagicMock(stream_once=stream)), \
             patch("app.core.agent_runtime.agent.runtime_event_recorder", _make_recorder()):
            result = asyncio.run(runtime.run(
                context=_make_context(tools=tools),
                messages=[{"role": "user", "content": "帮我执行部署"}],
            ))

        self.assertEqual(len(route_calls), 1, "TaskRouter 应在统一实现中恰好调用 1 次")
        # 决策仅写 metadata（不改执行路径：mock 流原样跑完）
        for key in ("task_type", "intent", "confidence", "reason"):
            self.assertIn(key, result.metadata, f"metadata 应含路由决策字段 {key}")


class TestAggregationCompat(unittest.TestCase):
    """D: 事件聚合 → AgentResult 结构兼容（content/usage/tool_calls/metadata）。"""

    def test_aggregates_result_fields(self):
        calls = [{"tool": "read_file", "tool_call_id": "c1", "success": True, "result": "内容"}]
        runtime = _make_runtime()
        _stub_run_stream(
            runtime,
            {"type": "state_change", "state": "llm_call", "reason": "execution loop"},
            {"type": "text", "content": "你"},
            {"type": "text", "content": "好"},
            {"type": "token_usage", "prompt_tokens": 100, "completion_tokens": 20,
             "total_tokens": 120, "cached_tokens": 8},
            {"type": "task_graph", "task_graph": {"total_steps": 1, "completed": 1, "is_all_done": True}},
            {"type": "tool_calls", "calls": calls},
            {"type": "finish", "finish_reason": "stop"},
        )
        with patch("app.core.agent_runtime.agent.runtime_event_recorder", _make_recorder()):
            result = asyncio.run(runtime.run(
                context=_make_context(),
                messages=[{"role": "user", "content": "hi"}],
            ))

        self.assertEqual(result.content, "你好")
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.tool_calls, calls)
        self.assertEqual(result.usage, {
            "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120, "cached_tokens": 8,
        })
        self.assertEqual(result.metadata.get("task_graph"), {"total_steps": 1, "completed": 1, "is_all_done": True})
        self.assertEqual(result.metadata.get("token_watermark", {}).get("total_tokens"), 120)
        self.assertEqual(result.metadata.get("agent_id"), "test")
        self.assertGreaterEqual(result.rounds, 1)

    def test_empty_content_fallback_matches_legacy(self):
        """无文本事件时兜底文案与旧实现口径一致。"""
        runtime = _make_runtime()
        _stub_run_stream(
            runtime,
            {"type": "tool_calls", "calls": [{"tool": "t", "success": True, "result": "r"}]},
            {"type": "finish", "finish_reason": "stop"},
        )
        with patch("app.core.agent_runtime.agent.runtime_event_recorder", _make_recorder()):
            result = asyncio.run(runtime.run(
                context=_make_context(), messages=[{"role": "user", "content": "hi"}],
            ))
        self.assertEqual(result.content, "已为您完成相关的处理与工具调用。")


class TestChoiceAutoAdopt(unittest.TestCase):
    """E: 抉择卡沿用旧契约 —— 非流式自动采纳推荐项，不挂起。"""

    def test_choice_request_auto_resolved(self):
        runtime = _make_runtime()
        with patch("app.core.agent_runtime.agent.runtime_event_recorder", _make_recorder()):
            async def _main():
                choice_id, _info = choice_registry.register(
                    tool_call_id="call_9", chat_id=1, question="怎么处理？",
                    options=[{"label": "方案A", "description": ""}, {"label": "方案B", "description": ""}],
                    recommended=1,
                )
                def _bind_stream(_cid=choice_id):
                    return lambda **kwargs: _stream_events(
                        {"type": "choice_request", "choice_id": _cid, "tool_call_id": "call_9",
                         "question": "怎么处理？", "options": [], "recommended": 1},
                        {"type": "text", "content": "已采纳"},
                        {"type": "finish", "finish_reason": "stop"},
                    )()
                runtime.run_stream = _bind_stream()
                try:
                    # 5s 超时兜底：若未自动采纳（挂起等待用户抉择）则失败
                    return await asyncio.wait_for(
                        runtime.run(context=_make_context(), messages=[{"role": "user", "content": "q"}]),
                        timeout=5,
                    )
                finally:
                    choice_registry.resolve(choice_id, {"selected": None, "custom_text": None})
                    choice_registry.remove(choice_id)

            result = asyncio.run(_main())
        self.assertEqual(result.content, "已采纳")


class TestStructureSingleLoop(unittest.TestCase):
    """F: 结构断言 —— agent.py 不再存在第二套工具轮次循环。"""

    def test_agent_py_has_no_second_tool_loop(self):
        agent_src = (Path(__file__).resolve().parent.parent / "app/core/agent_runtime/agent.py").read_text(encoding="utf-8")
        legacy_src = (Path(__file__).resolve().parent.parent / "app/core/agent_runtime/_legacy_run.py").read_text(encoding="utf-8")
        # 非流式旧的"审批拒绝"调用点（support_approval=False kwarg）只允许存在于归档文件
        # （agent.py 中的 144 行注释提到该历史分支，不计为调用点）
        self.assertNotIn("support_approval=False,", agent_src)
        self.assertIn("support_approval=False,", legacy_src)
        # 旧实现整体归档，运行时无 import / 无调用
        self.assertNotIn("from app.core.agent_runtime._legacy_run import", agent_src)
        self.assertNotIn("legacy_run(", agent_src)
        self.assertIn("async def legacy_run(", legacy_src)


if __name__ == "__main__":
    unittest.main()
