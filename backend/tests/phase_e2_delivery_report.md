# MfkAgent Phase E2 交付报告

> 阶段：Phase E2 — Runtime Event Persistence（运行时生命周期记录）
> 目标：让 AgentRuntime 拥有可查询的运行生命周期（AgentRun）与事件流水（RuntimeEvent），支撑后续审批决策、重放、调试
> 状态：**完成，验证通过（E2 5/5 全绿 + Phase A/B-1/C/3 回归全绿）**
> 日期：2026-08-06

---

## 1. 新增/修改文件

| 文件 | 变更 | 说明 |
|------|------|------|
| `backend/app/core/agent_runtime/recorder.py` | **新增** | `RuntimeEventRecorder`：`create_run(chat_id, agent_id)→run_id`、`emit(run_id, event_type, payload)`、`finish_run(run_id, status)`；sequence 进程内自增 + DB 续接；独立 Session；失败仅日志不阻断执行 |
| `backend/app/core/agent_runtime/__init__.py` | 扩展 | 导出 `RuntimeEventRecorder` / `runtime_event_recorder` 全局单例 |
| `backend/app/core/agent_runtime/agent.py` | 扩展 | `AgentContext` 加 `chat_id` 字段；`run()` / `run_stream()` 包装生命周期 + 事件持久化；`run_stream` 拆为包装器 + `_run_stream_events()` 内层生成器；CancelledError→cancelled |
| `backend/app/api/chat.py` | 修改 | send / stream 两处 `AgentContext` 已补 `chat_id` |
| `backend/app/models/agent.py` | 扩展 | 新增 `AgentRun` / `RuntimeEvent` 模型；`AgentRun.chat_id` 改 `nullable=True`（由上下文带入） |
| `backend/tests/test_runtime_event_phase_e2.py` | **新增** | E2 验证套件（5 用例） |

## 2. AgentRun 创建位置

- **入口**：`run()`（非流式，agent.py:206）与 `run_stream()`（流式，agent.py:355）包装器开头。
- 调用 `runtime_event_recorder.create_run(chat_id=context.chat_id, agent_id=context.agent_id)`：
  - 创建 `AgentRun(status="running")`，写 `started_at`；
  - 以 DB 内该 run 现有最大 `sequence` 为起点初始化进程内自增缓存（进程重启安全）；
  - `chat_id` 可空（由 `AgentContext` 带入，不阻塞无 chat 上下文场景）。

## 3. RuntimeEvent 写入位置

| 位置 | 事件 | payload |
|------|------|---------|
| `run_stream` 包装器循环（agent.py:363） | 所有 yield 事件 | 顶层 `type` 之外的字段（text/thinking/tool_start/tool_result/tool_approval/tool_calls/finish/error） |
| `run()` 非流式工具路径（agent.py:269） | tool 相关事件 | 工具调用/结果 |
| 异常分支（agent.py:313 / 374） | `error` | `{"message": str(e)}` |
| 收尾（agent.py:291/369、310/371、314/375） | `finish_run` | completed / cancelled / failed |

- **事件类型对齐 SSE 协议**：`text / thinking / tool_start / tool_result / tool_approval / tool_calls / finish / error`。
- **sequence**：同 run 内严格自增 `1,2,3,...`（测试断言无断号、无重复）。
- **幂等旁路**：任何 DB 失败仅 `logger.warning`，绝不阻断 Agent 执行。

## 4. 事件流

```
用户输入 ──▶ chat.py send/stream ──▶ AgentRuntime.run()/run_stream()
                                        │  create_run(status=running)
                                        │  emit(...)  ──▶ RuntimeEvent(sequence 1,2,3,...)
                                        │  finish_run(completed/failed/cancelled)
                                        ▼
                                   AgentRun(agent_runs 表)
                                        │
                                        ▼
                              SSE 透传前端（同一事件信封，type 顶层判别）
```

- `AgentRun`（agent_runs）与 `RuntimeEvent`（runtime_events）通过 `run_id` 关联（Cascade）。
- `AgentRun.chat_id` 关联 Chat；`agent_id` 记录执行的是哪个 Agent。

## 5. 数据库验证（测试临时 DB）

`test_runtime_event_phase_e2.py` 每次运行在临时目录 `phase_e2_test.db` 验证：

| 断言 | 结果 |
|------|------|
| 正常流式结束 → `AgentRun.status == "completed"`，started_at/finished_at 非空 | ✅ |
| 工具流 → `tool_start` / `tool_result` / `finish` 事件持久化，payload 含 tool 名与结果（exit code 0） | ✅ |
| 模型抛错 → `AgentRun.status == "failed"` + `error` 事件 | ✅ |
| 流被取消（CancelledError）→ `AgentRun.status == "cancelled"` | ✅ |
| 多轮 → 同 run 内 sequence 严格连续 `1..N` 无断号无重复 | ✅ |

实际采样（stream_lifecycle 用例）：`run_id=1, event_count=2, status=completed`；
`runtime_events` 记录：`sequence=1 text {"content": "这是 Phase E2 的文本回复。"}`、`sequence=2 finish {"finish_reason": "stop"}`。

## 6. 测试结果

| 套件 | 结果 |
|------|------|
| `test_runtime_event_phase_e2.py` | **5/5 PASS**（stream completed / tool events / failed / cancelled / sequence continuity） |
| `test_agent_runtime_phase3.py`（回归） | 7/7 PASS |
| `test_tool_runtime_phase_a.py`（回归） | PASS |
| `test_tool_runtime_phase_b1.py`（回归） | 4/4 PASS（残留审批为脚本自身手工注册 artifact） |
| `test_tool_runtime_phase_c.py`（回归） | 5/5 PASS |

调试记录：测试初期两个问题——`echo` 触发 ASK 审批导致 300s 等待挂起（改用只读白名单 `ipconfig` / `hostname`）；`_BlockingClient.aiter_text` 缺少 `yield` 导致 `async for` 拿不到异步生成器（补 `yield ""`）。

## 7. 下阶段建议（Phase E2.5+）

1. **审批决策层**：`tool_approval` 事件已持久化，但 Approve/Deny 决策尚未接入运行时决策源（当前仍走 `complete_approval` 注册表）。
2. **工具自动重发**：失败/拒绝的工具调用重试策略未实现。
3. **DB 读取修改（2.5 重设计）**：AgentRun/RuntimeEvent 只写不读，尚无查询 API 与前端重放/审计界面。
4. **tools getter / chat.py 参数补传**：工具清单与审批相关参数尚未完全收敛到 AgentContext。
5. **workflow 拉齐**：E2.5 阶段将非流式 `run()` 与流式 `run_stream()` 的工具事件持久化路径统一（当前 run() 内联 emit，未走 run_stream 的包装器循环）。
