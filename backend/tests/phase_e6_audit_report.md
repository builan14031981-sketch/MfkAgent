# MfkAgent Runtime Evolution E6 Audit Report

- 审查时间: 2026-08-06
- 审查方式: 只读代码审查（不修改任何生产代码）
- 审查基线: 产品企划书 V4.0 / Agent Runtime Evolution 调研 / Multi-Agent 调研 / Multimodal 调研
- 结论: **B — 需要补基础设施（量级小），补齐 P0/P1 后可进入 Planner**

---

## 1. AgentRuntime 是否唯一入口

### 当前调用链

```
Chat API
  └─ POST /api/chat/{id}/send          (chat.py:474-583)
  └─ POST /api/chat/{id}/send/stream   (chat.py:586-729)
        └─ ChatContextBuilder.build    (context_builder.py:286-411)  → AgentContext + messages + system prompt
        └─ AgentRuntime.run / run_stream (chat.py:514 / 646)
              ├─ Execution Loop（AgentRuntime 内部，agent.py:297-343 / 491-560）
              │    ├─ model_service.call_once()/stream_once()  单次 LLM 调用（agent.py:301/500）
              │    ├─ _exec_tool_calls → executor.execute_tool  工具执行闸（agent.py:80-127）
              │    ├─ approval_registry 审批闭环（tool-approval API 仅 resolve Future）
              │    └─ _exec_tool_calls_with_verification → verifier（agent.py:129-173）
              └─ runtime_event_recorder（AgentRun / RuntimeState / RuntimeEvent 旁路副作用）
审批: POST /api/chat/{id}/tool-approval (chat.py:737-753) → approval_registry.resolve 仅解锁 Future，
     工具实体仍在 AgentRuntime 循环内由 complete_approval 完成。
```

### 是否存在第二执行循环

**否。** 生产执行路径唯一：所有 `AgentRuntime(` 实例化仅出现在 `chat.py`（+ 测试）。Execution Loop
（多轮工具调用判断）只存在于 `AgentRuntime`（agent.py），`model_service.call_once/stream_once`
被明确设计为"单次原始调用，工具循环由 AgentRuntime 控制"（model.py:230）。无
`chat.py → model_service → 自己循环` 旁路。

**已确认的旁路 / 直连（见 §7 处置）：**
| 位置 | 类型 | 说明 |
|------|------|------|
| `api/models.py:116,141` `/api/models/chat` | 直连 | 裸单次 LLM 调用（无工具/无循环/无状态）。模型连通性测试端点，非 Agent 执行，**可接受**（建议标注为 debug 用途）。 |
| `api/tools.py:37` `/api/tools/call` | **旁路** | 直接 `tool_registry.execute()`，**绕过** risk_engine 三态闸/审批/Plan-Build 判定。可无差别执行 add_memory（写库）等。P1。 |
| `services/workflow.py:122` | 未接线 | `tool_registry.execute` 在 Workflow 数据模型内，无任何 API/循环调用它。死代码，非执行路径。 |
| `services/tool_runtime_v5/**`、`services/tool_runtime/**` | 死代码 | 全库零 import，未接线。非执行路径，建议清理。 |

---

## 2. Plan / Build 行为审查

### 判定链（三层防护）

```
风险判定唯一执行闸 executor.execute_tool (executor.py:76-100)
  ├─ run_command  → CommandRiskEngine.evaluate(cmd, mode)      (risk_engine.py:150-181)
  └─ 其它工具     → evaluate_tool(name, mode)                  (risk_engine.py:246-272)
工具目录: PermissionFilter.resolve(chat)                        (permission.py:37-62)
Prompt:   policy.get_permission_context / get_plan_mode_policy   (policy.py:29-85)
          context_builder._assemble_prompt ④/④b 层注入           (context_builder.py:258-283)
```

### Plan 模式验证

