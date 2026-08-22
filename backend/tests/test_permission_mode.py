"""Phase 3 T3/T8: 权限模式 + ApprovalPolicy + Notification 专项测试。

覆盖：
- ApprovalPolicy 三种模式（Safe / Standard / Autonomous）决策正确性
- 决策链：RiskEngine → ApprovalPolicy → ExecutionDecision
- RuntimeEventBus 通知事件（task_completed / approval_required / error）
- 高危操作在所有模式下强制审批
- 沙箱校验始终生效（与权限模式无关）
"""

import sys
import os
import asyncio
import unittest
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.tool_runtime.risk_engine import (
    RiskDecision, Verdict, RiskLevel,
    ExecutionDecision, ExecutionAction, command_risk_engine,
)
from app.core.tool_runtime.approval_policy import (
    ApprovalPolicy, ApprovalMode, get_approval_policy, set_approval_mode,
)
from app.core.tool_runtime.notification import (
    RuntimeEventBus, RuntimeNotification, NotificationType, event_bus,
)


# ═══════════════════════════════════════════════════════════════════
# 1. ApprovalPolicy 三种模式决策正确性
# ═══════════════════════════════════════════════════════════════════

class TestApprovalPolicySafeMode(unittest.TestCase):
    """Safe 模式：所有 REQUIRE_APPROVAL → 必须审批。"""

    def setUp(self):
        self.policy = ApprovalPolicy(ApprovalMode.SAFE)

    def test_allow_passes(self):
        """ALLOW 判定 → 直接执行。"""
        rd = RiskDecision(Verdict.ALLOW, RiskLevel.READ_ONLY, "git status", "git status")
        ed = self.policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.EXECUTE)

    def test_deny_blocks(self):
        """DENY 判定 → 阻断。"""
        rd = RiskDecision(Verdict.DENY, RiskLevel.DESTRUCTIVE, "rm -rf", "rm -rf /")
        ed = self.policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.BLOCK)

    def test_require_approval_in_safe(self):
        """Safe 模式下 REQUIRE_APPROVAL → 必须审批（不自动放行）。"""
        rd = RiskDecision(Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "git commit", "git commit -m test")
        ed = self.policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.REQUIRE_APPROVAL)

    def test_high_risk_in_safe(self):
        """Safe 模式下 HIGH_RISK → 强制审批。"""
        rd = RiskDecision(Verdict.HIGH_RISK, RiskLevel.DESTRUCTIVE, "git push --force", "git push --force")
        ed = self.policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.REQUIRE_APPROVAL)


class TestApprovalPolicyStandardMode(unittest.TestCase):
    """Standard 模式：普通写入自动，危险操作审批。"""

    def setUp(self):
        self.policy = ApprovalPolicy(ApprovalMode.STANDARD)

    def test_allow_passes(self):
        """ALLOW → 直接执行。"""
        rd = RiskDecision(Verdict.ALLOW, RiskLevel.READ_ONLY, "git status", "git status")
        ed = self.policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.EXECUTE)

    def test_require_approval_write_auto(self):
        """Standard 下 WRITE 级 REQUIRE_APPROVAL → 自动批准。"""
        rd = RiskDecision(Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "git commit", "git commit -m test")
        ed = self.policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.EXECUTE)
        self.assertIn("[STANDARD]", ed.reason)

    def test_require_approval_destructive_needs_approval(self):
        """Standard 下 DESTRUCTIVE 级 REQUIRE_APPROVAL → 仍需审批。"""
        rd = RiskDecision(Verdict.REQUIRE_APPROVAL, RiskLevel.DESTRUCTIVE, "npm install", "npm install")
        ed = self.policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.REQUIRE_APPROVAL)

    def test_high_risk_always_approval(self):
        """Standard 下 HIGH_RISK → 强制审批。"""
        rd = RiskDecision(Verdict.HIGH_RISK, RiskLevel.DESTRUCTIVE, "git push --force", "git push --force")
        ed = self.policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.REQUIRE_APPROVAL)


