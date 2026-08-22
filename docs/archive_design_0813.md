# 归档功能设计（2026-08-13）

## 需求
- 项目（Project）与会话（Chat，含通用对话）均可归档。
- 右键项目或会话 → 「归档」。
- 归档内容导出到**指定磁盘文件夹**（可配置，默认数据目录 `backend/Archive/`）。
- 设置中提供归档管理入口：可**恢复**（取消归档，回到主列表）或**彻底删除**（删归档文件 + 物理删记录）。
- 归档项目时**级联归档**其下所有会话（与现有软删除级联一致）。

## 已确认设计决策
1. 存储形态：**磁盘导出文件夹**（导出完整记录到可配置文件夹，主列表移除）。
2. 归档文件夹位置：**设置里可配置路径**，默认 `BACKEND_DIR/Archive/`。
3. 项目归档联动：**级联归档**其下会话。

## 核心架构：软标记 + 磁盘导出 双轨（推荐）
> 采用「数据库软标记」+「磁盘文件导出」组合，而非纯物理删除：
> - **数据库**：Project/Chat 新增 `is_archived` / `archived_at`，主列表查询过滤已归档项。
> - **磁盘**：归档时同步导出完整记录（Markdown + JSON）到归档文件夹，作为可读长期留档。
> - **恢复** = 清除 `is_archived` 标记（数据仍在库中，无损零成本）。
> - **彻底删除** = 删除磁盘归档文件 + 物理删除数据库记录（复用 trash forever 思路）。

选双轨而非「纯导出后物理删库」的原因：
- 恢复无损、无 id 外键丢失、无文件重导入的解析复杂度。
- 磁盘文件是可审计的副本，彻底删除才真正清空。
- 与现有 `is_deleted` 回收站模式完全同构，改动面小。

**边界**：归档/彻底删除均**只动数据库记录与归档文件夹**，绝不触碰项目关联的本地磁盘代码目录。

## 后端改动
### 1. 模型（`backend/app/models/agent.py`）
- `Project` 增加：`is_archived = Column(Boolean, default=False)`、`archived_at = Column(DateTime)`
- `Chat` 增加：同上两个字段

### 2. 轻量迁移（`backend/main.py` `_ensure_schema()`）
- `projects` 表补 `is_archived BOOLEAN DEFAULT 0`、`archived_at DATETIME`
- `chats` 表补同两列（沿用现有 ALTER TABLE 模式）

### 3. 默认设置（`backend/app/api/settings.py` `DEFAULT_SETTINGS`）
- 新增 `"archive_dir": ""`（空 = 默认 `BACKEND_DIR/Archive/`；用户设置后存绝对路径）

### 4. 归档 API（新建 `backend/app/api/archive.py`）
| 端点 | 作用 |
|------|------|
| `GET /api/archive` | 列出全部归档项（项目 + 会话，含归档时间/类型/名称） |
| `POST /api/archive/projects/{id}` | 归档项目：导出文件 + 级联归档其下会话（标记） |
| `POST /api/archive/chats/{id}` | 归档会话：导出文件 + 标记 |
| `POST /api/archive/{type}/{id}/restore` | 恢复（清除标记；若项目已归档则其下会话随之恢复） |
| `DELETE /api/archive/{type}/{id}` | 彻底删除：删归档文件 + 物理删数据库记录 |

归档文件格式（复用 `chat.py` `export_chat` 逻辑）：
- 会话：`{archive_dir}/chats/{title}_{id}.md` + `.json`（含全部消息、role、时间戳）
- 项目：`{archive_dir}/projects/{name}_{id}/` 目录，内含 `project.json`（项目元数据）+ 每个会话的 `.md`/`.json`

事务顺序（防不一致）：**先写文件成功 → 再标记/物理删库**；写文件失败则抛错，不动数据库。

### 5. 注册路由（`backend/main.py`）
- `app.include_router(archive.router, prefix="/api/archive", tags=["archive"])`

