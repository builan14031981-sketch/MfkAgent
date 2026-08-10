"""permission_mode（auto_approve / ask_always）专项测试。

覆盖：
- permission_mode → auto_approve 映射逻辑（auto_approve / ask_always / None 回退 / 优先级）
- auto_approve=True 时绕过 REQUIRE_APPROVAL 审批，直接执行
- auto_approve=False 时 REQUIRE_APPROVAL 命令进入审批流程
- HIGH_RISK 命令即使 auto_approve=True 仍强制审批
- 沙箱校验在 auto_approve 模式下仍然生效（底线防线）
"""

import sys
import os
import asyncio
import unittest
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.tool_runtime.executor import execute_tool
from app.core.sandbox import SandboxViolation, resolve_sandbox_path


def _map_permission_mode(auto_approve: bool, permission_mode: str | None) -> bool:
    """复现 chat.py 中的 permission_mode → auto_approve 映射逻辑。"""
    if permission_mode == "auto_approve":
        return True
    elif permission_mode == "ask_always":
        return False
    return auto_approve


class TestPermissionModeMapping(unittest.TestCase):
    """permission_mode → auto_approve 映射逻辑。"""

    def test_auto_approve_mode(self):
        """permission_mode='auto_approve' → True。"""
        self.assertTrue(_map_permission_mode(False, "auto_approve"))
        self.assertTrue(_map_permission_mode(True, "auto_approve"))

    def test_ask_always_mode(self):
        """permission_mode='ask_always' → False。"""
        self.assertFalse(_map_permission_mode(True, "ask_always"))
        self.assertFalse(_map_permission_mode(False, "ask_always"))

    def test_none_falls_back(self):
        """permission_mode=None → 回退到 auto_approve 字段。"""
        self.assertTrue(_map_permission_mode(True, None))
        self.assertFalse(_map_permission_mode(False, None))

    def test_priority_over_auto_approve(self):
        """permission_mode 优先级高于 auto_approve 字段。"""
        # auto_approve=True 但 permission_mode='ask_always' → False
        self.assertFalse(_map_permission_mode(True, "ask_always"))
        # auto_approve=False 但 permission_mode='auto_approve' → True
        self.assertTrue(_map_permission_mode(False, "auto_approve"))


class TestAutoApproveBypassApproval(unittest.TestCase):
    """auto_approve=True 时绕过 REQUIRE_APPROVAL 审批，直接执行。"""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_auto_approve_bypasses_require_approval(self):
        """auto_approve=True → REQUIRE_APPROVAL 级命令直接执行，不等待审批。"""
        tool_call = {
            "id": "tc_bypass",
            "function": {
                "name": "run_command",
                "arguments": '{"command": "git add ."}',
            },
        }

        executed = []

        async def _mock_run(func_name, func_args, project_path, ctx):
            executed.append(func_name)
            return "执行成功"

        with patch("app.core.tool_runtime.executor._run_tool", new=_mock_run):
            result = self._run(execute_tool(
                tool_call=tool_call,
                project_path="/tmp/test",
                read_only=False,
                auto_approve=True,
            ))

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(executed), 1, "工具应被直接执行")

    def test_ask_always_requires_approval(self):
        """auto_approve=False → REQUIRE_APPROVAL 级命令进入审批流程。"""
        tool_call = {
            "id": "tc_pending",
            "function": {
                "name": "run_command",
                "arguments": '{"command": "git add ."}',
            },
        }

        result = self._run(execute_tool(
            tool_call=tool_call,
            project_path="/tmp/test",
            read_only=False,
            auto_approve=False,
        ))

        self.assertEqual(result["status"], "awaiting_approval")
        self.assertIn("approval_id", result)


class TestHighRiskStillBlocked(unittest.TestCase):
    """HIGH_RISK 命令即使 auto_approve=True 仍强制审批。"""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_high_risk_forces_approval_with_auto_approve(self):
        """git push --force（HIGH_RISK）→ auto_approve=True 仍挂起。"""
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
            auto_approve=True,
        ))

        self.assertEqual(result["status"], "awaiting_approval")
        self.assertIn("approval_id", result)

    def test_destructive_command_forces_approval(self):
        """rm -rf（destructive）→ auto_approve=True 仍挂起。"""
        tool_call = {
            "id": "tc_rmrf",
            "function": {
                "name": "run_command",
                "arguments": '{"command": "rm -rf /tmp/test"}',
            },
        }

        result = self._run(execute_tool(
            tool_call=tool_call,
            project_path="/tmp/test",
            read_only=False,
            auto_approve=True,
        ))

        self.assertEqual(result["status"], "awaiting_approval")


