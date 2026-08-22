# -*- coding: utf-8 -*-
"""E2E 自检链路验证：让 frontend_ui Agent 调用 L1/L2/L3 三层自检工具并汇报。

目标：验证 Agent 能自主使用新增的 probe_ui / capture_screenshot / analyze_screenshot
工具，并跑通 tsc -> probe -> screenshot -> 视觉评审 的完整验证闭环。
"""
import json
import requests
import sys

CHAT_ID = 311
OUT = r"e:\智慧项目\Mfkagent\_agent_cap_test\selfcheck_311_events.jsonl"

PROMPT = """【任务】对"安全中心"页面做一次交付前自检，验证它是否符合项目 UI 视觉规范，并输出自检报告。

背景：我们刚为前端工程师接入了三层自检能力（L1 编译检查 / L2 数值抓取 / L3 视觉判读）。现在请你真实地使用这套自检工具，对前端"安全中心"页面做一次完整自检，全过程自主执行，不要向我询问任何路径或细节。

执行要求（严格按顺序调用工具，不要跳过，不要只靠肉眼或想象）：

1. L1 可编译：用 execute_command 在 frontend 目录执行 npx tsc --noEmit，确认前端无类型/语法错误（有错误就记录下数量与关键错误，不要卡死）。

2. L2 数值自检：用 probe_ui 打开本机前端"安全中心"页面（URL 形如 http://localhost:3000/settings/security 或你从代码里确认的真实路径），选择几个关键模块的选择器，抓取计算样式/尺寸，逐项核对：
   - 间距是否为 4px 增量（4/8/12/16/20...）
   - 是否复用设计 token（CSS 变量）而非硬编码魔法数值
   - 模块/卡片是否过大、行高是否过大、留白是否过多

3. L3 观感自检：用 capture_screenshot 对该页面截图，再用 analyze_screenshot 把截图交给视觉模型做观感级评审，拿到文字版视觉意见。

4. 汇总：把所有自检结果汇总成一份简洁的自检报告，说明：
   - 每个工具返回了什么（关键数据即可，不用贴全量 JSON）
   - 页面是否存在视觉问题（对照 4px 增量 / token 复用 / 模块大小 / 配色统一）
   - 若发现问题，给出具体的修复建议（能落到数值更好）

注意：你调用的 probe_ui / capture_screenshot / analyze_screenshot 是本机前端自检工具，URL 只允许 localhost，请在代码或项目结构里确认页面真实路径。"""


def main():
    url = f"http://127.0.0.1:8001/api/chat/{CHAT_ID}/send/stream"
    payload = {"content": PROMPT, "use_tools": True, "model": "glm-4.7"}
    print(f"[*] Sending self-check task to chat {CHAT_ID} ...", flush=True)
    try:
        resp = requests.post(url, json=payload, stream=True, timeout=1800)
    except Exception as e:
        print(f"[!] request error: {e}")
        sys.exit(1)
    print(f"[*] HTTP {resp.status_code}", flush=True)
    if resp.status_code != 200:
        print(resp.text[:2000])
        sys.exit(1)
    with open(OUT, "w", encoding="utf-8") as f:
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:
                continue
            if raw.startswith("data:"):
                data = raw[len("data:"):].strip()
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
            if etype in ("tool_call", "tool_result", "task_started", "task_completed",
                         "task_failed", "approval_required", "error"):
                # 精简打印：工具调用只打印工具名与参数摘要
                if etype == "tool_call":
                    fn = (evt.get("data") or evt.get("tool_call") or {}).get("name") or \
                         (evt.get("tool") or "")
                    args = (evt.get("data") or evt.get("tool_call") or {}).get("arguments") or {}
                    args_s = json.dumps(args, ensure_ascii=False)[:200]
                    print(f"[TOOL_CALL] {fn} {args_s}", flush=True)
                elif etype == "tool_result":
                    ok = evt.get("ok")
                    out = str(evt.get("result") or evt.get("output") or "")[:220].replace("\n", " ")
                    print(f"[TOOL_RESULT] ok={ok} {out}", flush=True)
                else:
                    print(f"[{etype}] {json.dumps(evt, ensure_ascii=False)[:300]}", flush=True)
    print(f"[*] Done. events saved to {OUT}", flush=True)


if __name__ == "__main__":
    main()
