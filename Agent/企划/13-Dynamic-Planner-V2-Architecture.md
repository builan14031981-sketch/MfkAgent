# MfkAgent Dynamic Planner V2 Architecture Proposal

- 版本: V0.1（Draft / 待评审）
- 阶段: Phase G2-A（架构设计，只读 —— 无代码、无数据库改动、无实现）
- 日期: 2026-08-06
- 基线: v73.0（G1 Planner V1 已落地）+ E8 Runtime Final Audit（闭环实测）
- 输入文档:
  - `Agent/企划/04-Planning-Architecture.txt`（Planning & Reasoning Architecture V1.0）
  - `Agent/企划/01-Agent-Core-Architecture.txt`（Agent Core Architecture）
  - `Agent/企划/02-Agent-Runtime-Architecture.txt`（Agent Runtime Architecture）
  - `Agent/企划/11-Multi-Agent-Collaboration.txt`（Multi-Agent Collaboration V1.0）
  - `交接文档.md` v73.0（§2.5 Runtime Evolution E1-E8 / §2.6 Planner V1）

---

## 1. 背景与现状

### 1.1 Planner V1（G1，已落地）
`backend/app/core/planner/`：
- `models.py`：`Plan` / `PlanStep{action, suggested_tools}`，`Plan.to_task_context()` → V1 `{goal, constraints, current_step}`
- `service.py`：`PlannerService` 启发式（意图/模式 → Plan），不调 LLM，`TASK_INTENTS` 6 模板
- `runtime.py`：`RuntimeTaskContextAdapter` 把 task_context 渲染为 system prompt ⑧ 段

局限：
1. 静态计划：`current_step` 固定指向第一步，不随执行推进。
2. 无 `expected_output` / `success_criteria`：无法程序化判断"这步是否达成"。
3. 无 Replan：Verification 失败仅注入反馈让 LLM 自行"内隐修复"，计划对象本身不变。
4. 无计划版本/审计：Plan 不持久化，仅作为 prompt 文本生效。
5. 步骤无依赖关系、无能力声明，Multi-Agent 分派无立足点。

### 1.2 Runtime（E1-E8，基线）
- 唯一执行入口：`AgentRuntime.run / run_stream`（`agent.py`），`chat.py` 只做 ContextBuilder 组装。
- 状态机 `states.py`：`pending → building_context / routing / llm_call / tool_execution / verifying / completing → completed | failed | cancelled`。
- 事件注册表 `RUNTIME_EVENT_TYPES`：text/thinking/tool_start/tool_result/tool_approval/tool_calls/verify_result/verification_failed/state_change/finish/error。
- Verification（E4）：`verifier.verify_all`（write_file 重读磁盘 / run_command 退出码），失败 → `verification_failed` 事件 + 注入 user 反馈消息 → 下一轮重试。
- Context：`ChatContextBuilder.build()` 组装 ①-⑧ 层 prompt + `AgentContext.task_context`。

### 1.3 设计文档约束（V1 已确立，V2 必须继承）
- 04 doc：Goal→Task→Step 三层拆解；Planner 只负责"为什么做/做什么"，Executor 负责"怎么做"；Replanning 流程 `Plan→Execute→Unexpected→Analyze→Update→Continue`；Human Approval（风险分级）；V1 已确认暂缓"自主长期规划/复杂推理树/多Agent规划"。
- 11 doc：Multi-Agent 必须有 Coordinator；共享 Task State `{goal, completed_tasks, results, issues}`；结构化消息 `{task, goal, input, expected_output}`；默认单 Agent，只有必要时升级。

---

## 2. 目标与设计原则

**目标**：在**不破坏 E8 Runtime 基线**的前提下，把 Planner 从"启发式静态"升级为"可 LLM 驱动、动态推进、可重规划"的系统，并为未来 Multi-Agent 奠定共享任务状态地基。

**原则**：
1. **Planner/Executor 分离**（04 doc）：Planner 输出计划，Runtime 执行计划；Planner 永不直接调工具/审批/验证。
2. **Runtime 唯一入口不变**：Planner 只是 ContextBuilder 的产出方 + 运行时的事件消费方，不改 AgentRuntime 执行闸。
3. **渐进升级、兼容优先**：task_context 只增不改，E7/E8"非任务请求 task_context=None"断言继续成立。
4. **成本控制**（11 doc）：默认启发式快速路径；仅 Planning Level≥2 才触发 LLM 计划；LLM 失败 → 启发式兜底。
5. **可观测**：Plan 生成/推进/重规划全部进入 runtime_events，可回放、可审计。

