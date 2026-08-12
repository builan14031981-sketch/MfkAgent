# -*- coding: utf-8 -*-
"""Round 2 失败模式优化 — 轮次耗尽去短路化 + 失败处置分级测试。

覆盖：
  Part A 纯函数辅助：
    A1: _build_completion_feedback 按 next_action 分级 + retry>=2 追加防逃逸强制约束
    A2: _is_hard_completion_failure 硬/软缺失分级
    A3: _build_completion_failure_report 结构化兜底汇报
    A4: _task_round_budget 探索/执行任务预算差异化
  Part B 端到端（mock，无真实 LLM / 工具）：
    B1: Round 2 回归场景 —— 跑过一次红色 pytest 后空回复 → 规则层拦截 →
        重试耗尽 → finish_reason=completion_failed + 结构化失败汇报（不再空回复静默 stop）
    B2: 对照场景 —— 无测试意图任务验证耗尽（软性缺失）→ 保留已有内容，不替换为失败汇报

全部通过 mock model_service.call_once / execute_tool 实现。
"""

import json
import sys
import os
import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.agent_runtime.agent import AgentRuntime  # noqa: E402
from app.core.agent_runtime.completion.llm_judge import JUDGE_MARKER  # noqa: E402


# ──── Mock 数据类（与 test_completion_loop.py 同款 harness）────


@dataclass
class MockSingleCallResult:
    content: str
    tool_calls: list = None
    finish_reason: str = "stop"
    usage: dict = None


class _MockModelMessage:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


def make_tool_call(name: str, args: str, call_id: str = "call_1"):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": args}}


def _is_judge_call(messages) -> bool:
    for m in messages or []:
        if isinstance(m, dict) and JUDGE_MARKER in str(m.get("content", "")):
            return True
        if hasattr(m, "content") and JUDGE_MARKER in str(getattr(m, "content", "")):
            return True
    return False


def _fake_result(missing=None, reason="", next_action=""):
    return SimpleNamespace(missing_items=missing or [], reason=reason, next_action=next_action)


# ──── Part A: 纯函数辅助 ────


class TestCompletionHelpers:

    def test_feedback_next_action_mapping(self):
        """fix_tool_actions / continue_execution 分别映射到对应要求文案。"""
        fb_fix = AgentRuntime._build_completion_feedback(
            _fake_result(missing=["工具执行失败: write_file"], next_action="fix_tool_actions"), retry_count=1
        )
        assert "修正上述失败的工具动作后重新执行" in fb_fix
        assert "【强制约束】" not in fb_fix, "retry_count<2 不应追加防逃逸约束"

        fb_cont = AgentRuntime._build_completion_feedback(
            _fake_result(missing=["缺少测试复跑"], next_action="continue_execution"), retry_count=0
        )
        assert "继续执行，直至上述缺失项全部消除" in fb_cont

    def test_feedback_anti_escape_on_repeat_failure(self):
        """连续失败 retry>=2 → 追加防逃逸强制约束（全量 pytest，不得跳过曾失败文件）。"""
        fb = AgentRuntime._build_completion_feedback(
            _fake_result(missing=["最后一次测试执行未全绿"], next_action="continue_execution"), retry_count=2
        )
        assert "【强制约束】" in fb
        assert "pytest tests" in fb
        assert "不得跳过" in fb

    def test_hard_failure_classification(self):
        """硬性关键词命中 → True；软性缺失 → False；None/空缺失 → False。"""
        assert AgentRuntime._is_hard_completion_failure(
            _fake_result(missing=["最后一次测试执行未全绿，需修复后重跑验证"])
        ) is True
        assert AgentRuntime._is_hard_completion_failure(
            _fake_result(missing=["验证范围缩水：曾失败的测试未复跑（tests/test_a.py）"])
        ) is True
        assert AgentRuntime._is_hard_completion_failure(
            _fake_result(missing=["未产出最终回答"])
        ) is False
        assert AgentRuntime._is_hard_completion_failure(_fake_result(missing=[])) is False
        assert AgentRuntime._is_hard_completion_failure(None) is False

    def test_failure_report_structure(self):
        """兜底汇报包含：标题 / 未完成项 / 判定原因 / 建议下一步。"""
        report = AgentRuntime._build_completion_failure_report(
            _fake_result(missing=["最后一次测试执行未全绿"], reason="规则层验证未通过")
        )
        assert report.startswith("【任务未完全完成】")
        assert "- 最后一次测试执行未全绿" in report
        assert "判定原因：规则层验证未通过" in report
        assert "建议下一步" in report

    def test_task_round_budget(self):
        """探索类任务收紧到 6（下限 3）；执行类保持默认。"""
        assert AgentRuntime._task_round_budget("确认数据库连接配置", 10) == 6
        assert AgentRuntime._task_round_budget("查看现有代码结构", 4) == 4
        assert AgentRuntime._task_round_budget("定位问题根因", 2) == 3
        assert AgentRuntime._task_round_budget("实现登录模块代码", 10) == 10
        assert AgentRuntime._task_round_budget("", 10) == 10


# ──── Part B: 端到端（轮次耗尽去短路化回归）────


