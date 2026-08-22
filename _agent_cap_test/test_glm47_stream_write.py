# -*- coding: utf-8 -*-
"""流式验证：GLM-4.7 在 write_file 输出大 content 时是否被 max_tokens 截断。

复刻 Agent 失败场景（run 309）：模型要写出整个文件内容作为 write_file 的 content。
对比 max_tokens=4096（Agent 默认）与更大值，检查 arguments 是否为空/截断。
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "backend"))

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
        print(f"[{label}] tool={fn.get('name')} args_len={len(args_str)} args_head={repr(args_str[:120])}")
        try:
            args = json.loads(args_str) if args_str else {}
            print(f"[{label}] parsed keys={list(args.keys())}")
        except Exception as e:
            print(f"[{label}] PARSE ERROR: {type(e).__name__}: {str(e)[:200]}")
    return ordered


async def main():
    # 场景1：直接给完整文件内容，要求 write_file 完整修改后文件 —— max_tokens=4096（Agent 默认）
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
    for mt in (4096, 16384):
        print(f"\n===== max_tokens={mt} =====")
        try:
            await run_round([msg], mt, f"mt={mt}")
        except Exception as e:
            print(f"[mt={mt}] ERROR: {type(e).__name__}: {str(e)[:300]}")


if __name__ == "__main__":
    asyncio.run(main())
