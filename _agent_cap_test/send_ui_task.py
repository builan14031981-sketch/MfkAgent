# -*- coding: utf-8 -*-
"""发送前端 UI 改造任务到 chat 308，流式捕获 SSE 事件并保存。"""
import json
import requests
import time
import sys

CHAT_ID = 311
OUT = r"e:\智慧项目\Mfkagent\_agent_cap_test\ui_task_311_events.jsonl"

PROMPT = """【任务】优化本项目前端"安全中心"页面的视觉质量。

背景：该页面当前存在明显的视觉质量问题——模块过大、间距过大、部分间距数值不符合项目规范。请你真实地完成一次前端 UI 修复，全过程自主执行，不要向我询问任何路径或细节。

执行要求（严格按顺序，不要跳过）：

1. 自主定位：在前端代码库中定位"安全中心"页面对应的组件文件。你可以搜索 security、安全 等关键字，也可以浏览前端目录结构（如 src/components、src/app 等）。不要问我文件在哪，自己去代码库中查找。

2. 问题排查：打开文件逐行审查样式，找出所有视觉问题，至少覆盖：
   - 间距不符合 4px 增量规范（必须是 4/8/12/16/20...，出现 6/10/14 等即为问题）
   - 硬编码 px 数值，未复用项目设计 token（CSS 变量，如 --spacing-*、--text-*、--color-*）
   - 模块/卡片过大、留白过多、行高过大导致页面臃肿
   - 配色与项目视觉语言不一致

3. 修改前备份：任何文件改动之前，先复制一份原文件作为备份，保证可以随时回滚。

4. 实施修复：复用设计 token、遵循 4px 增量规范，禁止硬编码魔法数值；保持最小改动，不引入任何无关修改；确保代码可编译。

5. 验证与汇报：修改完成后复查改动是否符合规范，然后向我汇报：定位到了哪个文件、发现了哪些问题、每个问题是怎么改的、备份文件在哪里、如何回滚。"""


def main():
    url = f"http://127.0.0.1:8001/api/chat/{CHAT_ID}/send/stream"
    payload = {
        "content": PROMPT,
        "use_tools": True,
        "model": "glm-4.7",
    }
    print(f"[*] Sending task to chat {CHAT_ID} ...", flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        with requests.post(url, json=payload, stream=True, timeout=1800) as resp:
            print(f"[*] HTTP {resp.status_code}", flush=True)
            if resp.status_code != 200:
                print(resp.text[:2000])
                sys.exit(1)
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                if raw.startswith("data:"):
                    data = raw[len("data:"):].strip()
                elif raw.startswith("event:"):
                    continue
                else:
                    data = raw
                if not data:
                    continue
                try:
                    evt = json.loads(data)
                except Exception:
                    continue
                f.write(json.dumps(evt, ensure_ascii=False) + "\n")
                f.flush()
                etype = evt.get("type", "")
                # 打印关键事件
                if etype in ("agent_state_update", "task_started", "task_completed",
                             "task_failed", "completion_verify_started",
                             "completion_verify_passed", "completion_verify_failed",
                             "approval_required", "tool_result"):
                    print(f"[{etype}] {json.dumps(evt, ensure_ascii=False)[:300]}", flush=True)
                elif etype in ("message", "token_usage", "runtime_event"):
                    pass
                elif etype == "error":
                    print(f"[ERROR] {data[:500]}", flush=True)
    print(f"[*] Done. events saved to {OUT}", flush=True)


if __name__ == "__main__":
    main()