## 前端改动
### 1. Hooks
- `useProjects.ts` / `useChat.ts`：`Project`/`Chat` 类型加 `is_archived`/`archived_at`；新增 `archiveProject(id)` / `archiveChat(id)`（POST 归档端点），变更后 `refreshAndBroadcast`。
- 新建 `useArchive.ts`（仿 `useTrash.ts`）：`listArchive()` / `restoreProject|Chat(id)` / `purgeProject|Chat(id)`。

### 2. 右键菜单（`SidebarContextMenu.tsx` + `Sidebar.tsx`）
- 会话菜单：重命名 / 置顶 / **归档**（新，置于顶与删除之间，分隔线隔开）/ 删除。
- 项目菜单：打开文件夹 / 置顶 / **归档**（新）/ 删除。
- `SidebarContextMenuState` 不变；新增 props `onArchiveChat` / `onArchiveProject`，用 `Archive` 图标（lucide）。
- `Sidebar.tsx` 加 `handleArchiveChat` / `handleArchiveProject`（带确认，不打断流？→ 若该会话 `isSending` 则提示不可归档）。
- 列表过滤：`useProjects`/`useChat` 后端已过滤 `is_archived`，前端无需额外处理。

### 3. 设置面板归档管理（`SettingsPanel.tsx`）
- 新增独立 Tab **「归档」**（icon: `Archive`，lucide），navItems 加一项（6 → 7 Tab）。
- 内容组件 `ArchivePanel.tsx`（仿回收站/备份面板）：
  - 顶部：**归档文件夹路径**配置（输入框 + 「选择目录」Electron 按钮 + 「恢复默认」）+ 显示当前生效路径。
  - 列表：归档项目 / 归档会话，每项显示名称、类型、归档时间；操作「恢复」与「彻底删除」（彻底删除需二次确认）。
- 空态提示文案。

### 4. 多语言（`locales/zh-CN.json` / `en-US.json`）
- 新增键：`settings.archive.title`、`archive.restore`、`archive.purge`、`archive.purgeConfirm`、`archive.empty`、`sidebar.archive`、`chat.archiveConfirm`、`chat.cannotArchiveRunning` 等。

## 边界与防御
- 归档进行中的会话（`isSending`）→ 前端禁用并提示。
- 归档文件夹路径无效/无权限 → 后端返回明确错误，前端展示。
- 导出文件名冲突 → 追加时间戳/序号。
- 彻底删除二次确认（前端确认弹窗）。
- 恢复项目时其下会话若仍在归档态 → 一并恢复（与 trash restore 语义对齐）。

## 测试与验证
- 后端：`pytest` 现有套件回归；新增归档流程 API 冒烟（归档/恢复/彻底删除各类型）。
- 前端：`npx tsc --noEmit` + `npm run lint`（仅关注新增文件无新错误）。
- 手工：右键会话/项目 → 归档 → 侧边栏消失 → 设置→归档 Tab 可见 → 恢复回列表 → 彻底删除确认。

## 实施顺序
1. 后端模型 + `_ensure_schema` 迁移 + `archive_dir` 默认设置
2. 后端 `archive.py` API + main.py 注册
3. 前端 hooks（useProjects/useChat 归档方法 + useArchive）
4. 右键菜单归档项
5. 设置面板归档 Tab + ArchivePanel
6. 多语言键
7. 类型检查 + 后端回归 + 手工验证

## 回滚
- 改动集中在：`models/agent.py`、`main.py`、`settings.py`、新建 `api/archive.py`、`useProjects.ts`、`useChat.ts`、`useArchive.ts`（新）、`Sidebar.tsx`、`SidebarContextMenu.tsx`、`SettingsPanel.tsx`、`ArchivePanel.tsx`（新）、locales。
- 实施前备份改动文件；字段为纯增量（ALTER TABLE 只加列不删），回滚 = 还原文件即可，数据库新列为空值不阻塞旧代码。
