# Skill 市场后端改动清单与回滚说明

改动时间：2026-08-12
目标：在 Mfkagent 后端落地「Skill 市场」能力（官方 15 个内置 Skill 的浏览 / 安装 / 卸载）。

## 一、改动清单

### 新增文件（删除即回滚）
| 文件 | 说明 |
|------|------|
| `backend/app/core/skill_catalog.py` | 15 个官方 Skill 的目录数据（元数据 + Prompt）+ 安装/卸载逻辑 |
| `backend/app/api/skills.py` | Skill 市场 REST API（builtin / installed / install / uninstall） |

### 修改文件（用本目录备份还原即回滚）
| 文件 | 改动 |
|------|------|
| `backend/main.py` | ① import 行追加 `skills, mcp`；② 注册 `/api/skills` 与 `/api/mcp` 路由 |
| `backend/build_backend.py` | PyInstaller 隐藏导入清单追加 `app.api.skills`、`app.core.skill_catalog` |

## 二、回滚方法

1. 删除新增文件：
   - `backend/app/core/skill_catalog.py`
   - `backend/app/api/skills.py`
2. 用本目录备份还原修改文件：
   - `main.py` ← 本目录 `main.py`
   - `build_backend.py` ← 本目录 `build_backend.py`
3. 重启后端即可回到改动前状态。

## 三、核心设计要点

- **概念映射（对齐项目现有 DB 架构）**：
  - V2 计划 `builtin.json` → `skill_catalog.SKILL_CATALOG`（内嵌目录）
  - V2 计划 `installed.json` → `skill_definitions.enabled`
  - V2 计划 `prompt.md` → 目录项的 `prompt` 字段（install 时写入 `system_prompt_fragment`）
- **市场语义**：目录为「可下载候选」，默认不预置进 DB；用户点下载才写入（enabled=True）。
- **卸载即禁用**：uninstall 仅置 enabled=False，记录保留，可随时重装（天然可回滚）。
- **API 端点**：
  - `GET  /api/skills/builtin` → 目录 + 安装状态
  - `GET  /api/skills/installed` → 已安装 id 列表
  - `POST /api/skills/install` → 安装（body `{skill_id}`）
  - `POST /api/skills/uninstall` → 卸载（body `{skill_id}`）
- **旧 seed 不冲突**：市场目录用连字符 id（如 `code-reviewer`），与旧 `seed_skills.py` 的下划线 name（`code_review`）不同名，互不覆盖。

## 四、待办（前端侧，本期后端未动）

- 前端 `ExtensionPanel` 现写死 5 个 Skill + localStorage，需改为对接 `GET /api/skills/builtin` / `install` / `uninstall`，由前端 AI 实施。
