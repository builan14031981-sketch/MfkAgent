"""续跑：项目绑定 bug 已修复，让主 Agent 重新委派构建 + 截图自检 + 迭代。"""
import httpx

BASE = "http://127.0.0.1:8001/api/chat/318/send"

TASK = """继续上次的任务：项目绑定 bug 已修复（之前子代理报"文件操作需要绑定项目"，现已解决）。
现在请把 E:\\智慧项目\\portfolio-mfkagent\\index.html 真正重写为基于那份 Codex 报告的高级感产品落地页，并自检迭代：

1. 【委派】用 delegate_sub_agent 把报告全文 + 你的设计方案委派给 sub_frontend，重写
   E:\\智慧项目\\portfolio-mfkagent\\index.html（单文件自包含、内联 CSS）。委派时传
   max_tokens=16384、max_tool_rounds=10、reasoning_effort=medium，并明确要求：
   写回后用 read_file 读回验证，不得只口述改动。
   - 配色要有辨识度：深色底（近黑/深空灰）+ 高亮强调色（青绿/紫/橙渐变或霓虹）这类
     "开发者工具高级感"，不要普通蓝灰白。
   - 组织成 Codex 智能体工作台产品落地页：首屏价值主张 + 能力对比表 + 扩展生态 + 场景 + 行动号召。
2. 【自检】用 capture_screenshot 截图本地 http://127.0.0.1:8000/index.html，再用
   analyze_screenshot 做视觉判读；如果评分低或有明显问题，再委派 sub_frontend 修一轮。
3. 【汇报】给出最终视觉方向、评审得分、改动摘要。

本地静态服务已在 127.0.0.1:8000 运行（服务 portfolio 目录）。开始执行。"""

if __name__ == "__main__":
    payload = {
        "content": TASK,
        "model": None,
        "temperature": 0.7,
        "max_tokens": 16384,
        "use_tools": True,
        "reasoning_effort": "medium",
        "planning_level": 2,
    }
    print("sending continuation to main agent (chat 318)...")
    resp = httpx.post(BASE, json=payload, timeout=2400)
    print("HTTP", resp.status_code)
    data = resp.json()
    ai = data.get("ai_message") or {}
    print("ai msg id:", ai.get("id"))
    content = ai.get("content") or ""
    print("--- reply ---")
    print(content[:2500])
    print("--- reply length:", len(content))