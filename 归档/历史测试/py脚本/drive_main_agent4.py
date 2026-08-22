"""第三轮自检迭代：给严格配色规格，驱动主 Agent 转交 sub_frontend 精确执行。"""
import httpx

BASE = "http://127.0.0.1:8001/api/chat/318/send"

SPEC = """以下配色规格是【硬约束】，请原样、完整地转交给 sub_frontend，不允许修改或增删任何色值/规则：
1. 背景 #0A0A0F（近黑）；卡片面 #14141A；卡片边框 rgba(255,255,255,0.08)
2. 强调色【全局只有一种】#4F8CFF（电光蓝）。它只能用于：主 CTA 按钮、主标题关键词语、核心图标描边、链接 hover
3. 对比表：✓ 用 #22C55E 深底上微光、× 用 #6B7280 灰（只有这两个特殊色，不得再加红/橙/紫/黄）
4. 删除所有：紫色、橙色、红色、黄色渐变与色块；标题/按钮/卡片的蓝紫渐变一律去掉，标题保持纯白 #F5F5F7，
   渐变只允许保留在"主 CTA 按钮"这一处（#4F8CFF → #22D3EE）
5. 文字层级：主标题 #F5F5F7 700、正文 #A1A1AA 400、辅助 #6B7280；深色卡内正文至少 #C7C7D1
6. 场景卡片背景统一 #14141A（不再用彩色底），图标统一线性单色 #4F8CFF
7. 图标风格统一：全部单色线性图标，去掉任何渐变/多彩图标
8. 模块间距：区块间垂直间距至少 96px；卡片 gap 32px
9. 按钮只有两种：主按钮（#4F8CFF 渐变 + 白字）+ 次按钮（透明 + 1px rgba(255,255,255,0.15) 边框 + #F5F5F7 文字）

任务：委派 delegate_sub_agent(sub_agent_id=sub_frontend, max_tokens=16384, max_tool_rounds=10,
reasoning_effort=medium)，把上述 9 条规格逐条核对应用到 E:\\智慧项目\\portfolio-mfkagent\\index.html
（单文件自包含、内容结构不变），写回后 read_file 验证。执行完回报实际用了哪些色值（列出 --color 变量）。"""

if __name__ == "__main__":
    payload = {
        "content": SPEC,
        "model": None,
        "temperature": 0.5,
        "max_tokens": 16384,
        "use_tools": True,
        "reasoning_effort": "medium",
        "planning_level": 1,
    }
    print("sending precise color spec to main agent...")
    resp = httpx.post(BASE, json=payload, timeout=2400)
    print("HTTP", resp.status_code)
    data = resp.json()
    ai = data.get("ai_message") or {}
    print("first reply:", (ai.get("content") or "")[:500])