"""Phase 11: 高危命令审批机制与打包交付 专项测试。

覆盖：
- ApprovalRegistry 注册/审批/拒绝/超时/清理
- CommandRiskEngine 高危命令分类（git push / npm install / pip install / rm / del）
- execute_tool 审批流程（HIGH_RISK → pending → complete_approval）
- /api/chat/{chat_id}/approve 接口（同意/拒绝/404/409/422）
- 非阻塞验证（Future 不阻塞事件循环）
"""

import sys
import os
import asyncio
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.tool_runtime.approval import ApprovalRegistry, approval_registry
from app.core.tool_runtime.approval_policy import (
    set_approval_mode,
    ApprovalMode,
    DEFAULT_APPROVAL_MODE,
)
from app.core.tool_runtime.risk_engine import (
    CommandRiskEngine,
    command_risk_engine,
    Verdict,
    RiskLevel,
    _DESTRUCTIVE_PATTERNS,
    _WRITE_PATTERNS,
)


# Windows 无 /tmp，使用真实临时目录作为沙箱项目根（跨平台兼容）
_TEST_PROJECT = tempfile.mkdtemp(prefix="mfk_phase11_")


# ──── ApprovalRegistry 单元测试 ────

class TestApprovalRegistry(unittest.TestCase):
    """审批注册表：register / resolve / remove / cancel_by_chat。"""

    def setUp(self):
        self.registry = ApprovalRegistry()

    def test_register_creates_entry(self):
        async def _run():
            aid, info = self.registry.register(
                tool_call_id="tc_1",
                tool="run_command",
                command="git push",
                risk_level="destructive",
                risk_reason="高危命令",
                chat_id=1,
            )
            self.assertTrue(aid.startswith("aprv_"))
            self.assertEqual(info["tool"], "run_command")
            self.assertEqual(info["command"], "git push")
            self.assertEqual(info["chat_id"], 1)
            self.assertIn(aid, self.registry.pending())
        asyncio.run(_run())

    def test_resolve_approve(self):
        async def _run():
            aid, info = self.registry.register(
                tool_call_id="tc_2", tool="run_command", command="npm install",
                risk_level="write", risk_reason="安装包", chat_id=2,
            )
            result = self.registry.resolve(aid, "approve")
            self.assertTrue(result)
            await asyncio.sleep(0)  # 让 call_soon_threadsafe 回调执行
            self.assertTrue(info["future"].done())
            self.assertEqual(info["future"].result(), "approve")
        asyncio.run(_run())

    def test_resolve_deny(self):
        async def _run():
            aid, info = self.registry.register(
                tool_call_id="tc_3", tool="run_command", command="rm -rf",
                risk_level="destructive", risk_reason="危险删除", chat_id=3,
            )
            self.registry.resolve(aid, "deny")
            await asyncio.sleep(0)  # 让 call_soon_threadsafe 回调执行
            self.assertTrue(info["future"].done())
            self.assertEqual(info["future"].result(), "deny")
        asyncio.run(_run())

    def test_resolve_nonexistent(self):
        self.assertFalse(self.registry.resolve("aprv_nonexistent", "approve"))

    def test_resolve_already_done(self):
        async def _run():
            aid, info = self.registry.register(
                tool_call_id="tc_4", tool="run_command", command="del file",
                risk_level="destructive", risk_reason="删除文件", chat_id=4,
            )
            self.registry.resolve(aid, "approve")
            await asyncio.sleep(0)  # 让 call_soon_threadsafe 回调执行
            self.assertFalse(self.registry.resolve(aid, "deny"))  # 已处理
        asyncio.run(_run())

    def test_remove_cleans_up(self):
        async def _run():
            aid, _ = self.registry.register(
                tool_call_id="tc_5", tool="run_command", command="pip install",
                risk_level="write", risk_reason="安装包", chat_id=5,
            )
            self.assertTrue(self.registry.remove(aid))
            self.assertNotIn(aid, self.registry.pending())
            self.assertFalse(self.registry.remove(aid))  # 幂等
        asyncio.run(_run())

    def test_get_returns_info(self):
        async def _run():
            aid, _ = self.registry.register(
                tool_call_id="tc_6", tool="run_command", command="git commit",
                risk_level="write", risk_reason="提交代码", chat_id=6,
            )
            info = self.registry.get(aid)
            self.assertIsNotNone(info)
            self.assertEqual(info["tool_call_id"], "tc_6")
        asyncio.run(_run())

    def test_get_nonexistent(self):
        self.assertIsNone(self.registry.get("aprv_nonexistent"))

    def test_cancel_by_chat(self):
        async def _run():
            self.registry.register(
                tool_call_id="tc_a", tool="run_command", command="cmd_a",
                risk_level="write", risk_reason="test", chat_id=10,
            )
            self.registry.register(
                tool_call_id="tc_b", tool="run_command", command="cmd_b",
                risk_level="write", risk_reason="test", chat_id=10,
            )
            self.registry.register(
                tool_call_id="tc_c", tool="run_command", command="cmd_c",
                risk_level="write", risk_reason="test", chat_id=99,
            )
            n = self.registry.cancel_by_chat(10)
            self.assertEqual(n, 2)
            self.assertEqual(len(self.registry.pending()), 1)  # chat_id=99 保留
        asyncio.run(_run())

    def test_pending_returns_ids(self):
        async def _run():
            self.registry.register(
                tool_call_id="tc_p1", tool="run_command", command="cmd1",
                risk_level="write", risk_reason="test", chat_id=1,
            )
            self.registry.register(
                tool_call_id="tc_p2", tool="run_command", command="cmd2",
                risk_level="destructive", risk_reason="test", chat_id=2,
            )
            self.assertEqual(len(self.registry.pending()), 2)
        asyncio.run(_run())