class TestApprovalPolicyAutonomousMode(unittest.TestCase):
    """Autonomous 模式：REQUIRE_APPROVAL 全部自动，HIGH_RISK 仍需审批。"""

    def setUp(self):
        self.policy = ApprovalPolicy(ApprovalMode.AUTONOMOUS)

    def test_allow_passes(self):
        """ALLOW → 直接执行。"""
        rd = RiskDecision(Verdict.ALLOW, RiskLevel.READ_ONLY, "git status", "git status")
        ed = self.policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.EXECUTE)

    def test_require_approval_all_auto(self):
        """Autonomous 下所有 REQUIRE_APPROVAL → 自动执行。"""
        rd = RiskDecision(Verdict.REQUIRE_APPROVAL, RiskLevel.DESTRUCTIVE, "npm install", "npm install")
        ed = self.policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.EXECUTE)
        self.assertIn("[AUTONOMOUS]", ed.reason)

    def test_high_risk_still_needs_approval(self):
        """Autonomous 下 HIGH_RISK → 仍需审批。"""
        rd = RiskDecision(Verdict.HIGH_RISK, RiskLevel.DESTRUCTIVE, "git push --force", "git push --force")
        ed = self.policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.REQUIRE_APPROVAL)

    def test_deny_blocks(self):
        """DENY → 始终阻断（shell 元字符等）。"""
        rd = RiskDecision(Verdict.DENY, RiskLevel.DESTRUCTIVE, "shell injection", "cmd; rm -rf /")
        ed = self.policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.BLOCK)


# ═══════════════════════════════════════════════════════════════════
# 2. 决策链全链路测试：RiskEngine → ApprovalPolicy → ExecutionDecision
# ═══════════════════════════════════════════════════════════════════

class TestDecisionChain(unittest.TestCase):
    """验证 RiskEngine → ApprovalPolicy → ExecutionDecision 完整链路。"""

    def test_git_status_chain(self):
        """git status → RiskEngine(ALLOW) → ApprovalPolicy → EXECUTE。"""
        rd = command_risk_engine.evaluate("git status", "build")
        self.assertEqual(rd.verdict, Verdict.ALLOW)

        policy = ApprovalPolicy(ApprovalMode.SAFE)
        ed = policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.EXECUTE)

    def test_git_commit_chain_safe(self):
        """git commit → RiskEngine(REQUIRE_APPROVAL) → Safe → REQUIRE_APPROVAL。"""
        rd = command_risk_engine.evaluate("git commit -m test", "build")
        self.assertEqual(rd.verdict, Verdict.REQUIRE_APPROVAL)

        policy = ApprovalPolicy(ApprovalMode.SAFE)
        ed = policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.REQUIRE_APPROVAL)

    def test_git_commit_chain_standard(self):
        """git commit → RiskEngine(REQUIRE_APPROVAL) → Standard → EXECUTE。"""
        rd = command_risk_engine.evaluate("git commit -m test", "build")
        self.assertEqual(rd.verdict, Verdict.REQUIRE_APPROVAL)

        policy = ApprovalPolicy(ApprovalMode.STANDARD)
        ed = policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.EXECUTE)

    def test_git_push_force_chain(self):
        """git push --force → RiskEngine(HIGH_RISK) → 任何模式 → REQUIRE_APPROVAL。"""
        rd = command_risk_engine.evaluate("git push --force origin main", "build")
        self.assertEqual(rd.verdict, Verdict.HIGH_RISK)

        for mode in [ApprovalMode.SAFE, ApprovalMode.STANDARD, ApprovalMode.AUTONOMOUS]:
            policy = ApprovalPolicy(mode)
            ed = policy.decide(rd)
            self.assertEqual(ed.action, ExecutionAction.REQUIRE_APPROVAL,
                             f"Mode {mode.value} should require approval for HIGH_RISK")

    def test_rm_rf_chain(self):
        """rm -rf → RiskEngine(HIGH_RISK) → 任何模式 → REQUIRE_APPROVAL。"""
        rd = command_risk_engine.evaluate("rm -rf /tmp/test", "build")
        self.assertEqual(rd.verdict, Verdict.HIGH_RISK)

        for mode in [ApprovalMode.SAFE, ApprovalMode.STANDARD, ApprovalMode.AUTONOMOUS]:
            policy = ApprovalPolicy(mode)
            ed = policy.decide(rd)
            self.assertEqual(ed.action, ExecutionAction.REQUIRE_APPROVAL,
                             f"Mode {mode.value} should require approval for rm -rf")

    def test_npm_install_chain_autonomous(self):
        """npm install → RiskEngine(REQUIRE_APPROVAL) → Autonomous → EXECUTE。"""
        rd = command_risk_engine.evaluate("npm install", "build")
        self.assertEqual(rd.verdict, Verdict.REQUIRE_APPROVAL)

        policy = ApprovalPolicy(ApprovalMode.AUTONOMOUS)
        ed = policy.decide(rd)
        self.assertEqual(ed.action, ExecutionAction.EXECUTE)


