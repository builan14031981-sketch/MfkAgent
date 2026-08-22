"""第八轮：把真实任务派给 agent 平台自主编排（研究→计划→构建），我只当甲方提需求 + 验收。"""
import httpx

BASE = "http://127.0.0.1:8001/api/chat/318/send"

TASK = """【甲方需求】重做 E:\\智慧项目\\portfolio-mfkagent\\index.html，做成 MfkAgent（AI Agent 智能体平台）的炫技级作品集/产品展示页。这是对我方 agent 平台能力的检验，需要你（主 Agent）自主编排完成，禁止套模板。

【一、必须自主编排，不得跳步】
依次委派三个子代理并汇总各自产出：
1. sub_researcher（调研）：用 FetchUrlTool 研究 https://mimo.xiaomi.com 的设计语言；再研究获奖动效站的鼠标交互模式（可检索：Lusion 的 reactive cursor、Wix Mouse Parallax、Active Theory 粒子跟随、磁吸按钮、cursor trail）。产出设计方向简报：调色板/字体体系/布局/动效的具体决策。
2. sub_architecture（计划）：基于调研简报产出逐节构建计划（Hero/引言/三大能力/技术时刻/技术栈/CTA），每节明确布局结构、字体用法、配色用法、交互实现方式。
3. sub_frontend（构建）：按计划全量重写 index.html（write_file），写回后 read_file 验证含 </html>。

【二、质量基线（反 AI 味，逐条必须达标）】
禁止：Inter/Poppins/Space Grotesk 做标题；青→紫/蓝→紫渐变；霓虹发光卡片；玻璃拟态泛滥；三张等宽特性卡片+小图标+两行字；水平居中一切；整页同一节奏；AI 套话文案（赋能/解锁/无缝/颠覆等）；假 logo/假头像。
必须：字体成体系（展示字体+正文+等宽数字/代码，三类分工）；色彩克制（单一强调色，中性底）；布局非对称、有编辑感；文案具体、第一人称叙事。

【三、动效是网站重点（必须做鼠标交互动画）】
1. 自定义光标：跟随圆点+滞后环形拖尾，悬停可交互元素时变形/变朱红色
2. 鼠标视差层：Hero 字墙/装饰元素按鼠标位置分层位移（深度系数不同）
3. 磁吸按钮：CTA 在光标接近时轻微吸附（≤8px），离开回弹
4. 3D tilt：能力区块悬停时 rotateX/rotateY 轻微倾斜（≤6deg）
5. 性能铁律：鼠标跟随一律 requestAnimationFrame + lerp，只改 transform/opacity，禁止在 mousemove 里改 left/top/width/height 触发 reflow；prefers-reduced-motion 全关；触碰设备禁用鼠标特效

【四、人格滑块组件（关键，用户点名）】
必须正好 5 档：专业/友好/中性/创意/幽默。离散吸附（拖/点只在档位切换时更新），禁止每像素重渲染导致卡顿。指示条/数值/档位文案联动更新。

【五、内容】
产品名 MfkAgent，AI Agent 智能体平台。三大亮点：人格滑块、三级记忆（全局/Agent专属/项目）、模型一键接入。技术栈 Python · FastAPI · Electron · AI Agent。禁止出现任何个人姓名/求职信息。

【六、技术约束】
单文件自包含、无外部图片依赖（全部 CSS/SVG/JS 实现）、移动端自适应、中文界面；任何 opacity:0 渐显必须带 1.2s 强制显示兜底。

【七、完成后回报】调研简报要点 + 构建计划要点 + 实际使用的字体/色值/动效/交互清单。"""

if __name__ == "__main__":
    payload = {
        "content": TASK,
        "model": None,
        "temperature": 0.5,
        "max_tokens": 16384,
        "use_tools": True,
        "reasoning_effort": "medium",
        "planning_level": 1,
    }
    print("delegating task to agent platform...")
    try:
        resp = httpx.post(BASE, json=payload, timeout=900)
        print("HTTP", resp.status_code)
        data = resp.json()
        ai = data.get("ai_message") or {}
        print("first reply:", (ai.get("content") or "")[:500])
    except httpx.HTTPError as e:
        print("client-side disconnect (run continues in background):", type(e).__name__)