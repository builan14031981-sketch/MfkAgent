# MfkAgent Tool Runtime Phase B-2 测试报告

- 时间: 2026-08-07 14:09:56
- 临时工作目录: `C:\Users\Asus\AppData\Local\Temp\mfk_phaseB2_im66l6n5`
- 测试模式: 单元级 (permission/runtime) + FastAPI TestClient + 脚本化 LLM

## 结果总览

| # | 用例 | 结果 | 耗时 |
|---|------|------|------|
| 1 | 权限目录组合 (permission.resolve) | ✅ PASS | 0ms |
| 2 | 目录与消息无关 (意图软提示) | ✅ PASS | 8ms |
| 3 | git_status 只读自动执行 | ✅ PASS | 1650ms |
| 4 | git_commit 触发审批并提交 | ✅ PASS | 2255ms |
| 5 | write_file plan 直接拒绝 | ✅ PASS | 253ms |
| 6 | 审批注册表无残留 | ✅ PASS | 0ms |

**通过率: 6/6**

## 验证明细

### 1. 权限目录组合 (permission.resolve)

- cases: [{'case': 'build+项目=全集', 'ok': True}, {'case': 'plan 移除写入工具', 'ok': True}, {'case': 'plan 保留 git 只读', 'ok': True}, {'case': '无项目移除项目工具', 'ok': True}]

### 2. 目录与消息无关 (意图软提示)

- install_need_tools: True
- greet_need_tools: True
- delete_need_tools: True

### 3. git_status 只读自动执行

- tool: git_status
- auto_executed: True
- no_approval: True
- chat_id: 1

### 4. git_commit 触发审批并提交

- tool: git_commit
- approval_gate: True
- committed: True
- chat_id: 2

### 5. write_file plan 直接拒绝

- tool: write_file
- plan_denied: True
- no_approval: True
- no_file: True
- chat_id: 3

### 6. 审批注册表无残留

- 说明: pending=0

## 结论

✅ **全部通过**：权限决定工具可见性、模型决定调用，写入类工具统一走审批/拒绝。