| 能力 | 是否允许 | 依据 |
|------|---------|------|
| read | ✅ | read_file / list_files 在 READ_ONLY_TOOLS（risk_engine.py:235-240）+ 目录保留（permission.py:20-26） |
| search | ✅ | search_files / web_search / fetch_url / github_search（READ_ONLY_TOOLS） |
| inspect | ✅ | git_status / git_diff / git_log + run_command 只读白名单（pytest/npm run test|build/git status 等，risk_engine.py:61-100） |
| analyze | ✅ | 只读命令 + 只读工具 + TaskRouter ANALYZE 分类（router.py:44-50） |
| write | ❌ | write_file → evaluate_tool DENY（risk_engine.py:259-263）+ 目录移除 |
| delete | ❌ | delete_file 已注册 TOOL_RISK_POLICY（risk_engine.py:229）→ Plan DENY |
| modify | ❌ | git_commit/restore/add/push 等全部 DENY；add_memory 写库 DENY（risk_engine.py:227） |
| 未声明工具 | ❌ | Plan fail-closed DENY（risk_engine.py:266-271） |

### 确认无"Plan 禁止全部工具"错误

- `READ_ONLY_TOOLS` 12 项两模式均 ALLOW（risk_engine.py:254-255）；
- run_command 只读白名单 Plan 自动放行（risk_engine.py:165-166 + :176-180）；
- Plan 目录仍保留 10 个工具（permission.py:52-56 移除写工具后）。
- prompt ④/④b 层明确列出"允许/禁止"双向清单，非"禁用一切"（policy.py:49-58, 77-85）。

**结论：Plan=只读（允许 read/search/inspect/analyze），Build=全量工具+审批。符合企划书语义。**

---

## 3. Runtime State 审查

### 覆盖对照

| 审查要求 | 现状 | 说明 |
|---------|------|------|
| idle | ⚠️ 未显式建模 | Chat 无进行中 run = 隐式 idle；无独立 RuntimePhase |
| running | ✅ | `AgentRun.status=running`（粗粒度，models/agent.py:69） |
| thinking | ⚠️ 覆盖于 llm_call | thinking 事件独立存在，无独立"thinking"阶段 |
| tool_calling | ✅ | `tool_execution`（states.py:25） |
| waiting_approval | ⚠️ 覆盖于 tool_execution | 审批等待发生在 tool_execution 内（executor awaiting_approval），无子态 |
| verifying | ✅ | `verifying`（states.py:26）+ E4 程序验证 |
| completed | ✅ | `completed`（states.py:28） |
| failed | ✅ | `failed` + `cancelled`（states.py:29-30） |

### 状态转换合法性

```
pending → 任意活跃阶段/终态
活跃阶段 → 其它活跃阶段 / 任意终态
终态 → 空集（不可再流转）
```
（states.py:54-73 `_build_transition_map`）

- `completed → running` 等终态再流转：**被禁止**。`recorder.transition` 对非法流转仅记日志并拒绝更新
  （recorder.py:129-133），旁路语义不阻断执行。
- 已由 E5 测试验证：非法流转拒绝、终态封闭、全阶段覆盖（tests/test_state_management_phase_e5.py）。

**结论：核心状态机合法、闭环。缺失 idle/thinking/waiting_approval 为粒度级缺口（P2），非架构阻断。**

---

## 4. RuntimeEvent 审查（Timeline 是否需重新设计）

### 现状

- `RuntimeEventType` 注册表 11 种（states.py:84-100）：
  text / thinking / tool_start / tool_result / tool_approval / tool_calls /
  verify_result / verification_failed / state_change / finish / error
- `recorder.emit` 对未注册类型**软校验**：记日志仍写入（recorder.py:151-177）→ 向后兼容扩展。
- `RuntimeEvent`（models/agent.py:79-97）+ `RuntimeState` 审计（:100-115）已持久化；sequence 同 run 自增。
- 前端"timeline" = `Message.timeline` JSON 快照（chat.py:531-559, 698-709），由事件去重拷贝生成。

### 未来事件支持

| 未来能力 | 现状 | 所需 |
|---------|------|------|
| verification | ✅ 已注册 verify_result / verification_failed | 无 |
| memory_write | ⚠️ add_memory 执行但无 memory_write 事件 | 注册新类型 + emit（P2） |
| vision | ⚠️ 未注册 | 注册新类型（P2） |
| sub_agent | ⚠️ 未注册 | 注册新类型 + task_id 字段（P2） |
| planning | ⚠️ 未注册 | 注册新类型（P2） |

**结论：Timeline **不需要重新设计**。注册表 + 软校验模式可无缝吸收全部未来事件类型（只增不改）。**
P2 事项：事件**只写不读** —— 无 `GET /api/runs/{id}/events` 回放/审计接口（P1，见 §7）。