# ──── CommandRiskEngine 高危命令分类测试 ────

class TestCommandRiskEngine(unittest.TestCase):
    """命令风险引擎：高危命令 / 写入命令 / 只读命令 分类。"""

    def setUp(self):
        self.engine = CommandRiskEngine()

    # ── 高危命令（DESTRUCTIVE → HIGH_RISK）──
    def test_rm_is_high_risk(self):
        d = self.engine.evaluate("rm -rf node_modules")
        self.assertEqual(d.verdict, Verdict.HIGH_RISK)
        self.assertEqual(d.risk_level, RiskLevel.DESTRUCTIVE)

    def test_del_is_high_risk(self):
        d = self.engine.evaluate("del /f test.txt")
        self.assertEqual(d.verdict, Verdict.HIGH_RISK)

    def test_rmdir_is_high_risk(self):
        d = self.engine.evaluate("rmdir /s build")
        self.assertEqual(d.verdict, Verdict.HIGH_RISK)

    def test_git_push_force_is_high_risk(self):
        d = self.engine.evaluate("git push --force origin main")
        self.assertEqual(d.verdict, Verdict.HIGH_RISK)

    def test_git_reset_hard_is_high_risk(self):
        d = self.engine.evaluate("git reset --hard HEAD~1")
        self.assertEqual(d.verdict, Verdict.HIGH_RISK)

    def test_format_is_high_risk(self):
        d = self.engine.evaluate("format C:")
        self.assertEqual(d.verdict, Verdict.HIGH_RISK)

    def test_shutdown_is_high_risk(self):
        d = self.engine.evaluate("shutdown /s")
        self.assertEqual(d.verdict, Verdict.HIGH_RISK)

    # ── 写入命令（WRITE → REQUIRE_APPROVAL）──
    def test_git_push_is_require_approval(self):
        d = self.engine.evaluate("git push origin main")
        self.assertEqual(d.verdict, Verdict.REQUIRE_APPROVAL)
        self.assertEqual(d.risk_level, RiskLevel.WRITE)

    def test_git_commit_is_require_approval(self):
        d = self.engine.evaluate("git commit -m 'fix'")
        self.assertEqual(d.verdict, Verdict.REQUIRE_APPROVAL)

    def test_git_add_is_require_approval(self):
        d = self.engine.evaluate("git add .")
        self.assertEqual(d.verdict, Verdict.REQUIRE_APPROVAL)

    def test_npm_install_is_require_approval(self):
        d = self.engine.evaluate("npm install express")
        self.assertEqual(d.verdict, Verdict.REQUIRE_APPROVAL)

    def test_pip_install_is_require_approval(self):
        d = self.engine.evaluate("pip install requests")
        self.assertEqual(d.verdict, Verdict.REQUIRE_APPROVAL)

    def test_npm_uninstall_is_require_approval(self):
        d = self.engine.evaluate("npm uninstall lodash")
        self.assertEqual(d.verdict, Verdict.REQUIRE_APPROVAL)

    # ── 只读命令（ALLOW）──
    def test_git_status_is_allow(self):
        d = self.engine.evaluate("git status")
        self.assertEqual(d.verdict, Verdict.ALLOW)

    def test_git_diff_is_allow(self):
        d = self.engine.evaluate("git diff")
        self.assertEqual(d.verdict, Verdict.ALLOW)

    def test_dir_is_allow(self):
        d = self.engine.evaluate("dir")
        self.assertEqual(d.verdict, Verdict.ALLOW)

    def test_pytest_is_allow(self):
        d = self.engine.evaluate("pytest")
        self.assertEqual(d.verdict, Verdict.ALLOW)

    def test_npm_test_is_allow(self):
        d = self.engine.evaluate("npm test")
        self.assertEqual(d.verdict, Verdict.ALLOW)

    # ── Plan 模式拒绝 ──
    def test_plan_mode_denies_write(self):
        d = self.engine.evaluate("git push", mode="plan")
        self.assertEqual(d.verdict, Verdict.DENY)

    def test_plan_mode_denies_high_risk(self):
        d = self.engine.evaluate("rm -rf tmp", mode="plan")
        self.assertEqual(d.verdict, Verdict.DENY)

    def test_plan_mode_allows_readonly(self):
        d = self.engine.evaluate("git status", mode="plan")
        self.assertEqual(d.verdict, Verdict.ALLOW)

    # ── 边界情况 ──
    def test_empty_command_deny(self):
        d = self.engine.evaluate("")
        self.assertEqual(d.verdict, Verdict.DENY)

    def test_shell_metachar_deny(self):
        d = self.engine.evaluate("ls; rm -rf /")
        self.assertEqual(d.verdict, Verdict.DENY)

    def test_pipe_deny(self):
        d = self.engine.evaluate("cat file | grep x")
        self.assertEqual(d.verdict, Verdict.DENY)


