# -*- coding: utf-8 -*-
"""任务验证误判修复专项测试（run 844 实证回归）。

覆盖修复点：
  P0-1: memory_operation 任务图降为单步（步骤名不含“写入”）
  P0-2: 验证反馈带「系统验证反馈·非用户发言」标记
  P1-1: _extract_task_goal 取最后一条真实 user 消息并跳过系统反馈
  P1-2: rule_write_detected 记忆类目标豁免 + add_memory/manage_todos 计入写动作
  P1-3: add_memory 工具描述含 scope 默认倾向（agent 优先）
"""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.agent_runtime.agent import (  # noqa: E402
    AgentRuntime,
)
from app.core.agent_runtime.completion.models import CompletionContext  # noqa: E402
from app.core.agent_runtime.completion.rules import rule_write_detected  # noqa: E402
from app.core.planner.service import _STEP_TEMPLATES  # noqa: E402
from app.services.tools import AddMemoryTool  # noqa: E402

VERIFICATION_FEEDBACK_PREFIX = "【验证反馈】"


def _ctx(goal: str, tools=None) -> CompletionContext:
    return CompletionContext(
        task_goal=goal,
        tool_records=[{"tool": t} for t in (tools or [])],
    )


# ──── P1-2: rule_write_detected ────


class TestRuleWriteDetected:
    def test_memory_goal_exempt_without_any_tool(self):
        """run 844 根因场景：目标是“写入记忆”但无任何文件写工具 → 不再误判。"""
        assert rule_write_detected(_ctx("写入记忆")) is None
        assert rule_write_detected(_ctx("请把用户的重要信息添加记忆")) is None

    def test_memory_goal_with_file_keyword_still_checked(self):
        """目标同时明确提到“文件” → 记忆豁免不生效，仍要求写动作。"""
        missing = rule_write_detected(_ctx("把记忆写入 notes.txt 文件"))
        assert missing == ["任务要求写入文件，但未执行任何写操作"]

    def test_add_memory_counts_as_write_action(self):
        """add_memory/manage_todos 属于写动作白名单。"""
        assert rule_write_detected(_ctx("写入用户信息", tools=["add_memory"])) is None
        assert rule_write_detected(_ctx("创建待办清单", tools=["manage_todos"])) is None

    def test_real_file_task_still_fails_without_write(self):
        """真实文件写任务无写工具 → 仍然拦截（防漏判）。"""
        missing = rule_write_detected(_ctx("创建一个 test.py 文件"))
        assert missing == ["任务要求写入文件，但未执行任何写操作"]
        assert rule_write_detected(_ctx("创建 test.py", tools=["write_file"])) is None


# ──── P0-2 / P1-1: 反馈标记与目标提取 ────


class TestFeedbackMarkerAndGoalExtraction:
    def test_completion_feedback_has_marker(self):
        result = SimpleNamespace(
            reason="规则层判定任务尚未完成",
            missing_items=["任务要求写入文件，但未执行任何写操作"],
            next_action="continue_execution",
        )
        text = AgentRuntime._build_completion_feedback(result)
        assert text.startswith("任务尚未完成。")

    def test_verification_feedback_has_marker(self):
        failed = [SimpleNamespace(tool="write_file", tool_call_id="t1", message="文件不存在")]
        text = AgentRuntime._build_verification_feedback(failed)
        assert text.startswith(VERIFICATION_FEEDBACK_PREFIX)

    def test_goal_extraction_skips_feedback_messages(self):
        """run 844 场景：验证反馈以 user 角色追加后，目标仍是用户真实发言。"""
        messages = [
            {"role": "system", "content": "人设"},
            {"role": "user", "content": "你可以和添加记忆吗 我爱你 我叫安欣"},
            {"role": "assistant", "content": "好，我记住了。"},
            {"role": "user", "content": VERIFICATION_FEEDBACK_PREFIX + "\n任务尚未完成。"},
        ]
        assert AgentRuntime._extract_task_goal(messages) == "你可以和添加记忆吗 我爱你 我叫安欣"

    def test_goal_extraction_takes_last_real_user_message(self):
        messages = [
            {"role": "user", "content": "上一轮的旧请求"},
            {"role": "assistant", "content": "旧回复"},
            {"role": "user", "content": "本轮新请求：记住我叫安欣"},
        ]
        assert AgentRuntime._extract_task_goal(messages) == "本轮新请求：记住我叫安欣"

    def test_goal_extraction_all_feedback_returns_empty(self):
        messages = [{"role": "user", "content": VERIFICATION_FEEDBACK_PREFIX + "任务尚未完成。"}]
        assert AgentRuntime._extract_task_goal(messages) == ""


# ──── P0-1: memory_operation 任务图降为单步 ────


class TestMemoryOperationPlan:
    def test_single_step_template(self):
        steps = _STEP_TEMPLATES["memory_operation"]
        assert len(steps) == 1
        assert "add_memory" in steps[0].suggested_tools

    def test_step_name_has_no_write_keyword(self):
        """步骤名不得含文件写关键词，避免 rule_write_detected 再次自触发。"""
        steps = _STEP_TEMPLATES["memory_operation"]
        for s in steps:
            assert not any(k in s.action for k in ("写入", "创建", "修改", "生成"))


# ──── P1-3: add_memory scope 指引 ────


class TestAddMemoryScopeGuidance:
    def test_description_prefers_agent_scope(self):
        tool = AddMemoryTool()
        assert "默认使用 agent" in tool.description
        scope_desc = tool.parameters["properties"]["scope"]["description"]
        assert "默认首选" in scope_desc and "仅用户明确要求" in scope_desc
