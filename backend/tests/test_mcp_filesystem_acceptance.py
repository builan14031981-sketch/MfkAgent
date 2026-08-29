"""T6 验收测试 — 接入真实 stdio MCP server：@modelcontextprotocol/server-filesystem（npx 启动）。

验收用例（任务书要求，全部实际跑通）：
    1. 能列出其工具（tools/list → 工具目录/注册表）
    2. 成功调用 read_file 类只读工具
    3. write 类工具正确触发现有审批流程（REQUIRE_APPROVAL → approval_requests 持久化 →
       用户批准后闭环执行；拒绝则不执行）
    4. 杀掉 MCP 子进程后主程序不崩、自动重启后可继续调用
    5. 外部工具调用在 sandbox_audit_logs 中有迹可循
    6. 会话冻结清单跨崩溃重启保持稳定

npx 不可用时跳过（CI 环境兜底）；本机开发环境必须真实跑通。
"""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import app.core.mcp_client as mcp_client_module  # noqa: E402
from app.core.mcp_client import ExternalMCPManager  # noqa: E402

SERVER_ID = "filesystem"
READ_TOOL = f"mcp__{SERVER_ID}__read_file"
WRITE_TOOL = f"mcp__{SERVER_ID}__write_file"

_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


def _db():
    from app.core.database import SessionLocal
    return SessionLocal()


@pytest.fixture(scope="module")
def fs_env():
    """启动真实 server-filesystem：临时目录作 allowed root，预置一个待读文件。"""
    if shutil.which("npx") is None:
        pytest.skip("npx 不可用，跳过真实 server-filesystem 验收")

    tmp = tempfile.mkdtemp(prefix="mcp_acceptance_")
    hello = Path(tmp) / "hello.txt"
    hello.write_text("MCP-ACCEPTANCE-内容\n", encoding="utf-8")

    from app.models.agent import PluginItem
    db = _db()
    try:
        db.query(PluginItem).filter(PluginItem.plugin_id == SERVER_ID).delete()
        db.add(PluginItem(
            plugin_id=SERVER_ID,
            name="Filesystem MCP Server",
            version="0.1.0",
            description="T6 验收：@modelcontextprotocol/server-filesystem",
            status="active",
            source="external_mcp",
            config={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", tmp],
            },
        ))
        db.commit()
    finally:
        db.close()

    manager = ExternalMCPManager()
    mcp_client_module.external_mcp_manager = manager
    _run(manager.refresh())  # npx 冷启动（已预热缓存）+ initialize + tools/list

    tools = manager.get_server_tools(SERVER_ID)
    assert tools, "server-filesystem 枚举结果为空"
    tool_names = {t["name"] for t in tools}
    assert "read_file" in tool_names and "write_file" in tool_names

    yield {"tmp": tmp, "hello": hello, "manager": manager, "tool_names": tool_names}

    _run(manager.shutdown())
    from app.models.agent import PluginItem, SandboxAuditLog, ApprovalRequest
    db = _db()
    try:
        db.query(PluginItem).filter(PluginItem.plugin_id == SERVER_ID).delete()
        db.query(SandboxAuditLog).filter(
            SandboxAuditLog.tool_name.in_([READ_TOOL, WRITE_TOOL])
        ).delete(synchronize_session=False)
        db.query(ApprovalRequest).filter(ApprovalRequest.tool_name == WRITE_TOOL).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    shutil.rmtree(tmp, ignore_errors=True)
    _LOOP.close()


def _chat(chat_id=9501, mode="build", project_path=None):
    return SimpleNamespace(id=chat_id, mode=mode, project_path=project_path)


# ──── 用例 1：列出其工具（目录可见性 + 注册表）────

def test_acceptance_list_tools_and_catalog(fs_env):
    from app.core.tool_runtime.permission import PermissionFilter
    from app.core.tool_runtime.selector import ToolSelector

    chat = _chat()
    names = PermissionFilter().resolve(chat)
    assert READ_TOOL in names and WRITE_TOOL in names

    defs = ToolSelector().select([READ_TOOL], chat)
    assert defs and defs[0]["function"]["name"] == READ_TOOL
    schema = defs[0]["function"]["parameters"]
    assert schema.get("type") == "object"
    # server-filesystem 的 read_file 需要路径参数
    assert "path" in json.dumps(schema)

    # 只读工具按 annotations.readOnlyHint 自动放行；write_file 未声明只读 → 强制人工审批
    from app.core.tool_runtime.risk_engine import evaluate_tool, Verdict
    assert evaluate_tool(READ_TOOL, "build").verdict == Verdict.ALLOW
    assert evaluate_tool(WRITE_TOOL, "build").verdict == Verdict.HIGH_RISK
    assert evaluate_tool(WRITE_TOOL, "plan").verdict == Verdict.DENY


# ──── 用例 2：只读工具真实调用 ────

def test_acceptance_read_file(fs_env):
    from app.core.tool_runtime.executor import execute_tool

    hello = fs_env["hello"]
    record = _run(execute_tool(
        tool_call={
            "function": {"name": READ_TOOL, "arguments": json.dumps({"path": str(hello)})},
            "id": "acc-read-1",
        },
        project_path=None, read_only=False, ctx={"chat_id": 9501},
    ))
    assert record["success"] is True, record["result"]
    assert "MCP-ACCEPTANCE-内容" in record["result"]


# ──── 用例 3：写入工具触发现有审批流程 ────

