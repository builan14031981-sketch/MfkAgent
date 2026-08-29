"""测试用假 MCP server — 最小 stdio JSON-RPC 2.0 实现（不依赖任何第三方库）。

用法：
    python mcp_fake_server.py [--crash-after N] [--delay-response SECONDS] [--no-annotations]

行为：
    - initialize → 返回 serverInfo；notifications/initialized 忽略
    - tools/list → 返回 fake_read（readOnlyHint）/ fake_write（默认无标注=写入类）
    - tools/call → fake_read 回显参数；fake_write 返回 ok；fake_fail 返回 isError
    - --crash-after N：处理完第 N 个请求后硬退出（模拟子进程崩溃，验证自动重启）
    - --delay-response S：每个响应延迟 S 秒（验证请求超时）
"""
import json
import os
import sys
import time

def _send(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def main():
    crash_after = None
    delay = 0.0
    no_annotations = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--crash-after":
            crash_after = int(args[i + 1]); i += 2
        elif args[i] == "--delay-response":
            delay = float(args[i + 1]); i += 2
        elif args[i] == "--no-annotations":
            no_annotations = True; i += 1
        else:
            i += 1

    tools = [
        {
            "name": "fake_read",
            "description": "假只读工具：回显参数",
            "inputSchema": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "假路径"}},
                "required": ["path"],
            },
        },
        {
            "name": "fake_write",
            "description": "假写入工具：返回 ok",
            "inputSchema": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path"],
            },
        },
        {
            "name": "fake_fail",
            "description": "假失败工具：返回 isError",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]
    if not no_annotations:
        tools[0]["annotations"] = {"readOnlyHint": True}
        # fake_write 故意不带 annotations → 客户端须按写入类 fail-closed 处理

    handled = 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" not in msg or msg.get("id") is None:
            continue  # 通知（notifications/initialized 等）
        if delay > 0:
            time.sleep(delay)

        method = msg.get("method")
        rid = msg["id"]
        if method == "initialize":
            _send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake-mcp", "version": "0.0.1"},
            }})
        elif method == "tools/list":
            _send({"jsonrpc": "2.0", "id": rid, "result": {"tools": tools}})
        elif method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name")
            call_args = params.get("arguments") or {}
            if name == "fake_read":
                _send({"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": "fake-read:" + json.dumps(call_args, ensure_ascii=False, sort_keys=True)}],
                    "isError": False,
                }})
            elif name == "fake_write":
                _send({"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": "fake-write-ok"}],
                    "isError": False,
                }})
            elif name == "fake_fail":
                _send({"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": "fake-boom"}],
                    "isError": True,
                }})
            else:
                _send({"jsonrpc": "2.0", "id": rid, "result": {
                    "content": [{"type": "text", "text": f"unknown tool: {name}"}],
                    "isError": True,
                }})
        else:
            _send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {method}"}})

        handled += 1
        if crash_after is not None and handled >= crash_after:
            sys.stdout.flush()
            os._exit(70)

if __name__ == "__main__":
    main()