---

## 5. ContextBuilder 审查（Planner 未来入口）

### AgentContext 现状（context.py:26-57）

```
identity      ✅ agent_identity + identity 只读别名（context.py:54-57）
capability    ✅ capabilities
project       ✅ project_context（project_id/path/name/workspace/mode）
history       ✅ history 字段（当前全量加载，context_builder.py:342-348,382-385）
memory        ✅ memory_context + memory_text
vision_context ✅ 字段已存在，当前 None（context.py:50；context_builder.py:381）
task_context  ❌ 不存在
```

### 重点

- **vision_context**：字段已预留，接入容易 —— 仅在 build() 中填充即可（Multimodal 调研落地零重构）。
- **task_context**：**缺失**。Planner 需要的当前任务结构化上下文（目标/子任务/进度/依赖）无承载字段。
  - `ContextBuildInput` 亦无 task 输入通道（context_builder.py:83-94）。
  - **P1：新增 `task_context` 字段（+ build 输入通道 + planner 填充位）**，改动面小。

### 扩展点

- `ContextBuilder` 抽象接口（context_builder.py:55-64）= AgentRuntime 内 message 变换钩子，
  History 窗口化 / token 预算 / 压缩的既定扩展点（docstring 已声明）。
- `ChatContextBuilder` 为顶层组装器（单例，context_builder.py:415-419），可注 Planner 上下文。

**结论：Context 架构已就绪，仅差 task_context（P1）。**

---

## 6. Verification 审查

### 现状链路

```
Tool 执行（executor）
  ↓ record 列表
Verifier.verify_all（仅 status=="success"，verifier.py:27-38）
  ├─ write_file  → 重读磁盘校验存在+内容一致（strategies.py:43-96）
  ├─ run_command → 解析 [exit code N]（strategies.py:99-136）
  └─ 其它工具     → default_verify 默认通过（strategies.py:139-141）
  ↓ VerificationResult（passed/need_retry/failed，models.py:23-25）
Runtime（_exec_tool_calls_with_verification，agent.py:129-173）
  ├─ verify_result 事件透传（每动作）
  ├─ 存在未通过 → verification_failed 事件 + 向 messages 注入【验证反馈】
  └─ 进入下一轮循环（LLM 依据反馈修正重试，agent.py:166-173 / 531-533）
```

### 确认

- **是** Tool执行 → Verifier → Runtime → 下一轮，程序化验证优先（确定性校验，不依赖 LLM 自答）。
- **不是** prompt 要求 AI 自己检查：`models.py` 文档明确"本阶段不做 LLM 自主判定验证结果"
  （models.py:16-17），策略表 VERIFIERS 全部为确定性函数（strategies.py:144-147）。
- 覆盖缺口：目前仅 write_file / run_command 有策略，git / 搜索 / add_memory 等默认 pass（P2）。

**结论：验证架构正确（E4 已实现闭环），需按工具扩充策略面（P2）。**

---

## 7. 最终建议

**判定：B — 需要补基础设施（进入 Planner 前）。**

核心架构（唯一入口 / Plan-Build 闸 / 状态机 / 事件 / 验证 / 上下文）在 E1-E5 已成型且回归全绿，
缺口均为**增量补充**而非重构。补齐 P0/P1 后即可进入 Planner 阶段。

### P0（无阻断性缺陷；安全红线建议优先）

- 无。

### P1（进入 Planner 前必须）

1. **封堵 `/api/tools/call` 执行旁路**（api/tools.py:37）：改为复用 `executor.execute_tool` 风险闸
   （带 mode/approval），或移除该端点；否则 Plan 只读约束对 tool_registry 工具（add_memory 写库）失效。
2. **AgentContext 增加 `task_context`**（context.py + ContextBuildInput + build() 填充位）：
   Planner 目标/子任务/进度/依赖的结构化承载字段（audit §5 明确要求）。
3. **新增运行时事件回放/审计 API**：`GET /api/runs/{id}/events` + `GET /api/runs/{id}/states`
   （RuntimeEvent / RuntimeState 目前只写不读；Planner 阶段需要审计与恢复）。

### P2（Planner 首期迭代内）

