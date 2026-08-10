# MfkAgent Agent Prompt Architecture 审计报告

> 生成时间：2026-08-10
> 审计范围：`backend/` 目录下全部 Prompt 组装链路
> 状态：只读审计，未修改任何代码

---

## 一、Prompt 来源映射表

| 层级 | 片段 | 来源文件 | 来源函数/字段 | 状态 |
|------|------|----------|--------------|------|
| ⓪ | **最高身份准则** | `app/core/identity_principle.py` | `get_identity_principle()` | ✅ 强制注入 |
| ① | **Agent Identity** | `app/models/agent.py` → `Agent.identity` | `context_builder.py:516-518` | ✅ `identity` 优先，fallback `system_prompt` |
| ② | **能力倾向** | `app/core/capability_profiles.py` | `get_capability_prompt(capabilities)` | ✅ 基于 `Agent.capabilities` 标签 |
| ③ | **执行规范** | `app/core/tool_runtime/policy.py` | `get_execution_policy()` | ✅ 全局注入 |
| ④ | **权限上下文** | `app/core/tool_runtime/policy.py` | `get_permission_context(chat, caps)` | ✅ 含可见工具列表 + Plan 只读约束 |
| ④b | **Plan 模式策略** | `app/core/tool_runtime/policy.py` | `get_plan_mode_policy()` | ✅ 仅 plan 模式 |
| ⑤ | **项目上下文** | `app/core/workspace.py` + `policy.py` | `_resolve_workspace()` + `get_project_policy()` | ✅ 项目绑定 / Default Workspace 兜底 |
| ⑥ | **人格 Prompt** | `app/services/personality.py` | `get_personality_prompt(level)` | ✅ 0-100 五档 |
| ⑦ | **意图提示** | `app/core/tool_runtime/planner.py` | `ToolPlanner.soft_hint()` | ✅ 软提示 |
| ⑧ | **任务计划** | `app/core/planner/` | `PlannerService.plan()` → `RuntimeTaskContextAdapter.render()` | ✅ heuristic/LLM 双轨 |
| ⑨ | **工具指导** | `app/core/tool_runtime/guidance.py` | `get_tool_guidance()` | ✅ 4 类任务模板 |
| ⑩ | **附件上下文** | `context_builder.py` | `_build_attachment_prompt()` | ✅ text/image/binary |
| 独立 | **Memory** | `context_builder.py` | `_build_memory_text()` | ✅ 不入 system prompt，由 `call_once(memory_text=)` 单独注入 |

---

## 二、完整 Prompt 组装流程

```
用户输入 (POST /api/chat/{id}/send/stream)
  │
  ▼
ChatContextBuilder.build(ContextBuildInput)          ← context_builder.py:507
  │
  ├── 1. 查 DB: Chat + Agent                          ← context_builder.py:510-519
  │     ├── system_prompt = agent.identity or agent.system_prompt or DEFAULT_IDENTITY
  │     └── capabilities = agent.capabilities
  │
  ├── 2. 人格解析                                      ← context_builder.py:522-527
  │     └── personality_prompt = get_personality_prompt(level)
  │
  ├── 3. 工作目录解析                                   ← context_builder.py:530
  │     └── _resolve_workspace(chat, message) → effective_chat + workspace_context
  │
  ├── 4. Memory 查询                                   ← context_builder.py:533
  │     └── _build_memory_text(db, project_id) → memory_text
  │
  ├── 5. 工具目录 + 意图识别                             ← context_builder.py:539-551
  │     └── tool_runtime.process(message, chat, capabilities) → tool_context
  │
  ├── 6. Planner 规划 (G2-B)                            ← context_builder.py:563-570
  │     └── PlannerService.plan(message, mode, decision, planning_level, model_id)
  │         ├── planning_level >= 2 → LLMPlanner.plan() (call_once)
  │         └── 失败/level<2 → heuristic (_plan_heuristic)
  │         └── plan.to_task_context() → task_context
  │
  ├── 7. System Prompt 组装                             ← context_builder.py:581-595
  │     └── _assemble_prompt(①-⑩层)
  │
  ├── 8. Vision Context 构建                            ← context_builder.py:598-600
  │     └── _build_vision_context(attachments, project_path) → vision_context
  │
  ├── 9. History 加载 + Thought Pruning                 ← context_builder.py:603-611
  │     └── prune_thought_history(history) → pruned_history
  │
  ├── 10. AgentContext 构造                             ← context_builder.py:614-654
  │
  └── 11. Messages 组装                                 ← context_builder.py:657-660
        └── [ModelMessage(system, full_prompt)] + [...pruned_history]
  │
  ▼
BuiltContext { context, messages, system_prompt, ... }
  │
  ▼
AgentRuntime.run_stream(context, messages)            ← agent.py
  │
  ├── loop_messages = messages (含 system prompt)
  │
  └── model_service.call_once(                        ← agent.py:881
        model_id, messages=loop_messages, tools=...,
        memory_text=..., vision_context=...
      )
  │
  ▼
最终发送 LLM
```

