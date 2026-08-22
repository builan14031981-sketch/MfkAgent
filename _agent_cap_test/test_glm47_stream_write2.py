# -*- coding: utf-8 -*-
"""流式验证（增强）：提高 max_tokens 后 write_file 大 content 能否完整输出。

monkeypatch app.core.proxy.build_llm_client 提高超时，绕过后端写死的 120s。
验证：max_tokens=16384/32768 时 write_file arguments 是否完整可解析。
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "backend"))

import app.core.proxy as proxy_mod  # noqa: E402


# monkeypatch：提高超时到 300s
def build_llm_client_300(api_base="", timeout=60.0, **kw):
    import httpx
    return httpx.AsyncClient(timeout=300.0, **kw)


proxy_mod.build_llm_client = build_llm_client_300

from app.core.tools import FILE_TOOLS_DEFINITIONS  # noqa: E402
from app.services.model import model_service  # noqa: E402

FILE_CONTENT = open(
    r"E:/智慧项目/Mfkagent/frontend/src/components/panels/security/SecurityView.tsx",
    encoding="utf-8",
).read()
print(f"FILE_CONTENT len={len(FILE_CONTENT)}")


async def run_round(messages, max_tokens, label):
    collected: dict = {}
    final_finish = "stop"
    usage = {}
    async for ev in model_service.stream_once(
        model_id="glm-4.7",
        messages=messages,
        temperature=0.7,
        max_tokens=max_tokens,
        tools=FILE_TOOLS_DEFINITIONS,
    ):
        et = ev.get("type")
        if et == "tool_calls":
            collected = {i: c for i, c in enumerate(ev.get("calls", []))}
        elif et == "finish":
            final_finish = ev.get("finish_reason")
            usage = ev.get("usage") or {}
    print(f"[{label}] finish={final_finish} completion={usage.get('completion_tokens')}")
    ordered = [collected[i] for i in sorted(collected)]
    for tc in ordered:
        fn = tc.get("function", {})
        args_str = fn.get("arguments", "") or ""
        print(f"[{label}] tool={fn.get('name')} args_len={len(args_str)} args_head={repr(args_str[:80])}")
        try:
            args = json.loads(args_str) if args_str else {}
            print(f"[{label}] parsed OK, keys={list(args.keys())}, content_len={len(args.get('content', ''))}")
        except Exception as e:
            print(f"[{label}] PARSE ERROR: {type(e).__name__}: {str(e)[:200]}")
    return ordered


async def main():
    msg = {
        "role": "user",
        "content": (
            "以下是目标文件 SecurityView.tsx 的完整内容：\n```\n"
            + FILE_CONTENT
            + "\n```\n"
            '请修改其中第 68 行的 marginBottom: 10 改为 8（4px 增量规范），'
            "然后调用 write_file 写入修改后的完整文件内容。relative_path=frontend/src/components/panels/security/SecurityView.tsx"
        ),
    }
    for mt in (16384,):
        print(f"\n===== max_tokens={mt} =====")
        try:
            await run_round([msg], mt, f"mt={mt}")
        except Exception as e:
            print(f"[mt={mt}] ERROR: {type(e).__name__}: {str(e)[:300]}")


if __name__ == "__main__":
    asyncio.run(main())