# ═══════════════════════════════════════════════════════════════════
# 3. RuntimeEventBus 通知事件测试
# ═══════════════════════════════════════════════════════════════════

class TestRuntimeEventBus(unittest.TestCase):
    """验证 RuntimeEventBus 通知事件发布与订阅。"""

    def setUp(self):
        self.bus = RuntimeEventBus()
        self.received: list[RuntimeNotification] = []

    def _collector(self, notification: RuntimeNotification):
        self.received.append(notification)

    def test_task_completed_event(self):
        """task_completed 事件发布 → 订阅者收到。"""
        self.bus.subscribe(chat_id=1, callback=self._collector)
        self.bus.task_completed(chat_id=1, task_description="Agent 任务完成", success=True, result_summary="测试通过")
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0].type, NotificationType.TASK_COMPLETED)
        self.assertEqual(self.received[0].data["success"], True)
        self.assertEqual(self.received[0].data["task_description"], "Agent 任务完成")

    def test_approval_required_event(self):
        """approval_required 事件发布 → 订阅者收到。"""
        self.bus.subscribe(chat_id=1, callback=self._collector)
        self.bus.approval_required(
            chat_id=1, approval_id="apr-001", tool_call_id="tc-001",
            tool="git_push", command="git push", risk_level="destructive",
            risk_reason="强制推送是高危操作",
        )
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0].type, NotificationType.APPROVAL_REQUIRED)
        self.assertEqual(self.received[0].data["tool"], "git_push")
        self.assertEqual(self.received[0].data["approval_id"], "apr-001")

    def test_error_event(self):
        """error 事件发布 → 订阅者收到。"""
        self.bus.subscribe(chat_id=1, callback=self._collector)
        self.bus.error(chat_id=1, error_type="agent_error", error_message="Something went wrong", recoverable=False)
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0].type, NotificationType.ERROR)
        self.assertEqual(self.received[0].data["error_type"], "agent_error")
        self.assertEqual(self.received[0].data["recoverable"], False)

    def test_task_started_event(self):
        """task_started 事件发布 → 订阅者收到。"""
        self.bus.subscribe(chat_id=1, callback=self._collector)
        self.bus.task_started(chat_id=1, task_description="开始执行任务")
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0].type, NotificationType.TASK_STARTED)

    def test_approval_completed_event(self):
        """approval_completed 事件发布 → 订阅者收到。"""
        self.bus.subscribe(chat_id=1, callback=self._collector)
        self.bus.approval_completed(
            chat_id=1, approval_id="apr-001", tool_call_id="tc-001",
            tool="git_push", action="approve",
        )
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0].type, NotificationType.APPROVAL_COMPLETED)
        self.assertEqual(self.received[0].data["action"], "approve")

    def test_subscribe_scoped_by_chat_id(self):
        """订阅者按 chat_id 隔离，不会收到其他 chat 的事件。"""
        self.bus.subscribe(chat_id=1, callback=self._collector)
        self.bus.task_completed(chat_id=2, task_description="其他 chat 的任务")
        self.assertEqual(len(self.received), 0)

    def test_global_subscriber_receives_all(self):
        """全局订阅者收到所有 chat 的事件。"""
        self.bus.subscribe_global(callback=self._collector)
        self.bus.task_completed(chat_id=1, task_description="任务 1")
        self.bus.task_completed(chat_id=2, task_description="任务 2")
        self.assertEqual(len(self.received), 2)

    def test_to_sse_format(self):
        """RuntimeNotification.to_sse() 输出 SSE 兼容格式。"""
        notif = self.bus.approval_required(
            chat_id=1, approval_id="apr-001", tool_call_id="tc-001",
            tool="git_push", command="git push", risk_level="destructive",
            risk_reason="高危",
        )
        sse = notif.to_sse()
        self.assertEqual(sse["type"], "approval_required")
        self.assertEqual(sse["approval_id"], "apr-001")
        self.assertEqual(sse["tool"], "git_push")
        self.assertEqual(sse["chat_id"], 1)