---

## 三、完整 Agent System Prompt 示例

### 3.1 Coder Agent（`agent_id="coder"`）— 假设绑定项目、build 模式、coding 意图

**Agent 数据：**
- `identity`（①层）: `"你是 MfkAgent 的代码审查与开发专家。专长：代码质量评估、架构设计、安全漏洞检测、边界情况分析。交付偏好：先阅读现有代码理解上下文，再给出可运行的具体方案；修改后主动运行验证确保代码正确。边界：在沙箱内操作项目文件，不执行系统级危险命令；涉及生产环境或不可逆操作时需先说明风险。"`
- `capabilities`（②层）: `["software_development", "project_debugging", "code_review"]`
- `personality_level`（⑥层）: `75`

**最终 System Prompt：**

```
⓪ [来源: identity_principle.py — get_identity_principle()]
🛑 【最高身份准则】：
1. 你是基于 Electron 运行的桌面级原生 AI 研发助手（MfkAgent），你具备完整的本地文件读写、目录创建及终端命令执行能力！
2. 绝对禁止向用户说出类似"我无法直接在你的设备上操作"、"我是 AI 无法创建文件夹"、"请手动 Win+E 创建"等任何脱离 Agent 能力的废话！
3. ⚠️ 【上下文放行特权 — 最高优先级】当上下文中已经以 `[附件上下文]` 或 `[文件: xxx]` 形式提供了文件内容时，说明数据已在内存中就绪。你必须**直接基于提供的内容进行分析和作答**，这绝对不属于需要调用工具的磁盘文件操作！禁止因看到文件引用而索要项目路径或拒绝回答。
4. ⚠️ 【文件操作阻断规则 — 严格限定范围】仅当用户明确要求你执行以下操作之一时，若当前未关联项目路径，才需要询问放置目录：
   - 创建新文件（write_file / 新建文件 / 保存文件）
   - 修改本地文件（编辑 / 覆盖 / 重命名）
   - 保存内容到本地磁盘
   对于纯读取、内容分析、基于已提供上下文的问答请求，**绝对禁止索要项目路径或绑定目录**！


① [来源: Agent.identity — context_builder.py:516-518]
你是 MfkAgent 的代码审查与开发专家。专长：代码质量评估、架构设计、安全漏洞检测、边界情况分析。交付偏好：先阅读现有代码理解上下文，再给出可运行的具体方案；修改后主动运行验证确保代码正确。边界：在沙箱内操作项目文件，不执行系统级危险命令；涉及生产环境或不可逆操作时需先说明风险。

② [来源: capability_profiles.py — get_capability_prompt()]
## 能力倾向
- 软件开发：编写可运行、可维护的代码，交付后主动验证（构建/测试）。
- 问题定位与修复：先复现、取证、定位根因，再修复并验证闭环。
- 代码审查：关注质量、架构、边界、安全与长期维护成本，主动指出风险。

③ [来源: tool_runtime/policy.py — get_execution_policy()]
## Execution Policy v1

1. 优先使用工具获取真实信息，不猜测环境状态；无法获取时明确说明。
2. 修改文件/执行有副作用操作前，先说明计划；需审批的操作等待审批，不重复发起。
3. 完成任务后用简短摘要总结做了什么、结果如何。

### 禁止行为
- 在可获取真实信息时仅提供假设性建议；忽略工具返回的真实数据。

### 自检规则
回答前自问："不获取外部数据能否给出可靠答案？" 若否，先调用工具。

④ [来源: tool_runtime/policy.py — get_permission_context()]
## 当前会话权限上下文
当前会话可见工具: read_file, write_file, list_files, run_command, git_status, git_diff, git_log, web_search, fetch_url, add_memory, manage_todos

⑤ [来源: tool_runtime/policy.py — get_project_policy()]
## 项目工作流（绑定项目时生效）

当你修改项目代码时，必须遵循"改后自验"闭环：

1. 每次调用 write_file 修改代码后，都必须调用 run_command 验证改动没有引入错误：
   - Python 项目：python -m py_compile <改动的文件>
   - 有测试则运行 pytest 或 python -m unittest
   - 前端/TS 项目：npm run lint / npm run typecheck / npm run build
2. 如果验证输出报错，不要结束任务：根据报错修复代码，然后重新运行验证，直到全部通过。
3. 只有在验证通过后，才允许输出最终回答。
4. 完成后用 git diff 或 git status 向用户总结你改了哪些文件。

⑥ [来源: personality.py — get_personality_prompt(75)]
回答时优先检查事实、逻辑和风险。如果用户观点存在问题，应该明确指出。保持专业和直接的态度。

⑦ [来源: tool_runtime/planner.py — ToolPlanner.soft_hint()] ← 有 coding intent 时
## 任务建议（仅供参考，非限制）
当前任务建议优先考虑使用工具: read_file, write_file, list_files, git_status, git_diff。你可以根据实际情况自主决定是否使用或改用其它可用工具。

⑧ [来源: planner/runtime.py — RuntimeTaskContextAdapter.render()] ← 有 task_context 时
## 当前任务计划（Planner V1）
目标: 用户消息首行
步骤: ...
按计划推进；若实际进展与计划不符，请先说明再调整。

⑨ [来源: tool_runtime/guidance.py — get_tool_guidance("coding")] ← coding 意图时
## 工具使用指导 (Tool Guidance)
以下为当前任务类型的工具使用建议，请优先参考但不强制遵循：

### 推荐工具流程
1. 探索阶段：先用 list_files 了解项目结构，再用 read_file 阅读相关代码
2. 修改阶段：用 write_file 写入修改后的代码，每次只改动必要的部分
3. 验证阶段：修改后立即用 run_command 编译/运行验证，确保无语法错误
4. 总结阶段：用 git diff 或 git status 向用户总结改动内容

### 工具使用建议
- 修改代码前必须先用 read_file 读取目标文件的最新内容
- 每次 write_file 后立即用 run_command 验证（如 python -m py_compile 或 npm run build）
- 优先使用项目已有的工具和依赖，不引入冗余第三方库
- 如果验证失败，根据报错信息修正后重新验证，直到通过

### 常见错误提醒
- 禁止在未读取文件的情况下直接修改代码
- 禁止一次修改多个不相关的文件，应逐个修改并验证
- 禁止忽略验证失败的结果，必须先修复再继续
- 禁止猜测文件路径，先用 list_files 确认

⑩ [来源: context_builder.py — _build_attachment_prompt()] ← 有附件时
<!-- ATTACHMENT_CONTEXT_NOTICE: 以下内容已由前端读取并注入内存，请直接基于此内容回答，无需调用任何文件读取工具，也绝对不需要项目路径。 -->
<attachments>
[附件上下文]
[文件: example.py] (src/example.py)
print("hello world")
</attachments>
```

