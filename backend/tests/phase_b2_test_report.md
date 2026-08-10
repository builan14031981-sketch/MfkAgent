# MfkAgent Tool Runtime Phase B-2 测试报告

- 时间: 2026-08-10 21:39:21
- 临时工作目录: `C:\Users\Asus\AppData\Local\Temp\mfk_phaseB2_lse5deg3`
- 测试模式: 单元级 (permission/runtime) + FastAPI TestClient + 脚本化 LLM

## 结果总览

| # | 用例 | 结果 | 耗时 |
|---|------|------|------|
| 1 | 权限目录组合 (permission.resolve) | ✅ PASS | 0ms |
| 2 | 目录与消息无关 (意图软提示) | ✅ PASS | 15ms |
| 3 | git_status 只读自动执行 | ✅ PASS | 2735ms |
| 4 | git_commit 触发审批并提交 | ❌ FAIL | 0ms |
| 5 | write_file plan 直接拒绝 | ✅ PASS | 266ms |
| 6 | 审批注册表无残留 | ✅ PASS | 0ms |

**通过率: 5/6**

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

- 说明: 20.0s 内审批未注册。state={'ok': True}

> 失败: 20.0s 内审批未注册。state={'ok': True}

### 5. write_file plan 直接拒绝

- tool: write_file
- plan_denied: True
- no_approval: True
- no_file: True
- chat_id: 3

### 6. 审批注册表无残留

- 说明: pending=0

## 结论

❌ **1 项未通过**，详见上方明细。