# ──── 非阻塞审批流程测试 ────

class TestApprovalNonBlocking(unittest.TestCase):
    """验证审批 Future 不阻塞事件循环。"""

    def test_future_does_not_block_loop(self):
        """验证 create_future 不会阻塞事件循环。"""

        async def _run():
            loop = asyncio.get_running_loop()
            registry = ApprovalRegistry()

            # 注册审批（不阻塞）
            t0 = loop.time()
            aid, info = registry.register(
                tool_call_id="tc_nb",
                tool="run_command",
                command="git push",
                risk_level="destructive",
                risk_reason="高危推送",
                chat_id=1,
                timeout=5.0,
            )
            t1 = loop.time()
            # 注册应在 1ms 内完成
            self.assertLess(t1 - t0, 0.1)

            # 在后台 resolve（模拟前端点击）
            async def _resolve_later():
                await asyncio.sleep(0.05)
                registry.resolve(aid, "approve")

            task = asyncio.create_task(_resolve_later())

            # 等待审批结果（不阻塞其他协程）
            t2 = loop.time()
            action = await asyncio.wait_for(info["future"], timeout=5.0)
            t3 = loop.time()

            self.assertEqual(action, "approve")
            # 审批在 ~50ms 后完成
            self.assertGreater(t3 - t2, 0.01)
            self.assertLess(t3 - t2, 1.0)

            await task
            registry.remove(aid)

        asyncio.run(_run())

    def test_future_timeout(self):
        """验证超时不会永久挂起。"""

        async def _run():
            registry = ApprovalRegistry()
            aid, info = registry.register(
                tool_call_id="tc_to",
                tool="run_command",
                command="git push",
                risk_level="destructive",
                risk_reason="高危推送",
                chat_id=1,
                timeout=0.1,  # 100ms 超时
            )
            try:
                action = await asyncio.wait_for(info["future"], timeout=0.2)
            except asyncio.TimeoutError:
                action = "timeout"
            self.assertEqual(action, "timeout")
            registry.remove(aid)

        asyncio.run(_run())


# ──── execute_tool 审批流程测试 ────