---

## 3. 决策摘要

| # | 决策 | 结论 |
|---|------|------|
| D1 | LLM Planner 接入位置 | 保留在 ContextBuilder 阶段（PlannerService 接口化 + heuristic 兜底），**不**新增 Runtime 状态；`planning` 状态/事件留 P2 |
| D2 | LLM 触发条件 | 按 Planning Level（0/1 直接走原流程，≥2 才 LLM 计划） |
| D3 | Plan 数据结构 | V2 扩展（id/expected_output/status/dependencies/verification_hint），**只增不改** |
| D4 | task_context 演进 | V1.1 保留三基键 + 新增 plan 快照键；`current_step` 由 Runtime 动态推进回写 |
| D5 | Planner/Runtime 边界 | 单向契约：Planner→Plan→快照；Runtime 读快照、回写步骤状态；禁止反向 |
| D6 | Replanning | 分级：Level0-1 内隐修复（现状）；Level≥2 结构化 Replan（LLM 修订计划 + 预算防循环） |
| D7 | Multi-Agent | **部分依赖**本设计：Coordinator≈动态 Planner+分派；V2 地基先行，Multi-Agent 后置 |

---

## 4. LLM Planner 如何接入

### 4.1 接入位置（决策 D1）
保持 G1 位置：**在 `ChatContextBuilder.build()` 内、进入 AgentRuntime 之前**产出计划。
```
User Request
  ↓
ChatContextBuilder.build()
  ├─ tool_runtime.process  → decision(intent, ...)
  ├─ PlannerService.plan() ──► [LLM 或 heuristic] ──► Plan
  ├─ Plan.to_task_context() ──► AgentContext.task_context（快照）
  └─ RuntimeTaskContextAdapter.render ──► system prompt ⑧
  ↓
AgentRuntime.run / run_stream（唯一执行入口，未改动）
```

理由：
- **最小侵入**：不新增 `planning` Runtime 状态，E8 状态机/事件/回放断言零影响。
- **唯一执行入口保持**：Planner 调用的是 `model_service.call_once`（单次 LLM，无自循环），由 PlannerService 内部完成一次"只读推理"，不经过 AgentRuntime 工具循环。
- **确定性兜底**：LLM 不可用/超时/解析失败 → 回落到现有启发式模板（fail-safe）。

### 4.2 触发条件（决策 D2，对接 04 doc Planning Level）
- **Level 0（直接回答）**：general_chat / 无工具意图 → 不规划，`task_context=None`（现状）。
- **Level 1（简单任务）**：单工具可完成 → 走启发式模板（现状 V1），不调 LLM。
- **Level 2（多步骤任务）**：需多工具/跨域 → 调 LLM 生成结构化 Plan。
- **Level 3（复杂项目）**：多步骤 + 高不确定性 → LLM Plan + 全程可 Replan。

Level 判定：`decision.intent` + 工具数 + 消息复杂度（长度/关键词）启发式；**必须保守** —— 判高只是多花一次 LLM 调用，判低则不达预期，故默认偏保守（宁可不调）。

### 4.3 LLM 计划协议（建议，非实现）
- 输入 prompt：goal、constraints、mode(plan/build)、可用工具名列表、能力（capabilities）、项目上下文摘要。
- 输出：严格 JSON（`{"goal", "steps":[{"action","expected_output","status":"pending"}], "constraints", "success_criteria"}`），用 schema 校验；解析失败 → 启发式兜底 + 记 `planning_failed` 事件。
- 使用 `model_service.call_once`（不传 tools），与 Runtime 的 Execution Loop 完全隔离。

### 4.4 成本/延迟控制
- 仅 Level≥2 触发；Level 1 保持启发式零成本。
- LLM 计划结果可在同 run 内缓存（相同 goal+context 不再重复生成）。
- 首 token 延迟影响：计划在首轮 LLM 调用之前完成 → 属于"推理前置"，可接受；后续 G2-C 可考虑流式展示计划。

---

## 5. Plan 数据结构升级（决策 D3）

