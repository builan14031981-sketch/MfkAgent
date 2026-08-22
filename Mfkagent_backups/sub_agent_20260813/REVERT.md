# 子代理（Sub-Agent）系统改动清单与回滚说明

改动时间：2026-08-13
目标：落地「子代理即工具」能力 —— 主 Agent 通过 `delegate_sub_agent` 工具将子任务委派给专门化子代理（代码审查员 / 网络调研员 / 文件分析师），子代理在隔离上下文中执行并返回摘要。

## 一、改动清单

### 新增文件（删除即回滚）
| 文件 | 说明 |
|------|------|
| `backend/app/api/sub_agents.py` | 子代理 CRUD REST API（`/api/sub-agents`：list/get/create/update/delete + available-tools 词表） |
| `backend/app/services/sub_agent.py` | SubAgentService：构建隔离 AgentContext → 调 AgentRuntime.run() → 返回结果摘要 |
| `backend/app/services/sub_agent_tool.py` | DelegateSubAgentTool（`delegate_sub_agent`）工具实现 |

### 修改文件（改动均带 `Phase SubAgent` 标记，按标记删除即可回滚）
| 文件 | 改动 |
|------|------|
| `backend/app/models/agent.py` | Agent 表新增 `is_sub_agent` / `allowed_tools` / `parent_agent_id` 三字段 |
| `backend/main.py` | ① `_ensure_schema` 加 3 条子代理字段迁移；② `_seed_sub_agents` 幂等补种；③ import 行追加 `sub_agents`；④ 注册 `/api/sub-agents` 路由 |
| `backend/seed_agents.py` | `PRESET_AGENTS` 新增 3 个内置子代理（sub_code_reviewer / sub_researcher / sub_file_analyst）；`seed_agents` 同步子代理字段 |
| `backend/app/services/tools.py` | 注册 `DelegateSubAgentTool` 到 `tool_registry` |
| `backend/app/core/tool_runtime/permission.py` | `BASE_TOOLS` 增加 `delegate_sub_agent` 一行 |

## 二、回滚方法（外科手术式，不影响其它开发者改动）

> 注意：上述 5 个修改文件与其它开发者共享，**禁止整文件 `git checkout` 还原**（会抹掉他人改动）。只删除带 `Phase SubAgent` 标记的代码块。

1. 删除 3 个新增文件：
   - `backend/app/api/sub_agents.py`
   - `backend/app/services/sub_agent.py`
   - `backend/app/services/sub_agent_tool.py`
2. `backend/main.py`：删除 `sub_agents` import、`_seed_sub_agents()` 调用与 `_seed_sub_agents` 函数体、`_ensure_schema` 中 3 条子代理字段 ALTER、`/api/sub-agents` 路由注册行。
3. `backend/seed_agents.py`：删除 3 个内置子代理字典条目，以及 `seed_agents` 函数中同步子代理字段的代码块。
4. `backend/app/models/agent.py`：删除 `# ──── 子代理标记（Phase SubAgent）────` 注释块下的 3 行字段。
5. `backend/app/services/tools.py`：删除 `DelegateSubAgentTool` 的 import 与注册两行。
6. `backend/app/core/tool_runtime/permission.py`：删除 `delegate_sub_agent` 一行及注释。
7. 重启后端即回到改动前状态。数据库已加的子代理列可保留（对其它逻辑无影响），如需彻底清理可手动 DROP，非必须。

## 三、核心设计要点

- **子代理即工具**：主 Agent 通过 function calling 调用 `delegate_sub_agent(sub_agent_id, task)`，与其它工具同一审批/执行链。
- **上下文隔离**：子代理的 messages 仅 `[system_prompt, task]`，不注入主会话历史；内部多轮工具调用发生在自己的 AgentRun 中，结束后只返回 content 摘要，主窗口 token 不被撑爆。
- **工具集收窄**：子代理仅能使用 `allowed_tools` 白名单中的工具（如代码审查员只读文件/git 工具）。
- **安全继承**：子代理继承主会话 `project_path` 与权限模式，高风险工具走同一审批链，不豁免。
- **权限可见性**：`delegate_sub_agent` 已加入 `PermissionFilter.BASE_TOOLS`，任何会话（含未绑定项目）均可委派。
- **API**：
  - `GET  /api/sub-agents` → 子代理列表（含 is_builtin 标记）
  - `GET  /api/sub-agents/available-tools` → 可用工具词表
  - `POST /api/sub-agents` → 创建（agent_id 唯一）
  - `PATCH /api/sub-agents/{agent_id}` → 更新
  - `DELETE /api/sub-agents/{agent_id}` → 删除（内置子代理禁止删除，仅可编辑）

## 四、待办（前端侧，本期后端未动）

- 前端 `api.ts` 新增子代理 API 函数/类型。
- 前端 `SubAgentPanel`（列表 + 编辑，复用 AgentListPanel UI 规范，保持紧凑不放大间隙）。
