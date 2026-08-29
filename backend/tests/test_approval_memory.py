"""T5 审批记忆（approval_memory）专项测试。

覆盖任务要求的四个场景：
1. 近90天同一命令模式 3 次 approve 后，第 4 次自动放行（REQUIRE_APPROVAL → EXECUTE），
   执行结果带 auto_approved_by_history=True 标注，且 approval_requests 表可查豁免来源
   （status=auto_approved 审计行）；
2. 该模式夹 1 次 deny 后恢复弹窗（出现过 deny 永不豁免）；
3. HIGH_RISK 命令与 run_outside_command（沙箱外）历史再多次 approve 也不放行；
4. 开关 approval_memory_enabled 关闭（默认）时行为与现状完全一致。

另含：命令归一化单元测试、ApprovalPolicy.decide 豁免前置检查单元测试。

隔离性：本文件全部数据操作走独立的内存 SQLite（StaticPool），不读写共享的
tests/mfkagent_test.db——审批记忆按 (tool_name, 归一化命令) 全局聚合，若直接用共享
测试库，其他测试文件遗留的 approve 行会污染计数（已验证会互相干扰）。
executor 路径通过 patch app.core.database.SessionLocal 注入隔离库。
"""

import asyncio
import os
import sys
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.models.agent  # noqa: F401  先注册模型到 Base.metadata
from app.core.database import Base
from app.core.tool_runtime import approval_memory
from app.core.tool_runtime.approval import approval_registry
from app.core.tool_runtime.approval_policy import (
    ApprovalMode,
    ApprovalPolicy,
)
from app.core.tool_runtime.risk_engine import (
    ExecutionAction,
    RiskDecision,
    RiskLevel,
    Verdict,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 独立内存库：单连接 StaticPool，进程内存活，与共享测试库完全隔离
_isolated_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=_isolated_engine)
IsolatedSession = sessionmaker(bind=_isolated_engine, expire_on_commit=False)

# executor ctx 用的标记 chat_id（仅隔离库内数据）
_MARKER = 777700001


