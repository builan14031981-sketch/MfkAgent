# MfkAgent Runtime 状态管理 Phase E5 测试报告

- 时间: 2026-08-18 14:31:59
- 临时工作目录: `C:\Users\Asus\AppData\Local\Temp\mfk_stateE5_vl3e1lnp`

## 交付内容

1. **RuntimeState 状态模型**：`RuntimeState` 表（`runtime_states`）记录每次状态流转审计
   （run_id / from_state / to_state / reason / created_at），按 id 升序可还原完整流转路径。
2. **AgentRun 生命周期扩展**：新增 `state` 列（细粒度阶段），与 `status`
   （running/completed/failed/cancelled 粗粒度）双层对齐；旧库经 `main.py _ensure_schema` 轻量迁移。
3. **RuntimeEvent 类型标准化**：`states.py` 注册表 `RuntimeEventType` / `RUNTIME_EVENT_TYPES`
   （11 种类型），`recorder.emit` 对未知类型软校验（记日志仍写入，向后兼容）。
4. **状态机接入 AgentRuntime**：`run()` 与 `run_stream()` 全生命周期发射 `state_change` 事件、
   更新 `AgentRun.state`、写入 `RuntimeState` 审计；流式路径 SSE 同步透传 `state_change`。
5. **状态机合法性校验**：`VALID_TRANSITIONS` 合法流转表；非法流转（如终态再流转）拒绝并记日志，不阻断执行。

## 状态流转说明

```
pending ──► building_context ──► routing ──► llm_call ──► tool_execution ──► verifying ──► llm_call ...
   │              │                │            │                │                │
   └──────────────┴────────────────┴────────────┴────────────────┴────────────────┘
                                        (活跃阶段可互转)
                                        … 最终：llm_call ──► completing ──► completed
                                任意活跃阶段 ──► failed | cancelled（异常/取消终态）
                                终态（completed/failed/cancelled）不可再流转
```

实测路径：
- 流式工具轮：`building_context → llm_call → tool_execution → verifying → llm_call → completing → completed`
- 流式纯文本：`building_context → llm_call → completing → completed`
- 流式异常：`building_context → llm_call → failed`
- 流式取消：`building_context → cancelled`
- 非流式 run()：`building_context → routing → llm_call → completing → completed`

## 修改文件

| 文件 | 变更 |
|------|------|
| backend/app/core/agent_runtime/states.py | 新增：RuntimePhase / RuntimeEventType / VALID_TRANSITIONS / RUNTIME_EVENT_TYPES / is_valid_transition（新增文件） |
| backend/app/models/agent.py | AgentRun 新增 `state` 列 + `state_history` 关系；新增 RuntimeState 表；RuntimeEvent 文档更新 |
| backend/app/core/agent_runtime/recorder.py | 新增 `transition()` / `get_state()`；`finish_run` 同步终态 state；`emit` 事件类型软校验；create_run 初始化 pending |
| backend/app/core/agent_runtime/agent.py | run()/run_stream()/_run_stream_events() 全生命周期接入状态机（_record_state + state_change 事件） |
| backend/app/core/agent_runtime/__init__.py | 导出 states 系列符号 |
| backend/main.py | `_ensure_schema` 增加 agent_runs.state 旧库迁移 |
| backend/tests/test_state_management_phase_e5.py | 新增状态管理测试脚本（新增文件） |

## 状态模型

- 粗粒度 `AgentRun.status`: running / completed / failed / cancelled
- 细粒度 `AgentRun.state`（`RuntimePhase`）: pending → building_context / routing / llm_call /
  tool_execution / verifying → completing → completed | failed | cancelled
- `RuntimeState` 表记录每次流转审计（from_state / to_state / reason）
- `RuntimeEventType` 注册表: text / thinking / tool_start / tool_result / tool_approval /
  tool_calls / verify_result / verification_failed / state_change / finish / error

## 结果总览

| # | 用例 | 结果 | 耗时 |
|---|------|------|------|
| 1 | 状态机合法性 | ✅ PASS | 0ms |
| 2 | 事件类型注册表 | ✅ PASS | 0ms |
| 3 | Recorder.transition 单元 | ✅ PASS | 65ms |
| 4 | 流式工具轮生命周期 | ✅ PASS | 461ms |
| 5 | 流式纯文本生命周期 | ✅ PASS | 140ms |
| 6 | 流式异常 failed | ✅ PASS | 102ms |
| 7 | 流式取消 cancelled | ✅ PASS | 259ms |
| 8 | 非流式 run() 生命周期 | ✅ PASS | 109ms |

**通过率: 8/8**

## 验证明细

### 1. 状态机合法性

- cases: [{'case': '合法流转允许', 'ok': True}, {'case': '非法流转拒绝', 'ok': True}, {'case': '终态封闭', 'ok': True}, {'case': '流转表覆盖全阶段', 'ok': True, 'phases': ['building_context', 'cancelled', 'completed', 'completing', 'failed', 'llm_call', 'pending', 'routing', 'tool_execution', 'verifying']}]

### 2. 事件类型注册表

- cases: [{'case': '注册表类型全集', 'ok': True, 'extra': [], 'missing': []}, {'case': '规范类型均注册', 'ok': True}, {'case': 'state_change 注册 / 未知未注册', 'ok': True}]

### 3. Recorder.transition 单元

- cases: [{'case': 'create_run 初始 state=pending', 'ok': True}, {'case': 'transition pending→building_context', 'ok': True, 'from': 'pending'}, {'case': 'transition building_context→llm_call', 'ok': True, 'from': 'building_context'}, {'case': '非法流转 completed→llm_call 拒绝', 'ok': True, 'from': None}, {'case': 'RuntimeState 审计行完整', 'ok': True, 'actual': [('pending', 'building_context'), ('building_context', 'llm_call'), ('llm_call', 'completed')]}]
- run_id: 1

### 4. 流式工具轮生命周期

- case: stream_tool_round
- run_id: 2
- status: completed
- state_path: ['building_context', 'llm_call', 'tool_execution', 'verifying', 'llm_call', 'completing']
- state_events: 6
- event_count: 18

### 5. 流式纯文本生命周期

- case: stream_text
- run_id: 3
- state_path: ['building_context', 'llm_call', 'completing']

### 6. 流式异常 failed

- case: stream_failed
- run_id: 4
- status: failed
- audit: ['building_context', 'llm_call', 'failed']

### 7. 流式取消 cancelled

- case: stream_cancelled
- run_id: 5
- status: cancelled
- audit: ['building_context', 'cancelled']

### 8. 非流式 run() 生命周期

- case: non_stream_run
- run_id: 6
- state_path: ['building_context', 'routing', 'llm_call', 'completing']

## 结论

✅ **全部通过**：AgentRun 状态机覆盖正常/工具/异常/取消/非流式全生命周期。

## 下阶段建议

- 前端接入：SSE 已透传 `state_change` 事件，可据此渲染运行阶段指示器 / 重连恢复运行中状态。
- 事件查询 API：新增 `GET /api/chat/{id}/runs` 与 `GET /api/runs/{id}/events` 便于审计/回放。
- 状态恢复：`status=running` 的遗留 run（进程崩溃残留）可启动时巡检并置为 failed + reason=orphan。
- History 窗口化：ContextBuilder 的 token budget / compression 扩展点可与 llm_call 阶段事件联动。
- 验证接入审批流：`tool_execution` 阶段内审批等待（awaiting_approval）可细分 `waiting_approval` 子态。