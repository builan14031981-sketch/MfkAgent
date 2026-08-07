"""Agent Runtime Phase 3 — Execution Loop 单元测试

测试 5 种流程：
  1. 普通聊天（无工具）
  2. 单工具调用
  3. 多轮工具调用
  4. 工具失败
  5. MAX_ROUNDS 限制

通过 mock model_service.call_once() 和 execute_tool() 实现，
无需真实 API 调用。
"""

import sys
import os
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import dataclass

# 确保 backend 在 sys.path 中
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

def make_tool_call(name: str, args: str, call_id: str = "call_1"):
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

class TestAgentRuntimePhase3:
    """AgentRuntime Phase 3 Execution Loop 测试"""

    def _make_context(self, tools=None, decision=None, memory_text=None):
        """构造 AgentContext"""
        from app.core.agent_runtime.agent import AgentContext
        return AgentContext(
            agent_id="test_agent",
            agent_identity="You are a helpful assistant.",
            personality_level=None,
            model_id="test-model",
            project_path="/tmp/test",
            tools=tools,
            decision=decision,
            memory_text=memory_text,
        )

    def _make_messages(self, user_text="hello"):
        """构造 messages 列表"""
        return [
            MockModelMessage(role="system", content="You are a helpful assistant."),
            MockModelMessage(role="user", content=user_text),
        ]

    # ──── Test 1: 普通聊天流程 ────

    @patch("app.services.model.model_service")
    async def test_normal_chat(self, mock_model_service):
        """测试：普通聊天（无工具），应返回 1 轮结果"""
        from app.core.agent_runtime.agent import AgentRuntime

        # Mock: 模型返回纯文本（无 tool_calls）
        mock_model_service.call_once = AsyncMock(return_value=MockSingleCallResult(
            content="你好！有什么可以帮助你的？",
            tool_calls=None,
            finish_reason="stop",
            usage={"total_tokens": 50},
        ))

        context = self._make_context(tools=None)
        messages = self._make_messages("你好")

        runtime = AgentRuntime()
        result = await runtime.run(context=context, messages=messages)

        # 验证
        assert result.content == "你好！有什么可以帮助你的？", f"预期文本回复，实际: {result.content}"
        assert result.rounds == 1, f"预期 rounds=1，实际: {result.rounds}"
        assert result.finish_reason == "stop", f"预期 finish_reason=stop，实际: {result.finish_reason}"
        assert result.tool_calls == [], f"预期 tool_calls=[]，实际: {result.tool_calls}"
        assert result.metadata["task_type"] == "chat", f"预期 task_type=chat，实际: {result.metadata['task_type']}"
        assert mock_model_service.call_once.call_count == 1, "预期只调用 1 次 call_once"

        print("  [PASS] Test 1: 普通聊天流程")

    # ──── Test 2: 单工具调用流程 ────

    @patch("app.core.tool_runtime.executor.execute_tool")
    @patch("app.services.model.model_service")
    async def test_single_tool_call(self, mock_model_service, mock_execute_tool):
        """测试：单工具调用 → 执行工具 → 回喂结果 → 最终回答，rounds=2"""
        from app.core.agent_runtime.agent import AgentRuntime

        call_count = 0

        async def call_once_side_effect(model_id, messages, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # 第一轮：返回 tool_call
                return MockSingleCallResult(
                    content="",
                    tool_calls=[make_tool_call("read_file", '{"relative_path": "test.py"}', "call_1")],
                    finish_reason="tool_calls",
                    usage={"total_tokens": 100},
                )
            else:
                # 第二轮：返回最终文本
                return MockSingleCallResult(
                    content="文件内容如下：print('hello')",
                    tool_calls=None,
                    finish_reason="stop",
                    usage={"total_tokens": 150},
                )

        mock_model_service.call_once = AsyncMock(side_effect=call_once_side_effect)
        mock_execute_tool.return_value = make_tool_result("read_file", "print('hello')")

        context = self._make_context(tools=[make_tool_def("read_file")])
        messages = self._make_messages("读取 test.py")

        runtime = AgentRuntime()
        result = await runtime.run(context=context, messages=messages)

        # 验证
        assert "print('hello')" in result.content, f"预期包含文件内容，实际: {result.content}"
        assert result.rounds == 2, f"预期 rounds=2，实际: {result.rounds}"
        assert result.finish_reason == "stop", f"预期 finish_reason=stop，实际: {result.finish_reason}"
        assert len(result.tool_calls) == 1, f"预期 1 个 tool_call，实际: {len(result.tool_calls)}"
        assert result.tool_calls[0]["name"] == "read_file"
        assert result.tool_calls[0]["success"] is True
        assert mock_model_service.call_once.call_count == 2, "预期 2 次 call_once"
        assert mock_execute_tool.call_count == 1, "预期 1 次工具执行"

        print("  [PASS] Test 2: 单工具调用流程")

    # ──── Test 3: 多轮工具调用流程 ────

    @patch("app.core.tool_runtime.executor.execute_tool")
    @patch("app.services.model.model_service")
    async def test_multi_round_tool_calls(self, mock_model_service, mock_execute_tool):
        """测试：两轮工具调用 → 最终回答，rounds=3"""
        from app.core.agent_runtime.agent import AgentRuntime

        call_count = 0

        async def call_once_side_effect(model_id, messages, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MockSingleCallResult(
                    content="",
                    tool_calls=[make_tool_call("list_files", '{"relative_path": "."}', "call_1")],
                    finish_reason="tool_calls",
                    usage={"total_tokens": 100},
                )
            elif call_count == 2:
                return MockSingleCallResult(
                    content="",
                    tool_calls=[make_tool_call("read_file", '{"relative_path": "main.py"}', "call_2")],
                    finish_reason="tool_calls",
                    usage={"total_tokens": 150},
                )
            else:
                return MockSingleCallResult(
                    content="分析了文件列表和 main.py，项目结构清晰。",
                    tool_calls=None,
                    finish_reason="stop",
                    usage={"total_tokens": 200},
                )

        mock_model_service.call_once = AsyncMock(side_effect=call_once_side_effect)

        tool_results = [
            make_tool_result("list_files", "main.py\ntest.py", call_id="call_1"),
            make_tool_result("read_file", "print('hello')", call_id="call_2"),
        ]
        mock_execute_tool.side_effect = tool_results

        context = self._make_context(tools=[make_tool_def("list_files"), make_tool_def("read_file")])
        messages = self._make_messages("分析项目结构")

        runtime = AgentRuntime()
        result = await runtime.run(context=context, messages=messages)

        # 验证
        assert "项目结构" in result.content, f"预期包含总结，实际: {result.content}"
        assert result.rounds == 3, f"预期 rounds=3，实际: {result.rounds}"
        assert len(result.tool_calls) == 2, f"预期 2 个 tool_call，实际: {len(result.tool_calls)}"
        assert mock_model_service.call_once.call_count == 3, "预期 3 次 call_once"
        assert mock_execute_tool.call_count == 2, "预期 2 次工具执行"

        print("  [PASS] Test 3: 多轮工具调用流程")

    # ──── Test 4: 工具失败流程 ────

    @patch("app.core.tool_runtime.executor.execute_tool")
    @patch("app.services.model.model_service")
    async def test_tool_failure(self, mock_model_service, mock_execute_tool):
        """测试：工具执行失败 → 错误回喂模型 → 模型给出替代回答，rounds=2"""
        from app.core.agent_runtime.agent import AgentRuntime

        call_count = 0

        async def call_once_side_effect(model_id, messages, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MockSingleCallResult(
                    content="",
                    tool_calls=[make_tool_call("read_file", '{"relative_path": "nonexistent.py"}', "call_1")],
                    finish_reason="tool_calls",
                    usage={"total_tokens": 100},
                )
            else:
                return MockSingleCallResult(
                    content="抱歉，无法读取 nonexistent.py，文件不存在。",
                    tool_calls=None,
                    finish_reason="stop",
                    usage={"total_tokens": 120},
                )

        mock_model_service.call_once = AsyncMock(side_effect=call_once_side_effect)
        mock_execute_tool.return_value = make_tool_result(
            "read_file", "错误: 文件不存在: nonexistent.py", success=False
        )

        context = self._make_context(tools=[make_tool_def("read_file")])
        messages = self._make_messages("读取 nonexistent.py")

        runtime = AgentRuntime()
        result = await runtime.run(context=context, messages=messages)

        # 验证
        assert "无法读取" in result.content or "不存在" in result.content, f"预期包含错误处理，实际: {result.content}"
        assert result.rounds == 2, f"预期 rounds=2，实际: {result.rounds}"
        assert len(result.tool_calls) == 1, f"预期 1 个 tool_call，实际: {len(result.tool_calls)}"
        assert result.tool_calls[0]["success"] is False, "预期工具失败"
        assert "文件不存在" in result.tool_calls[0]["result"], "预期错误信息"

        print("  [PASS] Test 4: 工具失败流程")

    # ──── Test 5: MAX_ROUNDS 限制流程 ────

    @patch("app.core.tool_runtime.executor.execute_tool")
    @patch("app.services.model.model_service")
    async def test_max_rounds_limit(self, mock_model_service, mock_execute_tool):
        """测试：模型持续返回 tool_calls → 第 3 轮无 tools → 强制文本回答"""
        from app.core.agent_runtime.agent import AgentRuntime

        # 模型始终返回 tool_calls（模拟"不听话"的模型）
        async def call_once_side_effect(model_id, messages, tools, **kwargs):
            if tools:
                return MockSingleCallResult(
                    content="",
                    tool_calls=[make_tool_call("read_file", '{"relative_path": "x.py"}', "call_x")],
                    finish_reason="tool_calls",
                    usage={"total_tokens": 50},
                )
            else:
                # 最后一轮无 tools，模型被迫返回文本
                return MockSingleCallResult(
                    content="我已经读取了足够的信息，总结如下...",
                    tool_calls=None,
                    finish_reason="stop",
                    usage={"total_tokens": 80},
                )

        mock_model_service.call_once = AsyncMock(side_effect=call_once_side_effect)
        mock_execute_tool.return_value = make_tool_result("read_file", "content")

        context = self._make_context(tools=[make_tool_def("read_file")])
        messages = self._make_messages("读取所有文件")

        runtime = AgentRuntime()
        result = await runtime.run(context=context, messages=messages)

        # 验证
        assert "总结" in result.content, f"预期包含总结，实际: {result.content}"
        # MAX_ROUNDS=3：前 2 轮有 tools（返回 tool_calls），第 3 轮无 tools（返回文本）
        # round_no 从 0 开始，每次 tool_calls 后 +1
        # round 0: tools=yes → tool_calls → round_no=1
        # round 1: tools=yes → tool_calls → round_no=2
        # round 2: tools=no → no tool_calls → break
        # rounds = 2 + 1 = 3
        assert result.rounds == 3, f"预期 rounds=3，实际: {result.rounds}"
        assert result.finish_reason == "stop", f"预期 finish_reason=stop，实际: {result.finish_reason}"
        assert len(result.tool_calls) == 2, f"预期 2 个 tool_call（前 2 轮），实际: {len(result.tool_calls)}"
        assert mock_model_service.call_once.call_count == 3, "预期 3 次 call_once"

        print("  [PASS] Test 5: MAX_ROUNDS 限制流程")

    # ──── Test 6: 无工具可用时跳过工具调用 ────

    @patch("app.services.model.model_service")
    async def test_no_tools_available(self, mock_model_service):
        """测试：无可用工具时，直接回答，不尝试工具调用"""
        from app.core.agent_runtime.agent import AgentRuntime

        mock_model_service.call_once = AsyncMock(return_value=MockSingleCallResult(
            content="Python 是一种解释型语言...",
            tool_calls=None,
            finish_reason="stop",
            usage={"total_tokens": 80},
        ))

        context = self._make_context(tools=None)  # 无工具
        messages = self._make_messages("什么是 Python？")

        runtime = AgentRuntime()
        result = await runtime.run(context=context, messages=messages)

        assert result.rounds == 1, f"预期 rounds=1，实际: {result.rounds}"
        assert result.tool_calls == [], "预期无 tool_calls"
        # 验证 call_once 被调用时 tools=None
        call_args = mock_model_service.call_once.call_args
        assert call_args[1]["tools"] is None, "预期 tools=None"

        print("  [PASS] Test 6: 无工具可用")

    # ──── Test 7: memory_text 仅首轮注入 ────

    @patch("app.services.model.model_service")
    async def test_memory_text_first_round_only(self, mock_model_service):
        """测试：memory_text 仅在 round 0 注入，后续轮次不注入"""
        from app.core.agent_runtime.agent import AgentRuntime

        call_count = 0

        async def call_once_side_effect(model_id, messages, tools, memory_text, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                assert memory_text is not None, "第 1 轮应有 memory_text"
                return MockSingleCallResult(
                    content="",
                    tool_calls=[make_tool_call("read_file", '{"relative_path": "test.py"}', "call_1")],
                    finish_reason="tool_calls",
                    usage={"total_tokens": 50},
                )
            else:
                assert memory_text is None, f"第 {call_count} 轮不应有 memory_text"
                return MockSingleCallResult(
                    content="done",
                    tool_calls=None,
                    finish_reason="stop",
                    usage={"total_tokens": 30},
                )

        mock_model_service.call_once = AsyncMock(side_effect=call_once_side_effect)

        with patch("app.core.tool_runtime.executor.execute_tool") as mock_exec:
            mock_exec.return_value = make_tool_result("read_file", "content")

            context = self._make_context(
                tools=[make_tool_def("read_file")],
                memory_text="<user_defined_memories>test memory</user_defined_memories>",
            )
            messages = self._make_messages("读取文件")

            runtime = AgentRuntime()
            result = await runtime.run(context=context, messages=messages)

            assert result.rounds == 2
            assert mock_model_service.call_once.call_count == 2, "预期 2 次 call_once"

        print("  [PASS] Test 7: memory_text 仅首轮注入")


# ──── 运行入口 ────

async def run_all_tests():
    """运行所有测试"""
    test = TestAgentRuntimePhase3()

    tests = [
        ("Test 1: 普通聊天流程", test.test_normal_chat),
        ("Test 2: 单工具调用流程", test.test_single_tool_call),
        ("Test 3: 多轮工具调用流程", test.test_multi_round_tool_calls),
        ("Test 4: 工具失败流程", test.test_tool_failure),
        ("Test 5: MAX_ROUNDS 限制", test.test_max_rounds_limit),
        ("Test 6: 无工具可用", test.test_no_tools_available),
        ("Test 7: memory_text 仅首轮注入", test.test_memory_text_first_round_only),
    ]

    passed = 0
    failed = 0
    errors = []

    for name, test_fn in tests:
        try:
            await test_fn()
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append((name, str(e)))
            print(f"  [FAIL] {name}: {e}")
        except Exception as e:
            failed += 1
            errors.append((name, f"异常: {e}"))
            print(f"  [ERROR] {name}: {e}")

    print(f"\n{'='*50}")
    print(f"测试结果: {passed} 通过 / {failed} 失败 / 共 {len(tests)} 项")
    if errors:
        print(f"\n失败详情:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    print(f"{'='*50}")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)