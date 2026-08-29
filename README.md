# 🚀 MfkAgent 智能 Agent 桌面工作站

<p align="center">
  <b>极速 · 本地沙箱 · 多Agent协作 · 豆包级截图 · 零配置开箱即用</b>
</p>

---

## 📌 项目简介 (Introduction)

**MfkAgent** 是一款面向普通用户极致易用、同时对专业开发者具备极高扩展上限的**全能型 AI 协作桌面工作站（Desktop Agent Workspace）**。

它摒弃了传统 Web 端问答对话框的浅层交互模式，采用 **Electron + Next.js 16 + FastAPI + SQLite** 架构，深度融合 **MCP 风格插件工具桥接**、**豆包级无感隐窗截图**、**关键词意图路由与闲聊短路**与 **L1-L3 闭环视觉自检**，旨在提供**零门槛开箱即用、强安全沙箱管控、高质感人机协同**的终极 Agent 体验。

---

## 💡 设计哲学：极致易用与专业深度兼备 (Design Philosophy)

MfkAgent 遵循 **“渐进式复杂性 (Progressive Disclosure)”** 的设计原则，在易用性与专业度之间取得了极致平衡：

* **🌱 对小白极度友好 (Zero-Threshold for Beginners - 7大易用设计)**
  - **可视化人格滑块调节 (Personality Level Slider)**：提供直观的 5 档人格控温滑动条（从“极度理性”到“热情陪伴”），小白无需书写复杂 Prompt 提示词即可一键改变 Agent 语气与态度。
  - **豆包级无感隐窗截图 (Doubao-style Screen Capture)**：一键快捷截屏，触发瞬间主窗口自动无缝隐去，捕获窗口后方的桌面/网页；截选完成后自动拉起视窗并将图片塞入对话框进行多模态视觉分析。
  - **UserChoice 结构化决策卡片**：遇到多方案分支时自动生成图形卡片（含推荐星级、单选/多选/自定义文本），鼠标点选或 Enter 快捷键即可指挥 Agent 下一步操作。
  - **一键项目脚手架引导 (Project Init Modal)**：新建项目时无需掌握命令行与配置，提供图形化模版引导、一键目录绑定与零门槛跳过指引。
  - **13 套内置视觉主题与欢迎语 (Built-in Themes)**：包含粘土风、Studio 石墨、Developer Terminal、warm-minimal 官方主题等 13 套个性化主题与欢迎语，轻松定制个性化工作台。
  - **拖拽上传与剪贴板随手粘贴 (Drag & Drop + Clipboard)**：支持任意文件、图片直接拖入聊天框，或通过 Ctrl+V 随手粘贴剪贴板图片与代码。
  - **AI 记忆可视化面板与误删回收站 (Memory Panel & Trash Bin)**：AI 自动记住个人偏好时弹窗提醒，提供纯文本可视化记忆管理；内置回收站机制，支持一键撤销恢复误删对话。

* **🛠️ 对专业用户与开发者深度接纳 (High Ceiling for Power Users & Developers)**
  - **MCP 风格插件工具桥接**：内置插件工具统一采用 MCP (Model Context Protocol) 风格协议封装（工具注册 / 清单发现 / 调用三组标准接口），覆盖 Playwright 浏览器自动化（页面导航、点击、输入、脚本执行）等能力；对接外部第三方 MCP Server 已支持 stdio 接入（工具以 `mcp__<server>__<tool>` 命名空间挂载，统一纳入现有 L0-L2 风险判定与审批链）。
  - **三态安全沙箱与 Plan/Build 隔离**：内置 Plan/Build 模式，L0 白名单 + L1 元字符防御 + L2 写入判定三层过滤，高危磁盘写操作走配额控制与人工审批。
  - **L1-L3 前端 UI 三级自检闭环**：为 Frontend Agent 打造 **L1 代码编译 (`npx tsc`) → L2 数值样式自检 (`probe_ui`) → L3 视觉大模型 (VL) 观感评审** 的自动化闭环，保证生成的界面符合生产级规范。
  - **轻量意图路由与闲聊短路 (Keyword Intent Routing)**：三层轻量关键词规则识别消息意图——闲聊问候短路直接流式回复、只读意图过滤收敛工具集、动作触发词自动装载项目上下文与工具链，另有 TaskRouter 关键词任务分类写入响应 metadata。

---

