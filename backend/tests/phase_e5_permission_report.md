# MfkAgent Plan / Build 权限模型修正 — Phase E5 测试报告

- 时间: 2026-08-07 19:02:48

## 修正前：Plan 权限实际行为

1. 工具目录（PermissionFilter.resolve）：plan 移除写入工具，仍可见 read_file / list_files /
   search_files / run_command / git_status / git_diff / git_log / web_search / fetch_url / github_search。
2. 执行闸（executor.execute_tool）：命令走 CommandRiskEngine（只读白名单 allow，其余 plan deny / build ask），
   非命令工具走 evaluate_tool。
3. 命令引擎：pytest / npm run test / git status / ipconfig 等 plan 自动放行；写命令 plan 拒绝 / build 审批。
4. 写入工具（write_file / git_commit / git_restore / git_revert）：plan 直接拒绝、无审批、不落盘；build 审批。

## 存在的问题（修正对象）

- **P1 执行闸 fail-open（违反 Plan 禁止修改数据库）**：evaluate_tool 对 TOOL_RISK_POLICY 之外的任何工具
  一律 ALLOW（含 plan）。add_memory（写 MemoryItem 库）因此在 plan 可被直接调用写库。
- **P2 权限清单漂移**：PermissionFilter._plan_write_tools 与 TOOL_RISK_POLICY 两处独立硬编码，
  且含不存在的工具名（git_add/git_reset/git_clean/git_push/git_pull）。新增写入工具易漏注册 → plan 静默放行。
- **P3 上下文提示不完整**：plan 模式 system prompt 未明确禁止清单，模型可能尝试写入工具（多耗一轮）。

## 修正方案（单一事实来源）

- risk_engine.py 新增 READ_ONLY_TOOLS（只读白名单）+ TOOL_RISK_POLICY（写入/有副作用）为唯一权限清单。
- evaluate_tool 重写：只读→两模式 ALLOW；写入→build 按表（ASK/ALLOW）、plan DENY；未声明→plan fail-closed DENY、build 放行。
- add_memory 纳入写入分类（build ALLOW / plan DENY）；预留 delete_file / rename_file（注册即被 Plan 拒绝）。
- PermissionFilter._plan_write_tools 派生自 PLAN_FORBIDDEN_TOOLS（消除漂移）。
- policy.py + context_builder.py：plan 模式 prompt 枚举禁止/只读清单。

## 修改文件

| 文件 | 变更 |
|------|------|
| backend/app/core/tool_runtime/risk_engine.py | READ_ONLY_TOOLS / PLAN_FORBIDDEN_TOOLS；evaluate_tool plan fail-closed；add_memory/delete_file/rename_file 注册 |
| backend/app/core/tool_runtime/permission.py | _plan_write_tools 派生自 PLAN_FORBIDDEN_TOOLS |
| backend/app/core/tool_runtime/policy.py | permission_context 枚举禁止/只读清单；build_policy 追加 plan 策略 |
| backend/app/core/agent_runtime/context_builder.py | Chat API prompt 链路追加 plan 只读策略段 |
| backend/tests/test_plan_build_permission_phase_e5.py | 新增测试脚本（新增文件） |

## 修正要点

- 设计原则：Plan 与 Build 的区别不是工具能力区别，而是修改权限区别。
- 单一事实来源：`READ_ONLY_TOOLS`（只读白名单）+ `TOOL_RISK_POLICY`（写入/有副作用）。
- `evaluate_tool` 对未声明工具：Plan 模式 fail-closed 拒绝，Build 模式放行（消除 P1）。
- `PermissionFilter._plan_write_tools` 派生自 `PLAN_FORBIDDEN_TOOLS`，消除清单漂移（P2）。
- `add_memory`（写数据库）纳入写入分类：Plan 拒绝 / Build 放行。

## 结果总览

| # | 用例 | 结果 | 耗时 |
|---|------|------|------|
| 1 | evaluate_tool 三态矩阵 | ✅ PASS | 0ms |
| 2 | 命令引擎 Plan 只读约束 | ✅ PASS | 0ms |
| 3 | 权限目录 + 单一事实来源 | ✅ PASS | 0ms |
| 4 | E2E: plan 只读 read_file 放行 | ✅ PASS | 242ms |
| 5 | E2E: plan write_file 拒绝 | ✅ PASS | 165ms |
| 6 | E2E: plan add_memory 拒绝(写库) | ✅ PASS | 182ms |
| 7 | E2E: build add_memory 放行 | ✅ PASS | 195ms |
| 8 | 审批注册表无残留 | ✅ PASS | 0ms |

**通过率: 8/8**

## 验证明细

### 1. evaluate_tool 三态矩阵

