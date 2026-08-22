# -*- coding: utf-8 -*-
"""最小化测试：GLM-4.7 是否能为 write_file 生成正确的 arguments。

直接调用 model_service.call_once 带 FILE_TOOLS_DEFINITIONS，
要求模型生成 write_file 调用，打印原始 tool_calls 的 arguments。
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.tools import FILE_TOOLS_DEFINITIONS  # noqa: E402
from app.services.model import model_service  # noqa: E402


async def main():
    messages = [
        {
            "role": "user",
            "content": (
                '请修改文件 frontend/src/components/panels/security/SecurityView.tsx 中的间距问题：'
                '将第 68 行的 marginBottom: 10 改为 8，第 312 行的 gap: 6 改为 8，'
                '第 318 行的 padding: "6px 10px" 改为 "4px 8px"。'
                "直接调用 write_file 写入修改后的完整文件内容。"
            ),
        }
    ]
    result = await model_service.call_once(
        model_id="glm-4.7",
        messages=messages,
        tools=FILE_TOOLS_DEFINITIONS,
        max_tokens=4096,
    )
    print("content:", (result.content or "")[:300])
    print("finish_reason:", result.finish_reason)
    tcs = result.tool_calls or []
    print("tool_calls count:", len(tcs))
    for tc in tcs:
        fn = tc.get("function", {})
        print("  name:", fn.get("name"))
        print("  arguments raw:", repr(fn.get("arguments"))[:500])
        try:
            args = json.loads(fn.get("arguments") or "{}")
            print("  arguments parsed keys:", list(args.keys()))
        except Exception as e:
            print("  arguments parse error:", e)


if __name__ == "__main__":
    asyncio.run(main())