## 💼 简历亮点提炼 (Resume Highlights)

> 如果您正在寻找可用于**简历项目描述**的高含金量表达，本项目提供以下切入点：

- **“渐进式复杂性 (Progressive Disclosure)”产品设计**：针对普通非技术用户，设计人格滑块控温、豆包级无感隐窗截图与 `UserChoice` 结构化决策卡片，降维 Prompt 使用门槛；同时为专业开发者提供 MCP 风格插件工具桥接、Playwright 浏览器自动化与沙箱三态安全防护，兼顾极低入门门槛与工程级扩展上限。
- **人机协同 (HMI) 与极客体验创新**：设计可视化工具操作卡片、13 套可更换主题与结构化决策表单，将自由文本协商重构为图形卡片点选（标星推荐/单多选/快捷键），显著降低用户交互与决策成本。
- **自动化质量控制闭环**：为前端 UI Agent 构建 **L1 语法编译 + L2 CSS 变量 Token 校验 + L3 VL 视觉大模型评审** 三级自检机制，确保代码与 UI 成果物符合生产级规范。
- **视觉多模态与系统集成**：实现 Electron 原生 200ms 隐窗屏刷同步截图、多模态视觉模型联动与 Windows Toast 异步通知路由。

---

## 🌟 核心特色与硬核功能 (Key Features)

### 1. ⚡ 轻量意图路由与闲聊短路 (Keyword Intent Routing)
* **Casual Chat 短路 (闲聊关键词短路)**：对问候、日常闲聊与纯知识解惑场景，命中关键词规则后直接跳过工具与沙箱上下文装载，更早进入流式回复，显著节省 Token 并提升响应速度。
* **动作触发词识别 (Action Triggers)**：消息命中“修改代码”、“运行测试”、“构建”、“生图”等动作触发词时不走闲聊短路，自动装载项目上下文与工具链，进入任务执行模式。
* **只读意图过滤 (Read-Only Intent)**：命中“只分析不改”类只读声明时，工具目录自动收敛为只读工具集，并与 Plan 模式形成纵深二层防御。
* **TaskRouter 关键词任务分类（非流式路径）**：按闲聊/问答/检索/执行/分析/代码六类关键词归类任务类型，分类结果（task_type / intent / confidence）写入响应 metadata，供前端展示与统计。
* **Persona System V1 (人设与表达控温)**：内置 `ExpressionKnowledge` 表达知识库，精细调控 Emoji 密度、删除线玩笑、短句停顿与口语化程度，彻底消除机械化“AI 腔调”。

### 2. 📸 豆包级“无感”截图 & 视觉大模型联动 (Doubao-style Screen Capture)
* **Zero-Latency 预制遮罩**：启动即预加载 Overlay 截图窗口，点击瞬间极速响应。
* **200ms 隐窗无感捕获**：截图触发瞬间主窗口自动无缝隐藏（配合 200ms 屏刷延迟），精准抓取主窗口后方的桌面、网页或 IDE；选区完成后自动拉起主窗口，图片直接注入视觉模型上下文。
* **多模态 VL 模型联动**：支持对接 Gemini、通义千问 VL 等具备视觉能力的多模态模型，实现一键截图分析、视觉 Bug 识别与 UI 对齐审查。

### 3. 🧩 UserChoice 结构化决策交互 (User Choice Composer)
* 告别传统“请在回复中打数字 1 或 2”的笨拙对话。
* AI 调取决策时，前端自动渲染高保真 UI 交互组件：
  * 🌟 **推荐选项高亮标星**
  * 🔘 **结构化单选 / 多选项**
  * ✍️ **自由文本补充与自定义回答**
  * ⌨️ **键盘上下键（ArrowUp/Down）选择 + Enter 快捷提交 / 跳过**

### 4. 🛡️ 严格的三态安全沙箱与 Plan/Build 隔离 (Command Risk Engine)
* **L0 白名单 + L1 元字符防御 + L2 写入关键字判定**：统一计算 `ExecutionDecision`（allow / deny / ask）。
* **Plan / Build 权限模式隔离**：
  * **Plan 模式**：所有写文件、修改系统、危险命令一律硬阻断（Deny），确保规划阶段零安全风险。
  * **Build 模式**：提供 `allow / require_approval / high_risk` 动态分级审批。