- cases: [{'case': '只读 read_file', 'ok': True, 'build': 'allow', 'plan': 'allow'}, {'case': '只读 list_files', 'ok': True, 'build': 'allow', 'plan': 'allow'}, {'case': '只读 search_files', 'ok': True, 'build': 'allow', 'plan': 'allow'}, {'case': '只读 git_status', 'ok': True, 'build': 'allow', 'plan': 'allow'}, {'case': '只读 git_diff', 'ok': True, 'build': 'allow', 'plan': 'allow'}, {'case': '只读 git_log', 'ok': True, 'build': 'allow', 'plan': 'allow'}, {'case': '只读 web_search', 'ok': True, 'build': 'allow', 'plan': 'allow'}, {'case': '只读 fetch_url', 'ok': True, 'build': 'allow', 'plan': 'allow'}, {'case': '只读 github_search', 'ok': True, 'build': 'allow', 'plan': 'allow'}, {'case': '写入 write_file', 'ok': True, 'build': 'ask', 'plan': 'deny'}, {'case': '写入 git_commit', 'ok': True, 'build': 'ask', 'plan': 'deny'}, {'case': '写入 git_restore', 'ok': True, 'build': 'ask', 'plan': 'deny'}, {'case': '写入 git_revert', 'ok': True, 'build': 'ask', 'plan': 'deny'}, {'case': '写入 delete_file', 'ok': True, 'build': 'ask', 'plan': 'deny'}, {'case': '写入 rename_file', 'ok': True, 'build': 'ask', 'plan': 'deny'}, {'case': 'add_memory(写库)', 'ok': True, 'build': 'allow', 'plan': 'deny'}, {'case': '未知 future_write_tool', 'ok': True, 'build': 'allow', 'plan': 'deny'}, {'case': '未知 some_new_registry_tool', 'ok': True, 'build': 'allow', 'plan': 'deny'}]

### 2. 命令引擎 Plan 只读约束

- cases: [{'case': "只读命令 'pytest'", 'ok': True, 'plan': 'allow'}, {'case': "只读命令 'git status'", 'ok': True, 'plan': 'allow'}, {'case': "只读命令 'git diff'", 'ok': True, 'plan': 'allow'}, {'case': "只读命令 'ipconfig'", 'ok': True, 'plan': 'allow'}, {'case': "只读命令 'systeminfo'", 'ok': True, 'plan': 'allow'}, {'case': "只读命令 'python -m py_compile app.py'", 'ok': True, 'plan': 'allow'}, {'case': "只读命令 'npm run test'", 'ok': True, 'plan': 'allow'}, {'case': "只读命令 'reg query HKCU'", 'ok': True, 'plan': 'allow'}, {'case': "写入命令 'git reset --hard HEAD'", 'ok': True, 'plan': 'deny', 'build': 'ask'}, {'case': "写入命令 'pip install requests'", 'ok': True, 'plan': 'deny', 'build': 'ask'}, {'case': "写入命令 'rm -rf .'", 'ok': True, 'plan': 'deny', 'build': 'ask'}, {'case': "写入命令 'npm install lodash'", 'ok': True, 'plan': 'deny', 'build': 'ask'}, {'case': "写入命令 'taskkill /f /im test.exe'", 'ok': True, 'plan': 'deny', 'build': 'ask'}]

### 3. 权限目录 + 单一事实来源

- cases: [{'case': '目录过滤与风险引擎清单同步', 'ok': True, 'plan_forbidden': ['add_memory', 'delete_file', 'git_add', 'git_clean', 'git_commit', 'git_pull', 'git_push', 'git_reset', 'git_restore', 'git_revert', 'rename_file', 'write_file']}, {'case': 'build+项目 = 基础全集', 'ok': True, 'diff': []}, {'case': 'plan 保留只读工具', 'ok': True, 'missing': []}, {'case': 'plan 移除写入工具', 'ok': True, 'leak': []}]

### 4. E2E: plan 只读 read_file 放行

- tool: read_file
- plan_allowed: True
- auto_executed: True
- no_approval: True
- chat_id: 1

### 5. E2E: plan write_file 拒绝

- tool: write_file
- plan_denied: True
- no_approval: True
- no_file: True
- chat_id: 2

### 6. E2E: plan add_memory 拒绝(写库)

- tool: add_memory
- plan_denied: True
- no_approval: True
- no_db_write: True
- chat_id: 3

### 7. E2E: build add_memory 放行

- tool: add_memory
- build_allowed: True
- db_written: True
- chat_id: 4

### 8. 审批注册表无残留

- 说明: pending=0

## 结论

✅ **全部通过**：Plan 只读可用、禁止一切写入（含数据库），Build 写入走审批/放行。
