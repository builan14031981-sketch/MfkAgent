# 🚀 MfkAgent 智能 Agent 桌面工作站

<p align="center">
  <b>极速 · 本地沙箱 · 多Agent协作 · 豆包级截图 · 零配置开箱即用</b>
</p>

---

## 📌 项目简介 (Introduction)

**MfkAgent** 是一款面向普通用户极致易用、同时对专业开发者具备极高扩展上限的**全能型 AI 协作桌面工作站（Desktop Agent Workspace）**。

它摒弃了传统 Web 端问答对话框的浅层交互模式，采用 **Electron + Next.js 16 + FastAPI + SQLite** 架构，深度融合 **Anthropic MCP (Model Context Protocol)** 协议标准、**豆包级无感隐窗截图**、**双流短路路由引擎**与 **L1-L3 闭环视觉自检**，旨在提供**零门槛开箱即用、强安全沙箱管控、高质感人机协同**的终极 Agent 体验。

---

## 💡 设计哲学：极致易用与专业深度兼备 (Design Philosophy)

MfkAgent 遵循 **“渐进式复杂性 (Progressive Disclosure)”** 的设计原则，在易用性与专业度之间取得了极致平衡：

* **🌱 对小白极度友好 (Zero-Threshold for Beginners)**
  - **零 Key 门槛**：内置免费 API 聚合网关与免费模型通道，下载双击即可对话，无需繁琐配置。
  - **直觉化交互**：集成**豆包级一键隐窗截图**与 **UserChoice 结构化决策卡片**，无需学习 Prompt 提示词工程，点击卡片即可高效指挥 Agent。
  - **人味语气 (Persona V1)**：自然口语化沟通，告别机械死板的 AI 客服腔调。

* **🛠️ 对专业用户深度接纳 (High Ceiling for Power Users & Developers)**
  - **MCP 生态扩展**：原生支持 Anthropic MCP (Model Context Protocol) 协议，无缝接入浏览器自动化 (Playwright) 与第三方工具。
  - **三态安全沙箱**：内置 Plan/Build 权限隔离模式、命令行三态风险引擎与磁盘配额防护，满足工程级代码重构与运维部署需求。
  - **L1-L3 视觉质量闭环**：针对前端 UI 设计与代码提供从语法编译、样式网格到大模型视觉观感的三重自动化校验。

---

## 💼 简历亮点提炼 (Resume Highlights)

> 如果您正在寻找可用于**简历项目描述**的高含金量表达，本项目提供以下切入点：

- **渐进式复杂性产品设计 (Progressive Disclosure)**：针对非技术用户打造零配置开箱即用体验（免费网关+卡片点选交互+隐窗截图），降低 Prompt 使用门槛；同时为专业开发者提供 Anthropic MCP 协议扩展、Playwright 浏览器自动化与沙箱三态安全阻断，兼顾极低门槛与专业工程上限。
- **人机交互 (HMI) 创新**：设计 `UserChoice` 结构化决策交互组件，将自由文本协商降维为图形卡片点选（标星推荐/单多选/快捷键），显著提升用户决策效率。
- **自动化质量控制闭环**：为前端 Agent 构建 **L1 语法编译 + L2 CSS 变量 Token 校验 + L3 VL 视觉大模型评审** 三级自检机制，确保生成界面无缝融入项目原质感。

---

## 🌟 核心特色与硬核功能 (Key Features)

### 1. ⚡ 智能双流路由与闲聊短路 (Dual-Stream Fast-Path Router)
* **Casual Chat Fast-Path (闲聊毫秒短路)**：对问候、日常闲聊与纯知识解惑场景，智能绕过重型工具与沙箱挂载，实现**毫秒级流式首字吐出**，显著节省 Token 并提升响应速度。
* **Action Trigger Engine (动作驱动提升)**：精准捕捉“修改代码”、“运行测试”、“构建”、“生图”等动作语义，秒级提升为**任务执行模式**，装载项目上下文与工具链。
* **Persona System V1 (人设与表达控温)**：内置 `ExpressionKnowledge` 表达知识库，精细调控 Emoji 密度、删除线玩笑、短句停顿与口语化程度，彻底消除机械化“AI 腔调”。

### 2. 📸 豆包级“无感”截图 & 视觉大模型联动 (Doubao-style Screen Capture)
* **Zero-Latency 预制遮罩**：启动即预加载 Overlay 截图窗口，点击瞬间极速响应。
* **200ms 隐窗无感捕获**：截图触发瞬间主窗口自动无缝隐藏（配合 200ms 屏刷延迟），精准抓取主窗口后方的桌面、网页或 IDE；选区完成后自动拉起主窗口，图片直接注入视觉模型上下文。
* **多模态 VL 模型联动**：无缝对接 Qwen3-VL、Gemini Flash 视觉模型，实现一键截图分析、视觉 Bug 识别与 UI 对齐审查。

### 3. 🧩 UserChoice 结构化决策交互 (User Choice Composer)
* 告别传统“请在回复中打数字 1 或 2”的笨拙对话。
* AI 调取决策时，前端自动渲染高保真 UI 交互组件：
  * 🌟 **推荐选项高亮标星**
  * 🔘 **结构化单选 / 多选项**
  * ✍️ **自由文本补充与自定义回答**
  * ⌨️ **键盘上下键（ArrowUp/Down）选择 + Enter 快捷提交 / 跳过**

