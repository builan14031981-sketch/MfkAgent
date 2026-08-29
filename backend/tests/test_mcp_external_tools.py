"""T6 外部 MCP 工具链路集成测试 — 配置/可见性/风险判定/审批/审计/会话冻结。

真实链路：plugins 表(source=external_mcp) → ExternalMCPManager 枚举注册
→ PermissionFilter.resolve（会话冻结清单）→ ToolSelector.select（_def_map 合并）
→ executor.execute_tool（evaluate_tool fail-closed 判定 → 审批链）
→ tool_registry 分发 → StdioMCPConnection.tools/call → SandboxAuditLog 审计。

使用 tests/mcp_fake_server.py（stdio JSON-RPC）作为外部 server。
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.core.mcp_client as mcp_client_module  # noqa: E402
from app.core.mcp_client import ExternalMCPManager  # noqa: E402

FAKE_SERVER = str(Path(__file__).resolve().parent / "mcp_fake_server.py")
SERVER_ID = f"fakesrv-{uuid.uuid4().hex[:8]}"
READ_TOOL = f"mcp__{SERVER_ID}__fake_read"
WRITE_TOOL = f"mcp__{SERVER_ID}__fake_write"

_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


def _db():
    from app.core.database import SessionLocal
    return SessionLocal()


def setup_module(module):
    """注册外部 MCP 插件记录（source=external_mcp）并枚举。"""
    from app.models.agent import PluginItem

    db = _db()
    try:
        db.add(PluginItem(
            plugin_id=SERVER_ID,
            name="Fake MCP Server",
            version="0.0.1",
            description="集成测试用假 MCP server",
            status="active",
            source="external_mcp",
            config={"command": sys.executable, "args": [FAKE_SERVER]},
        ))
        db.commit()
    finally:
        db.close()

    # 独立管理器（不污染其他测试的全局单例）
    module.manager = ExternalMCPManager()
    mcp_client_module.external_mcp_manager = module.manager
    _run(module.manager.refresh())


def teardown_module(module):
    _run(module.manager.shutdown())
    from app.models.agent import PluginItem, SandboxAuditLog
    db = _db()
    try:
        db.query(PluginItem).filter(PluginItem.plugin_id == SERVER_ID).delete()
        db.query(SandboxAuditLog).filter(
            SandboxAuditLog.tool_name.in_([READ_TOOL, WRITE_TOOL])
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    _LOOP.close()


def _chat(chat_id=9001, mode="build", project_path=None):
    return SimpleNamespace(id=chat_id, mode=mode, project_path=project_path)


# ──── 注册与风险策略注入（fail-closed）────

def test_external_tools_registered():
    from app.services.tools import tool_registry
    assert tool_registry.get(READ_TOOL) is not None
    assert tool_registry.get(WRITE_TOOL) is not None
    # MCP inputSchema → OpenAI Function Calling 格式
    definition = tool_registry.get(READ_TOOL).get_definition()
    assert definition["type"] == "function"
    assert definition["function"]["parameters"]["type"] == "object"
    assert "path" in definition["function"]["parameters"]["properties"]


def test_risk_policy_injection_fail_closed():
    """readOnlyHint=true → 只读自动放行；无标注 → 写入类（build 需审批 / plan 拒绝）。"""
    from app.core.tool_runtime.risk_engine import evaluate_tool, Verdict

    d = evaluate_tool(READ_TOOL, "build")
    assert d.verdict == Verdict.ALLOW, "声明只读的外部工具 build 模式应自动放行"
    d = evaluate_tool(READ_TOOL, "plan")
    assert d.verdict == Verdict.ALLOW

    d = evaluate_tool(WRITE_TOOL, "build")
    assert d.verdict == Verdict.HIGH_RISK, "未声明只读的外部工具必须强制人工审批（HIGH_RISK）"
    d = evaluate_tool(WRITE_TOOL, "plan")
    assert d.verdict == Verdict.DENY, "写入类外部工具 plan 模式必须拒绝（fail-closed）"


# ──── 会话可见性（冻结清单）────

def test_permission_resolve_includes_external():
    from app.core.tool_runtime.permission import PermissionFilter

    names = PermissionFilter().resolve(_chat(9001))
    assert READ_TOOL in names
    assert WRITE_TOOL in names


def test_permission_plan_mode_excludes_write():
    from app.core.tool_runtime.permission import PermissionFilter

    names = PermissionFilter().resolve(_chat(9001, mode="plan"))
    assert READ_TOOL in names
    assert WRITE_TOOL not in names


def test_selector_merges_external_definitions():
    from app.core.tool_runtime.selector import ToolSelector

    chat = _chat(9001)
    defs = ToolSelector().select([READ_TOOL, WRITE_TOOL], chat)
    got = {d["function"]["name"] for d in defs}
    assert got == {READ_TOOL, WRITE_TOOL}


def test_session_freeze_and_drift():
    """会话期内冻结：server 停用后已冻结会话不变、新会话拿不到、漂移可检测。"""
    from app.core.tool_runtime.permission import PermissionFilter
    from app.models.agent import PluginItem

    chat_a = _chat(9101)
    assert READ_TOOL in PermissionFilter().resolve(chat_a)

    # 停用 server（复用现有插件启停：status → inactive）并刷新实时状态
    db = _db()
    try:
        row = db.query(PluginItem).filter(PluginItem.plugin_id == SERVER_ID).first()
        row.status = "inactive"
        db.commit()
    finally:
        db.close()
    _run(module_manager_refresh())

    # 已冻结会话：清单不变（工具变更下个会话生效）
    names_a = PermissionFilter().resolve(chat_a)
    assert READ_TOOL in names_a and WRITE_TOOL in names_a

    # 新会话：不再可见
    names_b = PermissionFilter().resolve(_chat(9102))
    assert READ_TOOL not in names_b and WRITE_TOOL not in names_b

    # 漂移检测：提示用户新开会话
    drift = module_manager().get_session_drift(chat_a)
    assert drift["stale"] is True
    assert set(drift["removed_tools"]) == {READ_TOOL, WRITE_TOOL,
                                           f"mcp__{SERVER_ID}__fake_fail"}

    # 恢复 active 供后续测试使用
    db = _db()
    try:
        row = db.query(PluginItem).filter(PluginItem.plugin_id == SERVER_ID).first()
        row.status = "active"
        db.commit()
    finally:
        db.close()
    _run(module_manager_refresh())


# ──── 执行链路：只读直通 / 写入审批 / 审计 ────

def test_executor_read_only_direct_execution():
    """只读外部工具：evaluate ALLOW → 直接执行 → tool_registry 分发 → MCP 调用。"""
    from app.core.tool_runtime.executor import execute_tool

    record = _run(execute_tool(
        tool_call={"function": {"name": READ_TOOL, "arguments": '{"path": "hello.txt"}'}, "id": "tc-read-1"},
        project_path=None, read_only=False, ctx={"chat_id": 9001},
    ))
    assert record["success"] is True, record["result"]
    assert "fake-read:" in record["result"]
    assert '"path": "hello.txt"' in record["result"]


def test_executor_write_requires_approval_and_completes():
    """写入外部工具：REQUIRE_APPROVAL → pending record → 审批 → complete_approval 执行。"""
    from app.core.tool_runtime.executor import execute_tool, complete_approval
    from app.core.tool_runtime.approval import approval_registry
    from app.models.agent import ApprovalRequest

    record = _run(execute_tool(
        tool_call={"function": {"name": WRITE_TOOL, "arguments": '{"path": "out.txt", "content": "x"}'}, "id": "tc-write-1"},
        project_path=None, read_only=False, ctx={"chat_id": 9001},
    ))
    # 1) 挂起审批（不执行）
    assert record["status"] == "awaiting_approval"
    assert record["success"] is False
    approval_id = record["approval_id"]
    info = approval_registry.get(approval_id)
    assert info is not None and info["tool"] == WRITE_TOOL
    # 2) 审批请求持久化（审批链有迹可循）
    db = _db()
    try:
        row = db.query(ApprovalRequest).filter(ApprovalRequest.approval_id == approval_id).first()
        assert row is not None
        assert row.status == "pending"
        assert row.tool_name == WRITE_TOOL
    finally:
        db.close()

    # 3) 用户批准 → complete_approval 闭环执行
    assert approval_registry.resolve(approval_id, "approve") is True
    final = _run(complete_approval(record))
    assert final["status"] == "success", final["result"]
    assert "fake-write-ok" in final["result"]

    # 4) 拒绝路径：不执行
    record2 = _run(execute_tool(
        tool_call={"function": {"name": WRITE_TOOL, "arguments": '{"path": "y"}'}, "id": "tc-write-2"},
        project_path=None, read_only=False, ctx={"chat_id": 9001},
    ))
    approval_registry.resolve(record2["approval_id"], "deny")
    final2 = _run(complete_approval(record2))
    assert final2["status"] == "denied"
    assert "fake-write" not in final2["result"]


def test_external_calls_audited_in_sandbox_audit_logs():
    from app.models.agent import SandboxAuditLog

    db = _db()
    try:
        rows = (
            db.query(SandboxAuditLog)
            .filter(SandboxAuditLog.tool_name == READ_TOOL)
            .all()
        )
        assert rows, "外部只读工具调用必须留下 sandbox_audit_logs 审计"
        ok = [r for r in rows if r.success]
        assert ok
        assert ok[-1].command.startswith(f"mcp://{SERVER_ID}/fake_read")
    finally:
        db.close()


def test_server_down_fails_soft_without_crash():
    """server 未连接/重启中：调用返回错误文本，不抛异常不崩主链路。"""
    async def run():
        text, ok, err = await module_manager().call_external("no-such-server", "whatever", {})
        assert ok is False
        assert text.startswith("错误")
    _run(run())


# ──── 辅助（供模块内复用）────

def module_manager():
    return mcp_client_module.external_mcp_manager


async def module_manager_refresh():
    await mcp_client_module.external_mcp_manager.refresh()


if __name__ == "__main__":
    sys.exit(__import__("pytest").main([__file__, "-v"]))