### 5.1 现状 → V2 映射（对齐 04/02 doc）
| 维度 | V1（现状） | V2（提议） | 依据 |
|------|-----------|-----------|------|
| Plan.goal | 首行文本 | goal + constraints + success_criteria | 04 doc Goal 结构 |
| PlanStep.action | 动作描述 | action + id + expected_output + status + dependencies + verification_hint | 04/02 doc Plan 结构 |
| suggested_tools | 文本参考 | 保留（仍不 gate 工具） | 不变量 |
| level | 无 | planning level（0-3） | 04 doc 分级 |
| plan_id / version | 无 | 有（可审计、可 Replan 新版本） | 可观测原则 |

### 5.2 提议的 V2 结构（概念级）
```jsonc
{
  "plan_id": "pln_...",
  "version": 1,
  "level": 2,
  "goal": "优化项目性能",
  "constraints": ["不能改数据库结构"],
  "success_criteria": "接口延迟降低≥30%",
  "steps": [
    {
      "id": "s1",
      "action": "分析热点代码",
      "expected_output": "热点函数列表",
      "status": "pending",          // pending|running|done|failed|skipped
      "dependencies": [],            // 依赖 step id（顺序/并行）
      "verification_hint": "run_command"  // 关联 E4 验证策略
    }
  ]
}
```

### 5.3 落地原则（G2-B/C 实现时）
- **只增不改**：V2 字段全部新增，V1 已有字段语义不变。
- **Plan 是"规划产物"（不可变版本），task_context 是"运行时快照"（可变）** —— 二者分离，是 Replan 与审计的基础。
- 持久化：优先以 `runtime_events` 承载（`planning` / `plan_updated` 事件，P2 注册表）；是否新建 `plans` 表留未决（见 §12），V1 阶段不新增表。

---

## 6. task_context 演进（决策 D4）

### 6.1 现状
`AgentContext.task_context` V1 = `{goal, constraints, current_step}`，静态注入 system prompt ⑧。

### 6.2 V1.1 演进（不破坏兼容）
```jsonc
{
  "goal": "...",                // 保留（E7 契约）
  "constraints": [...],         // 保留
  "current_step": "分析热点代码", // 语义不变，但值由 Runtime 动态回写推进
  // ── 新增（快照，来自 V2 Plan）──
  "plan_id": "pln_...",
  "step_index": 0,              // 当前步骤序号（推进依据）
  "steps_summary": "1/5 · 分析热点代码（进行中）…", // 注入 prompt 的紧凑摘要
  "status": "running"           // pending|running|completed|replanned
}
```

### 6.3 动态推进（G2-C）
- **推进点**：Runtime 在 `tool_execution` 完成后（`verifying` 前后）依据 `verification_hint` 的验证结果更新 `step_index` 并回写 `task_context` 快照。
- **回写机制**：Runtime 持有 `task_context` 引用，更新后通过 `RuntimeTaskContextAdapter` 重新渲染 ⑧ 段，或在下一次 `llm_call` 的 prompt 中体现（实现细节留 G2-C）。
- **与 Verification 联动**：`verify_result` status 为 passed → `step_index+1`；failed → 走 Replan（§8）。
- **边界**：task_context 是"当前进度快照"，不等于持久化 Plan；进度一致性以 `plan_updated` 事件为准（审计）。

---

## 7. Planner 与 AgentRuntime 边界（决策 D5）

### 7.1 单向契约
```
PlannerService（ContextBuilder 阶段）
  └─ 产出 Plan（不可变）→ Plan.to_task_context() → AgentContext.task_context（快照）
AgentRuntime（执行）
  ├─ 读取：task_context（注入 ⑧ 段，模型可见）
  ├─ 推进：tool_execution/verifying 后更新 step_index → 回写 task_context
  └─ 上报：verification_failed → 触发 PlannerService.replan()（仅请求，不内联执行工具）
```

### 7.2 明确禁止
- Planner 直接调 `execute_tool` / `complete_approval` / `verifier`（04 doc：Planner 只决定 what/why）。
- Runtime 自行"生成计划"（Runtime 只执行、只推进、只上报）。
- Planner 修改工具可见性 / 权限（仍由 E5 `READ_ONLY_TOOLS` + `TOOL_RISK_POLICY` 单一事实来源决定）。

