# MfkAgent 会话压缩引擎 测试报告（Phase G6-B）

- 时间: 2026-08-07 16:02:30

## 结果总览

| # | 用例 | 结果 | 耗时 |
|---|------|------|------|
| 1 | T1  三段式拆分 + 摘要节点位置 | ✅ PASS | 2ms |
| 2 | T2  中间内容不足 → 返回原列表 | ✅ PASS | 1ms |
| 3 | T3  摘要成功 → memory 节点注入（dict） | ✅ PASS | 1ms |
| 4 | T4  摘要异常 → fail-safe 返回原列表 | ✅ PASS | 1ms |
| 5 | T5  摘要为空 → fail-safe 返回原列表 | ✅ PASS | 1ms |
| 6 | T6  ModelMessage 类型保持 | ✅ PASS | 1ms |
| 7 | T7  keep_recent 覆盖全部 → 不压缩 | ✅ PASS | 1ms |
| 8 | T8  摘要 Prompt 内容正确 | ✅ PASS | 1ms |
| 9 | T9  模型解析优先级 | ✅ PASS | 1ms |
| 10 | T10 自定义 keep_recent / min_middle | ✅ PASS | 1ms |
| 11 | T11 独立接口不破坏 run/run_stream | ✅ PASS | 0ms |

**通过率: 11/11**

## 验证明细

### 1. T1  三段式拆分 + 摘要节点位置

- total: 7
- roles: ['system', 'system', 'user', 'user', 'assistant', 'user', 'assistant']
- memory_prefix_ok: True
- recent_preserved: True
- call_once_called: True

### 2. T2  中间内容不足 → 返回原列表

- unchanged: True
- len: 8
- call_once_not_called: True

### 3. T3  摘要成功 → memory 节点注入（dict）

- memory_role: user
- memory_has_path: True
- total: 6

### 4. T4  摘要异常 → fail-safe 返回原列表

- failsafe_ok: True
- len: 10
- no_exception: True

### 5. T5  摘要为空 → fail-safe 返回原列表

- failsafe_ok: True
- empty_summary_handled: True

### 6. T6  ModelMessage 类型保持

- all_model_message: True
- memory_role: user
- head_identity_preserved: True
- recent_identity_preserved: True

### 7. T7  keep_recent 覆盖全部 → 不压缩

- unchanged: True
- call_once_not_called: True

### 8. T8  摘要 Prompt 内容正确

- sys_has_constraint: True
- sys_has_max_chars: True
- user_has_middle: True
- user_excludes_recent: True
- user_excludes_system: True

### 9. T9  模型解析优先级

- explicit_priority: True
- config_priority: True
- default_fallback: qwen-flash

### 10. T10 自定义 keep_recent / min_middle

- total: 4
- recent_len: 2
- max_chars_in_prompt: True

### 11. T11 独立接口不破坏 run/run_stream

- has_compress_history: True
- has_run: True
- has_run_stream: True
- empty_ok: True
- single_ok: True