### 4. 🛡️ 严格的三态安全沙箱与 Plan/Build 隔离 (Command Risk Engine)
* **L0 白名单 + L1 元字符防御 + L2 写入关键字判定**：统一计算 `ExecutionDecision`。
* **Plan / Build 权限模式隔离**：
  * **Plan 模式**：所有写文件、修改系统、危险命令一律硬阻断（Deny），确保规划阶段零安全风险。
  * **Build 模式**：提供 `allow / require_approval / high_risk` 动态分级审批。
* **防越界与磁盘配额**：自动拦截 `cd ..` 路径逃逸，高危写操作内置磁盘配额校验（Quota Check）。

### 5. 🔌 MCP 协议桥接与内置插件生态 (Anthropic MCP Integration)
* **原生 MCP 标准支持**：完整实现 Anthropic MCP 协议标准，支持与外部 MCP Server 无缝挂载。
* **内置浏览器自动化插件 (Playwright/Browser Automation)**：内置 `browser_navigate`, `browser_click`, `browser_type`, `browser_screenshot`, `browser_evaluate` 等工具，Agent 可自主完成网页浏览、自动化测试与数据抓取。
* **DB 持久化插件管理**：插件状态由 `plugins` 数据表统一管控，支持一键热启/停用，配置永久保存。

### 6. 🤖 预设四大专家级 Agent 阵容 (Preset Specialist Agents)
| Agent 角色 | 名称 | 职责与特殊能力 |
| :--- | :--- | :--- |
| **General** | **安 (AnGent)** | 默认通用助手，口语化、接地气、干练吐槽但干实事。 |
| **Coder** | **开发者** | 遵循“复现先行 → 根因导向 → 最小修复 → 验证闭环”方法的专业工程师。 |
| **Frontend UI**| **前端工程师**| 独创 **L1 编译自检 (`npx tsc`) → L2 数值样式自检 (`probe_ui`) → L3 视觉观感自检 (VL 视觉大模型评审)** 三级闭环，严格守卫 4px 增量网格。 |
| **Auditor** | **G 审查官** | 负责架构把关，实施方向、实现细节、长期风险的**多轮严格审查机制**。 |

### 7. 🎁 零门槛免费 API 与热更新模型库 (Zero-Barrier Model Registry)
* **内置 FreeLLMAPI (免费聚合网关)** 模板与通义千问/Gemini 免费体验区，**无需买 Key，下载解压即可直接开启完整 AI 对话**。
* **自定义端点热加载**：支持用户随时添加第三方 OpenAI 兼容 API，支持“一键在线拉取远程模型定义”，即插即用无需重启。

### 8. ✨ 极客级桌面体验细节 (Thoughtful UX Polish)
* **Thinking Mode (思维链展示)**：深度支持 DeepSeek R1、Qwen3.8 Thinking 等思考模型，配合 `thinking-orbs` 光轮动画与折叠面板。
* **Windows Toast 原生通知**：后台耗时任务完成或需高危审批时，自动唤起 Toast + 提示音，点击可直接精准客户端路由跳转至目标 Chat。
* **托盘常驻与无残留退出**：防止重复多开；退出时递归树状终结 Python 后端进程，保证 0 端口死锁残留。
* **原生文件管理器打通**：支持在系统资源管理器中直接“定位选中文件”与“打开项目根目录”。

---

## 🛠️ 快速开始 (Quick Start)

### 环境要求
* **Node.js** >= 18.0
* **Python** >= 3.10
* **Windows 10 / 11** (推荐)

### 1. 克隆项目
```bash
git clone https://github.com/builan14031981-sketch/MfkAgent.git
cd MfkAgent
```

### 2. 自动化启动 (推荐)
直接双击根目录下的脚本：
```cmd
start-desktop.bat
```
脚本将自动拉起 Python FastAPI 后端与 Electron 前端视窗。

### 3. 手动开发模式 (Manual Development)
**后端启动 (Backend):**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

**前端与 Electron 启动 (Frontend & Electron):**
```bash
cd frontend
npm install
npm run electron:dev
```

---

## 🧩 扩展 Skill 技能目录 (Built-in Skills)

项目内置 15+ 开箱即用的专业 Skill 扩展：
- 💻 **开发协作**：Code Reviewer (代码审查)、Git Assistant (Git助手)、API Doc Generator、SQL Builder、Unit Test Writer、README Generator。
- 🎨 **视觉设计**：UI/UX Pro Max (设计系统与框架指引)、Canvas Design (精美排版与字体)、Frontend Visual QA、Theme Factory (主题工厂)。
- 📝 **文档办公**：PPTX Builder (原生专业 PPTX 构建)、Slides Creator、Meeting Minutes (会议纪要)、Doc Translator、Tech Blog Writer。
- 🎮 **专业推演**：Slay The Spire 2 (杀戮尖塔 2 算杀与卡牌推演引擎)。

---

## 📜 开源许可 (License)

本项目采用 [MIT License](LICENSE) 开源许可证。
