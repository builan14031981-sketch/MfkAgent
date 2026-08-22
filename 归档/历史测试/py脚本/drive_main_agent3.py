"""第二轮自检迭代：把视觉评审意见回喂主 Agent，让它委派修复 + 复检。"""
import httpx

BASE = "http://127.0.0.1:8001/api/chat/318/send"

TASK = """子代理已成功产出 Codex 智能体工作台深色落地页（E:\\智慧项目\\portfolio-mfkagent\\index.html）。
现在对页面做了视觉判读，评分：排版7/10、配色6.5/10、字体7.5/10、整体7/10。请按评审意见委派 sub_frontend 修一轮：

1. 【配色 6.5】强调色（蓝紫渐变）用得太多太饱和，多处重复导致视觉疲劳；部分文字在深色背景上对比度不足。
   -> 强调色收敛：只保留核心 CTA 按钮、主标题、关键图标用渐变强调；其他用单一静态高亮色或浅灰辅助色。
   -> 提高正文对比度（WCAG AA，至少 4.5:1）；不同模块可用不同色相区分（对比表用青色、场景用紫色）。
2. 【排版 7】模块间距不一致；生态卡片顶部轻微错位；场景三栏过于对称呆板。
   -> 模块间距统一用 32/48/64px 节奏；生态卡片顶部对齐或做微小错落；场景栏中间卡片略大或上移形成焦点。
3. 【字体 7.5】标题与正文缺字重/字号区分。
   -> 主标题用更粗字重（Black/700+）拉大与正文的对比；场景子标题加粗或换辅助色。
4. 保持深色底 + 高级感方向不变，不要退回浅色。

委派 delegate_sub_agent(sub_agent_id=sub_frontend, max_tokens=16384, max_tool_rounds=10,
reasoning_effort=medium)，要求写回 E:\\智慧项目\\portfolio-mfkagent\\index.html 后 read_file 验证。
完成后用 capture_screenshot + analyze_screenshot 复检一次，汇报新的评审得分与改动摘要。"""

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
    print("sending review-feedback iteration to main agent...")
    resp = httpx.post(BASE, json=payload, timeout=2400)
    print("HTTP", resp.status_code)
    data = resp.json()
    ai = data.get("ai_message") or {}
    content = ai.get("content") or ""
    print("first reply:", content[:800])