* **防越界与磁盘配额**：写入严格限制在项目沙箱边界内（`safe_resolve` 路径校验防 Windows Junction 穿透），高危写操作内置磁盘配额校验（Quota Check）。

### 5. 🔌 MCP 风格插件桥接与内置插件生态 (MCP-style Plugin Bridge)
* **MCP 风格工具协议**：内置插件工具以 MCP (Model Context Protocol) 风格协议统一封装，提供 `register_plugin_tools_to_mcp` / `call_mcp_tool` / `get_mcp_tools` 三组标准接口，Agent 以统一的工具发现与调用方式使用全部插件；外部第三方 MCP Server 已支持 stdio 接入（工具以 `mcp__<server>__<tool>` 命名空间挂载，统一纳入现有风险判定与审批链）。
* **内置浏览器自动化插件 (Playwright/Browser Automation)**：内置 `browser_navigate`, `browser_click`, `browser_type`, `browser_screenshot`, `browser_evaluate` 等工具，Agent 可自主完成网页浏览、自动化测试与数据抓取。
* **DB 持久化插件管理**：插件状态由 `plugins` 数据表统一管控，支持一键热启/停用，配置永久保存。

### 6. 🤖 预设专家级 Agent 阵容 (Preset Specialist Agents)
| Agent 角色 | 名称 | 职责与特殊能力 |
| :--- | :--- | :--- |
| **General** | **安 (AnGent)** | 默认通用助手，口语化、接地气、干练吐槽但干实事。 |
| **Coder** | **开发者** | 遵循“复现先行 → 根因导向 → 最小修复 → 验证闭环”方法的专业工程师。 |
| **Frontend UI**| **前端工程师**| 独创 **L1 编译自检 (`npx tsc`) → L2 数值样式自检 (`probe_ui`) → L3 视觉观感自检 (VL 视觉大模型评审)** 三级闭环，严格守卫 4px 增量网格。 |
| **Auditor** | **G 审查官** | 负责架构把关，实施方向、实现细节、长期风险的**多轮严格审查机制**。 |

> 除上述四大核心 Agent 外，另预置产品策略师、理性导师、调研员等专家 Agent，美学创作、答辩 PPT 专家、杀戮尖塔 2 战术教练等特色 Agent，以及代码审查员、架构师、测试工程师、安全审计师等子 Agent 协作团队。

### 7. 🎁 零门槛免费 API 与热更新模型库 (Zero-Barrier Model Registry)
* **内置 FreeLLMAPI (免费聚合网关) 模板**，配合本地网关脚本启动，**无需买 Key，下载解压即可直接开启完整 AI 对话**；并预置通义千问 / Gemini 等模型接入模板。
* **自定义端点热加载**：支持用户随时添加第三方 OpenAI 兼容 API，支持“一键在线拉取远程模型定义”，即插即用无需重启。

### 8. ✨ 极客级桌面体验细节 (Thoughtful UX Polish)
* **Thinking Mode (思维链展示)**：支持思考模型（Reasoning Models）的思维链流式展示，配合 `thinking-orbs` 光轮动画与折叠面板。
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

项目内置 70+ 开箱即用的专业 Skill 扩展：
- 💻 **开发协作**：Code Reviewer (代码审查)、Git Assistant (Git助手)、API Doc Generator、SQL Builder、Unit Test Writer、README Generator、Code Simplifier (代码精简)。
- 📝 **文档办公**：PPT Builder (PPT 生成)、Meeting Minutes (会议纪要)、Doc Translator (文档翻译)、Tech Blog Writer (技术博客)、CSV 分析、JSON 工具、定时报告。
- 🎨 **设计/UI**：UI/UX Pro Max (风格数据库)、Taste (反模板化前端品味)、Impeccable (高质感设计系统)、shadcn/ui 组件库、Kami (印刷级文档排版)、Frontend UI Designer (前端 UI 设计)。
- 🖼️ **图像创作**：数十种风格化出图模板（赛博朋克霓虹、包豪斯海报、吉卜力夏日、新海诚光云、黑神话水墨等）与 ComfyUI 本地生图。
- 🛡️ **效率与安全**：Sensitive Scanner (敏感信息扫描)、Data Privacy Check (数据合规检查)、Content Creator (自媒体文案)、Douyin Video Script (抖音爆款脚本)。

---

## 📜 开源许可 (License)

本项目采用 MIT License 开源许可证。
