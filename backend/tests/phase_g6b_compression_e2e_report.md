# MfkAgent 会话压缩 端到端验证报告（Phase G6-B E2E）

- 时间: 2026-08-07 19:01:32

- 链路: ChatContextBuilder → 历史 payload → 压缩引擎 → 模型 payload

- 方式: 真实 DB + 真实 ContextBuilder + mock model_service.call_once（零真实 LLM）

## 结果总览

| # | 用例 | 结果 | 耗时 |
|---|------|------|------|
| 1 | E2E-1 真实 ContextBuilder payload > 20 条 | ✅ PASS | 0ms |
| 2 | E2E-2 压缩触发，消息数明显减少 | ✅ PASS | 0ms |
| 3 | E2E-3 system message 保留 | ✅ PASS | 0ms |
| 4 | E2E-4 存在【历史记忆摘要】节点 | ✅ PASS | 0ms |
| 5 | E2E-5 最近 4 条消息保留 | ✅ PASS | 0ms |
| 6 | E2E-6 摘要含关键变量 | ✅ PASS | 0ms |
| 7 | E2E-7 原始 messages 未被修改 | ✅ PASS | 0ms |
| 8 | E2E-8 call_once mock + 摘要注入 | ✅ PASS | 0ms |

**通过率: 8/8**

## 验证明细

### 1. E2E-1 真实 ContextBuilder payload > 20 条

- before_count: 35
- over_20: True

### 2. E2E-2 压缩触发，消息数明显减少

- before: 35
- after: 6
- reduced: True

### 3. E2E-3 system message 保留

- system_role: system
- preserved: True

### 4. E2E-4 存在【历史记忆摘要】节点

- memory_index: 1
- prefix_ok: True

### 5. E2E-5 最近 4 条消息保留

- recent_preserved: True

### 6. E2E-6 摘要含关键变量

- key_vars: ['AgentRuntime', 'TaskGraph', 'FastAPI']
- all_present: True

### 7. E2E-7 原始 messages 未被修改

- unchanged: True
- len: 35

### 8. E2E-8 call_once mock + 摘要注入

- call_once_called: True
- injected: True
