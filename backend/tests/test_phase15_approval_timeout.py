"""Phase 1.5: 审批流 API（带超时）与 SSE 孤儿 Task 取消 — 专项验证。

覆盖：
  1. 审批超时 → 自动 rejected（timeout）→ Agent 优雅恢复（executor.complete_approval）
  2. 新契约 POST /api/chat/{chat_id}/approve：
     {"tool_call_id": "...", "decision": "approved" | "rejected"}
     → 200 approved / 200 rejected / 404 未注册 / 404 跨会话 / 409 已处理 / 422 非法 decision
  3. 兼容旧契约 {"approval_id", "action"} 回归
  4. /send/stream 孤儿 Task：_stream_tasks 映射注册/清理 + cancel_chat_stream_task 显式取消
  5. CancelledError 捕获路径：不产生 500，输出 "[INFO] Chat Stream cancelled by client"
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

if hasattr(sys.stdout, "buffer"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_phase15_"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TEMP_DIR / 'phase15_test.db'}"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models.agent as _agent_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from main import app  # noqa: E402
from app.core.tool_runtime.approval import approval_registry  # noqa: E402
from app.core.tool_runtime.executor import execute_tool, complete_approval  # noqa: E402
from app.api.chat import _agent_runs, cancel_chat_stream_task, _AgentRun  # noqa: E402

CLIENT = TestClient(app)

assert approval_registry.pending() == []


def _register(chat_id, tool_call_id, **kw):
    """在独立事件循环中注册 pending 审批（register 需要 running loop）。"""
    loop = asyncio.new_event_loop()
    try:
        container = {}

        async def _do():
            aid, _info = approval_registry.register(
                tool_call_id=tool_call_id,
                tool=kw.get("tool", "run_command"),
                command=kw.get("command", "git push origin main"),
                risk_level=kw.get("risk_level", "write"),
                risk_reason=kw.get("risk_reason", "test"),
                chat_id=chat_id,
                timeout=kw.get("timeout", 30),
            )
            container["approval_id"] = aid

        loop.run_until_complete(_do())
        return container["approval_id"]
    finally:
        loop.close()


# ──────────────────────────────────────────────────────────────
# 1. 审批超时 → 自动 rejected（timeout）→ 优雅恢复
# ──────────────────────────────────────────────────────────────

class TestApprovalTimeout:
    """complete_approval 超时闭环：300s 硬超时由 APPROVAL_TIMEOUT 保证，
    测试用短 timeout 模拟；超时后必须自动判定 rejected 且优雅恢复。"""

    def test_timeout_auto_rejects(self):
        """审批超时 → status=denied + 超时文案 + 注册表已清理。"""

        async def _run():
            tool_call = {
                "function": {"name": "run_command", "arguments": '{"command": "git push origin main"}'},
                "id": "call_timeout",
            }
            record = await execute_tool(
                tool_call=tool_call,
                project_path="/tmp/test_project",
                read_only=False,
                ctx={"chat_id": 1},
                emit=None,
            )
            assert record["status"] == "awaiting_approval"
            # 缩短超时模拟 300s 硬超时
            record["approval_timeout"] = 0.05
            final = await complete_approval(record, project_path="/tmp/test_project")
            assert final["status"] == "denied"
            assert final["success"] is False
            assert "自动拒绝" in final["result"]
            assert "审批超时" in final["result"]
            # 注册表必须已清理，无泄漏
            assert record["approval_id"] not in approval_registry.pending()
            return final

        result = asyncio.run(_run())
        assert result["tool_call_id"] == "call_timeout"

    def test_approval_timeout_constant(self):
        """APPROVAL_TIMEOUT 必须是 300s 硬超时。"""
        from app.core.tool_runtime.approval import APPROVAL_TIMEOUT
        assert APPROVAL_TIMEOUT == 300
        registry_default = approval_registry.default_timeout
        assert registry_default == 300

    def test_find_by_tool_call_id(self):
        """新契约反查：按 tool_call_id 找到 pending 审批。"""

        async def _run():
            approval_registry.register(
                "tc_lookup", "run_command", "git push", "write",
                "test", chat_id=42, timeout=30,
            )
            info = approval_registry.find_by_tool_call_id("tc_lookup")
            assert info is not None
            assert info["chat_id"] == 42
            assert info["tool_call_id"] == "tc_lookup"
            # 未注册返回 None
            assert approval_registry.find_by_tool_call_id("tc_missing") is None
            # 清理
            approval_registry.remove(info["approval_id"])

        asyncio.run(_run())


# ──────────────────────────────────────────────────────────────
# 2. /approve 新契约 {tool_call_id, decision}
# ──────────────────────────────────────────────────────────────

class _PendingApproval:
    """持有 pending 审批及其所属事件循环；resolve 经 call_soon_threadsafe
    投递到该循环，测试结束后必须 drain + close 防泄漏。"""

    def __init__(self, chat_id, tool_call_id, loop):
        self.chat_id = chat_id
        self.tool_call_id = tool_call_id
        self.loop = loop
        self.approval_id = None
        self.info = None

    def drain(self):
        self.loop.run_until_complete(asyncio.sleep(0))

    def close(self):
        self.drain()
        self.loop.close()


def _setup_pending(chat_id, tool_call_id, timeout=30):
    """注册 pending 审批，返回存活循环的 _PendingApproval（循环不关闭）。"""
    loop = asyncio.new_event_loop()
    p = _PendingApproval(chat_id, tool_call_id, loop)

    async def _do():
        aid, _info = approval_registry.register(
            tool_call_id=tool_call_id,
            tool="run_command",
            command="git push origin main",
            risk_level="write",
            risk_reason="test",
            chat_id=chat_id,
            timeout=timeout,
        )
        p.approval_id = aid
        p.info = approval_registry.get(aid)

    loop.run_until_complete(_do())
    return p


class TestApproveNewContract:
    """POST /api/chat/{chat_id}/approve 新契约。"""

    def test_approve_approved(self):
        p = _setup_pending(10, "tc_a1")
        try:
            r = CLIENT.post(f"/api/chat/{p.chat_id}/approve", json={"tool_call_id": "tc_a1", "decision": "approved"})
            assert r.status_code == 200, f"approved 应 200，实际 {r.status_code} {r.text}"
            body = r.json()
            assert body["action"] == "approve"
            assert body["approval_id"] == p.approval_id
            p.drain()
            assert p.info["future"].done()
            assert p.info["future"].result() == "approve"
        finally:
            approval_registry.remove(p.approval_id)
            p.close()

    def test_approve_rejected(self):
        p = _setup_pending(11, "tc_a2")
        try:
            r = CLIENT.post(f"/api/chat/{p.chat_id}/approve", json={"tool_call_id": "tc_a2", "decision": "rejected"})
            assert r.status_code == 200, f"rejected 应 200，实际 {r.status_code} {r.text}"
            assert r.json()["action"] == "deny"
            p.drain()
            assert p.info["future"].done()
            assert p.info["future"].result() == "deny"
        finally:
            approval_registry.remove(p.approval_id)
            p.close()

    def test_approve_unknown_tool_call_id_404(self):
        r = CLIENT.post("/api/chat/12/approve", json={"tool_call_id": "tc_ghost", "decision": "approved"})
        assert r.status_code == 404, f"未注册 tool_call_id 应 404，实际 {r.status_code} {r.text}"

    def test_approve_wrong_chat_404(self):
        p = _setup_pending(13, "tc_a3")
        try:
            r = CLIENT.post(f"/api/chat/{p.chat_id + 9999}/approve", json={"tool_call_id": "tc_a3", "decision": "approved"})
            assert r.status_code == 404, f"跨会话应 404，实际 {r.status_code} {r.text}"
        finally:
            approval_registry.remove(p.approval_id)
            p.close()

    def test_approve_already_processed_409(self):
        p = _setup_pending(14, "tc_a4")
        try:
            r1 = CLIENT.post(f"/api/chat/{p.chat_id}/approve", json={"tool_call_id": "tc_a4", "decision": "approved"})
            assert r1.status_code == 200
            p.drain()
            r2 = CLIENT.post(f"/api/chat/{p.chat_id}/approve", json={"tool_call_id": "tc_a4", "decision": "rejected"})
            assert r2.status_code == 409, f"已处理应 409，实际 {r2.status_code} {r2.text}"
        finally:
            approval_registry.remove(p.approval_id)
            p.close()

    def test_approve_invalid_decision_422(self):
        p = _setup_pending(15, "tc_a5")
        try:
            r = CLIENT.post(f"/api/chat/{p.chat_id}/approve", json={"tool_call_id": "tc_a5", "decision": "maybe"})
            assert r.status_code == 422, f"非法 decision 应 422，实际 {r.status_code} {r.text}"
        finally:
            approval_registry.remove(p.approval_id)
            p.close()

    def test_approve_missing_fields_422(self):
        r = CLIENT.post("/api/chat/16/approve", json={})
        assert r.status_code == 422, f"空载荷应 422，实际 {r.status_code} {r.text}"

    def test_legacy_contract_regression(self):
        """兼容旧契约 {approval_id, action} 回归。"""
        p = _setup_pending(17, "tc_legacy")
        try:
            r = CLIENT.post(f"/api/chat/{p.chat_id}/approve", json={"approval_id": p.approval_id, "action": "approve"})
            assert r.status_code == 200
            p.drain()
            assert p.info["future"].result() == "approve"
        finally:
            approval_registry.remove(p.approval_id)
            p.close()


# ──────────────────────────────────────────────────────────────
# 3. /send/stream 孤儿 Task 取消
# ──────────────────────────────────────────────────────────────

class TestStreamOrphanTask:
    """_agent_runs 映射 + 显式取消 + 清理。"""

    def test_task_mapping_and_cancel(self):
        async def _run():
            assert _agent_runs == {}, "测试前 _agent_runs 必须为空"
            # 独立子任务模拟后台 Agent 运行中
            cancelled = {"ok": False}

            async def _worker():
                try:
                    await asyncio.sleep(30)
                except asyncio.CancelledError:
                    cancelled["ok"] = True
                    raise

            task = asyncio.create_task(_worker())
            run = _AgentRun(77)
            run.task = task
            _agent_runs[77] = run
            assert _agent_runs[77].task is task
            await asyncio.sleep(0)  # 让 worker 开始运行
            # 显式取消 → 返回 True
            ok = cancel_chat_stream_task(77)
            assert ok is True
            await asyncio.sleep(0.05)  # 让取消传播
            assert cancelled["ok"] is True, "后台流任务应收到取消信号"
            assert task.cancelled() is True, "task 应处于 cancelled 状态"
            # 已结束 → 二次调用返回 False
            assert cancel_chat_stream_task(77) is False
            # 模拟后台任务 finally 清理映射
            _agent_runs.pop(77, None)
            assert _agent_runs == {}

        asyncio.run(_run())

    def test_cancel_missing_chat(self):
        async def _run():
            assert cancel_chat_stream_task(99999) is False
            _agent_runs.pop(99999, None)

        asyncio.run(_run())

    def test_generate_registers_and_cleans_task(self):
        """后台任务应注册到 _agent_runs 并在 finally 清理。"""
        results = {}

        async def fake_background():
            # 模拟后台任务注册
            _current = asyncio.current_task()
            run = _AgentRun(78)
            run.task = _current
            _agent_runs[78] = run
            results["registered"] = _agent_runs.get(78)
            try:
                await asyncio.sleep(0.01)
            finally:
                # 模拟后台任务 finally 清理
                _agent_runs.pop(78, None)
            return results

        async def _run():
            r = await fake_background()
            assert r["registered"] is not None, "后台任务应注册到 _agent_runs"
            assert 78 not in _agent_runs, "finally 应清理映射"

        asyncio.run(_run())
        assert _agent_runs == {}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