### 7.3 可选状态/事件（P2，收口 E6 遗留）
- 状态机新增 `planning` 与 `replanning`：`building_context → planning → routing / llm_call`；`verifying → replanning → llm_call`。
- 事件注册新增：`planning` / `plan_updated` / `planning_failed` / `sub_agent`（Multi-Agent 预留）。
- **本提案建议**：G2-B 阶段仍不引入 `planning` 状态（保持 E8 状态机冻结）；状态与事件在 G2-E 一并注册。此决策可复核（§12 未决项）。

---

## 8. Verification 失败后的 Replanning 设计（决策 D6）

### 8.1 现状与局限
现状（E4）：`verifier.verify_all` 产出 `verify_result`；failed → `verification_failed` 事件 + 注入 user 反馈 → LLM 下一轮"内隐修复"。计划对象与 `current_step` 不变 —— 属于 **implicit repair（无结构化 Replan）**。

### 8.2 分级处置
| Level | Verification 失败处置 |
|-------|---------------------|
| 0-1 | **in-loop repair（现状）**：注入反馈，LLM 重试；不重规划 |
| 2+ | **structured Replan**：见 8.3 |

### 8.3 Structured Replan（G2-D 目标）
```
verifying → verify_result(failed)
  ↓ 收集失败证据（tool/arguments/evidence/feedback）
PlannerService.replan(plan, evidence, context)
  ├─ 预算检查：replan_count < MAX_REPLANS(默认2) 且总轮次未超 MAX_ROUNDS
  ├─ LLM 修订 → 新 Plan 版本（plan_id 不变、version+1）
  ├─ 生成 plan_updated 说明（改动摘要）
  └─ 回写 task_context（status=replanned, step_index 指向调整后步骤）
  ↓
注入【计划变更通知】user 消息 → 继续 llm_call 执行
```
- **不改变权限**：Replan 只改计划文本/步骤顺序，写入类步骤仍走 E5 风险闸 + 审批。
- **循环防护**：`MAX_REPLANS` 预算 + 现有 `MAX_ROUNDS`/`MAX_STREAM_ROUNDS` 联动；超限 → 转 `failed` 并在 finish 消息中向用户说明"计划多次调整仍失败"。
- **审计**：每次 Replan 记 `plan_updated` 事件（旧版本→新版本、reason、evidence 摘要），可回放。

---

## 9. Multi-Agent 是否依赖该设计（决策 D7）

### 9.1 结论：**部分依赖，且本设计是前置地基**
依据 11 doc：Multi-Agent 必须有 Coordinator，共享 Task State，结构化消息。对照：

| Multi-Agent 需求（11 doc） | 本设计的对应物 | 状态 |
|---------------------------|---------------|------|
| Coordinator Agent（理解/分配/收集/决策下一步） | Dynamic Planner（Level≥2 拆解 + Replan 决策） | 本设计是其"单 Agent 版"雏形；分派维度需扩展 |
| 共享 Task State `{goal, completed_tasks, results, issues}` | `Plan`（goal/steps/status）+ `task_context` 快照（current_step/status） | **可直接演进**：`steps[].status`≈completed_tasks，`expected_output`≈results 校验口径 |
| 结构化消息 `{task, goal, input, expected_output}` | `PlanStep{action, expected_output}` + 工具参数 | 需扩展 `task_id`/`agent_id` 归属字段（G2 不做） |
| Synthesis（结果整合） | Replan/Plan 修订中的"更新计划"逻辑 | 需 Coordinator 级整合，晚于本设计 |
| 失败处理（Retry/替代/降级/通知） | Replanning 分级 + 预算防循环 | 复用；Multi-Agent 时升级为 Coordinator 决策 |

### 9.2 依赖方向
- **Multi-Agent 强依赖本设计**：没有稳定的 Plan/task_context/Replan 地基，Coordinator 分派与共享任务状态无从落地。
- **本设计不依赖 Multi-Agent**：Planner 是单 Agent 能力，可独立演进。
- **建议顺序**（与 11 doc"默认单 Agent，只有必要时升级"一致）：
  ```
  V2 Planner（本提案）→ 自动任务树 V3（steps 依赖/并行）→ Multi-Agent V4（Coordinator+Specialist+Synthesis）
  ```

---

## 10. 演进路线图（G2 后续阶段拆解）