# ═══════════════════════════════════════════════════════════════════
# 4. 全局单例模式切换测试
# ═══════════════════════════════════════════════════════════════════

class TestApprovalPolicySingleton(unittest.TestCase):
    """验证全局 ApprovalPolicy 单例和模式切换。"""

    def test_default_mode_is_standard(self):
        """默认模式为 STANDARD。"""
        policy = ApprovalPolicy()
        self.assertEqual(policy.mode, ApprovalMode.STANDARD)

    def test_mode_switch_reflected_in_decide(self):
        """模式切换后 decide() 行为变化。"""
        rd = RiskDecision(Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "git commit", "git commit")

        # Safe 模式 → 审批
        safe = ApprovalPolicy(ApprovalMode.SAFE)
        self.assertEqual(safe.decide(rd).action, ExecutionAction.REQUIRE_APPROVAL)

        # Standard 模式 → 自动
        std = ApprovalPolicy(ApprovalMode.STANDARD)
        self.assertEqual(std.decide(rd).action, ExecutionAction.EXECUTE)

        # Autonomous 模式 → 自动
        auto = ApprovalPolicy(ApprovalMode.AUTONOMOUS)
        self.assertEqual(auto.decide(rd).action, ExecutionAction.EXECUTE)

    def test_should_auto_approve_backward_compat(self):
        """should_auto_approve() 向后兼容方法。"""
        rd = RiskDecision(Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "git commit", "git commit")

        self.assertFalse(ApprovalPolicy(ApprovalMode.SAFE).should_auto_approve(rd))
        self.assertTrue(ApprovalPolicy(ApprovalMode.STANDARD).should_auto_approve(rd))
        self.assertTrue(ApprovalPolicy(ApprovalMode.AUTONOMOUS).should_auto_approve(rd))


# ═══════════════════════════════════════════════════════════════════
# 5. 沙箱校验始终生效（与权限模式无关）
# ═══════════════════════════════════════════════════════════════════

class TestSandboxAlwaysEnforced(unittest.TestCase):
    """沙箱校验与权限模式无关，始终硬性生效。"""

    def test_sandbox_rejects_path_traversal(self):
        """路径穿越 → SandboxViolation。"""
        from app.core.sandbox import SandboxViolation, resolve_sandbox_path
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises((SandboxViolation, PermissionError)):
                resolve_sandbox_path("../../etc/passwd", tmpdir)

    def test_sandbox_allows_within_project(self):
        """项目内路径 → 正常解析。"""
        from app.core.sandbox import resolve_sandbox_path
        with tempfile.TemporaryDirectory() as tmpdir:
            result = resolve_sandbox_path("src/main.py", tmpdir)
            self.assertTrue(str(result).startswith(tmpdir))


