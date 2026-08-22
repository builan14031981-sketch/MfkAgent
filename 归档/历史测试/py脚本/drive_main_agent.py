"""把 Codex 报告作为设计依据，交由主 Agent 自主编排重设计作品集配色与页面。"""
import httpx

BASE = "http://127.0.0.1:8001/api/chat/318/send"

REPORT = """## 为什么选择 Codex 作为你的 Agent？

你手握 API，却选择 Codex，这就像拥有引擎却选择整车——Codex 不只是 API 的封装，而是一个完整的 Agent 工作平台。以下是 Codex 的独特价值：

### 一站式 Agent 工作台
- 统一界面：无需编写代码即可管理多个 AI 任务、文件、浏览器和系统操作
- 任务协调：支持多 Agent 并行工作，自动分配子任务，协调复杂工作流
- 上下文感知：直接访问本地文件、浏览器、系统应用，无需额外配置

### 超越 API 调用的能力
| 你直接调用 API | 你使用 Codex |
|----------------|--------------|
| 需要自己编写错误处理、重试逻辑 | 内置任务管理、状态跟踪、自动重试 |
| 需要手动管理对话上下文 | 自动维护会话历史、任务状态 |
| 需要自己实现文件操作、浏览器控制 | 集成文件系统、浏览器、系统控制 |
| 需要自己构建可视化、交互工具 | 内置可视化引擎，支持创建交互式工具 |

### 独特的扩展生态系统
- 技能系统：可安装现成技能（图像生成、浏览器控制、计算机操作等）
- 插件市场：支持创建和分享自定义插件
- 自动化引擎：支持定时任务、监控、提醒、后续操作
- 可视化工具：直接创建图表、模拟器、交互式探索工具

### 创意与生产力工具
graph: 你的想法 -> Codex Agent -> [代码生成|图像生成|数据分析|浏览器自动化|系统操作] -> [完整应用|视觉素材|洞察报告|网页测试|桌面自动化]

### 与市面上其他方案的区别
1. 比纯 API 调用更简单：无需编写胶水代码，专注创意本身
2. 比其他 Agent 框架更完整：集成开发环境、文件管理、浏览器、系统控制
3. 比传统 IDE 更智能：AI 原生设计，支持多模态输入输出
4. 比在线 AI 工具更强大：本地运行，隐私安全，可扩展性强

### 你的 API + Codex = 超级组合
- 你的 API：提供 AI 能力的核心引擎
- Codex：提供完整的工作平台、工具链、扩展生态
- 结果：你获得的不是简单的聊天机器人，而是一个完整的数字助手操作系统

### 适合你的场景
- 开发复杂应用：Codex 可以协调多个 Agent 并行编写、测试、部署
- 自动化工作流：从数据收集到报告生成的完整流水线
- 创意项目：图像生成、视频编辑、音乐创作的 AI 辅助
- 系统管理：自动化桌面操作、文件整理、系统维护

简单来说：Codex 让你从「API 使用者」升级为「AI 工作流设计师」。你不再需要关心基础设施，只需专注于你的创意和目标。"""

TASK = f"""当前作品集页面 E:\\智慧项目\\portfolio-mfkagent\\index.html 的配色被用户评价为"非常一般"（现在是最普通的蓝灰 + 白底）。

请基于下面这份产品报告，把它重设计成有辨识度、高级感的页面。这是对你自己（主 Agent 自主编排能力）的真实测试，请全程自主完成，不要询问用户：

【你的自主工作流程】
1. 【调研】先用 web_search 调研 2-3 个顶级产品的配色/设计语言（例如 Linear / Stripe / Raycast / Vercel / Arc 这类现代开发者工具的风格：深色或强对比、克制渐变、发光强调色、细边框、玻璃拟态等），挑一个最适合"AI Agent 工作台"产品气质的视觉方向。
2. 【编排】用 spawn_orchestration 编排 architecture + frontend 两个角色，产出重设计方案（配色 token、字体、布局、区块结构）。
3. 【委派】用 delegate_sub_agent 把完整报告 + 设计方案委派给 sub_frontend 重写 E:\\智慧项目\\portfolio-mfkagent\\index.html（保持单文件自包含）。委派时记得传 max_tokens=16384 和 reasoning_effort=medium 以支持大文件写入。
4. 【自检】用浏览器截图工具（capture_screenshot 或 probe_ui）对本地 http://127.0.0.1:8000 打开后的页面截图，再用 analyze_screenshot 做视觉判读；如果评分低或有问题，再委派 sub_frontend 修一轮。
5. 【汇报】给出最终视觉方向说明、评审得分与改动摘要。

【设计要求】
- 页面向用户展示"Codex 智能体工作台"这款 AI Agent 产品（把报告内容组织成产品落地页：首屏价值主张 + 能力对比表格 + 扩展生态 + 场景 + 行动号召）
- 配色要有辨识度：不要普通蓝灰，建议深色底（近黑/深空灰）+ 高亮强调色（如青绿/紫/橙渐变或霓虹）这类"开发者工具高级感"
- 字体：可用现代无衬线（Inter 等）+ 等宽字点缀代码感；标题可加字重/字号强对比
- 保留作品集的"我"的元素可弱化，重点是产品展示页
- 响应式、hover 微交互、纯 CSS 实现

请开始执行。"""

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
    print("sending task to main agent (chat 318)...")
    resp = httpx.post(BASE, json=payload, timeout=1800)
    print("HTTP", resp.status_code)
    data = resp.json()
    ai = data.get("ai_message") or {}
    print("ai msg id:", ai.get("id"))
    content = ai.get("content") or ""
    print("--- reply (first 3000 chars) ---")
    print(content[:3000])
    print("--- reply length:", len(content))