def _seed_approval(tool_name: str, command: str, status: str, age_days: float = 1.0):
    """向隔离库 approval_requests 插入一条历史审批记录。"""
    from app.models.agent import ApprovalRequest

    db = IsolatedSession()
    try:
        row = ApprovalRequest(
            approval_id="aprv_t5_" + uuid.uuid4().hex[:12],
            tool_call_id="tc_t5_" + uuid.uuid4().hex[:8],
            tool_name=tool_name,
            command=command,
            risk_level="write",
            risk_reason="测试种子数据",
            chat_id=_MARKER,
            status=status,
            created_at=datetime.utcnow() - timedelta(days=age_days),
            resolved_at=datetime.utcnow() - timedelta(days=age_days),
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def _set_switch(value: str):
    """在隔离库写/删 settings 开关 approval_memory_enabled。"""
    from app.models.agent import Setting

    db = IsolatedSession()
    try:
        row = db.query(Setting).filter(Setting.key == approval_memory.MEMORY_ENABLED_KEY).first()
        if value is None:
            if row:
                db.delete(row)
        else:
            if row:
                row.value = value
            else:
                db.add(Setting(key=approval_memory.MEMORY_ENABLED_KEY, value=value))
        db.commit()
    finally:
        db.close()


def _rows_by_tool_call(tool_call_id: str):
    from app.models.agent import ApprovalRequest

    db = IsolatedSession()
    try:
        return (
            db.query(ApprovalRequest)
            .filter(ApprovalRequest.tool_call_id == tool_call_id)
            .all()
        )
    finally:
        db.close()


def _wipe_isolated():
    """清空隔离库的审批行与开关（每个用例前后执行）。"""
    from app.models.agent import ApprovalRequest, Setting

    db = IsolatedSession()
    try:
        db.query(ApprovalRequest).delete()
        db.query(Setting).filter(Setting.key == approval_memory.MEMORY_ENABLED_KEY).delete()
        db.commit()
    finally:
        db.close()


class _IsolatedDBTest(unittest.TestCase):
    """公共 setUp/tearDown：开关默认开启（各用例可覆盖）、清空隔离库。"""

    def setUp(self):
        _wipe_isolated()
        _set_switch("true")

    def tearDown(self):
        _wipe_isolated()


# ──── 归一化单元测试 ────

class TestNormalizeCommandPattern(unittest.TestCase):
    """去引号、去参数值，保留命令首 token 与子命令。"""

    def test_git_status_variants_same_pattern(self):
        self.assertEqual(
            approval_memory.normalize_command_pattern("git status --porcelain -b"),
            approval_memory.normalize_command_pattern("git status"),
        )
        self.assertEqual(approval_memory.normalize_command_pattern("git status"), "git status")

    def test_pip_install_prefix(self):
        self.assertEqual(
            approval_memory.normalize_command_pattern("pip install requests==2.1 -i https://pypi.org/simple"),
            "pip install",
        )

    def test_npm_run_keeps_subcommand_only(self):
        self.assertEqual(approval_memory.normalize_command_pattern("npm run build"), "npm run")

    def test_quotes_stripped_and_flag_value_dropped(self):
        self.assertEqual(
            approval_memory.normalize_command_pattern('git commit -m "fix bug"'),
            "git commit",
        )
        self.assertEqual(
            approval_memory.normalize_command_pattern("git commit -m 'fix: 同步脚本'"),
            approval_memory.normalize_command_pattern('git commit -m "any message"'),
        )

    def test_case_insensitive(self):
        self.assertEqual(
            approval_memory.normalize_command_pattern("Git Status"),
            approval_memory.normalize_command_pattern("git status"),
        )

    def test_tool_description_head(self):
        self.assertEqual(approval_memory.normalize_command_pattern("写入文件: src/a.py"), "写入文件")
        self.assertEqual(
            approval_memory.normalize_command_pattern("写入文件: b.py"),
            approval_memory.normalize_command_pattern("写入文件: 完全不同的路径.txt"),
        )
        self.assertEqual(approval_memory.normalize_command_pattern("git_commit(path='x')"), "git_commit")

    def test_outside_command_bracket_prefix_stripped(self):
        # [cwd: ...] 前缀剥离（豁免与否另由 run_outside_command 硬边界决定）
        self.assertEqual(
            approval_memory.normalize_command_pattern("[cwd: C:/x] git push origin dev"),
            "git push",
        )

    def test_empty(self):
        self.assertEqual(approval_memory.normalize_command_pattern(""), "")
        self.assertEqual(approval_memory.normalize_command_pattern(None), "")


# ──── check() 历史聚合判定测试 ────

class TestApprovalMemoryCheck(_IsolatedDBTest):
    """approval_memory.check：90 天窗口 / deny 永不豁免 / 开关 / 硬边界。"""

    def test_three_approves_exempts(self):
        for cmd in ("git push origin main", "git push", "git push origin dev"):
            _seed_approval("run_command", cmd, "approve")
        r = approval_memory.check("run_command", "git push origin feature-x", db=IsolatedSession())
        self.assertIsNotNone(r)
        self.assertEqual(r.pattern, "git push")
        self.assertEqual(r.approve_count, 3)
        self.assertTrue(r.reason.startswith(approval_memory.MEMORY_EXEMPT_TAG))

    def test_two_approves_not_enough(self):
        _seed_approval("run_command", "git push origin main", "approve")
        _seed_approval("run_command", "git push", "approve")
        self.assertIsNone(approval_memory.check("run_command", "git push origin main", db=IsolatedSession()))

    def test_approves_outside_90d_window_ignored(self):
        _seed_approval("run_command", "git push", "approve", age_days=100)
        _seed_approval("run_command", "git push", "approve", age_days=120)
        _seed_approval("run_command", "git push", "approve", age_days=95)
        self.assertIsNone(approval_memory.check("run_command", "git push origin main", db=IsolatedSession()))

    def test_any_deny_blocks_forever(self):
        _seed_approval("run_command", "git push origin main", "approve")
        _seed_approval("run_command", "git push", "approve")
        _seed_approval("run_command", "git push origin dev", "approve")
        # deny 发生在 200 天前（窗口外）→ 仍然永不豁免
        _seed_approval("run_command", "git push origin old", "deny", age_days=200)
        self.assertIsNone(approval_memory.check("run_command", "git push origin main", db=IsolatedSession()))

    def test_timeout_cancelled_pending_not_counted(self):
        _seed_approval("run_command", "git push", "approve")
        _seed_approval("run_command", "git push", "approve")
        _seed_approval("run_command", "git push", "timeout")
        _seed_approval("run_command", "git push", "cancelled")
        _seed_approval("run_command", "git push", "pending")
        self.assertIsNone(approval_memory.check("run_command", "git push origin main", db=IsolatedSession()))

    def test_pattern_must_match(self):
        for cmd in ("git commit -m 'a'", "git commit -m 'b'", "git commit -m 'c'"):
            _seed_approval("run_command", cmd, "approve")
        # git commit 历史 ≠ git push 模式
        self.assertIsNone(approval_memory.check("run_command", "git push origin main", db=IsolatedSession()))

    def test_switch_off_returns_none(self):
        for _ in range(4):
            _seed_approval("run_command", "git push", "approve")
        _set_switch("false")
        self.assertIsNone(approval_memory.check("run_command", "git push origin main", db=IsolatedSession()))

    def test_switch_absent_returns_none(self):
        for _ in range(4):
            _seed_approval("run_command", "git push", "approve")
        _set_switch(None)  # 未配置 = 默认关闭
        self.assertIsNone(approval_memory.check("run_command", "git push origin main", db=IsolatedSession()))

    def test_outside_command_hard_boundary(self):
        # 沙箱外命令即使历史全 approve 也永不豁免
        for _ in range(5):
            _seed_approval("run_outside_command", "dir", "approve")
        self.assertIsNone(approval_memory.check("run_outside_command", "dir", db=IsolatedSession()))

    def test_explicit_enabled_bypasses_switch(self):
        # enabled=True 显式传入（测试注入用）：跳过 settings 读取，直接查历史
        _set_switch("false")
        for _ in range(3):
            _seed_approval("run_command", "git push", "approve")
        r = approval_memory.check("run_command", "git push origin main", enabled=True, db=IsolatedSession())
        self.assertIsNotNone(r)
        self.assertEqual(r.pattern, "git push")

    def test_explicit_disabled(self):
        # enabled=False 显式传入：恒不豁免
        for _ in range(3):
            _seed_approval("run_command", "git push", "approve")
        self.assertIsNone(
            approval_memory.check("run_command", "git push origin main", enabled=False, db=IsolatedSession())
        )

    def test_db_error_fail_closed(self):
        # 查询异常 → 不豁免（绝不因记忆故障放大权限）
        for _ in range(4):
            _seed_approval("run_command", "git push", "approve")

        class _Broken:
            def __getattr__(self, name):
                raise RuntimeError("mock db failure")

        self.assertIsNone(approval_memory.check("run_command", "git push origin main", db=_Broken()))


# ──── ApprovalPolicy.decide 豁免前置检查测试 ────

class TestApprovalPolicyDecideMemoryExemption(unittest.TestCase):
    """decide(memory_exemption=...)：仅 REQUIRE_APPROVAL 可豁免，硬边界不可逾越。"""

    def _exemption(self):
        return approval_memory.MemoryExemption(
            pattern="git push", approve_count=3, deny_count=0,
            reason=approval_memory.build_exempt_reason("git push", 3),
        )

    def test_require_approval_elevates_to_execute(self):
        policy = ApprovalPolicy(ApprovalMode.SAFE)
        decision = RiskDecision(Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "需审批", "git push origin main")
        ed = policy.decide(decision, memory_exemption=self._exemption())
        self.assertEqual(ed.action, ExecutionAction.EXECUTE)
        self.assertTrue(ed.reason.startswith(approval_memory.MEMORY_EXEMPT_TAG))
        self.assertEqual(ed.original_verdict, Verdict.REQUIRE_APPROVAL)

    def test_high_risk_never_elevates(self):
        policy = ApprovalPolicy(ApprovalMode.SAFE)
        decision = RiskDecision(Verdict.HIGH_RISK, RiskLevel.DESTRUCTIVE, "危险命令", "rm -rf build")
        ed = policy.decide(decision, memory_exemption=self._exemption())
        self.assertEqual(ed.action, ExecutionAction.REQUIRE_APPROVAL)

    def test_deny_never_elevates(self):
        policy = ApprovalPolicy(ApprovalMode.SAFE)
        decision = RiskDecision(Verdict.DENY, RiskLevel.DESTRUCTIVE, "元字符", "ls; rm")
        ed = policy.decide(decision, memory_exemption=self._exemption())
        self.assertEqual(ed.action, ExecutionAction.BLOCK)

    def test_no_exemption_keeps_legacy_behavior(self):
        policy = ApprovalPolicy(ApprovalMode.SAFE)
        decision = RiskDecision(Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "需审批", "git push")
        ed = policy.decide(decision)
        self.assertEqual(ed.action, ExecutionAction.REQUIRE_APPROVAL)


# ──── execute_tool 端到端集成测试（隔离库经 SessionLocal patch 注入）────

class TestExecuteToolMemoryExemption(_IsolatedDBTest):
    """execute_tool 端到端：第 4 次自动放行 + 标注 + 审批表豁免来源；deny/硬边界/开关关闭恢复现状。"""

    def _exec(self, tool: str, arguments_json: str, call_id: str):
        from app.core.tool_runtime.executor import execute_tool

        return execute_tool(
            tool_call={"function": {"name": tool, "arguments": arguments_json}, "id": call_id},
            project_path=None,
            read_only=False,
            ctx={"chat_id": _MARKER, "permission_mode": "safe"},
            emit=None,
        )

    def _run_patched(self, coro_fn):
        """在 SessionLocal 指向隔离库的前提下运行 execute_tool 协程。"""
        with patch("app.core.database.SessionLocal", IsolatedSession):
            return asyncio.run(coro_fn())

    def test_fourth_call_auto_executes_with_annotation_and_audit(self):
        for cmd in ("git push origin main", "git push", "git push origin dev"):
            _seed_approval("run_command", cmd, "approve")

        async def _run():
            with patch(
                "app.core.tool_runtime.executor._run_tool", new_callable=AsyncMock
            ) as mock_run:
                mock_run.return_value = "Everything up-to-date"
                record = await self._exec(
                    "run_command", '{"command": "git push origin main"}', "call_t5_auto"
                )
                return record

        record = self._run_patched(_run)
        self.assertEqual(record["status"], "success")  # 不再弹窗
        self.assertNotIn("approval_id", record)
        self.assertTrue(record.get("auto_approved_by_history"))  # 结果标注
        # 审批表可查豁免来源
        rows = _rows_by_tool_call("call_t5_auto")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, approval_memory.AUTO_APPROVED_STATUS)
        self.assertIn(approval_memory.MEMORY_EXEMPT_TAG, rows[0].risk_reason)
        self.assertIn("git push", rows[0].risk_reason)

    def test_write_file_pattern_exemption(self):
        # 非命令工具：同工具描述模式（写入文件）3 次批准后自动放行
        for path in ("a.py", "b.py", "c.py"):
            _seed_approval("write_file", f"写入文件: {path}", "approve")

        async def _run():
            with patch(
                "app.core.tool_runtime.executor._run_tool", new_callable=AsyncMock
            ) as mock_run:
                mock_run.return_value = "ok"
                return await self._exec(
                    "write_file",
                    '{"relative_path": "d.py", "content": "x"}',
                    "call_t5_write",
                )

        record = self._run_patched(_run)
        self.assertEqual(record["status"], "success")
        self.assertTrue(record.get("auto_approved_by_history"))

    def test_deny_in_history_keeps_prompting(self):
        _seed_approval("run_command", "git push origin main", "approve")
        _seed_approval("run_command", "git push", "approve")
        _seed_approval("run_command", "git push origin dev", "approve")
        _seed_approval("run_command", "git push origin old", "deny")

        async def _run():
            return await self._exec(
                "run_command", '{"command": "git push origin main"}', "call_t5_deny"
            )

        record = self._run_patched(_run)
        self.assertEqual(record["status"], "awaiting_approval")  # 恢复弹窗
        self.assertNotIn("auto_approved_by_history", record)
        approval_registry.remove(record["approval_id"])
        # 本次仍是普通 pending 审批行，而非豁免审计行
        rows = _rows_by_tool_call("call_t5_deny")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "pending")

    def test_switch_off_behaves_like_legacy(self):
        # 开关关闭：与现状完全一致——弹窗、无标注、无豁免审计行
        for _ in range(4):
            _seed_approval("run_command", "git push", "approve")
        _set_switch("false")

        async def _run():
            return await self._exec(
                "run_command", '{"command": "git push origin main"}', "call_t5_off"
            )

        record = self._run_patched(_run)
        self.assertEqual(record["status"], "awaiting_approval")
        self.assertNotIn("auto_approved_by_history", record)
        approval_registry.remove(record["approval_id"])
        rows = _rows_by_tool_call("call_t5_off")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "pending")

    def test_high_risk_command_never_exempted(self):
        # HIGH_RISK（破坏性命令）：历史再多 approve 也不放行
        for _ in range(5):
            _seed_approval("run_command", "rm -rf build", "approve")

        async def _run():
            return await self._exec(
                "run_command", '{"command": "rm -rf build"}', "call_t5_highrisk"
            )

        record = self._run_patched(_run)
        self.assertEqual(record["status"], "awaiting_approval")
        self.assertNotIn("auto_approved_by_history", record)
        approval_registry.remove(record["approval_id"])

    def test_outside_command_never_exempted(self):
        # run_outside_command（沙箱外命令）：硬边界，历史再多 approve 也不放行
        for _ in range(5):
            _seed_approval("run_outside_command", "dir", "approve")

        async def _run():
            return await self._exec(
                "run_outside_command", '{"command": "dir", "cwd": "C:/tmp"}', "call_t5_outside"
            )

        record = self._run_patched(_run)
        self.assertEqual(record["status"], "awaiting_approval")
        self.assertNotIn("auto_approved_by_history", record)
        approval_registry.remove(record["approval_id"])


# ──── settings 开关注册 ────

class TestSettingsSwitchRegistered(unittest.TestCase):
    def test_default_settings_contains_switch_off(self):
        from app.api.settings import DEFAULT_SETTINGS

        self.assertIn(approval_memory.MEMORY_ENABLED_KEY, DEFAULT_SETTINGS)
        self.assertEqual(DEFAULT_SETTINGS[approval_memory.MEMORY_ENABLED_KEY], "false")

    def test_default_disabled_in_module(self):
        # 隔离库未配置开关时 check 恒不豁免（默认灰度关闭）
        self.assertFalse(approval_memory._read_enabled(IsolatedSession()))


if __name__ == "__main__":
    unittest.main()