class TestSandboxStillEnforced(unittest.TestCase):
    """auto_approve 模式下沙箱校验仍然硬性生效（底线防线）。"""

    def test_sandbox_rejects_path_traversal(self):
        """路径穿越 → SandboxViolation（与 auto_approve 无关）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises((SandboxViolation, PermissionError)):
                resolve_sandbox_path("../../etc/passwd", tmpdir)

    def test_sandbox_rejects_absolute_path(self):
        """绝对路径 → SandboxViolation。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises((SandboxViolation, PermissionError, ValueError)):
                resolve_sandbox_path("/etc/passwd", tmpdir)

    def test_sandbox_allows_within_project(self):
        """项目内路径 → 正常解析。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = resolve_sandbox_path("src/main.py", tmpdir)
            self.assertTrue(str(result).startswith(tmpdir))

    def test_file_tool_uses_sandbox_regardless_of_auto_approve(self):
        """write_file 始终经过沙箱校验 + sanitize 防护，auto_approve 不影响。

        sanitize 层将 `..` 中和为安全文件名（防御纵深），sandbox 层拦截剩余穿越。
        两者独立于 auto_approve，始终生效。
        """
        from app.core.tools import write_file

        with tempfile.TemporaryDirectory() as tmpdir:
            # 正常写入 — 项目内路径
            result = write_file(tmpdir, "test.txt", "hello")
            self.assertIn("已写入", result)

            # 路径穿越 — sanitize 层将 `..` 中和为安全文件名，
            # 文件被安全写入项目内子目录，不会越权到项目外
            write_file(tmpdir, "../../escape.txt", "content")
            # 项目上级目录不应存在 escape.txt（穿越被阻止）
            parent = os.path.dirname(tmpdir)
            self.assertFalse(os.path.exists(os.path.join(parent, "escape.txt")))
            self.assertFalse(os.path.exists(os.path.join(parent, "..", "escape.txt")))

    def test_read_file_sandbox_enforced(self):
        """read_file 始终经过沙箱校验。"""
        from app.core.tools import read_file, ToolExecutionError

        with tempfile.TemporaryDirectory() as tmpdir:
            # 项目内文件 — 正常读取
            write_path = os.path.join(tmpdir, "data.txt")
            with open(write_path, "w") as f:
                f.write("test data")
            result = read_file(tmpdir, "data.txt")
            self.assertEqual(result, "test data")

            # 路径穿越 — 被拦截
            with self.assertRaises((SandboxViolation, PermissionError, ToolExecutionError, ValueError)):
                read_file(tmpdir, "../../../etc/hostname")


class TestAllowToolWithAutoApprove(unittest.TestCase):
    """ALLOW 级工具在 auto_approve 下行为不变（直接执行）。"""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_allow_tool_executes_directly(self):
        """git status（ALLOW）→ 无论 auto_approve 与否都直接执行。"""
        tool_call = {
            "id": "tc_allow",
            "function": {
                "name": "run_command",
                "arguments": '{"command": "git status"}',
            },
        }

        executed = []

        async def _mock_run(func_name, func_args, project_path, ctx):
            executed.append(func_name)
            return "On branch main"

        with patch("app.core.tool_runtime.executor._run_tool", new=_mock_run):
            result = self._run(execute_tool(
                tool_call=tool_call,
                project_path="/tmp/test",
                read_only=False,
                auto_approve=False,
            ))

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(executed), 1)

    def test_read_only_tool_in_plan_mode(self):
        """Plan 模式下只读工具（read_file）正常执行。"""
        tool_call = {
            "id": "tc_read",
            "function": {
                "name": "read_file",
                "arguments": '{"relative_path": "test.txt"}',
            },
        }

        executed = []

        async def _mock_run(func_name, func_args, project_path, ctx):
            executed.append(func_name)
            return "file content"

        with patch("app.core.tool_runtime.executor._run_tool", new=_mock_run):
            result = self._run(execute_tool(
                tool_call=tool_call,
                project_path="/tmp/test",
                read_only=True,
                auto_approve=True,
            ))

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(executed), 1)


class TestPermissionModeIntegration(unittest.TestCase):
    """permission_mode 全链路集成测试。"""

    def _run(self, coro):
        return asyncio.run(coro)

    def test_auto_approve_full_flow_no_blocking(self):
        """验收标准：auto_approve 模式下发起 Tool Call，无需等待确认即可完成全流程。"""
        tool_call = {
            "id": "tc_full_flow",
            "function": {
                "name": "run_command",
                "arguments": '{"command": "git commit -m test"}',
            },
        }

        executed_commands = []

        async def _mock_run(func_name, func_args, project_path, ctx):
            executed_commands.append(func_args.get("command", ""))
            return "[main abc123] test"

        with patch("app.core.tool_runtime.executor._run_tool", new=_mock_run):
            result = self._run(execute_tool(
                tool_call=tool_call,
                project_path="/tmp/test",
                read_only=False,
                auto_approve=True,
            ))

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(executed_commands), 1)
        self.assertIn("git commit", executed_commands[0])

    def test_ask_always_blocks_at_approval(self):
        """ask_always 模式下，REQUIRE_APPROVAL 命令被拦截等待审批。"""
        tool_call = {
            "id": "tc_blocked",
            "function": {
                "name": "run_command",
                "arguments": '{"command": "git commit -m test"}',
            },
        }

        executed_commands = []

        async def _mock_run(func_name, func_args, project_path, ctx):
            executed_commands.append(func_args.get("command", ""))
            return "should not reach"

        with patch("app.core.tool_runtime.executor._run_tool", new=_mock_run):
            result = self._run(execute_tool(
                tool_call=tool_call,
                project_path="/tmp/test",
                read_only=False,
                auto_approve=False,
            ))

        self.assertEqual(result["status"], "awaiting_approval")
        self.assertEqual(len(executed_commands), 0, "ask_always 模式下不应执行")


if __name__ == "__main__":
    unittest.main()
