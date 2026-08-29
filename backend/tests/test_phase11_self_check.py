"""Phase 11 — Agent 战力解封与代码强制自查机制 单元测试

测试 5 大场景：
  1. max_tool_rounds 达到 10 轮且第 9 轮能正确注入倒数预警
  2. 模拟调用 write_file 后，验证系统能在内存中插队触发自查并设置 self_check_done
  3. 验证达到 max_tool_rounds 边界时不会死循环插队
  4. 验证自查 Prompt 绝不落库存入 chat_messages 表
  5. 验证未触发写操作时（如纯查询/聊天），不触发自查插队

通过 mock model_service.call_once() 和 execute_tool() 实现，无需真实 API 调用。
"""

import sys
import os
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import dataclass

import pytest
from tests._t4_mock_adapter import stream_from_single_call  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──── Mock 数据类 ────

@dataclass
class MockSingleCallResult:
    content: str
    tool_calls: list = None
    finish_reason: str = "stop"
    usage: dict = None


@dataclass
class MockModelMessage:
    role: str
    content: str

    def dict(self):
        return {"role": self.role, "content": self.content}


# ──── 辅助函数 ────

def make_tool_call(name: str, args: str = '{"relative_path": "test.py"}', call_id: str = "call_1"):
    """构造标准 tool_call 格式"""
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": args},
    }


def make_tool_result(name: str, result: str, success: bool = True, call_id: str = "call_1"):
    """构造 tool_result record"""
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


def make_tool_def(name: str):
    """构造工具定义"""
    return {"type": "function", "function": {"name": name, "description": "", "parameters": {}}}


# ──── 测试用例 ────

class TestPhase11ResolveMaxToolRounds:
    """_resolve_max_tool_rounds 静态方法测试"""

    def test_explicit_param(self):
        """显式参数优先级最高"""
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context import AgentContext

        ctx = AgentContext(
            agent_id="x", agent_identity="y", personality_level=None, model_id="m"
        )
        assert AgentRuntime._resolve_max_tool_rounds(ctx, 5) == 5

    def test_context_attribute(self):
        """AgentContext.max_tool_rounds 次优先"""
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.agent_runtime.context import AgentContext

        ctx = AgentContext(
            agent_id="x", agent_identity="y", personality_level=None, model_id="m",
            max_tool_rounds=7,
        )
        assert AgentRuntime._resolve_max_tool_rounds(ctx) == 7

    def test_default(self):
        """无显式配置时返回默认值 10"""
        from app.core.agent_runtime.agent import AgentRuntime, DEFAULT_MAX_TOOL_ROUNDS
        from app.core.agent_runtime.context import AgentContext

        ctx = AgentContext(
            agent_id="x", agent_identity="y", personality_level=None, model_id="m"
        )
        assert AgentRuntime._resolve_max_tool_rounds(ctx) == DEFAULT_MAX_TOOL_ROUNDS
        assert AgentRuntime._resolve_max_tool_rounds(ctx) == 10


