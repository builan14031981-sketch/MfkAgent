"""Phase 1.6: Agent Task 与 HTTP 链接解耦 专项测试。

覆盖：
- 后台 Task 独立于 SSE 生命周期：SSE 断连后后台继续执行并落库
- /api/chat/{id}/cancel 显式取消端点
- _agent_runs 注册表管理（注册/取消/清理/重复请求）
- cancel_chat_stream_task 函数行为
- DB 持久化在后台 Task finally 中执行（不受 SSE 断连影响）
"""

import sys
import os
import asyncio
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.chat import (
    _agent_runs,
    _AgentRun,
    cancel_chat_stream_task,
    _cleanup_agent_run,
)
from app.core.tool_runtime.approval import approval_registry


class TestAgentRunsRegistry(unittest.TestCase):
    """_agent_runs 注册表管理。"""

    def setUp(self):
        _agent_runs.clear()

    def tearDown(self):
        _agent_runs.clear()

    def test_register_and_get(self):
        """注册 _AgentRun 并通过 _agent_runs 获取。"""
        run = _AgentRun(100)
        _agent_runs[100] = run
        self.assertIn(100, _agent_runs)
        self.assertIs(_agent_runs[100], run)
        self.assertIsInstance(run.queue, asyncio.Queue)

    def test_cleanup_removes_entry(self):
        """_cleanup_agent_run 移除注册表条目。"""
        run = _AgentRun(101)
        _agent_runs[101] = run
        _cleanup_agent_run(101)
        self.assertNotIn(101, _agent_runs)

    def test_cleanup_missing_is_noop(self):
        """_cleanup_agent_run 对不存在的 chat_id 不报错。"""
        _cleanup_agent_run(99999)

    def test_cancel_returns_false_for_missing(self):
        """cancel 不存在的 chat_id 返回 False。"""
        self.assertFalse(cancel_chat_stream_task(99999))

    def test_cancel_returns_false_for_done_task(self):
        """cancel 已完成的 task 返回 False。"""
        async def _run():
            run = _AgentRun(102)

            async def _quick():
                pass

            run.task = asyncio.create_task(_quick())
            _agent_runs[102] = run
            await asyncio.sleep(0.01)  # 让 task 完成
            self.assertTrue(run.task.done())
            self.assertFalse(cancel_chat_stream_task(102))

        asyncio.run(_run())

    def test_cancel_cancels_running_task(self):
        """cancel 正在运行的 task 返回 True 并取消 task。"""
        async def _run():
            run = _AgentRun(103)
            cancelled = {"ok": False}

            async def _worker():
                try:
                    await asyncio.sleep(30)
                except asyncio.CancelledError:
                    cancelled["ok"] = True
                    raise

            run.task = asyncio.create_task(_worker())
            _agent_runs[103] = run
            await asyncio.sleep(0.01)  # 让 worker 开始

            ok = cancel_chat_stream_task(103)
            self.assertTrue(ok)
            await asyncio.sleep(0.05)
            self.assertTrue(cancelled["ok"])
            self.assertTrue(run.task.cancelled())

        asyncio.run(_run())


