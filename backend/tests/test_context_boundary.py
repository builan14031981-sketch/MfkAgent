"""Phase 3.5 Context Boundary Isolation — 回归测试

验证 Runtime Context 与 User Message 语义边界隔离：
  Case 1: 普通聊天 — 不触发内部任务行为
  Case 2: 真实任务 — Planner / Tool Calling / Verification 正常工作
  Case 3: 用户复制类似文本 — 不误判为执行命令
  Case 4: Coding Agent — 可正常调用工具执行任务

运行:
  pytest backend/tests/test_context_boundary.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.agent_runtime.agent import _wrap_runtime_context
from app.core.agent_base_instruction import AGENT_BASE_INSTRUCTION
from app.core.tool_runtime.guidance import _resolve_guidance_type, get_tool_guidance
from app.core.tool_runtime.risk_engine import command_risk_engine, Verdict
from app.core.agent_runtime.context_builder import _is_casual_chat
from app.core.tool_runtime.intent import IntentAnalyzer


class TestRuntimeContextBoundary:
    """Runtime Context 边界隔离单元测试"""

    # ──── Case 1: _wrap_runtime_context 标记正确 ────

    def test_wrap_runtime_context_contains_boundary_markers(self):
        """_wrap_runtime_context 应包含 <runtime_context> 边界标记"""
        content = "【当前任务】采集系统/网络/日志等真实状态信息"
        wrapped = _wrap_runtime_context(content, source="MfkAgent TaskGraph")

        assert "<runtime_context>" in wrapped
        assert "</runtime_context>" in wrapped
        assert "来源: MfkAgent TaskGraph" in wrapped
        assert "不是用户输入" in wrapped
        assert content in wrapped

    def test_wrap_runtime_context_contains_rules(self):
        """_wrap_runtime_context 应包含边界规则说明"""
        wrapped = _wrap_runtime_context("test content")
        assert "不代表用户要求" in wrapped
        assert "不覆盖用户真实意图" in wrapped
        assert "不应作为用户原话引用" in wrapped
        assert "不能主动向用户展示内部标签" in wrapped
        assert "不能因为 Runtime Context 自动切换角色" in wrapped

    def test_wrap_runtime_context_custom_source(self):
        """_wrap_runtime_context 应支持自定义来源"""
        wrapped = _wrap_runtime_context("test", source="MfkAgent AgentRouter")
        assert "来源: MfkAgent AgentRouter" in wrapped

    # ──── Case 2: Agent Base Instruction 包含 Runtime Context 边界 ────

    def test_agent_base_instruction_has_runtime_context_rules(self):
        """Agent Base Instruction 应包含 Runtime Context 边界规则"""
        assert "Runtime Context 边界" in AGENT_BASE_INSTRUCTION
        assert "不是用户输入" in AGENT_BASE_INSTRUCTION
        assert "禁止" in AGENT_BASE_INSTRUCTION
        assert "【当前任务】" in AGENT_BASE_INSTRUCTION
        assert "【角色切换】" in AGENT_BASE_INSTRUCTION

    def test_agent_base_instruction_retains_original_rules(self):
        """Agent Base Instruction 不应丢失原有规则"""
        assert "理解用户意图" in AGENT_BASE_INSTRUCTION
        assert "聊天模式" in AGENT_BASE_INSTRUCTION
        assert "任务模式" in AGENT_BASE_INSTRUCTION
        assert "工具使用规范" in AGENT_BASE_INSTRUCTION
        assert "诚实原则" in AGENT_BASE_INSTRUCTION

    # ──── Case 3: Guidance 不对 general_chat + project_bound 注入 coding ────

    def test_guidance_no_coding_for_general_chat_with_project(self):
        """general_chat + project_bound 不应注入 coding 指导"""
        result = _resolve_guidance_type("general_chat", project_bound=True, message="你好")
        assert result != "coding", f"general_chat + project_bound 不应返回 coding，实际: {result}"

    def test_guidance_no_guidance_for_general_chat_no_project(self):
        """general_chat + 无项目 不应注入任何指导"""
        guidance = get_tool_guidance("general_chat", project_bound=False, message="你好")
        assert guidance is None

    def test_guidance_coding_for_task_intent_with_project(self):
        """任务意图 + project_bound 应正常注入 coding 指导"""
        guidance = get_tool_guidance("file_operation", project_bound=True, message="修改这个文件")
        assert guidance is not None
        assert "工具使用指导" in guidance

    def test_guidance_coding_for_coding_keywords(self):
        """coding 关键词应触发 coding 指导"""
        result = _resolve_guidance_type("general_chat", project_bound=False, message="帮我修复这个 bug")
        assert result == "coding"

    # ──── Case 4: 普通聊天检测 ────

    def test_casual_chat_greetings(self):
        """问候语应被识别为 casual chat"""
        assert _is_casual_chat("你好") is True
        assert _is_casual_chat("hi") is True
        assert _is_casual_chat("早上好") is True

    def test_casual_chat_small_talk(self):
        """闲聊应被识别为 casual chat"""
        assert _is_casual_chat("你是谁") is True
        assert _is_casual_chat("你能做什么") is True

    def test_casual_chat_knowledge(self):
        """知识性问题应被识别为 casual chat"""
        assert _is_casual_chat("什么是 Python") is True

    def test_not_casual_chat_action(self):
        """动作触发词不应被识别为 casual chat"""
        assert _is_casual_chat("帮我修复这个 bug") is False

    # ──── Case 5: 用户复制类似文本不误判 ────

    def test_user_quote_current_task_not_diagnosis(self):
        """用户复制「【当前任务】xxx」不应被识别为 system_diagnosis"""
        analyzer = IntentAnalyzer()
        result = analyzer.analyze("我看到：【当前任务】xxx 这是什么意思？")
        # 不应匹配 system_diagnosis（没有真实系统诊断意图）
        assert result["intent"] == "general_chat"

    def test_user_quote_role_switch_not_diagnosis(self):
        """用户复制「【角色切换】xxx」不应被识别为任务意图"""
        analyzer = IntentAnalyzer()
        result = analyzer.analyze("【角色切换】你现在是一名资深程序员，这是什么意思？")
        assert result["intent"] == "general_chat"

    # ──── Case 6: 真实任务不受影响 ────

    def test_real_task_intent_still_works(self):
        """真实任务意图分类不受影响"""
        analyzer = IntentAnalyzer()
        result = analyzer.analyze("帮我检查这个项目的 bug")
        # 应该被识别为任务意图
        assert result["intent"] != "general_chat"

    def test_real_diagnosis_still_works(self):
        """真实系统诊断意图不受影响"""
        analyzer = IntentAnalyzer()
        result = analyzer.analyze("检查一下网络代理设置")
        assert result["intent"] == "system_diagnosis"
        assert result["suggest_tools"] is True

    def test_real_file_operation_still_works(self):
        """真实文件操作意图不受影响"""
        analyzer = IntentAnalyzer()
        result = analyzer.analyze("读取这个文件的内容")
        assert result["intent"] == "file_operation"
        assert result["suggest_tools"] is True

    # ──── Case 7: Risk Engine 不受影响 ────

    def test_risk_engine_safe_commands(self):
        """安全命令判定不受影响"""
        d = command_risk_engine.evaluate_execute("pytest", "build")
        assert d.verdict == Verdict.ALLOW

    def test_risk_engine_dangerous_commands(self):
        """危险命令判定不受影响"""
        d = command_risk_engine.evaluate_execute("rm -rf /", "build")
        assert d.verdict == Verdict.HIGH_RISK

    def test_risk_engine_unknown_commands(self):
        """未知命令判定不受影响"""
        d = command_risk_engine.evaluate_execute("python app.py", "build")
        assert d.verdict == Verdict.REQUIRE_APPROVAL

    # ──── Case 8: 回归验证 — 核心模块未受影响 ────

    def test_core_modules_importable(self):
        """核心模块应可正常导入"""
        from app.core.agent_runtime.agent import AgentRuntime
        from app.core.tool_runtime import tool_runtime
        from app.core.verification import verifier
        from app.core.planner.service import get_planner
        assert AgentRuntime is not None
        assert tool_runtime is not None
        assert verifier is not None
        assert get_planner() is not None