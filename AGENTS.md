# AGENTS.md — MfkAgent 仓库指引

> 本文件面向进入本仓库工作的 AI 助手 / Agent，提供**构建测试命令、架构要点、非显性约束**。
> ⚠️ 本文件为**自动生成**，请勿手改：由 `scripts/generate_agents_md.py` 生成；内容变更请改脚本后重跑。

## 一、构建 / 测试 / 启动命令

### 后端（FastAPI + SQLAlchemy + SQLite，目录 `backend/`）

- **Python 环境**：固定使用 `backend/.venv`（Windows 解释器：`backend/.venv/Scripts/python.exe`）。
  安装依赖：`cd backend` → `.venv\Scripts\activate` → `pip install -r requirements.txt`。
  ⚠️ `chromadb==0.4.22` 在 Windows + Python 3.12 装不上，见「非显性约束」第 2 条，勿强装。
- **全量测试**（在 `backend/` 下执行）：
  ```
  python -m pytest tests/ -q
  ```
  或激活 venv 后直接 `pytest tests/ -q`。
  - 测试库由 `backend/tests/conftest.py` 自举（独立临时 SQLite + 最小种子），不触碰业务库 `backend/mfkagent.db`；依赖真实 API / 本地 8001 后端的用例已在 conftest 统一 skip。
  - `backend/tests/pytest.ini` 设 `asyncio_mode = auto`（未打标记的 async 测试自动纳入事件循环）。
- **启动后端**（在 `backend/` 下执行）：`python main.py`
  - 自动探测可用端口（8001~8005），端口写入 `backend/.mfkagent_port`；若端口已有健康后端则直接退出（单实例防多开）。
  - 环境变量：`MFK_PORT`（Electron 主进程指定端口）、`MFK_HOST=0.0.0.0`（安卓局域网访问）。
  - 根目录 `backend_guardian.ps1`：后端守护脚本（崩溃自动重启 + 日志 `backend/logs/watchdog.log`）。
- **一键启动**：根目录 `start-desktop.bat` / `start.bat` / `start-gateway.bat`（拉起后端 + Electron 前端）。

### 前端（Next.js 16 + React 19 + Electron，目录 `frontend/`）

- 安装依赖：`cd frontend` → `npm install`。
- 开发调试：`npm run dev`（Next dev server）。
- **构建**：`npm run build`（即 `next build`）。
- 类型检查：`npx tsc`（前端 UI Agent 的 L1 自检）。
- Electron 开发 / 打包：`npm run electron:dev` / `npm run electron:build`。

## 二、架构要点

### 后端分层（`backend/app/`）

| 层 | 目录 | 职责 |
|---|---|---|
| 路由层 | `api/` | REST 端点（`/api/...`，按资源拆分：agents / chat / memory / projects / skills / mcp / …） |
| 核心运行时 | `core/` | 业务核心：`agent_runtime/`（Agent 执行循环）、`tool_runtime/`、`orchestrator/`、`planner/`、`task_graph/`、`verification/`、`persona/` |
| 服务层 | `services/` | 业务服务（记忆、MCP、飞书、子代理、终端、编排工具等） |
| 模型层 | `models/` | SQLAlchemy ORM 模型 |
| 数据 | `data/` | 静态数据（如 `greetings.json`，由 `scripts/build_greetings.py` 生成） |
| 工具 | `utils/` | 通用工具函数 |

- **核心模块 `core/tool_runtime/`**：工具执行运行时——意图识别（intent）、权限 / 审批（permission / approval / preapproval）、风险判定（risk_engine）、策略（policy / strategy）、选择器（selector）、观察者（observer）、执行器（executor）、事件（events）。工具准入、审批链与沙箱管控都汇聚于此，是本项目最核心的子系统之一。
- **入口 `backend/main.py`**：建表（create_all）→ 轻量 schema 迁移（`_ensure_schema`）→ 各类 seed → 路由注册 → 中间件（移动端配对鉴权、CORS）→ uvicorn 启动。

### 前端结构（`frontend/src/`）

- `app/`：App Router 页面（`chat/[id]`、`projects/[id]`、`memories`、`pair` 等）。
- `components/`：UI 组件（hero 主题 `themes/`、面板 `panels/`、聊天组件、agent 图标等）。
- `hooks/`：数据请求 hooks（useChat / useProjects / useMemory / …）。
- `lib/`：工具库与状态（`api.ts`、`store.ts`、`theme.ts`、`artifactStore.ts` 等）。
- `locales/`：多语言（zh-CN / en-US）。
- `electron/`：Electron 主进程（托盘常驻、截图 overlay、Windows Toast 通知）。

### 其他目录

- `external_skills/`：外部 Skill 资产（提交文件数量最多的目录）。
- `scripts/`：根级工具脚本（`build_greetings.py` 生成欢迎语、`generate_agents_md.py` 生成本文件）。
- `docs/`：架构 / 设计文档（部分入库）。
- `安卓/`：安卓端相关资产。

## 三、非显性约束（务必遵守）

1. **venv 固定放 `backend/.venv`**：后端命令一律使用 `backend/.venv/Scripts/python.exe`（Windows）；不要在别处新建 / 移动 venv。`.venv/` 已 gitignore。
2. **chromadb 在 Windows + Python 3.12 装不上，勿强装**：`requirements.txt` 中的 `chromadb==0.4.22` 在当前环境装不上。请勿强装、降级或替换版本去"修"它——代码与测试均在无 chromadb 环境下正常运行（`backend/.venv` 亦无此包）。遇相关报错先确认是否为环境差异，不要为装它改动依赖。
3. **备份 / 调试残留一律不入库**：`.gitignore` 已忽略 `*.bak*`、`_backup/`、`_bak*/`、`backup_*/`、`_archive/`、`_trash/`、根目录 `_*.py` / `_*.png`、`backend/data/`、`chroma_db/`、`uploads/`、`*.log` 等。不要把备份、截图、日志或调试文件 add / commit。
4. **worktree 纪律**：
   - 项目以 git worktree 并行开发：每个工单从 `master` 建独立分支 + 独立 worktree（例：`E:/智慧项目/mfk-g-<任务名>`），**不在 master 上直接改**。
   - 只改动工单允许的文件范围；改动必须"测试随单"；不 push master。
   - 各 worktree 共享同一仓库对象库，`.venv` 按 worktree 各自独立；新 worktree 未建 `.venv` 时，可用主 worktree 的 venv 解释器跑测试（代码取自当前 worktree 目录）。
5. **测试库隔离**：后端测试跑在 conftest 自举的临时 SQLite 上，**不要**在测试中强依赖业务库或真实外部 API。
6. **生成物由脚本产出**：`backend/app/data/greetings.json` ← `scripts/build_greetings.py`；`AGENTS.md` ← `scripts/generate_agents_md.py`。手改生成物会被重跑覆盖，改动应落到脚本。
