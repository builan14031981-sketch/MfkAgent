# MfkAgent Agent Prompt Architecture 审计报告

> 审计日期：2026-08-09
> 范围：仅审查，不修改代码

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
  │     └── prune_thought_history