4. **状态机粒度扩展**：`idle`、`thinking`、`waiting_approval` 显式子态（当前覆盖于
   llm_call / tool_execution；不影响合法性，提升前端指示精度）。
5. **事件类型注册**：`memory_write` / `vision` / `sub_agent` / `planning` 入 `RuntimeEventType` 注册表
   （机制已具备，仅登记）。
6. **流式路径接入 TaskRouter**：`run_stream` 无 `routing` 阶段（agent.py:482 直接 llm_call），
   与 run() 行为不对称；Planner 需要统一路由语义。
7. **验证策略扩充**：write_file / run_command 之外增加 git / add_memory 等策略（VERIFIERS 路由表）。
8. **清理死代码**：`services/tool_runtime_v5/**`、`services/tool_runtime/**`（全库零引用），
   消除双 Tool Runtime 认知负担。
9. **`/api/models/chat` 标注 debug 用途**（直连单次调用，非 Agent 执行路径，防误用）。

### 放行条件

- P1 ① 封堵执行旁路 → 恢复"Plan 不得修改数据库"闭环一致性。
- P1 ② task_context 就位 → Planner 上下文入口完备。
- P1 ③ 事件回放 API → 审计/恢复能力落地。
- 三项完成后 → 重新审查为 **A（可以进入 Planner）**。

---

## 8. E7 落实情况（2026-08-06 补充）

Phase E7（Runtime Stabilization）已闭环，E6 P1 清单处置如下：

| E6 P1 | E7 处置 | 状态 |
|-------|--------|------|
| ① 封堵 `/api/tools/call` 旁路 | 移除 `POST /api/tools/call`（404）；裸执行移至 `/api/devtools/tools/call`，`settings.DEBUG` 门控；`GET /api/tools`、`GET /api/tools/definitions` 只读保留 | ✅ 已封堵 |
| ② AgentContext 增加 `task_context` | `context.py` 新增 `task_context: dict|None`（V1: goal/constraints/current_step）；`context_builder.py` 填充 None 预留位 | ✅ 已就位 |
| ③ 事件回放 API | 新增 `GET /api/runs/{run_id}/events`（sequence ASC + payload 展开 + run 摘要）；`/states` 可由 events 中的 state_change 还原，暂不单独提供 | ✅ 已提供 |

**E7 测试**：`tests/test_runtime_stabilization_phase_e7.py` 12/12 通过（原 tools API 行为、旁路 404、dev 门控开关、
Plan 权限闸级联、task_context 默认/V1/预留位、Replay 404/ASC 排序/摘要字段）。
完整回归：A 5/5、B1 4/4、B2 6/6、C 5/5、Phase3 7/7、E2 5/5、E3 7/7、E4 7/7、E5×2 各 8/8、D 7/7、E7 12/12。

> 结论：E6 判定的 P1 已全部落地，P2（状态粒度/事件注册/流式路由/验证策略/死代码清理）留给 Planner 首期迭代。

## 9. E8 Final Audit 确认（2026-08-06 补充）

`tests/test_runtime_final_audit_phase_e8.py` 7/7 通过，闭环成立（详见 `phase_e8_final_audit_report.md`）：

| 支柱 | E8 实测 | 结果 |
|------|--------|------|
| Runtime | build 流式端到端：state_path `building_context→llm_call→tool_execution→verifying→llm_call→completing`，AgentRun=completed，14 事件 | ✅ |
| Context | ChatContextBuilder→AgentContext 7 支柱契约（含 task_context） | ✅ |
| State | state_change 合法保序流转 + RuntimeState 审计 7 行 + 终态 completed | ✅ |
| Event | runtime_events 持久化 + `GET /api/runs/{id}/events` 回放 sequence ASC | ✅ |
| Permission | plan write_file 拒绝（无审批不落盘）+ 只读放行 11 + 未声明 fail-closed | ✅ |
| Verification | run_command 真实执行 → `[exit code 0]` → verify_result passed（非 LLM 自检） | ✅ |
| Task Context | `AgentContext.task_context` 就位（V1 goal/constraints/current_step，Planner 预留） | ✅ |

> **最终结论：E6 审查 P0/P1 全部落地并经 E8 实测闭环，本报告结论由 B 升级为 A（可以进入 Planner）。**
> P2 剩余项随 Planner 首期迭代处理。