| 阶段 | 内容 | 依赖 | 基线影响 |
|------|------|------|---------|
| G2-B | PlannerService 接口化（heuristic / LLM 双实现）；Level≥2 LLM 计划 + heuristic 兜底 | G2-A 本提案 | 无状态/事件改动；回归全绿 |
| G2-C | Plan 数据结构 V2 + task_context V1.1；`current_step` 动态推进回写 | G2-B | 快照只增不改；E7/E8 断言兼容 |
| G2-D | Structured Replan（证据收集 + 计划修订 + 预算防循环 + plan_updated 事件） | G2-C | 新增事件；不改执行闸 |
| G2-E | `planning`/`replanning` 状态 + `planning/plan_updated/planning_failed` 事件注册；审计收口 | G2-D | 状态机扩展（P2 收口） |
| G3 | 自动任务树（steps 依赖/并行/子任务） | G2-E | — |
| G4 | Multi-Agent（Coordinator + Specialist + Synthesis） | G3 | 依赖 Plan/task_context 地基 |

每步交付时保持全量回归全绿（A/B1/B2/C/Phase3/E2-E5/E7/E8/G1），`test_timeline_persistence.py` 为外部验收用例。

---

## 11. 决策记录摘要（ADR）

| # | 决策 | 备选 | 选定理由 |
|---|------|------|---------|
| D1 | Planner 留在 ContextBuilder；不新增 Runtime 状态（G2 内） | 新增 planning 状态 | 最小侵入、E8 状态机冻结；planning 状态留 G2-E |
| D2 | LLM 仅 Level≥2 触发，启发式兜底 | 全部走 LLM | 成本控制（11 doc）、fail-safe |
| D3 | Plan V2 只增不改、版本化 | 重写 V1 结构 | 兼容 E7/E8 断言、可审计 Replan |
| D4 | task_context V1.1：三基键保留 + 快照扩展 + 动态推进 | 全量改结构 | 兼容优先 |
| D5 | Planner→Runtime 单向契约 | 双向耦合 | 04 doc 分离原则、防越权 |
| D6 | Replan 分级 + 预算 | 全部结构化 Replan | 简单任务不浪费、防无限循环 |
| D7 | Multi-Agent 后置于 V2 | 并行推进 | 11 doc"默认单 Agent"、地基先行 |

---

## 12. 风险与未决问题

**风险**
1. **成本/首 token 延迟**：LLM 计划增加一次调用。缓解：仅 Level≥2、heuristic 快速路径、同 run 缓存。
2. **Prompt 增长**：计划细节注入 ⑧ 段。缓解：只注入"当前步骤 + 进度摘要"，不注入全计划原文。
3. **快照一致性**：`task_context` 内存快照与 `runtime_events` 事件可能漂移。缓解：以事件为准、`plan_updated` 全量落审计。

**未决（需评审确认）**
1. **Plan 持久化形态**：仅事件承载（`planning`/`plan_updated`） vs 新建 `plans` 表。倾向：先事件承载，观察审计需求再定。
2. **`planning` 状态引入时机**：G2-B 提前引入 vs G2-E 收口。倾向：G2-E（保持 E8 状态机冻结优先）。
3. **success_criteria 程序化评估**：`verify_result` 目前只验工具级结果（exit code/文件重读）；"目标级成功条件"（如延迟下降 30%）如何评估 —— 需扩展验证策略 or 由 LLM 判定（违反 E4"非 LLM 自检"原则），倾向先人工/文本兜底。
4. **LLM 计划 schema 校验失败降级**：兜底到启发式后，是否把"计划降级"事件暴露给前端（无 UI 改动约束，先仅事件）。

---

## 13. 结论

- **接入**：LLM Planner 以 `PlannerService` 双实现（heuristic/LLM）接入 ContextBuilder，不触碰 AgentRuntime 唯一执行入口。
- **数据结构**：Plan 升级为版本化 V2（步骤状态/预期产出/依赖/验证提示），task_context 演进为 V1.1 快照并动态推进。
- **边界**：Planner 决定 what/why，Runtime 执行 how；单向契约，禁止越权。
- **Replanning**：Verification 失败分级处置 —— 简单任务内隐修复，复杂任务结构化 Replan（预算防循环、事件审计）。
- **Multi-Agent**：**依赖本设计**（Coordinator≈动态 Planner、共享 Task State≈Plan/task_context），但应后置于 V2/V3。
- **本阶段不产出代码、不改数据库、不实现**；后续 G2-B→G2-E 按路线图分阶段落地并保持 E8 基线全绿。