class TestExhaustedPath:

    @staticmethod
    def _make_context(max_completion_retry=1, tools=None):
        from app.core.agent_runtime.agent import AgentContext
        return AgentContext(
            agent_id="test_agent",
            agent_identity="You are a helpful assistant.",
            personality_level=None,
            model_id="test-model-qwen",
            project_path=None,
            tools=tools,
            plan=None,
            memory_context={},
            chat_id=None,
            completion_verification=True,
            max_completion_retry=max_completion_retry,
        )

    # Round 2 实证逃逸序列：pytest 红色一次 → 之后持续空回复
    _PYTEST_RED = (
        "=========================== short test summary info ===========================\n"
        "FAILED tests/test_api.py::test_login - AssertionError\n"
        "========================= 1 failed in 0.42s =========================\n"
        "[exit code 1]"
    )

    @patch("app.core.tool_runtime.executor.execute_tool")
    @patch("app.core.agent_runtime.agent.runtime_event_recorder")
    @patch("app.services.model.model_service")
    def test_red_pytest_then_silence_reports_failure(
        self, mock_model_service, mock_recorder, mock_execute_tool
    ):
        """Round 2 回归：跑过一次红色 pytest 后空回复 → 验证管道拦截 →
        重试耗尽 → completion_failed + 结构化失败汇报（不再空回复静默 stop）。"""
        call_count = 0

        async def side_effect(model_id, messages, tools=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if _is_judge_call(messages):
                # 规则层应先行拦截；judge 兜底也判未完成
                return MockSingleCallResult(
                    content=json.dumps(
                        {"completed": False, "reason": "测试未绿", "missing": ["测试未绿"], "suggestion": ""},
                        ensure_ascii=False,
                    )
                )
            if call_count == 1 and tools:
                return MockSingleCallResult(
                    content="",
                    tool_calls=[make_tool_call(
                        "run_command", '{"command": "pytest tests/test_api.py"}', "call_1"
                    )],
                    finish_reason="tool_calls",
                    usage={"total_tokens": 100},
                )
            # 之后全部空回复、无工具（模拟 Round 2 的静默逃逸）
            return MockSingleCallResult(content="", tool_calls=None, usage={"total_tokens": 50})

        mock_model_service.call_once = AsyncMock(side_effect=side_effect)
        mock_execute_tool.return_value = {
            "name": "run_command",
            "tool": "run_command",
            "path": "",
            "success": True,
            "status": "success",
            "arguments": {"command": "pytest tests/test_api.py"},
            "result": self._PYTEST_RED,
            "duration_ms": 420,
            "tool_call_id": "call_1",
        }

        context = self._make_context(
            max_completion_retry=1,
            tools=[{"type": "function", "function": {
                "name": "run_command", "description": "", "parameters": {},
            }}],
        )
        messages = [
            _MockModelMessage(role="system", content="You are a helpful assistant."),
            _MockModelMessage(role="user", content="修复登录缺陷，并保证测试全绿"),
        ]

        result = asyncio.run(AgentRuntime().run(context=context, messages=messages))

        # 1) 收尾语义：completion_failed 而非静默 stop
        assert result.finish_reason == "completion_failed", (
            f"预期 completion_failed，实际: {result.finish_reason}"
        )
        # 2) 兜底汇报：非空且结构化（杜绝空回复），包含硬性失败项
        assert result.content and result.content.startswith("【任务未完全完成】"), (
            f"预期结构化失败汇报，实际: {result.content!r}"
        )
        assert any(k in result.content for k in ("未全绿", "验证失败", "执行失败")), (
            f"预期兜底汇报含硬性失败项，实际: {result.content!r}"
        )
        # 3) metadata 记录验证失败与原因
        meta = result.metadata["completion"]
        assert meta["verified"] is False
        assert meta["retry_count"] == 1
        # 4) 事件链：至少 1 次 completion_verify_failed，且缺失项命中硬性关键词
        emits = [c.args for c in mock_recorder.emit.call_args_list]
        failed_events = [e for e in emits if e[1] == "completion_verify_failed"]
        assert len(failed_events) >= 1, "预期至少 1 次 completion_verify_failed"
        assert any(
            any(k in item
                for item in (e[2].get("missing_items") or [])
                for k in ("未全绿", "验证范围缩水", "验证失败", "执行失败"))
            for e in failed_events
        ), "预期验证管道拦截（missing 命中硬性关键词）"

    @patch("app.core.agent_runtime.agent.runtime_event_recorder")
    @patch("app.services.model.model_service")
    def test_soft_missing_keeps_content(self, mock_model_service, mock_recorder):
        """对照：软性缺失（judge 报"未产出最终回答"类缺失）耗尽 → 保留已有内容，不替换为失败汇报。"""

        async def side_effect(model_id, messages, tools=None, **kwargs):
            if _is_judge_call(messages):
                return MockSingleCallResult(
                    content=json.dumps(
                        {"completed": False, "reason": "回答不完整", "missing": ["未产出最终回答"], "suggestion": ""},
                        ensure_ascii=False,
                    )
                )
            return MockSingleCallResult(
                content="已完成部分工作。", tool_calls=None, usage={"total_tokens": 80}
            )

        mock_model_service.call_once = AsyncMock(side_effect=side_effect)

        context = self._make_context(max_completion_retry=1)
        messages = [
            _MockModelMessage(role="system", content="You are a helpful assistant."),
            _MockModelMessage(role="user", content="整理一份说明"),
        ]

        result = asyncio.run(AgentRuntime().run(context=context, messages=messages))

        # 软性缺失：finish_reason 覆写为 completion_failed，但保留模型已产出的内容
        assert result.finish_reason == "completion_failed"
        assert result.content == "已完成部分工作。", "软性缺失应保留已完成内容，不替换为兜底汇报"
        assert result.metadata["completion"]["verified"] is False
