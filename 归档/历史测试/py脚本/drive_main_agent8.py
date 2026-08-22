"""第七轮：三阶段编排——调研子代理 → 计划子代理 → 前端子代理，按 DESIGN.md 硬约束重做炫技作品集。"""
import httpx

BASE = "http://127.0.0.1:8001/api/chat/318/send"

SPEC = """对 E:\\智慧项目\\portfolio-mfkagent\\index.html 执行一次「三阶段子代理编排」重做。核心基准：E:\\智慧项目\\portfolio-mfkagent\\DESIGN.md（新写的设计系统，先 read_file 完整读它）。这是炫技级 AI Agent 平台作品集，产品名 MfkAgent，禁止出现任何个人姓名。

必须按顺序完成以下编排，不得跳步：

【阶段一 · 调研（委派 sub_researcher）】
delegate_sub_agent(sub_agent_id=sub_researcher, max_tokens=8192, reasoning_effort=high)，
任务：read_file 读取 DESIGN.md；再 FetchUrlTool 抓取 https://mimo.xiaomi.com 研究其设计语言（巨型字墙/第一人称叙事/编辑留白）；输出一份「设计方向简报」（≤600字）：确认设计基调、指出必须避免的 AI 模板痕迹、给出本页 3 个 bold moment 建议。

【阶段二 · 计划（委派 sub_architecture）】
delegate_sub_agent(sub_agent_id=sub_architecture, max_tokens=8192, reasoning_effort=high)，
任务：read_file 读取 DESIGN.md 与阶段一简报，输出「分节构建计划」：逐节（Hero 字墙 / 第一人称引言 / 三大能力编号编辑列表 / 终端时刻 / 技术栈 / CTA页脚）给出：布局结构、字体层级、配色用法、需要实现的交互 demo。计划必须逐条满足 DESIGN.md 第 9 节硬禁令。

【阶段三 · 构建（委派 sub_frontend）】
delegate_sub_agent(sub_agent_id=sub_frontend, max_tokens=16384, max_tool_rounds=12, reasoning_effort=medium)，
任务：先 read_file 完整读取 DESIGN.md 和阶段二计划，再 write_file 全量重写 index.html（单文件自包含、无外部图片、移动端自适应）。必须实现 3 个真实交互 demo：五档人格滑块、三级记忆可视化 hover、一键拉取模型按钮。任何 opacity:0 渐显必须带 1.2s 强制显示兜底。写回后 read_file 验证含 </html>。

【总约束】
- 三大能力用「01/02/03 编号编辑列表 + 段落 + demo」，禁止三张等宽小图标卡片
- 字体：展示 Noto Serif SC 衬线 / 正文 Noto Sans SC / 数字与终端 JetBrains Mono；禁止 Inter/Poppins/Space Grotesk
- 配色：#12141C 暖深炭主色 / #EDE8E0 暖白 / 朱红 #C0392B 强调（10%）/ ✓#22C55E ✗#6B7280 功能色
- 文案禁 AI 套话（赋能/解锁/无缝/颠覆），要具体、第一人称、有密度
- 完成后回报：调研简报要点 + 构建计划要点 + 实际色值/字体/已实现交互清单"""

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
    print("sending 3-stage orchestration spec...")
    try:
        resp = httpx.post(BASE, json=payload, timeout=900)
        print("HTTP", resp.status_code)
        data = resp.json()
        ai = data.get("ai_message") or {}
        print("first reply:", (ai.get("content") or "")[:600])
    except httpx.HTTPError as e:
        print("client-side disconnect (run continues in background):", type(e).__name__)