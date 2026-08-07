# MfkAgent Phase E1 交付报告

> 阶段：Phase E1 — Unified Agent Runtime Execution Pipeline（统一 Agent Runtime 执行链路）
> 目标：将 AgentRuntime 设为唯一执行入口，剥离 ModelService 的执行循环职责
> 状态：**完成，验证通过（Phase A / B-1 / C / 3 全绿）**
> 日期：2026-08-06

---

## 1. 修改文件

| 文件 | 变更 | 说明 |
|------|------|------|
| `backend/app/services/model.py` | 重构 | 删除 `chat()` / `chat_stream()` / `_chat_openai_compatible()` / `_exec_tool_calls()` / `_normalizer_feedback()` / `_inject_memory_text()` / `_log_memory_injection()`；清理 tool_runtime imports；新增 `stream_once()` |
| `backend/app/core/agent_runtime/agent.py` | 重构+扩展 | `run()` 收敛到纯执行循环；新增 `run_stream()` 流式执行循环；新增 `_exec_tool_calls()` / `_normalizer_feedback()` / `_to_dict_messages()`；Context Builder 接入；`MAX_STREAM_ROUNDS=8` |
| `backend/app/core/agent_runtime/context_builder.py` | 新增 | `ContextBuilder` 接口 + `PassthroughContextBuilder` 透传实现 + `get_default_context_builder()` |
| `backend/app/core/agent_runtime/__init__.py` | 扩展 | 导出 ContextBuilder 系列 |
| `backend/app/api/chat.py` | 修改 | 流式 `/send/stream` 改走 `AgentRuntime.run_stream()`（Context 组装仍内联，仅换执行入口） |
| `backend/app/api/models.py` | 修复 | `/chat` → `call_once()`；`/chat/stream` → `stream_once()` |
| `backend/test_models.py` | 适配 | `model_service.chat` → `call_once()` |
| `backend/tests/test_tool_runtime_phase_c.py` | 适配 | 非流式审批用例改用 `AgentRuntime.run()` |

## 2. 旧 / 新调用链

**旧链路（执行循环散落在 ModelService）：**

```
chat.py send（非流式）  → AgentRuntime.run()  → model_service.call_once()
chat.py /send/stream    → model_service.chat_stream()  ← while(max_tool_rounds=8) 内置工具环
model_service.chat()    → _chat_openai_compatible()    ← 内置工具环（遗留）
```

- ModelService 同时承载「单次 LLM 调用」+「多轮工具执行循环」+「归一化」三份职责。
- `chat_stream()` 的 8 轮工具环、事件透传、审批闭环、normalizer 兜底全部耦合在 model 层。
- 遗留 `chat()` / `_chat_openai_compatible()` 是第二份重复的工具环，维护成本高、易漂移。

**新链路（唯一执行入口 = AgentRuntime）：**

```
Chat API ──▶ AgentRuntime.run() / run_stream()
                │
                ├─▶ ContextBuilder.build()（Phase E1 透传）
                ├─▶ Execution Loop（round 0..N，工具轮预算控制）
                │     ├─▶ model_service.call_once() / stream_once()   ← 只做单次 LLM 调用
                │     └─▶ _exec_tool_calls() → execute_tool / complete_approval / normalizer
                └─▶ yield 事件流（text/thinking/tool_start/tool_result/tool_approval/tool_calls/finish/error）
```

- **ModelService 只剩原子能力**：`call_once()`（非流式单次）+ `stream_once()`（流式单次）+ 模型配置管理。
- **AgentRuntime 成为执行编排唯一入口**：任务路由、工具轮预算、工具执行、审批闭环、归一化兜底、事件透传。
- Context Builder 建立接口位（暂透传），后续 Phase 可注入真实上下文组装。

## 3. AgentRuntime 职责（Phase E1 后）

- `run()`：非流式执行循环（`MAX_ROUNDS=3`，保持 Phase 3 行为），工具执行、审批显式拒绝（非流式不支持审批）。
- `run_stream()`：流式执行循环（`MAX_STREAM_ROUNDS=8`，对齐旧 `chat_stream` 轮次预算），逐轮：
  1. `stream_once()` → 透传 text/thinking，收集结构化 tool_calls 与 finish_reason；
  2. 结构化调用 → `_exec_tool_calls()`（含审批闭环）→ 回喂结果 → 继续；
  3. 无结构化调用但有文本 → normalizer 归一化非标准调用（XML invoke / 文本调用）；
  4. 归一化失败 → `_normalizer_feedback()` 结构化回馈，不静默；
  5. 轮次耗尽 → 补一次无工具收尾请求，保证必有总结。
- `_exec_tool_calls()`：assistant tool_calls 消息 + 逐工具执行 + 事件透传 + 审批等待/拒绝。
- 保持 SSE 协议与旧 `chat_stream()` 完全兼容（顶层 `type` 信封）。

## 4. ModelService 职责（Phase E1 后）

- 只做**单次** LLM 调用：`call_once()` / `stream_once()`。
- 不负责：工具循环、轮次判断、行为决策、工具执行、审批、归一化。
- Memory 注入仍留在 model 层（仅首轮注入 system 消息），与旧行为一致。
- `stream_once()` 的 yield 协议：`text` / `thinking` / `tool_calls`(本轮有序原始调用) / `finish`。

## 5. 是否影响前端

**否。** 前端 SSE 协议（text / thinking / tool_start / tool_approval / tool_result / finish / tool_calls 汇总）未变：

- `useChatStream.ts` / `useMessages.ts` 的事件消费逻辑无需改动；
- `/api/chat/{id}/send` 与 `/api/chat/{id}/send/stream` 的请求/响应契约不变；
- `/api/models/chat`、`/api/models/chat/stream` 响应结构不变（非流式补齐 `ChatResponse` 组装，原直接返回内部对象）。

## 6. 验证

| 测试 | 结果 |
|------|------|
| `compileall`（backend 全量） | ✅ PASS |
| `test_agent_runtime_phase3.py`（7 项） | ✅ 7/7 |
| `test_tool_runtime_phase_a.py`（工具调用闭环） | ✅ 5 项 PASS |
| `test_tool_runtime_phase_b1.py`（审批闭环 4 项 + 残留警告为测试自身手工注册 artifact） | ✅ 4/4 |
| `test_tool_runtime_phase_c.py`（normalizer + 非流式审批拒绝 5 项） | ✅ 5 项 PASS |

## 7. 下一步建议（Phase E2+）

1. **Context Builder 落地**：实现真实上下文组装（历史截断 / token 预算 / 文件上下文 / worktree 识别）。
2. **Verification（自验）闭环**：在 AgentRuntime 层加入「工具执行后自验」阶段。
3. **规划器 / Multi-Agent**：Planner 接入执行循环（当前仅 soft_hint 提示词注入）。
4. **Vision 能力**：模型层透传图片输入。
5. **清理遗留**：删除 `model_service.chat` / `chat_stream` 的所有历史引用（docs 中的描述性文本），统一文档为 Phase E1 新链路。