---

### 3.2 General Agent（`agent_id="general"`）— 无项目绑定、非任务型请求

**Agent 数据：**
- `identity`（①层）: `"你是 MfkAgent 的通用助手。专长：日常问答、信息整理、任务执行。交付偏好：简洁直接，根据问题复杂度决定回答深度。边界：不替代专业领域判断；不确定时说明不确定。"`
- `capabilities`（②层）: `["general_assistance"]`
- `personality_level`（⑥层）: `0`

**最终 System Prompt（精简版，无任务型请求时不注入 ⑦⑧⑨⑤）：**

```
⓪ [来源: identity_principle.py]
🛑 【最高身份准则】：
...（同上，全局强制注入）

① [来源: Agent.identity]
你是 MfkAgent 的通用助手。专长：日常问答、信息整理、任务执行。交付偏好：简洁直接，根据问题复杂度决定回答深度。边界：不替代专业领域判断；不确定时说明不确定。

② [来源: capability_profiles.py]
## 能力倾向
- 通用协助：日常问答、信息整理、任务执行，按需调用可用工具。

③ [来源: tool_runtime/policy.py]
## Execution Policy v1
...（同上）

④ [来源: tool_runtime/policy.py]
## 当前会话权限上下文
当前会话无可用工具。

⑥ [来源: personality.py]
回答时优先关注用户感受。不要直接否定用户。即使发现问题，也应该温和表达。你的目标是让用户感受到理解和支持。
```