# ═══════════════════════════════════════════════════════════════════
# 6. 执行器 integration 测试（Mock）
# ═══════════════════════════════════════════════════════════════════

class TestExecutorWithApprovalPolicy(unittest.TestCase):
    """验证 execute_tool 使用 ApprovalPolicy 决策链。"""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_allow_tool_executes_directly(self):
        """ALLOW 工具在所有模式下直接执行。"""
        from app.core.tool_runtime.executor import execute_tool

        tool_call = {
            "id": "tc_allow",
            "function": {
                "name": "run_command",
                "arguments": '{"command": "git status"}',
            },
        }

        executed = []

        async def _mock_run(func_name, func_args, project_path, ctx, emit=None):
            executed.append(func_name)
            return "On branch main"

        with patch("app.core.tool_runtime.executor._run_tool", new=_mock_run):
            result = self._run(execute_tool(
                tool_call=tool_call,
                project_path="/tmp/test",
                read_only=False,
            ))

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(executed), 1)

    def test_git_push_force_always_requires_approval(self):
        """git push --force 在所有模式下都需要审批。"""
        from app.core.tool_runtime.executor import execute_tool

        tool_call = {
            "id": "tc_highrisk",
            "function": {
                "name": "run_command",
                "arguments": '{"command": "git push --force origin main"}',
            },
        }

        result = self._run(execute_tool(
            tool_call=tool_call,
            project_path="/tmp/test",
            read_only=False,
        ))

        self.assertEqual(result["status"], "awaiting_approval")
        self.assertIn("approval_id", result)


# ═══════════════════════════════════════════════════════════════════
# 7. 三种权限模式 × 真实 Runtime 调用链测试
# ═══════════════════════════════════════════════════════════════════

