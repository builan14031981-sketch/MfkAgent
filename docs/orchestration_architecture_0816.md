# 当前 Agent 平台架构报告 & Agent Orchestration 设计（2026-08-16）

## 一、当前架构（只读分析结论）

### 1.1 Agent 生命周期

| 环节 | 现状 |
|---|---|
| 创建方式 | `seed_agents.py` 预置 10 个主 Agent + 3 个内置子代理；`/api/sub-agents` 支持运行时创建/编辑/删除子代理（仅 `is_sub_agent=True` 记录） |
| 配置结构 | `agents` 表：`agent_id/name/identity/capabilities/status/expression_profile/is_sub_agent/allowed_tools/parent_agent_id` |
| 状态管理 | `AgentRun`（running/completed/failed/cancelled）+ `RuntimeState`（细粒度阶段流转）+ `RuntimeEvent`（事件流水，回放/审计） |
| 通信方式 | **单通道**：主 Agent 执行循环内通过工具（`delegate_sub_agent`）委派子任务，子代理返回**纯文本摘要** |
| 任务执行流程 | Chat API → `ChatContextBuilder`（组装 ①-⑩+ 层 system prompt）→ `PlannerService`（启发式/LLM Plan）→ `AgentRuntime.run/run_stream`（Execution Loop，最多 10 轮工具调用）→ 结果落库 |

### 1.2 多 Agent 能力现状

| 能力 | 支持情况 | 说明 |
|---|---|---|
| Agent 调用 Agent | ⚠️ 部分 | 仅 `delegate_sub_agent` 工具单次委派，返回摘要文本 |
| Agent 创建子 Agent | ✅ 支持 | 子代理 CRUD API + seed 内置 3 个（代码审查员/网络调研员/文件分析师） |
| Agent 传递上下文 | ⚠️ 受限 | 子代理只看到 [system, task]，无主会话历史（隔离是优点但也是限制） |
| Agent 共享任务状态 | ❌ 不支持 | 子代理间无共享状态，无任务级上下文累积 |
| Agent 汇总结果 | ⚠️ 部分 | 单子代理返回摘要；无多子代理并行 + 汇总机制 |

### 1.3 当前任务系统

- **任务入口**：`POST /api/chat/{id}/send`（非流式）与 `/send/stream`（流式，后台 Task + SSE 队列）。
- **谁理解任务**：`ChatContextBuilder` → `tool_runtime.process`（意图识别）+ `PlannerService`（启发式意图模板 / LLM 生成 Plan）。
- **谁拆解任务**：`PlannerService` → `Plan`（goal/steps/constraints）→ `TaskGraphBuilder` 转 `TaskGraph`（线性依赖 DAG，节点带 `task_type`/`assigned_agent`）。
- **谁决定调用哪个 Agent**：`AgentRuntime` 单 Agent 循环；TaskGraph 节点上的 `assigned_agent`（coding_agent/research_agent）目前只是**角色显示标签**，实际执行仍是同一个 LLM 循环（G5-A 曾设计多 Agent 路由，但未真正 spawn 独立子代理）。
- **谁负责最终输出**：主 Agent（AnGent 或会话选中的 Agent）。

### 1.4 现有基础设施亮点

1. **AgentRuntime 执行循环成熟**：多轮工具调用、审批闭环、抉择闭环、策略层、验证循环、完成验证、反思自愈、Token 水位、事件流水全都有。
2. **TaskGraph 状态机可用**：DAG 校验、依赖调度、失败级联 skip、反思动态注入修复节点。
3. **子代理隔离模型已建立**：`run_sub_agent()` 构建隔离 AgentContext（仅 system+task、窄工具集、继承 project_path、审批不豁免），`DelegateSubAgentTool` 已注册进主 Agent 工具目录，`permission.py` 已开放 `delegate_sub_agent`。
4. **前端事件类型已预留**：`RuntimeEventType` 已包含 `sub_agent` 扩展类型（`ExtensionEvent`）。
5. **模型服务统一**：`model_service.call_once/stream_once`，支持 11+ provider，LLM 调用稳定。

### 1.5 当前缺陷

| # | 缺陷 | 后果 |
|---|---|---|
| D1 | **单 Agent 思维占主导**：TaskGraph 的 `assigned_agent` 不真正 spawn 独立执行上下文，只是显示名 | 无法并行/专职化，长任务全在主上下文，易撑爆 token |
| D2 | **无 Orchestrator 层**：没有"谁做 Manager、谁拆解、谁调度、谁汇总"的中心决策 | 任务拆解依赖 Planner 模板，无法按角色动态编排 |
| D3 | **无共享任务状态**：子代理只回传一段摘要，无结构化结果、无中间产物记录 | 主 Agent 无法基于子代理中间结果二次调度，无法纠偏 |
| D4 | **无并行子代理**：`delegate_sub_agent` 一次一个、串行 | 多子任务耗时长；无法"架构→后端/前端并行" |
| D5 | **角色池僵化**：子代理只能来自 `agents` 表 `is_sub_agent=True` 的行，角色是写死的 3 个 | 无法按任务动态 spawn（如"商城系统"需要架构/后端/前端/测试/安全） |
| D6 | **汇总能力弱**：只有单次摘要文本，无"结果结构化汇总 + 关键决策提炼" | 主 Agent 难以高质量合并多子代理产出 |

### 1.6 距离 Codex 式 Agent 系统差距