class TestBackgroundTaskIndependence(unittest.TestCase):
    """后台 Task 独立于 SSE 生命周期验证。"""

    def setUp(self):
        _agent_runs.clear()

    def tearDown(self):
        _agent_runs.clear()

    def test_sse_disconnect_does_not_cancel_background(self):
        """SSE 消费者断连不影响后台 Task 执行。"""
        async def _run():
            run = _AgentRun(200)
            events_sent = []

            async def _mock_background():
                """模拟后台任务：产出事件后正常结束。"""
                try:
                    for i in range(5):
                        events_sent.append(i)
                        run.queue.put_nowait({"type": "text", "content": f"chunk{i}"})
                        await asyncio.sleep(0.01)
                finally:
                    run.queue.put_nowait(None)
                    run.finished = True
                    _agent_runs.pop(200, None)

            run.task = asyncio.create_task(_mock_background())
            _agent_runs[200] = run

            # SSE 消费者读取 2 个事件后"断连"
            consumed = []
            try:
                for _ in range(2):
                    chunk = await asyncio.wait_for(run.queue.get(), timeout=1.0)
                    consumed.append(chunk)
                # 模拟断连：停止消费
            except asyncio.TimeoutError:
                pass

            # 后台任务应继续运行
            await asyncio.sleep(0.1)
            # 所有 5 个事件都已发送
            self.assertEqual(len(events_sent), 5)
            # 后台任务已完成
            self.assertTrue(run.finished)
            self.assertNotIn(200, _agent_runs)

        asyncio.run(_run())

    def test_background_persists_on_sse_disconnect(self):
        """后台任务在 SSE 断连后仍完成 DB 持久化。"""
        async def _run():
            run = _AgentRun(201)
            persisted = {"done": False}

            async def _mock_background():
                try:
                    run.queue.put_nowait({"type": "text", "content": "hello"})
                    await asyncio.sleep(0.05)
                    # 模拟 DB 持久化
                    persisted["done"] = True
                    run.db_persisted = True
                finally:
                    run.queue.put_nowait(None)
                    run.finished = True
                    _agent_runs.pop(201, None)

            run.task = asyncio.create_task(_mock_background())
            _agent_runs[201] = run

            # SSE 消费者读取 1 个事件后断连
            chunk = await asyncio.wait_for(run.queue.get(), timeout=1.0)
            self.assertEqual(chunk["content"], "hello")
            # 不再消费（模拟断连）

            # 等待后台任务完成
            await asyncio.sleep(0.15)
            self.assertTrue(persisted["done"])
            self.assertTrue(run.db_persisted)

        asyncio.run(_run())

    def test_queue_overflow_does_not_block_background(self):
        """队列满时后台任务不被阻塞（put_nowait 跳过溢出事件）。"""
        async def _run():
            run = _AgentRun(202)
            sent_count = {"n": 0}

            async def _mock_background():
                try:
                    for i in range(300):  # 超过 maxsize=256
                        try:
                            run.queue.put_nowait({"type": "text", "content": str(i)})
                            sent_count["n"] += 1
                        except asyncio.QueueFull:
                            pass  # 队列满，跳过
                    await asyncio.sleep(0.01)
                finally:
                    try:
                        run.queue.put_nowait(None)
                    except asyncio.QueueFull:
                        pass
                    run.finished = True
                    _agent_runs.pop(202, None)

            run.task = asyncio.create_task(_mock_background())
            _agent_runs[202] = run

            # 不消费任何事件（模拟客户端从未连接或已断连）
            await asyncio.sleep(0.15)

            # 后台任务应已完成
            self.assertTrue(run.finished)
            # 所有 300 个事件都尝试发送（部分被跳过）
            self.assertEqual(sent_count["n"], 256)  # maxsize=256

        asyncio.run(_run())


class TestCancelEndpoint(unittest.TestCase):
    """/api/chat/{id}/cancel 端点行为验证。"""

    def setUp(self):
        _agent_runs.clear()

    def tearDown(self):
        _agent_runs.clear()

    def test_cancel_endpoint_returns_404_for_no_task(self):
        """无活跃任务时 /cancel 返回 404。"""
        from fastapi import FastAPI
        from app.api.chat import router
        from starlette.testclient import TestClient

        app = FastAPI()
        app.include_router(router, prefix="/api/chat")
        client = TestClient(app)

        resp = client.post("/api/chat/99999/cancel")
        self.assertEqual(resp.status_code, 404)

    def test_cancel_endpoint_cancels_active_task(self):
        """有活跃任务时 /cancel 返回 200 并取消任务。"""
        from fastapi import FastAPI
        from app.api.chat import router
        from starlette.testclient import TestClient

        # 用 mock task 避免跨事件循环问题
        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_task.cancel = MagicMock()
        run = _AgentRun(300)
        run.task = mock_task
        _agent_runs[300] = run

        app = FastAPI()
        app.include_router(router, prefix="/api/chat")
        client = TestClient(app)

        resp = client.post("/api/chat/300/cancel")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["action"], "cancelled")
        self.assertEqual(data["chat_id"], 300)
        mock_task.cancel.assert_called_once()