def test_acceptance_write_file_approval_chain(fs_env):
    from app.core.tool_runtime.executor import execute_tool, complete_approval
    from app.core.tool_runtime.approval import approval_registry
    from app.models.agent import ApprovalRequest

    target = Path(fs_env["tmp"]) / "written-by-mcp.txt"
    marker = f"写入于验收 {uuid.uuid4().hex[:8]}"

    # 3.1 发起写调用 → 挂起审批（不执行）
    record = _run(execute_tool(
        tool_call={
            "function": {"name": WRITE_TOOL, "arguments": json.dumps({"path": str(target), "content": marker})},
            "id": "acc-write-1",
        },
        project_path=None, read_only=False, ctx={"chat_id": 9501},
    ))
    assert record["status"] == "awaiting_approval"
    assert not target.exists(), "审批前不得实际写文件"
    approval_id = record["approval_id"]
    assert approval_registry.get(approval_id) is not None

    # 3.2 审批请求持久化（审批链有迹可循）
    db = _db()
    try:
        row = db.query(ApprovalRequest).filter(ApprovalRequest.approval_id == approval_id).first()
        assert row is not None and row.status == "pending" and row.tool_name == WRITE_TOOL
    finally:
        db.close()

    # 3.3 批准 → 闭环执行 → 磁盘真实落盘
    assert approval_registry.resolve(approval_id, "approve") is True
    final = _run(complete_approval(record))
    assert final["status"] == "success", final["result"]
    assert target.exists() and marker in target.read_text(encoding="utf-8")

    # 3.4 拒绝路径：不执行
    target2 = Path(fs_env["tmp"]) / "denied-by-mcp.txt"
    record2 = _run(execute_tool(
        tool_call={
            "function": {"name": WRITE_TOOL, "arguments": json.dumps({"path": str(target2), "content": "should-not-write"})},
            "id": "acc-write-2",
        },
        project_path=None, read_only=False, ctx={"chat_id": 9501},
    ))
    approval_registry.resolve(record2["approval_id"], "deny")
    final2 = _run(complete_approval(record2))
    assert final2["status"] == "denied"
    assert not target2.exists()


# ──── 用例 4：杀子进程 → 主程序不崩 → 自动重启 → 可继续调用 ────

def test_acceptance_kill_subprocess_auto_restart(fs_env):
    from app.core.tool_runtime.executor import execute_tool
    from app.core.tool_runtime.permission import PermissionFilter

    async def run():
        manager = fs_env["manager"]
        conn = manager.get_connection(SERVER_ID)
        assert conn is not None and conn.is_running
        pid = conn._proc.pid

        # 冻结清单在崩溃前后保持稳定（缓存前缀稳定性）
        chat = _chat()
        names_before = [n for n in PermissionFilter().resolve(chat) if n.startswith("mcp__")]

        # 外部强杀整个进程树（等价于用户在任务管理器杀 node）
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            os.kill(pid, 9)

        # 先等 EOF 被事件循环感知（is_running 翻 False）——必须在循环内 await 才能驱动 reader
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and conn.is_running:
            await asyncio.sleep(0.1)
        assert not conn.is_running, "子进程被杀后 is_running 应翻转（主程序不受影响）"

        # 崩溃窗口内调用：fail-soft 返回错误文本，不抛异常
        text, ok, _ = await manager.call_external(SERVER_ID, "read_file", {"path": str(fs_env["hello"])})
        assert ok is False and text.startswith("错误")

        # 等待自动重启（指数退避 1s 起步）+ 重新握手
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and not (conn.is_ready and conn.is_running):
            await asyncio.sleep(0.5)
        assert conn.is_ready and conn.is_running, "MCP 子进程被杀后未自动重启"

        # 重启后可继续调用（新 pid）
        assert conn._proc.pid != pid
        text, ok, _ = await manager.call_external(SERVER_ID, "read_file", {"path": str(fs_env["hello"])})
        assert ok is True and "MCP-ACCEPTANCE-内容" in text

        # 冻结清单不变
        names_after = [n for n in PermissionFilter().resolve(chat) if n.startswith("mcp__")]
        assert names_before == names_after

        # 端到端：重启后经 executor 链路再读一次
        record = await execute_tool(
            tool_call={
                "function": {"name": READ_TOOL, "arguments": json.dumps({"path": str(fs_env["hello"])})},
                "id": "acc-read-after-restart",
            },
            project_path=None, read_only=False, ctx={"chat_id": 9501},
        )
        assert record["success"] is True, record["result"]

    _run(run())


# ──── 用例 5：审计有迹可循 ────

def test_acceptance_audit_trail(fs_env):
    from app.models.agent import SandboxAuditLog

    db = _db()
    try:
        rows = db.query(SandboxAuditLog).filter(
            SandboxAuditLog.tool_name.in_([READ_TOOL, WRITE_TOOL])
        ).all()
        assert rows, "外部 MCP 调用必须写入 sandbox_audit_logs"
        by_tool = {r.tool_name: [] for r in rows}
        for r in rows:
            by_tool[r.tool_name].append(r)
        assert any(r.success for r in by_tool.get(READ_TOOL, [])), "只读调用应有成功审计"
        assert any(r.success for r in by_tool.get(WRITE_TOOL, [])), "审批后执行的写调用应有成功审计"
        sample = next(r for r in rows if r.success)
        assert sample.command.startswith(f"mcp://{SERVER_ID}/")
        assert sample.duration_ms >= 0 and sample.exit_code == 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
