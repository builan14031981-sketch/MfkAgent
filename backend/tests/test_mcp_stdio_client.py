"""T6 外部 MCP stdio 客户端单元测试 — StdioMCPConnection 协议层。

覆盖：
    - initialize 握手 + tools/list 枚举
    - tools/call 调用与 isError 处理
    - 请求超时（超时后连接仍可用，迟到响应被丢弃）
    - 子进程崩溃 → 自动重启（指数退避）→ 重启后可继续调用
    - 未连接时调用 fail-closed
    - MCP 工具 schema → OpenAI Function Calling 定义转换

直接运行兜底：python tests/test_mcp_stdio_client.py（conftest 不生效时）
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.mcp_client import (  # noqa: E402
    StdioMCPConnection,
    external_tool_name,
    merge_external_definitions,
)

FAKE_SERVER = str(Path(__file__).resolve().parent / "mcp_fake_server.py")

# 每个模块共用一个事件循环（连接/任务的 Future 与循环绑定，跨 run 会报错）
_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


def _make_conn(**kwargs) -> StdioMCPConnection:
    return StdioMCPConnection(
        server_id="fakesrv",
        command=sys.executable,
        args=[FAKE_SERVER, *kwargs.pop("extra_args", [])],
        **kwargs,
    )


def teardown_module(module):
    _LOOP.close()


# ──── 握手 + 枚举 + 调用 ────

def test_handshake_and_tools_list():
    async def run():
        conn = _make_conn()
        try:
            await conn.start()
            await conn.ensure_ready(timeout=15)
            assert conn.is_ready
            names = {t["name"] for t in conn.tools}
            assert names == {"fake_read", "fake_write", "fake_fail"}

            result = await conn.call_tool("fake_read", {"path": "a.txt"})
            assert result.get("isError") is False
            text = result["content"][0]["text"]
            assert '"path": "a.txt"' in text

            # 迟到响应/未知 id 不影响后续调用
            result2 = await conn.call_tool("fake_read", {"path": "b.txt"})
            assert "b.txt" in result2["content"][0]["text"]
        finally:
            await conn.stop()
    _run(run())


def test_call_tool_iserror_propagates():
    async def run():
        conn = _make_conn()
        try:
            await conn.start()
            await conn.ensure_ready(timeout=15)
            result = await conn.call_tool("fake_fail", {})
            assert result.get("isError") is True
        finally:
            await conn.stop()
    _run(run())


def test_request_timeout_connection_still_usable():
    async def run():
        conn = _make_conn(extra_args=["--delay-response", "3"])
        try:
            await conn.start()
            await conn.ensure_ready(timeout=15)
            try:
                await conn.call_tool("fake_read", {"path": "x"}, timeout=0.3)
                raised = False
            except asyncio.TimeoutError:
                raised = True
            assert raised, "慢响应应在超时后抛出 TimeoutError"

            # 迟到响应被丢弃（不污染 pending 表），后续正常请求可用
            result = await conn.call_tool("fake_read", {"path": "y"}, timeout=10)
            assert '"path": "y"' in result["content"][0]["text"]
        finally:
            await conn.stop()
    _run(run())


def test_crash_auto_restart_and_recover():
    """--crash-after 3：握手(1)+枚举(2)+调用(3) 后硬退出 → 自动重启 → 调用恢复。"""
    async def run():
        conn = _make_conn(extra_args=["--crash-after", "3"])
        try:
            await conn.start()
            await conn.ensure_ready(timeout=15)
            first = await conn.call_tool("fake_read", {"path": "pre-crash"}, timeout=10)
            assert "pre-crash" in first["content"][0]["text"]

            # 响应已返回后进程退出（backoff 1s 起步）
            # 先等 reader 感知 EOF（is_running 翻 False），再等自动重启完成
            for _ in range(40):
                if not conn.is_running:
                    break
                await asyncio.sleep(0.1)
            for _ in range(60):
                if conn.is_ready and conn.is_running:
                    break
                await asyncio.sleep(0.5)
            assert conn.is_ready and conn.is_running, "子进程崩溃后应自动重启并重新握手"

            result = await conn.call_tool("fake_read", {"path": "post-restart"}, timeout=10)
            assert "post-restart" in result["content"][0]["text"]
            # 重启成功后退避计数归零
            assert conn._restart_attempts == 0
        finally:
            await conn.stop()
    _run(run())


def test_call_fails_closed_when_not_connected():
    async def run():
        conn = _make_conn()
        # 未 start 就调用 → ConnectionError
        try:
            await conn.call_tool("fake_read", {})
            raised = False
        except ConnectionError:
            raised = True
        assert raised, "未连接时调用应 fail-closed 抛 ConnectionError"
    _run(run())


def test_stop_disables_auto_restart():
    async def run():
        conn = _make_conn()
        await conn.start()
        await conn.ensure_ready(timeout=15)
        await conn.stop()
        assert conn._stopping is True
        await asyncio.sleep(1.5)
        assert not conn.is_running or conn._stopping, "stop 后不应再自动重启"
    _run(run())


# ──── 命名与定义转换 ────

def test_tool_naming():
    assert external_tool_name("filesystem", "read_file") == "mcp__filesystem__read_file"


def test_merge_external_definitions_into_def_map():
    from app.services.tools import tool_registry
    from app.core.mcp_client import MCPExternalTool

    tool = MCPExternalTool(
        name="mcp__fakesrv__fake_read",
        description="假只读工具",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}},
        server_id="fakesrv",
        tool_name="fake_read",
    )
    tool_registry.register(tool)

    def_map = {}
    merge_external_definitions(def_map, ["mcp__fakesrv__fake_read", "read_file", "mcp__fakesrv__missing"])
    # 外部工具定义已合并为 OpenAI Function Calling 格式
    assert def_map["mcp__fakesrv__fake_read"]["type"] == "function"
    assert def_map["mcp__fakesrv__fake_read"]["function"]["name"] == "mcp__fakesrv__fake_read"
    assert def_map["mcp__fakesrv__fake_read"]["function"]["parameters"]["type"] == "object"
    # 内置工具已有定义不覆盖；不存在的工具不产生条目
    assert "read_file" not in def_map
    assert "mcp__fakesrv__missing" not in def_map


if __name__ == "__main__":
    sys.exit(__import__("pytest").main([__file__, "-v"]))
