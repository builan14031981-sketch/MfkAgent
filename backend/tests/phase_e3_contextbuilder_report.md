# Phase E3 — Context Builder 正式化 交付报告

## 1. 新增文件

| 文件 | 说明 |
| --- | --- |
| `backend/app/core/agent_runtime/context.py` | 独立 Context 系统模块：正式 `AgentContext`（含 Phase E3 结构化字段）+ `AgentResult` |
| `backend/app/core/agent_runtime/context_builder.py` | 重写：保留 `ContextBuilder` 抽象接口（AgentRuntime message 变换钩子，默认 Passthrough），新增 `ChatContextBuilder` / `ContextBuildInput` / `BuiltContext` / `get_chat_context_builder()` 单例 |
| `backend/tests/test_context_builder_phase_e3.py` | E3 自动化验证（7 项用例，真实 DB） |

## 2. AgentContext 结构

`AgentContext`（`app/core/agent_runtime/context.py`）字段按模块职责组织：

- **存储字段（向后兼容）**：`agent_id` / `agent_identity` / `personality_level` / `model_id` / `chat_id` / `project_id` / `project_path` / `memory_context` / `memory_text` / `knowledge_context` / `tools` / `decision`
- **Phase E3 结构化字段**：
  - `capabilities: Optional[list]` — 能力标签（来自 `Agent.capabilities`）
  - `personality: Optional[str]` — 人格 Prompt 文本（personality service）
  - `project_context: Optional[dict]` — `{project_id, project_path, project_name, workspace_context, mode}`
  - `vision_context: Optional[dict]` — **预留**，本阶段恒为 `None`
  - `history: Optional[list]` — 历史消息（当前全量加载，`[{"role","content"}, ...]`）
  - `metadata: Optional[dict]` — `{mode, use_tools, intent}`
- `identity` 为只读 property 别名 → `agent_identity`
- 旧导入路径 `from app.core.agent_runtime.agent import AgentContext` 保持兼容（agent.py 内改为 `from .context import AgentContext, AgentResult`）

`AgentResult` 同步移入 `context.py`（content / usage / rounds / finish_reason / tool_calls / metadata）。

## 3. 原 chat.py 逻辑迁移

以下函数/逻辑从 `app/api/chat.py` 迁至 `context_builder.py`（chat.py 中已删除）：

| 原 chat.py | 现 context_builder.py | 说明 |
| --- | --- | --- |
| `_get_default_model()` | `get_default_model()` | chat.py 保留 `_get_default_model` 转发（test_model_config_phase_d.py:252 依赖） |
| `_get_default_reasoning_effort()` | `get_default_reasoning_effort()` | 已删除原实现 |
| `_get_agent_prompt()` | `build()` 内 ① identity | 取 `agent.identity or agent.system_prompt or DEFAULT_IDENTITY` |
| `_get_agent_capabilities()` | `build()` 内 capabilities | `list(agent.capabilities or [])` |
| `_resolve_workspace()` | `_resolve_workspace()` | Default Workspace 兜底（SimpleNamespace 视图） |
| `_build_memory_text()` | `_build_memory_text(db, project_id)` | 全量拼接（global≤30 + project≤30，XML 包裹） |
| ①-⑧ 内联 prompt 组装 | `_assemble_prompt()` | ⓪ 身份准则 → ① identity → ② capability → ③ execution policy → ④ permission context → ⑤ project/workspace → ⑥ personality → ⑦ intent hint |
| `tool_runtime.process(...)` | `build()` 内 | 用 effective_chat 视图；未绑定项目且无兜底时 `tools_arg=None` |

`chat.py` 的 `send` 与 `/send/stream` 均已改为「commit 用户消息 → `get_chat_context_builder().build(ContextBuildInput(...))` → `runtime.run/run_stream(built.context, built.messages, ...)`」。

## 4. 当前 Context 生成流程

```
Chat API (send / send/stream)
  └─ ChatContextBuilder.build(ContextBuildInput{chat_id, content, model, personality_level,
                                                 use_tools, temperature, max_tokens, reasoning_effort})
       ├─ 1. Agent 身份/能力        ← Agent.identity / Agent.capabilities
       ├─ 2. 人格                  ← get_personality_prompt(level)
       ├─ 3. 项目/工作目录          ← _resolve_workspace(chat, content)（Default Workspace 兜底）
       ├─ 4. Memory               ← _build_memory_text(db, project_id)（模型层注入，不入 system prompt）
       ├─ 5. 工具目录 + 意图        ← tool_runtime.process(effective_chat, capabilities)
       ├─ 6. History              ← Message 全量加载（未来 token budget / compression / window 扩展点）
       ├─ 7. System Prompt ①-⑦    ← _assemble_prompt(...)
       └─ BuiltContext{context: AgentContext, messages, system_prompt, effective_model,
                       temperature, max_tokens, reasoning_effort, read_only, memory_text, tool_context}
```

## 5. AgentRuntime 调用方式

`AgentRuntime` 仍持 `ContextBuilder` 抽象接口（透传 message 变换钩子，默认 `PassthroughContextBuilder`），执行签名不变：

```python
runtime = AgentRuntime()
result = await runtime.run(
    context=built.context, messages=built.messages,
    temperature=built.temperature, max_tokens=built.max_tokens,
    reasoning_effort=built.reasoning_effort, read_only=built.read_only,
)
# 流式：
async for event in runtime.run_stream(context=built.context, messages=built.messages, ...):
    ...
```

`memory_text` 通过 `call_once/stream_once(memory_text=...)` 在模型层注入（首轮），不入 system prompt。

## 6. 测试结果

E3 新增（`test_context_builder_phase_e3.py`）：**7/7 通过**

| 用例 | 结果 |
| --- | --- |
| AgentContext 结构字段 | PASS |
| system prompt ①-⑦ 层组装 | PASS |
| memory_text 全量拼接 | PASS |
| 无项目+文件操作→Default Workspace | PASS |
| 无项目+非文件操作→工具禁用 | PASS |
| plan 模式→read_only | PASS |
| use_tools=False→禁用工具 | PASS |

回归（全部通过）：

| 套件 | 结果 |
| --- | --- |
| test_runtime_event_phase_e2.py | 5/5 PASS |
| test_agent_runtime_phase3.py | 7/7 PASS |
| test_tool_runtime_phase_a.py | PASS |
| test_tool_runtime_phase_b1.py | 4/4 PASS |
| test_tool_runtime_phase_c.py | 5/5 PASS |
| test_model_config_phase_d.py | 7/7 PASS |

修复说明：回归首轮曾因 chat.py 移除 `Agent` 导入后 `create_chat`（人格快照）引用残留报 `NameError`，已恢复 `Agent` 导入。

## 7. 下阶段建议

1. **History 窗口化 / token budget**：`history` 字段与 `ContextBuilder` 钩子已就位，可在 AgentRuntime 层按 token 预算裁剪，为压缩做准备。
2. **Memory 重构**：`memory_text` 全量拼接逻辑暂存 `context_builder._build_memory_text`，未来独立为 Memory Service（分页 / 相关性排序）。
3. **Vision 接入**：`vision_context` 字段已预留，后续 Vision Phase 由 builder 填充图片输入即可，`_assemble_prompt` 无需改动。
4. **Multi-Agent / Planner**：`metadata` 可承载 mode 差异；Planner 的 `soft_hint` 当前由 builder 在 ⑦ 层调用，后续可下沉为正式规划层。
5. **性能**：`build()` 内 Chat / Agent / History / Memory 为串行查询，可并行化（`asyncio.gather` + 独立 session）。