| 维度 | Codex/Claude Code | 当前平台 | 差距 |
|---|---|---|---|
| 任务规划 | 计划+拆分+执行三态，动态调整 | Planner 只产软提示步骤 | 缺复杂度判断与动态规划闭环 |
| 子代理调度 | 按需 spawn 专才（reader/editor/reviewer） | 仅 3 个静态子代理 + 单次委派 | 缺动态 spawn 与角色池 |
| 并行执行 | 多子代理可并行 | 串行 | 缺并行 |
| 结果汇总 | 主代理综合多来源输出 | 单摘要 | 缺结构化汇总 |
| 任务状态共享 | 共享文件系统/检查点 | 无 | 缺 |

---

## 二、目标架构：Agent Orchestration

### 2.1 设计原则

1. **任何 Agent 都能成为 Manager**：不新增"特殊主代理"，能力注入为通用工具 + 服务层。
2. **最小侵入**：复用现有 AgentRuntime / TaskGraph / 审批 / 事件流水，不重构执行内核。
3. **可回滚**：新增模块独立，旧路径（无编排直接执行）行为完全不变。
4. **上下文隔离优先**：子代理仍拿隔离上下文，但通过结构化 `SubTaskResult` 回传，主 Agent 可累积。

### 2.2 分层架构

```
用户任务
  │
  ▼
ChatContextBuilder（现有）──────► ① Task Planner（增强）
  │                                  - 复杂度分级（简单/中等/复杂）
  │                                  - 需要子代理？需要哪些角色？
  ▼
AgentRuntime（现有主循环）
  │  Execution Loop
  ▼
② Orchestrator 工具（新）spawn_orchestration
  │
  ├─ Manager 决策：拆分为 SubTask[]（角色 + 任务描述 + 期望输出）
  ├─ 并行 spawn 子代理（复用 run_sub_agent + asyncio.gather）
  ├─ 收集结构化 SubTaskResult[]（role / status / summary / key_findings）
  └─ 汇总为 OrchestrationReport（决策要点 + 各角色结论 + 建议下一步）
  │
  ▼
主 Agent 拿到报告，继续主导（再调度 / 再 spawn / 输出最终答案）
```

### 2.3 新增模块

| 模块 | 文件 | 职责 |
|---|---|---|
| `core/orchestrator/models.py` | 新增 | `TaskComplexity` / `SubTaskSpec` / `SubTaskResult` / `OrchestrationReport` 数据结构 |
| `core/orchestrator/planner.py` | 新增 | LLM 任务分析：复杂度分级 + 角色推荐 + 子任务拆分（JSON 输出，失败降级单子任务） |
| `core/orchestrator/roles.py` | 新增 | 角色目录（architecture/backend/frontend/testing/security/researcher/code_reviewer 等），含身份模板与建议工具 |
| `core/orchestrator/runner.py` | 新增 | 编排执行：并行 spawn（asyncio.gather）+ 结果收集 + 汇总 |
| `services/orchestrator_tool.py` | 新增 | `spawn_orchestration` 工具（注册进 tool_registry + permission BASE_TOOLS） |
| `services/sub_agent.py` | 增强 | `run_sub_agent` 支持传入 `identity_override`（角色模板）以支持动态角色 |

### 2.4 数据流

- `spawn_orchestration(task, roles?)`：
  1. `OrchestrationPlanner.plan(task)` → `{complexity, need_orchestration, subtasks:[{role, task, output_format}]}`
  2. 若 `complexity == simple` → 返回 `orchestration_skipped`，主 Agent 直接执行。
  3. 否则对每个 subtask：查角色目录 → 用角色身份模板构造 `run_sub_agent(role_id 或 identity_override, task)`。
  4. `asyncio.gather` 并行执行（上限 4，防 token 爆炸）。
  5. 汇总 `OrchestrationReport`（含每角色结果摘要 + 关键发现 + 交叉结论），作为工具结果返回主 Agent。
  6. 整个编排过程 emit `sub_agent` 事件（role/status/summary），前端 `ExtensionEvent` 渲染。

---

## 三、实施计划

| # | 步骤 | 文件 | 验证 |
|---|---|---|---|
| 1 | 数据结构 + 角色目录 | `core/orchestrator/models.py`, `roles.py` | py_compile |
| 2 | LLM 任务分析器（复杂度+拆分） | `core/orchestrator/planner.py` | py_compile + 单测 mock |
| 3 | 编排执行器（并行 spawn + 汇总） | `core/orchestrator/runner.py` | py_compile |
| 4 | 增强 `run_sub_agent` 支持动态角色 | `services/sub_agent.py` | py_compile |
| 5 | `spawn_orchestration` 工具 + 注册 | `services/orchestrator_tool.py` + `tools.py` + `permission.py` | 工具出现在主 Agent 目录 |
| 6 | 前端 `sub_agent` 事件渲染 | `types/runtime.ts` + `MessageList.tsx` + `useChatStream.ts` | tsc |
| 7 | 测试 | `tests/test_orchestration_phase_f.py` | pytest（Python<3.14） |
| 8 | 回归 + 文档 | 交接文档 | 全绿 |

### 回滚方案

- 全部改动集中在新增 `core/orchestrator/` + `services/orchestrator_tool.py` + 三处小增强（sub_agent.py 参数、tools.py 注册、permission.py 白名单）+ 前端三文件。
- 已备份：`_backup/orchestration_20260816_173510/`（7 个改前文件）。
- 回滚 = 恢复备份 + 删除新增文件（新增模块不影响旧路径）。

### 风险

- 并行子代理 token 成本：限制最大并行数 4、单子代理 max_tokens 4096、仅复杂任务才 spawn。
- LLM 拆分 JSON 不稳定：失败降级为单子任务（角色=researcher 或直接不编排）。
- 动态角色身份覆盖：不写 agents 表，纯内存身份模板，避免污染 Agent 数据。