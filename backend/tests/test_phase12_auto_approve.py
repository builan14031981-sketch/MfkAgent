"""Phase 12: Agent 自治模式 (Autonomous Mode) 与三级安全漏斗 — 专项防御测试。

测试覆盖：
  1. auto_approve=True + REQUIRE_APPROVAL 级工具（write_file）→ 自动放行 + ToolStartEvent
  2. auto_approve=True + HIGH_RISK 级命令（rm -rf）→ 自动模式被击穿，强制挂起审批
  3. auto_approve=False + REQUIRE_APPROVAL → 正常审批流程（回归）
  4. 三级漏斗判定矩阵验证
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.tool_runtime.risk_engine import (
    Verdict, RiskDecision, RiskLevel,
    command_risk_engine, evaluate_tool,
    TOOL_RISK_POLICY, READ_ONLY_TOOLS,
)
from app.core.tool_runtime.executor import execute_tool


# ============================================================================
# Test 1: 三级漏斗判定矩阵
# ============================================================================

def test_tiered_funnel_matrix():
    """验证 ALLOW / REQUIRE_APPROVAL / HIGH_RISK / DENY 四级判定正确分流。"""
    results = []

    # ── ALLOW: 只读工具 ──
    for tool in READ_ONLY_TOOLS:
        d = evaluate_tool(tool, "build")
        ok = d.verdict == Verdict.ALLOW
        results.append({"case": f"只读工具 {tool}", "ok": ok, "verdict": d.verdict.value})

    # ── REQUIRE_APPROVAL: 常规写工具 ──
    require_approval_tools = ["write_file", "git_commit", "git_add", "git_push", "git_pull", "rename_file"]
    for tool in require_approval_tools:
        d = evaluate_tool(tool, "build")
        ok = d.verdict == Verdict.REQUIRE_APPROVAL
        results.append({"case": f"可自动审批 {tool}", "ok": ok, "verdict": d.verdict.value})

    # ── HIGH_RISK: 高危工具 ──
    high_risk_tools = ["git_restore", "git_reset", "git_clean", "git_revert", "delete_file"]
    for tool in high_risk_tools:
        d = evaluate_tool(tool, "build")
        ok = d.verdict == Verdict.HIGH_RISK
        results.append({"case": f"高危工具 {tool}", "ok": ok, "verdict": d.verdict.value})

    # ── DENY: plan 模式拒绝 ──
    for tool in ["write_file", "git_clean"]:
        d = evaluate_tool(tool, "plan")
        ok = d.verdict == Verdict.DENY
        results.append({"case": f"Plan 拒绝 {tool}", "ok": ok, "verdict": d.verdict.value})

    failed = [r for r in results if not r["ok"]]
    assert not failed, f"三级漏斗判定矩阵失败: {failed}"
    print(f"  [PASS] 三级漏斗判定矩阵: {len(results)} 个用例全部通过")


# ============================================================================
# Test 2: 命令引擎 — 三级漏斗
# ============================================================================

def test_command_engine_tiered():
    """验证命令风险引擎的三级分流。"""
    results = []

    # ALLOW
    d = command_risk_engine.evaluate("ipconfig", "build")
    results.append({"case": "ipconfig ALLOW", "ok": d.verdict == Verdict.ALLOW})

    # REQUIRE_APPROVAL
    d = command_risk_engine.evaluate("pip install requests", "build")
    results.append({"case": "pip install REQUIRE_APPROVAL", "ok": d.verdict == Verdict.REQUIRE_APPROVAL})

    d = command_risk_engine.evaluate("git add .", "build")
    results.append({"case": "git add REQUIRE_APPROVAL", "ok": d.verdict == Verdict.REQUIRE_APPROVAL})

    # HIGH_RISK
    d = command_risk_engine.evaluate("rm -rf /tmp/test", "build")
    results.append({"case": "rm -rf HIGH_RISK", "ok": d.verdict == Verdict.HIGH_RISK})

    d = command_risk_engine.evaluate("shutdown /s", "build")
    results.append({"case": "shutdown HIGH_RISK", "ok": d.verdict == Verdict.HIGH_RISK})

    d = command_risk_engine.evaluate("format C:", "build")
    results.append({"case": "format HIGH_RISK", "ok": d.verdict == Verdict.HIGH_RISK})

    # DENY: shell 元字符
    d = command_risk_engine.evaluate("ls; rm -rf /", "build")
    results.append({"case": "shell meta DENY", "ok": d.verdict == Verdict.DENY})

    d = command_risk_engine.evaluate("echo `whoami`", "build")
    results.append({"case": "backtick DENY", "ok": d.verdict == Verdict.DENY})

    failed = [r for r in results if not r["ok"]]
    assert not failed, f"命令引擎三级漏斗失败: {failed}"
    print(f"  [PASS] 命令引擎三级漏斗: {len(results)} 个用例全部通过")


# ============================================================================
# Test 3: auto_approve=True + REQUIRE_APPROVAL → 自动放行 + ToolStartEvent
# ============================================================================

class FakeEmitter:
    """收集 tool_start / tool_result 事件用于断言。"""
    def __init__(self):
        self.events = []

    def __call__(self, event: dict):
        self.events.append(event)


def test_auto_approve_write_file():
    """auto_approve=True + write_file → 自动放行，emit tool_start 和 tool_result。"""
    async def _run():
        emitter = FakeEmitter()
        record = await execute_tool(
            tool_call={
                "function": {"name": "write_file", "arguments": '{"relative_path": "test.txt", "content": "hello"}'},
                "id": "call_001",
            },
            project_path=".",
            read_only=False,
            ctx={},
            emit=emitter,
            auto_approve=True,
        )

        # 断言 1: 状态为 success（非 awaiting_approval）
        assert record["status"] == "success", f"Expected success, got {record['status']}"
        assert record["success"] is True, f"Expected success=True"

        # 断言 2: 发射了 tool_start 事件
        start_events = [e for e in emitter.events if e.get("type") == "tool_start"]
        assert len(start_events) >= 1, f"Expected at least 1 tool_start event, got {len(start_events)}"
        assert start_events[0]["tool"] == "write_file"

        # 断言 3: 发射了 tool_result 事件
        result_events = [e for e in emitter.events if e.get("type") == "tool_result"]
        assert len(result_events) >= 1, f"Expected at least 1 tool_result event, got {len(result_events)}"

        # 断言 4: 没有 tool_approval 事件（因为自动放行了）
        approval_events = [e for e in emitter.events if e.get("type") == "tool_approval"]
        assert len(approval_events) == 0, f"Expected 0 tool_approval events, got {len(approval_events)}"

        print(f"  [PASS] auto_approve=True + write_file: 自动放行成功, events={[e['type'] for e in emitter.events]}")

    asyncio.run(_run())


# ============================================================================
# Test 4: auto_approve=True + HIGH_RISK → 自动模式被击穿，强制挂起审批
# ============================================================================

def test_auto_approve_high_risk_command():
    """auto_approve=True + 高危命令（rm -rf）→ 强行挂起，不自动放行。"""
    async def _run():
        emitter = FakeEmitter()
        record = await execute_tool(
            tool_call={
                "function": {"name": "run_command", "arguments": '{"command": "rm -rf /tmp/test"}'},
                "id": "call_002",
            },
            project_path=".",
            read_only=False,
            ctx={},
            emit=emitter,
            auto_approve=True,
        )

        # 断言 1: 状态为 awaiting_approval（被拦截）
        assert record["status"] == "awaiting_approval", (
            f"Expected awaiting_approval for HIGH_RISK, got {record['status']}"
        )

        # 断言 2: 有 approval_id（进入了审批流程）
        assert "approval_id" in record, "Expected approval_id in record"
        assert record["approval_id"], "approval_id should not be empty"

        # 断言 3: 发射了 tool_approval 事件
        approval_events = [e for e in emitter.events if e.get("type") == "tool_approval"]
        assert len(approval_events) >= 1, f"Expected at least 1 tool_approval event, got {len(approval_events)}"

        # 断言 4: 没有 tool_result 事件（因为在等待审批）
        result_events = [e for e in emitter.events if e.get("type") == "tool_result"]
        assert len(result_events) == 0, f"Expected 0 tool_result events for pending approval, got {len(result_events)}"

        print(f"  [PASS] auto_approve=True + rm -rf: 自动模式被击穿, 强制审批, events={[e['type'] for e in emitter.events]}")

    asyncio.run(_run())


# ============================================================================
# Test 5: auto_approve=True + HIGH_RISK 工具（git_clean）→ 强制挂起
# ============================================================================

def test_auto_approve_high_risk_tool():
    """auto_approve=True + git_clean → 高危工具，自动模式被击穿。"""
    async def _run():
        emitter = FakeEmitter()
        record = await execute_tool(
            tool_call={
                "function": {"name": "git_clean", "arguments": '{}'},
                "id": "call_003",
            },
            project_path=".",
            read_only=False,
            ctx={},
            emit=emitter,
            auto_approve=True,
        )

        # 断言: 高危工具仍被拦截
        assert record["status"] == "awaiting_approval", (
            f"Expected awaiting_approval for HIGH_RISK tool, got {record['status']}"
        )
        assert "approval_id" in record

        approval_events = [e for e in emitter.events if e.get("type") == "tool_approval"]
        assert len(approval_events) >= 1

        print(f"  [PASS] auto_approve=True + git_clean: 高危工具被击穿拦截")

    asyncio.run(_run())


# ============================================================================
# Test 6: auto_approve=False + REQUIRE_APPROVAL → 正常审批流程（回归）
# ============================================================================

def test_no_auto_approve_normal_flow():
    """auto_approve=False 时，write_file 仍走正常审批流程。"""
    async def _run():
        emitter = FakeEmitter()
        record = await execute_tool(
            tool_call={
                "function": {"name": "write_file", "arguments": '{"relative_path": "test.txt", "content": "hello"}'},
                "id": "call_004",
            },
            project_path=".",
            read_only=False,
            ctx={},
            emit=emitter,
            auto_approve=False,
        )

        # 断言: 正常审批流程
        assert record["status"] == "awaiting_approval"
        assert "approval_id" in record

        approval_events = [e for e in emitter.events if e.get("type") == "tool_approval"]
        assert len(approval_events) >= 1

        print(f"  [PASS] auto_approve=False + write_file: 正常审批流程")

    asyncio.run(_run())


# ============================================================================
# Test 7: ALLOW 工具不受 auto_approve 影响
# ============================================================================

def test_auto_approve_allow_tool():
    """auto_approve=True 时，ALLOW 级工具始终直接放行。"""
    async def _run():
        for tool_name in ["read_file", "web_search", "git_status"]:
            emitter = FakeEmitter()
            args = '{"relative_path": "test.txt"}' if tool_name == "read_file" else '{}'
            record = await execute_tool(
                tool_call={
                    "function": {"name": tool_name, "arguments": args},
                    "id": f"call_allow_{tool_name}",
                },
                project_path=".",
                read_only=False,
                ctx={},
                emit=emitter,
                auto_approve=True,
            )

            assert record["status"] != "awaiting_approval", (
                f"ALLOW tool {tool_name} should not be pending approval"
            )

        print(f"  [PASS] ALLOW 工具不受 auto_approve 影响")

    asyncio.run(_run())


# ============================================================================
# Test 8: DENY 工具不受 auto_approve 影响
# ============================================================================

def test_auto_approve_deny_tool():
    """auto_approve=True 时，DENY 级命令始终被拒绝。"""
    async def _run():
        emitter = FakeEmitter()
        record = await execute_tool(
            tool_call={
                "function": {"name": "run_command", "arguments": '{"command": "ls; rm -rf /"}'},
                "id": "call_deny",
            },
            project_path=".",
            read_only=False,
            ctx={},
            emit=emitter,
            auto_approve=True,
        )

        assert record["status"] == "failed" or record["success"] is False, (
            f"DENY should be blocked, got {record['status']}"
        )

        print(f"  [PASS] DENY 命令不受 auto_approve 影响: {record['result'][:80]}")

    asyncio.run(_run())


# ============================================================================
# Runner
# ============================================================================

if __name__ == "__main__":
    print("=== Phase 12: Agent 自治模式 专项防御测试 ===\n")
    test_tiered_funnel_matrix()
    test_command_engine_tiered()
    test_auto_approve_write_file()
    test_auto_approve_high_risk_command()
    test_auto_approve_high_risk_tool()
    test_no_auto_approve_normal_flow()
    test_auto_approve_allow_tool()
    test_auto_approve_deny_tool()
    print("\n=== 全部测试通过 ===")