class TestPhase11SelfCheck:
    """Phase 11: Agent 战力解封与代码强制自查机制 集成测试"""

    def _make_context(self, tools=None, max_tool_rounds=None):
        from app.core.agent_runtime.context import AgentContext
        return AgentContext(
            agent_id="test_agent",
            agent_identity="You are a helpful assistant.",
            personality_level=None,
            model_id="test-model",
            project_path="/tmp/test",
            tools=tools,
            max_tool_rounds=max_tool_rounds,
        )

    def _make_messages(self, user_text="hello"):
        return [
            MockModelMessage(role="system", content="You are a helpful assistant."),
            MockModelMessage(role="user", content=user_text),
        ]

    # ──── Test 1: max_tool_rounds=10 且第 9 轮注入倒数预警 ────

    @pytest.mark.asyncio
    @patch("app.core.tool_runtime.executor.execute_tool")
    @patch("app.services.model.model_service")
    async def test_max_tool_rounds_10_with_countdown(self, mock_model_service, mock_execute_tool):
        """测试：max_tool_rounds=10，第 9 轮（0-indexed round 8）注入倒数预警"""
        from app.core.agent_runtime.agent import AgentRuntime, COUNTDOWN_WARNING

        call_count = 0
        captured_messages_per_round = []

        async def call_once_side_effect(model_id, messages, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            # 捕获本轮 messages 用于验证
            captured_messages_per_round.append([dict(m) if isinstance(m, dict) else m for m in messages])

            if call_count <= 9:
                # 前 9 轮：始终返回 tool_call
                return MockSingleCallResult(
                    content="",
                    tool_calls=[make_tool_call("read_file", '{"relative_path": "test.py"}', f"call_{call_count}")],
                    finish_reason="tool_calls",
                    usage={"total_tokens": 100},
                )
            else:
                # 第 10 轮：返回最终文本
                return MockSingleCallResult(
                    content="任务完成。",
                    tool_calls=None,
                    finish_reason="stop",
                    usage={"total_tokens": 150},
                )

        mock_model_service.stream_once = stream_from_single_call(call_once_side_effect)
        mock_execute_tool.return_value = make_tool_result("read_file", "content")

        context = self._make_context(
            tools=[make_tool_def("read_file")],
            max_tool_rounds=10,
        )
        messages = self._make_messages("分析项目")

        runtime = AgentRuntime()
        result = await runtime.run(context=context, messages=messages)

        # 验证：10 轮全部执行
        assert call_count == 10, f"预期 10 次 call_once，实际: {call_count}"
        assert result.rounds == 10, f"预期 rounds=10，实际: {result.rounds}"
        assert result.finish_reason == "stop"

        # 验证：第 9 轮（call_count=9，即 0-indexed round 8）的消息中包含倒数预警
        round_9_messages = captured_messages_per_round[8]  # 0-indexed round 8
        found_countdown = any(
            m.get("content") == COUNTDOWN_WARNING
            for m in round_9_messages
        )
        assert found_countdown, f"第 9 轮消息中应包含倒数预警，实际未找到。消息列表: {[m.get('content','')[:80] for m in round_9_messages]}"

        # 验证：倒数预警不应出现在第 1 轮
        round_1_messages = captured_messages_per_round[0]
        found_early = any(
            m.get("content") == COUNTDOWN_WARNING
            for m in round_1_messages
        )
        assert not found_early, "第 1 轮不应包含倒数预警"

        print("  [PASS] Test 1: max_tool_rounds=10 且第 9 轮注入倒数预警")

    # ──── Test 2: write_file 触发自查插队 ────

    @pytest.mark.asyncio
    @patch("app.core.tool_runtime.executor.execute_tool")
    @patch("app.services.model.model_service")
    async def test_write_file_triggers_self_check(self, mock_model_service, mock_execute_tool):
        """测试：调用 write_file 后，LLM 准备结束时应触发自查插队"""
        from app.core.agent_runtime.agent import AgentRuntime, SELF_CHECK_PROMPT

        call_count = 0
        captured_messages_per_round = []

        async def call_once_side_effect(model_id, messages, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            captured_messages_per_round.append([dict(m) if isinstance(m, dict) else m for m in messages])

            if call_count == 1:
                # 第 1 轮：调用 write_file
                return MockSingleCallResult(
                    content="",
                    tool_calls=[make_tool_call("write_file", '{"relative_path": "test.py", "content": "print(1)"}', "call_1")],
                    finish_reason="tool_calls",
                    usage={"total_tokens": 100},
                )
            elif call_count == 2:
                # 第 2 轮：LLM 返回原始最终答案（无 tool_calls）→ 应被自查拦截
                return MockSingleCallResult(
                    content="已完成文件修改。",
                    tool_calls=None,
                    finish_reason="stop",
                    usage={"total_tokens": 120},
                )
            else:
                # 第 3 轮：自查后的最终汇报
                return MockSingleCallResult(
                    content="已核对修改，确认 write_file 写入内容正确，无语法错误。",
                    tool_calls=None,
                    finish_reason="stop",
                    usage={"total_tokens": 130},
                )

        mock_model_service.stream_once = stream_from_single_call(call_once_side_effect)
        mock_execute_tool.return_value = make_tool_result("write_file", "文件写入成功")

        context = self._make_context(tools=[make_tool_def("write_file")])
        messages = self._make_messages("创建 test.py")

        runtime = AgentRuntime()
        result = await runtime.run(context=context, messages=messages)

        # 验证：总共 3 次 call_once（第 1 轮工具调用 + 第 2 轮原始答案 + 第 3 轮自查汇报）
        assert call_count == 3, f"预期 3 次 call_once（工具+原始+自查），实际: {call_count}"

        # 验证：第 2 轮的消息中注入了自查提示
        round_2_messages = captured_messages_per_round[1]
        found_self_check = any(
            m.get("content") == SELF_CHECK_PROMPT
            for m in round_2_messages
        )
        assert not found_self_check, (
            "第 2 轮消息不应包含自查提示（自查提示应在第 2 轮返回后被注入，用于第 3 轮）"
        )

        # 验证：第 3 轮的消息中包含自查提示
        round_3_messages = captured_messages_per_round[2]
        found_self_check = any(
            m.get("content") == SELF_CHECK_PROMPT
            for m in round_3_messages
        )
        assert found_self_check, "第 3 轮消息中应包含自查提示"

        # 验证：最终结果是自查后的汇报，而非原始答案
        assert "已核对修改" in result.content, f"最终结果应为自查汇报，实际: {result.content}"
        assert result.content != "已完成文件修改。", "最终结果不应是原始答案"

        print("  [PASS] Test 2: write_file 触发自查插队")

    # ──── Test 3: max_tool_rounds 边界不会死循环 ────

    @pytest.mark.asyncio
    @patch("app.core.tool_runtime.executor.execute_tool")
    @patch("app.services.model.model_service")
    async def test_no_infinite_loop_at_boundary(self, mock_model_service, mock_execute_tool):
        """测试：达到 max_tool_rounds 边界时不会死循环插队"""
        from app.core.agent_runtime.agent import AgentRuntime, SELF_CHECK_PROMPT

        call_count = 0
        captured_messages_per_round = []

        async def call_once_side_effect(model_id, messages, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            captured_messages_per_round.append([dict(m) if isinstance(m, dict) else m for m in messages])

            if call_count == 1:
                # 第 1 轮：调用 write_file
                return MockSingleCallResult(
                    content="",
                    tool_calls=[make_tool_call("write_file", '{"relative_path": "test.py", "content": "x=1"}', "call_1")],
                    finish_reason="tool_calls",
                    usage={"total_tokens": 100},
                )
            else:
                # 后续轮次：返回最终答案
                return MockSingleCallResult(
                    content="完成。",
                    tool_calls=None,
                    finish_reason="stop",
                    usage={"total_tokens": 50},
                )

        mock_model_service.stream_once = stream_from_single_call(call_once_side_effect)
        mock_execute_tool.return_value = make_tool_result("write_file", "ok")

        # 设置 max_tool_rounds=2：第 0 轮有工具，第 1 轮无工具
        context = self._make_context(
            tools=[make_tool_def("write_file")],
            max_tool_rounds=2,
        )
        messages = self._make_messages("修改 test.py")

        runtime = AgentRuntime()
        result = await runtime.run(context=context, messages=messages)

        # 验证：不会死循环，最多 3 次调用（工具 + 回答 + 自查）
        assert call_count <= 3, f"不应死循环，预期最多 3 次调用，实际: {call_count}"

        # 验证：最终有结果返回
        assert result.content is not None
        assert len(result.content) > 0

        print("  [PASS] Test 3: max_tool_rounds 边界不会死循环")

    # ──── Test 4: 自查 Prompt 不落库 ────

    @pytest.mark.asyncio
    @patch("app.core.tool_runtime.executor.execute_tool")
    @patch("app.services.model.model_service")
    async def test_self_check_prompt_not_persisted(self, mock_model_service, mock_execute_tool):
        """测试：自查 Prompt 仅在内存中参与推理，不写入最终结果"""
        from app.core.agent_runtime.agent import AgentRuntime, SELF_CHECK_PROMPT

        call_count = 0
        all_messages_seen = []

        async def call_once_side_effect(model_id, messages, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            for m in messages:
                all_messages_seen.append(dict(m) if isinstance(m, dict) else m)

            if call_count == 1:
                return MockSingleCallResult(
                    content="",
                    tool_calls=[make_tool_call("write_file", '{"relative_path": "a.py", "content": "pass"}', "call_1")],
                    finish_reason="tool_calls",
                    usage={"total_tokens": 100},
                )
            elif call_count == 2:
                return MockSingleCallResult(
                    content="文件已修改。",
                    tool_calls=None,
                    finish_reason="stop",
                    usage={"total_tokens": 50},
                )
            else:
                return MockSingleCallResult(
                    content="自查完成：write_file 写入正确，无语法错误。",
                    tool_calls=None,
                    finish_reason="stop",
                    usage={"total_tokens": 60},
                )

        mock_model_service.stream_once = stream_from_single_call(call_once_side_effect)
        mock_execute_tool.return_value = make_tool_result("write_file", "ok")

        context = self._make_context(tools=[make_tool_def("write_file")])
        messages = self._make_messages("创建 a.py")

        runtime = AgentRuntime()
        result = await runtime.run(context=context, messages=messages)

        # 验证：自查提示确实在内存消息中出现过（参与了推理）
        found_in_memory = any(
            m.get("content") == SELF_CHECK_PROMPT
            for m in all_messages_seen
        )
        assert found_in_memory, "自查提示应在内存消息中出现（参与推理）"

        # 验证：最终 AgentResult.content 不包含自查提示原文
        assert SELF_CHECK_PROMPT not in result.content, (
            f"最终结果不应包含自查提示原文，实际: {result.content[:200]}"
        )

        # 验证：最终结果是自查后的汇报，不是原始答案
        assert "文件已修改。" not in result.content or "自查" in result.content, (
            "最终结果应包含自查内容"
        )

        print("  [PASS] Test 4: 自查 Prompt 不落库")

    # ──── Test 5: 纯查询不触发自查 ────

    @pytest.mark.asyncio
    @patch("app.core.tool_runtime.executor.execute_tool")
    @patch("app.services.model.model_service")
    async def test_read_only_no_self_check(self, mock_model_service, mock_execute_tool):
        """测试：纯查询/聊天操作（read_file）不触发自查插队"""
        from app.core.agent_runtime.agent import AgentRuntime, SELF_CHECK_PROMPT

        call_count = 0
        all_messages_seen = []

        async def call_once_side_effect(model_id, messages, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            for m in messages:
                all_messages_seen.append(dict(m) if isinstance(m, dict) else m)

            if call_count == 1:
                # 第 1 轮：调用 read_file（非写操作）
                return MockSingleCallResult(
                    content="",
                    tool_calls=[make_tool_call("read_file", '{"relative_path": "test.py"}', "call_1")],
                    finish_reason="tool_calls",
                    usage={"total_tokens": 100},
                )
            else:
                # 第 2 轮：返回最终答案
                return MockSingleCallResult(
                    content="文件内容为: print('hello')",
                    tool_calls=None,
                    finish_reason="stop",
                    usage={"total_tokens": 80},
                )

        mock_model_service.stream_once = stream_from_single_call(call_once_side_effect)
        mock_execute_tool.return_value = make_tool_result("read_file", "print('hello')")

        context = self._make_context(tools=[make_tool_def("read_file")])
        messages = self._make_messages("读取 test.py")

        runtime = AgentRuntime()
        result = await runtime.run(context=context, messages=messages)

        # 验证：只调用了 2 次 call_once（工具调用 + 最终回答）
        assert call_count == 2, f"预期 2 次调用，实际: {call_count}"

        # 验证：自查提示从未出现在任何消息中
        found_self_check = any(
            m.get("content") == SELF_CHECK_PROMPT
            for m in all_messages_seen
        )
        assert not found_self_check, "纯查询操作不应触发自查提示"

        # 验证：结果正常返回
        assert "print('hello')" in result.content
        assert result.finish_reason == "stop"

        print("  [PASS] Test 5: 纯查询不触发自查")


# ──── Test 6: 纯文本聊天（无工具）不触发自查 ────

class TestPhase11NoTools:
    """Phase 11: 无工具场景不触发自查"""

    @pytest.mark.asyncio
    @patch("app.services.model.model_service")
    async def test_pure_chat_no_self_check(self, mock_model_service):
        """测试：纯文本聊天（无工具）不触发自查插队"""
        from app.core.agent_runtime.agent import AgentRuntime, SELF_CHECK_PROMPT

        call_count = 0
        all_messages_seen = []

        async def call_once_side_effect(model_id, messages, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            for m in messages:
                all_messages_seen.append(dict(m) if isinstance(m, dict) else m)
            return MockSingleCallResult(
                content="你好！有什么可以帮助你的？",
                tool_calls=None,
                finish_reason="stop",
                usage={"total_tokens": 50},
            )

        mock_model_service.stream_once = stream_from_single_call(call_once_side_effect)

        from app.core.agent_runtime.context import AgentContext
        context = AgentContext(
            agent_id="test_agent",
            agent_identity="You are a helpful assistant.",
            personality_level=None,
            model_id="test-model",
            tools=None,
        )
        messages = [
            MockModelMessage(role="system", content="You are a helpful assistant."),
            MockModelMessage(role="user", content="你好"),
        ]

        runtime = AgentRuntime()
        result = await runtime.run(context=context, messages=messages)

        # 验证：只调用 1 次
        assert call_count == 1, f"预期 1 次调用，实际: {call_count}"

        # 验证：自查提示未出现
        found_self_check = any(
            m.get("content") == SELF_CHECK_PROMPT
            for m in all_messages_seen
        )
        assert not found_self_check, "无工具场景不应触发自查"

        assert result.content == "你好！有什么可以帮助你的？"

        print("  [PASS] Test 6: 纯文本聊天不触发自查")