class TestPermissionModeRuntimeIntegration(unittest.TestCase):
    """验证三种权限模式在真实 Runtime 调用链中的行为。

    测试矩阵：
      SAFE:       write_file → approval
      STANDARD:   git commit → execute;  git push --force → approval
      AUTONOMOUS: git commit → execute;  git push --force → approval
    """

    def _run(self, coro):
        return asyncio.run(coro)

    # ──── SAFE 模式 ────

    def test_safe_write_file_requires_approval(self):
        """SAFE: write_file → approval（所有写入需要审批）。"""
        from app.core.tool_runtime.executor import execute_tool
        from app.core.tool_runtime.approval_policy import set_approval_mode, ApprovalMode

        set_approval_mode(ApprovalMode.SAFE)

        tool_call = {
            "id": "tc_safe_write",
            "function": {
                "name": "write_file",
                "arguments": '{"relative_path": "test.txt", "content": "hello"}',
            },
        }

        result = self._run(execute_tool(
            tool_call=tool_call,
            project_path="/tmp/test",
            read_only=False,
        ))

        self.assertEqual(result["status"], "awaiting_approval",
                         "SAFE 模式下 write_file 应触发审批")

        # 恢复默认模式
        set_approval_mode(ApprovalMode.STANDARD)

    def test_safe_git_commit_requires_approval(self):
        """SAFE: git commit → approval。"""
        from app.core.tool_runtime.executor import execute_tool
        from app.core.tool_runtime.approval_policy import set_approval_mode, ApprovalMode

        set_approval_mode(ApprovalMode.SAFE)

        tool_call = {
            "id": "tc_safe_commit",
            "function": {
                "name": "run_command",
                "arguments": '{"command": "git commit -m test"}',
            },
        }

        result = self._run(execute_tool(
            tool_call=tool_call,
            project_path="/tmp/test",
            read_only=False,
        ))

        self.assertEqual(result["status"], "awaiting_approval",
                         "SAFE 模式下 git commit 应触发审批")

        set_approval_mode(ApprovalMode.STANDARD)

    # ──── STANDARD 模式 ────

    def test_standard_normal_write_executes(self):
        """STANDARD: git commit（WRITE 级）→ execute。"""
        from app.core.tool_runtime.executor import execute_tool
        from app.core.tool_runtime.approval_policy import set_approval_mode, ApprovalMode

        set_approval_mode(ApprovalMode.STANDARD)

        executed = []

        async def _mock_run(func_name, func_args, project_path, ctx, emit=None):
            executed.append(func_name)
            return "执行成功"

        tool_call = {
            "id": "tc_std_commit",
            "function": {
                "name": "run_command",
                "arguments": '{"command": "git commit -m test"}',
            },
        }

        with patch("app.core.tool_runtime.executor._run_tool", new=_mock_run):
            result = self._run(execute_tool(
                tool_call=tool_call,
                project_path="/tmp/test",
                read_only=False,
            ))

        self.assertEqual(result["status"], "success",
                         "STANDARD 模式下 git commit 应自动执行")
        self.assertEqual(len(executed), 1)

    def test_standard_dangerous_requires_approval(self):
        """STANDARD: git push --force（HIGH_RISK）→ approval。"""
        from app.core.tool_runtime.executor import execute_tool
        from app.core.tool_runtime.approval_policy import set_approval_mode, ApprovalMode

        set_approval_mode(ApprovalMode.STANDARD)

        tool_call = {
            "id": "tc_std_force",
            "function": {
                "name": "run_command",
                "arguments": '{"command": "git push --force origin main"}',
            },
        }

        result = self._run(execute_tool(
            tool_call=tool_call,
            project_path="/tmp/test",
            read_only=False,
        ))

        self.assertEqual(result["status"], "awaiting_approval",
                         "STANDARD 模式下 git push --force 应触发审批")

    # ──── AUTONOMOUS 模式 ────

    def test_autonomous_normal_write_executes(self):
        """AUTONOMOUS: git commit（REQUIRE_APPROVAL）→ execute。"""
        from app.core.tool_runtime.executor import execute_tool
        from app.core.tool_runtime.approval_policy import set_approval_mode, ApprovalMode

        set_approval_mode(ApprovalMode.AUTONOMOUS)

        executed = []

        async def _mock_run(func_name, func_args, project_path, ctx, emit=None):
            executed.append(func_name)
            return "执行成功"

        tool_call = {
            "id": "tc_auto_commit",
            "function": {
                "name": "run_command",
                "arguments": '{"command": "git commit -m test"}',
            },
        }

        with patch("app.core.tool_runtime.executor._run_tool", new=_mock_run):
            result = self._run(execute_tool(
                tool_call=tool_call,
                project_path="/tmp/test",
                read_only=False,
            ))

        self.assertEqual(result["status"], "success",
                         "AUTONOMOUS 模式下 git commit 应自动执行")
        self.assertEqual(len(executed), 1)

        set_approval_mode(ApprovalMode.STANDARD)

    def test_autonomous_dangerous_requires_approval(self):
        """AUTONOMOUS: git push --force（HIGH_RISK）→ approval。"""
        from app.core.tool_runtime.executor import execute_tool
        from app.core.tool_runtime.approval_policy import set_approval_mode, ApprovalMode

        set_approval_mode(ApprovalMode.AUTONOMOUS)

        tool_call = {
            "id": "tc_auto_force",
            "function": {
                "name": "run_command",
                "arguments": '{"command": "git push --force origin main"}',
            },
        }

        result = self._run(execute_tool(
            tool_call=tool_call,
            project_path="/tmp/test",
            read_only=False,
        ))

        self.assertEqual(result["status"], "awaiting_approval",
                         "AUTONOMOUS 模式下 git push --force 仍需审批")

        set_approval_mode(ApprovalMode.STANDARD)


if __name__ == "__main__":
    unittest.main()