---

## 四、每个 Prompt 片段来源标记

| 层级 | 片段名称 | 文件路径 | 行号 | 函数/字段 | 注入条件 |
|------|----------|----------|------|-----------|----------|
| ⓪ | 最高身份准则 | `app/core/identity_principle.py` | L7-L18 | `IDENTITY_PRINCIPLE` 常量 | **无条件强制注入** |
| ① | Agent Identity | `app/models/agent.py` → `app/core/agent_runtime/context_builder.py` | L516-518 | `agent.identity or agent.system_prompt or DEFAULT_IDENTITY` | 有 Agent 时 |
| ② | 能力倾向 | `app/core/capability_profiles.py` | L22-L46 | `get_capability_prompt(capabilities)` | `capabilities` 非空时 |
| ③ | 执行规范 | `app/core/tool_runtime/policy.py` | L14-L26 | `get_execution_policy()` | **无条件注入** |
| ④ | 权限上下文 | `app/core/tool_runtime/policy.py` | L29-L59 | `get_permission_context(chat, capabilities)` | **无条件注入** |
| ④b | Plan 模式策略 | `app/core/tool_runtime/policy.py` | L77-L85 | `get_plan_mode_policy()` | `chat.mode == "plan"` |
| ⑤ | 项目上下文 | `app/core/workspace.py` + `policy.py` | workspace.py L34-L43 + policy.py L62-L74 | `get_project_policy()` / `get_default_workspace_context()` | 绑定项目或有 workspace_context |
| ⑥ | 人格 Prompt | `app/services/personality.py` | L3-L23 → L26-L33 | `get_personality_prompt(level)` | `level` 非 None 时 |
| ⑦ | 意图提示 | `app/core/tool_runtime/planner.py` | L25-L49 | `ToolPlanner.soft_hint(intent, tools)` | `tool_context.need_tools == True` |
| ⑧ | 任务计划 | `app/core/planner/service.py` → `runtime.py` | service.py L101-L146 → runtime.py L23-L38 | `PlannerService.plan()` → `RuntimeTaskContextAdapter.render()` | 非 `general_chat` 意图 |
| ⑨ | 工具指导 | `app/core/tool_runtime/guidance.py` | L178-L226 | `get_tool_guidance(intent, project_bound, message)` | 可解析 guidance_type 时 |
| ⑩ | 附件上下文 | `app/core/agent_runtime/context_builder.py` | L279-L359 | `_build_attachment_prompt(attachments, project_path)` | `attachments` 非空时 |
| 独立 | Memory | `app/core/agent_runtime/context_builder.py` | L195-L235 | `_build_memory_text(db, project_id)` | 不入 system prompt，`call_once(memory_text=)` 单独注入 |

---

## 五、关键发现

1. **`system_prompt` 字段仍存在但已降级**：`Agent` 表同时有 `identity` 和 `system_prompt` 两个字段。`identity` 优先，`system_prompt` 仅作 fallback。目前仅 `coder` 和 `writer` Agent 的 `system_prompt` 有旧值，其余 Agent 该字段为空。

2. **Planner 有独立的 LLM 调用**：`LLMPlanner` 使用自己的 `_SYSTEM_PROMPT`（`planner/llm_planner.py:19-45`），与主 Agent 的 system prompt 完全独立。仅在 `planning_level >= 2` 时触发。

3. **Memory 不入 system prompt**：`memory_text` 通过 `model_service.call_once(memory_text=)` 单独注入，由模型层决定如何拼接，不在 `_assemble_prompt` 的 ⓪-⑩ 层中。

4. **Prompt 层数已达 11 层**（⓪-⑩ + Memory），内容密度较高，可能存在 token 冗余。

---

## 六、当前活跃 Agent 列表（数据库实际数据）

| agent_id | name | identity（摘要） | capabilities | personality |
|----------|------|-----------------|--------------|-------------|
| coder | 代码审查 AI | 代码审查与开发专家... | software_development, project_debugging, code_review | 75 |
| writer | 笔神 | 写作与表达专家... | writing, web_research | 25 |
| general | 通用助手 | 通用助手... | general_assistance | 0 |
| analyst | 分析师 | 分析与决策审查专家... | system_analysis, data_analysis | 100 |
| frontend_ui | 前端 UI 设计 AI | 前端 UI 设计与实现专家... | software_development, frontend_design, web_research | 50 |
