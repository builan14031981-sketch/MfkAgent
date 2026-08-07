# MfkAgent Runtime Stabilization Phase E7 测试报告

- 时间: 2026-08-07 17:19:03
- 临时工作目录: `C:\Users\Asus\AppData\Local\Temp\mfk_stabE7_c7clgg7q`

## 交付内容

- **E7-1 封堵 Tool API 绕过**：移除 `POST /api/tools/call`（404）；裸工具执行移至
  `/api/devtools/tools/call`，仅 `settings.DEBUG=True` 可用；只读列表/定义接口保留。
- **E7-2 AgentContext.task_context**：新增 `task_context: dict | None` 字段
  （V1: goal / constraints / current_step，Planner 预留），ContextBuilder 填充 None。
- **E7-3 Runtime Event Replay API**：`GET /api/runs/{run_id}/events`，sequence ASC 排序，
  payload 展开到事件顶层，附 run 摘要（status/state/started_at/finished_at）。

## 结果总览

| # | 用例 | 结果 | 耗时 |
|---|------|------|------|
| 1 | 原工具列表 API 保持不变 (GET /api/tools) | ✅ PASS | 44ms |
| 2 | 原工具定义 API 保持不变 (GET /api/tools/definitions) | ✅ PASS | 3ms |
| 3 | 旁路封堵 (POST /api/tools/call → 404) | ✅ PASS | 12ms |
| 4 | dev 裸工具调用 DEBUG 开启可用 | ✅ PASS | 4ms |
| 5 | dev 裸工具调用 DEBUG 关闭 404 | ✅ PASS | 3ms |
| 6 | Runtime 权限闸不受影响 (Plan 拒绝写/放行只读) | ✅ PASS | 4ms |
| 7 | AgentContext.task_context 默认 None | ✅ PASS | 0ms |
| 8 | AgentContext.task_context V1 结构 | ✅ PASS | 0ms |
| 9 | ChatContextBuilder task_context 预留位 | ✅ PASS | 23ms |
| 10 | Replay API 不存在 run → 404 | ✅ PASS | 6ms |
| 11 | Replay API sequence ASC 排序 + payload 展开 | ✅ PASS | 17ms |
| 12 | Replay API run 摘要字段 | ✅ PASS | 14ms |

**通过率: 12/12**

## 验证明细

### 1. 原工具列表 API 保持不变 (GET /api/tools)

- count: 6
- has_add_memory: True

### 2. 原工具定义 API 保持不变 (GET /api/tools/definitions)

- count: 6

### 3. 旁路封堵 (POST /api/tools/call → 404)

- status_code: 404

### 4. dev 裸工具调用 DEBUG 开启可用

- status_code: 200
- output: 2026-08-07 17:19:03

### 5. dev 裸工具调用 DEBUG 关闭 404

- status_code: 404

### 6. Runtime 权限闸不受影响 (Plan 拒绝写/放行只读)

- status: failed
- memory_before: 0
- memory_after: 0

### 7. AgentContext.task_context 默认 None

- task_context: None

### 8. AgentContext.task_context V1 结构

- keys: ['constraints', 'current_step', 'goal']

### 9. ChatContextBuilder task_context 预留位

- task_context: None
- chat_id: 1

### 10. Replay API 不存在 run → 404

- status_code: 404

### 11. Replay API sequence ASC 排序 + payload 展开

- run_id: 1
- seqs: [1, 2, 3, 4, 5]
- types: ['state_change', 'thinking', 'tool_start', 'verify_result', 'text']

### 12. Replay API run 摘要字段

- run_keys: ['agent_id', 'chat_id', 'finished_at', 'started_at', 'state', 'status']
- events: 5

## 修改文件

| 文件 | 变更 |
|------|------|
| backend/app/api/tools.py | 移除 POST /call 执行端点；仅保留只读列表/定义 |
| backend/app/api/devtools.py | 新增 /tools/call 开发执行端点（DEBUG 门控） |
| backend/app/core/agent_runtime/context.py | AgentContext 新增 task_context 字段 |
| backend/app/core/agent_runtime/context_builder.py | AgentContext 构造注入 task_context=None 预留位 |
| backend/app/api/runs.py | 新增（E7-3）Replay API：GET /api/runs/{id}/events |
| backend/main.py | 注册 runs router |
| backend/tests/test_runtime_stabilization_phase_e7.py | 新增测试脚本（本文件） |

## 结论

✅ **全部通过**：Tool API 旁路已封堵（dev 门控）、task_context 就位、事件回放 API 可用。