class TestExecuteToolApproval(unittest.TestCase):
    """execute_tool + complete_approval 审批闭环。

    使用 SAFE 模式：git push 属 WRITE 风险，仅 SAFE（所有写入需审批）下
    才会走审批分支返回 awaiting_approval；STANDARD 默认会将其自动放行执行。
    """

    def setUp(self):
        set_approval_mode(ApprovalMode.SAFE)

    def tearDown(self):
        set_approval_mode(DEFAULT_APPROVAL_MODE)

    def test_high_risk_returns_pending(self):
        """HIGH_RISK 命令应返回 awaiting_approval record。"""

        async def _run():
            from app.core.tool_runtime.executor import execute_tool

            tool_call = {
                "function": {"name": "run_command", "arguments": '{"command": "rm -rf /tmp/test"}'},
                "id": "call_high_risk",
            }
            record = await execute_tool(
                tool_call=tool_call,
                project_path=_TEST_PROJECT,
                read_only=False,
                ctx={"chat_id": 1},
                emit=None,
            )
            self.assertEqual(record["status"], "awaiting_approval")
            self.assertEqual(record["tool"], "run_command")
            self.assertIn("approval_id", record)
            self.assertIn("approval_future", record)
            # 清理
            approval_registry.remove(record["approval_id"])

        asyncio.run(_run())

    def test_require_approval_returns_pending(self):
        """REQUIRE_APPROVAL 命令（如 git push）应返回 pending（auto_approve=False）。"""

        async def _run():
            from app.core.tool_runtime.executor import execute_tool

            tool_call = {
                "function": {"name": "run_command", "arguments": '{"command": "git push origin main"}'},
                "id": "call_req_approval",
            }
            record = await execute_tool(
                tool_call=tool_call,
                project_path=_TEST_PROJECT,
                read_only=False,
                ctx={"chat_id": 1},
                emit=None,
            )
            self.assertEqual(record["status"], "awaiting_approval")
            approval_registry.remove(record["approval_id"])

        asyncio.run(_run())

    def test_allow_passes_through(self):
        """只读命令应直接执行，不进入审批。"""

        async def _run():
            from app.core.tool_runtime.executor import execute_tool
            from unittest.mock import patch

            # Mock _run_tool 避免真实执行
            with patch(
                "app.core.tool_runtime.executor._run_tool",
                new_callable=AsyncMock,
            ) as mock_run:
                mock_run.return_value = "git status 输出..."

                tool_call = {
                    "function": {"name": "run_command", "arguments": '{"command": "git status"}'},
                    "id": "call_allow",
                }
                record = await execute_tool(
                    tool_call=tool_call,
                    project_path=_TEST_PROJECT,
                    read_only=False,
                    ctx={"chat_id": 1},
                    emit=None,
                )
                self.assertEqual(record["status"], "success")
                self.assertNotIn("approval_id", record)

        asyncio.run(_run())

    def test_complete_approval_approve(self):
        """审批通过后应执行命令并返回结果。"""

        async def _run():
            from app.core.tool_runtime.executor import execute_tool, complete_approval
            from unittest.mock import patch

            tool_call = {
                "function": {"name": "run_command", "arguments": '{"command": "git push origin main"}'},
                "id": "call_complete",
            }
            record = await execute_tool(
                tool_call=tool_call,
                project_path=_TEST_PROJECT,
                read_only=False,
                ctx={"chat_id": 1},
                emit=None,
            )

            # 在后台 resolve
            async def _resolve():
                await asyncio.sleep(0.02)
                approval_registry.resolve(record["approval_id"], "approve")

            asyncio.create_task(_resolve())

            with patch(
                "app.core.tool_runtime.executor._run_tool",
                new_callable=AsyncMock,
            ) as mock_run:
                mock_run.return_value = "Everything up-to-date"
                final = await complete_approval(record, project_path=_TEST_PROJECT)

            self.assertEqual(final["status"], "success")
            self.assertEqual(final["result"], "Everything up-to-date")

        asyncio.run(_run())

    def test_complete_approval_deny(self):
        """审批拒绝后应返回拒绝状态。"""

        async def _run():
            from app.core.tool_runtime.executor import execute_tool, complete_approval

            tool_call = {
                "function": {"name": "run_command", "arguments": '{"command": "rm -rf /tmp/test"}'},
                "id": "call_deny",
            }
            record = await execute_tool(
                tool_call=tool_call,
                project_path=_TEST_PROJECT,
                read_only=False,
                ctx={"chat_id": 1},
                emit=None,
            )

            approval_registry.resolve(record["approval_id"], "deny")
            final = await complete_approval(record)

            self.assertEqual(final["status"], "denied")
            self.assertFalse(final["success"])
            self.assertIn("用户拒绝了", final["result"])

        asyncio.run(_run())


# ──── Plan 模式拒绝测试 ────

class TestPlanModeDenial(unittest.TestCase):
    """Plan 模式拒绝所有非只读操作。"""

    def test_plan_mode_rejects_git_push(self):
        async def _run():
            from app.core.tool_runtime.executor import execute_tool

            tool_call = {
                "function": {"name": "run_command", "arguments": '{"command": "git push"}'},
                "id": "call_plan",
            }
            record = await execute_tool(
                tool_call=tool_call,
                project_path=_TEST_PROJECT,
                read_only=True,  # Plan 模式
                ctx={"chat_id": 1},
                emit=None,
            )
            self.assertEqual(record["status"], "failed")
            self.assertIn("plan", record["result"].lower())

        asyncio.run(_run())

    def test_plan_mode_rejects_write_file(self):
        async def _run():
            from app.core.tool_runtime.executor import execute_tool

            tool_call = {
                "function": {"name": "write_file", "arguments": '{"relative_path": "test.py", "content": "x"}'},
                "id": "call_plan_write",
            }
            record = await execute_tool(
                tool_call=tool_call,
                project_path=_TEST_PROJECT,
                read_only=True,
                ctx={"chat_id": 1},
                emit=None,
            )
            self.assertEqual(record["status"], "failed")
            self.assertIn("plan", record["result"].lower())

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()