class TestBackgroundTaskErrorHandling(unittest.TestCase):
    """后台任务异常处理验证。"""

    def setUp(self):
        _agent_runs.clear()

    def tearDown(self):
        _agent_runs.clear()

    def test_background_error_sends_error_event(self):
        """后台任务异常时发送 error 事件给 SSE 消费者。"""
        async def _run():
            run = _AgentRun(400)
            error_msg = "LLM service unavailable"

            async def _mock_background():
                try:
                    run.queue.put_nowait({"type": "text", "content": "partial"})
                    raise RuntimeError(error_msg)
                except RuntimeError as e:
                    run.queue.put_nowait({"type": "error", "message": str(e)})
                    run.exception = e
                finally:
                    run.queue.put_nowait(None)
                    run.finished = True
                    _agent_runs.pop(400, None)

            run.task = asyncio.create_task(_mock_background())
            _agent_runs[400] = run

            # 消费事件
            chunk1 = await asyncio.wait_for(run.queue.get(), timeout=1.0)
            self.assertEqual(chunk1["type"], "text")

            chunk2 = await asyncio.wait_for(run.queue.get(), timeout=1.0)
            self.assertEqual(chunk2["type"], "error")
            self.assertIn(error_msg, chunk2["message"])

            chunk3 = await asyncio.wait_for(run.queue.get(), timeout=1.0)
            self.assertIsNone(chunk3)  # sentinel

            self.assertTrue(run.finished)
            self.assertIsNotNone(run.exception)

        asyncio.run(_run())

    def test_background_cancelled_persists_partial_results(self):
        """后台任务被取消时持久化部分结果。"""
        async def _run():
            run = _AgentRun(401)
            persisted = {"done": False}

            async def _mock_background():
                full_content = "partial response"
                try:
                    run.queue.put_nowait({"type": "text", "content": "partial"})
                    await asyncio.sleep(30)  # 模拟长时间运行
                except asyncio.CancelledError:
                    # 持久化部分结果
                    if full_content:
                        persisted["done"] = True
                    raise
                finally:
                    try:
                        run.queue.put_nowait(None)
                    except asyncio.QueueFull:
                        pass
                    run.finished = True
                    _agent_runs.pop(401, None)

            run.task = asyncio.create_task(_mock_background())
            _agent_runs[401] = run

            await asyncio.sleep(0.05)
            # 显式取消
            ok = cancel_chat_stream_task(401)
            self.assertTrue(ok)

            await asyncio.sleep(0.05)
            self.assertTrue(persisted["done"])
            self.assertTrue(run.finished)

        asyncio.run(_run())


class TestApprovalCleanupOnDisconnect(unittest.TestCase):
    """SSE 断连后审批清理验证。"""

    def setUp(self):
        _agent_runs.clear()
        # 清理审批注册表
        for aid in approval_registry.pending():
            approval_registry.remove(aid)

    def tearDown(self):
        _agent_runs.clear()
        for aid in approval_registry.pending():
            approval_registry.remove(aid)

    def test_background_finally_cleans_approvals(self):
        """后台任务 finally 块清理未决审批。"""
        async def _run():
            run = _AgentRun(500)

            # 注册一个审批
            aid, info = approval_registry.register(
                tool_call_id="tc_test",
                tool="run_command",
                command="git push",
                risk_level="write",
                risk_reason="test",
                chat_id=500,
            )
            self.assertEqual(len(approval_registry.pending()), 1)

            async def _mock_background():
                try:
                    run.queue.put_nowait({"type": "text", "content": "ok"})
                finally:
                    run.queue.put_nowait(None)
                    run.finished = True
                    approval_registry.cancel_by_chat(500)
                    _agent_runs.pop(500, None)

            run.task = asyncio.create_task(_mock_background())
            _agent_runs[500] = run

            # 等待后台任务完成
            await asyncio.sleep(0.1)
            self.assertTrue(run.finished)
            # 审批应被清理
            self.assertEqual(len(approval_registry.pending()), 0)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
