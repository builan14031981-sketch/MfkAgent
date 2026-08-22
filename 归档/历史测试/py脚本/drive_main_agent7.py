"""第六轮：全量重做 MfkAgent 智能体平台「炫技」展示页（深色高级 + 真实交互 demo + 无个人署名）。"""
import httpx

BASE = "http://127.0.0.1:8001/api/chat/318/send"

SPEC = """把 E:\\智慧项目\\portfolio-mfkagent\\index.html 全量重写为一个「炫技级」的 AI Agent 平台产品展示页（产品名：MfkAgent，AI Agent 智能体平台）。这是能力展示作品集，不是求职简历。委派 delegate_sub_agent(sub_agent_id=sub_frontend, max_tokens=16384, max_tool_rounds=12, reasoning_effort=medium) 执行，写回后 read_file 验证完整。

【禁止事项】页面中不得出现任何个人姓名/头像/求职信息（不得出现"严志辉"），主体是产品本身。

【一、真实产品内容（必须使用）】
产品定位：MfkAgent —— 面向非技术用户的 AI Agent 智能体平台，解决市面 Agent 产品体验痛点。
三大核心亮点（必须各做成一个可交互/可视化的炫技模块）：
1. 人格滑块 · Agent 人格交互：五档人格滑块，可视化控制系统提示词注入，把复杂 Prompt 配置变成简单滑块操作，降低非技术用户门槛。【做真实可拖拽的滑块组件，拖动时数字/描述/进度实时变化，当前档位高亮】
2. 三级记忆体系：全局记忆 / Agent 专属记忆 / 项目记忆 三级体系，多 Agent 协作时记忆共享与隔离兼顾。【做三层可视化结构图，hover 各层高亮并显示说明】
3. 模型接入优化：内置常用模型官方入口 +「一键拉取官方最新模型」，减少手动配置、降低接入门槛。【做模型徽章/列表 + 一键拉取按钮的点击动效与状态反馈】
技术栈：Python · FastAPI · Electron · AI Agent · H5/落地页

【二、炫技级视觉与交互硬约束】
1. 背景近黑 #0A0E16；卡片面 #101624；卡片边框 rgba(255,255,255,0.08)；毛玻璃导航（backdrop-filter）
2. 强调色全局唯一：电光青 #22D3EE。渐变只允许 2 处：HERO 主标题文字渐变（#22D3EE → #6366F1）与主 CTA 按钮（#22D3EE → #00C2A8）。禁止橙/红/粉/紫大面积色块；对比表仅用绿 #22C55E ✓ / 灰 #6B7280 ✗
3. 文字层级：#F5F5F7 主标题 / #A1A1AA 正文 / #6B7280 辅助
4. 炫技元素至少实现 4 个：HERO 动态背景（CSS 网格/光晕/粒子动画）、数字增长动画（滚动触发）、终端打字机风格代码窗格（展示平台核心能力，逐字符打字）、3D 卡片 tilt 悬停、滑块交互、滚动渐显。以上必须带 1.2 秒强制显示兜底，禁止任何初始 opacity:0 无兜底写法
5. 章节：Hero 大屏 → 三大核心亮点（交互 demo）→ 平台全景/架构 → 技术栈 → CTA → 页脚（© MfkAgent）
6. 单文件自包含、无外部图片（全部用 CSS/SVG/JS 实现）、移动端自适应（max-width 媒体查询）、中文界面

执行完用 read_file 验证文件完整（含 </html>），回报：实际色值清单 + 已实现的炫技交互列表。"""

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
    print("sending 炫技 showcase spec...")
    try:
        resp = httpx.post(BASE, json=payload, timeout=900)
        print("HTTP", resp.status_code)
        data = resp.json()
        ai = data.get("ai_message") or {}
        print("first reply:", (ai.get("content") or "")[:600])
    except httpx.HTTPError as e:
        print("client-side disconnect (run continues in background):", type(e).__name__)