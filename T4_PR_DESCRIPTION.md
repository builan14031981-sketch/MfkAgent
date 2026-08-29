# T4 双循环合一：run_stream() 成为唯一执行实现

## 一、run() 调用方全量清单（动手前核实，硬前置交付）

全仓 `AgentRuntime` 实例化点仅 3 处（`grep -rn "AgentRuntime()" app/`，排除 `*.backup` 归档）：
`api/chat.py:827`（非流式 /send）、`api/chat.py:1208`（流式 /send）、`api/chat.py:1501`（compress_history，非执行循环）。
`.run(` 真正命中 `AgentRuntime.run` 的调用方共 **2 处**：

| # | 调用方 | 位置 | 对返回值 `AgentResult` 的依赖 | 兼容性结论 |
|---|---|---|---|---|
| 1 | 非流式 `/send` 端点 `send_message` | `api/chat.py:828` | `.content` → 落库 assistant Message、V14.1 动作守卫 regen、记忆提取输入；`.usage` → `SendResponse.token_usage`（仅判 dict 的 `total_tokens`）；`.tool_calls` → timeline 构造（tool_start/tool_result 对）；异常 → 兜底文案 `"[AI回复失败]"` | 聚合器按同结构重建，本单在此端点加 pending_approval 契约 |
| 2 | 子代理 `execute_sub_agent` | `services/sub_agent.py:176` | 仅 `.content`（空时兜底 `"[子代理执行完成，无返回内容]"`）；异常 → `SubAgentError` | 不改动该文件，聚合结果天然兼容 |

**显式排除的疑似调用方（逐一确认非 AgentRuntime.run）**：
- `api/chat.py:722` 与 `api/chat.py:1022` 的 `await rt.run(_emit)` → `RoundtableRuntime.run`（`app/core/roundtable_runtime.py`，圆桌自有实现，不经 AgentRuntime）；
- `api/chat.py:1501` 的 `AgentRuntime()` → 调用 `compress_history`（摘要函数），非执行循环；
- TaskGraph / orchestrator：不是独立调用方——TaskGraph 循环在 `run()`/`run_stream()` **内部**（`context.plan` 驱动 `init_task_graph`），planner 仅注入 Plan（`app/core/planner/`，不调 run）；
- `services/sub_agent_tool.py`、`orchestrator_tool.py`、`autotask.py`、`workflow.py`：无 AgentRuntime 调用（grep 证实）。

**测试侧 mock 面（结构性适配点）**：patch `model_service.call_once` 且调用 `run()` 的测试共 4 个文件——`test_task_graph_stabilization_phase_g4c.py`、`test_runtime_task_graph.py`、`test_completion_exhausted_path.py`、`test_completion_loop.py`。合一后 `run()` 内部走 `stream_once`，这 4 个文件的 run 路径 mock 改为流式事件形状（断言语义不变）。

## 二、改动内容

1. **`agent.py`**：
   - `run()` 重写为 `run_stream()` 的事件流消费者：drain 事件（协议全集见现状文档 3.5）聚合出兼容 `AgentResult`（content/usage/rounds/finish_reason/tool_calls/metadata）；
   - 非流式审批契约：遇 `tool_approval` 立即返回 `finish_reason="pending_approval"` + `metadata.pending_approval`（approval_id/tool/tool_call_id/command/risk_level/risk_reason），**不同步等待**（旧行为是 resolve cancelled 拒绝执行，已废除）；审批条目留在 `approval_registry` 由前端 `POST /{chat_id}/approve` 闭环，后台续跑任务等审批 Future 后继续执行至收尾，完整结果经可选 `on_complete` 回调交付；
   - 抉择卡（`choice_request`）沿用旧契约：非流式自动采纳推荐项（resolve `{"selected": None, ..., "note": ...}`），不挂起；
   - 旧 `run()` 循环体整体移入 `_legacy_run.py`（`legacy_run(self, ...)`，保留一个发布周期，期满删除；运行时不引用）；
   - TaskRouter 统一：`_run_stream_events` 在 context build 后调用一次 `self.router.route(...)`，决策仅写入 `context.metadata`（task_type/intent/confidence/reason），不改变执行路径；
   - 聚合所需的 usage/completion 汇总由统一实现写入 `context.metadata` 私有键（`_t4_usage`/`_t4_completion`，消费端读取后剔除），**不改 SSE yield 协议**（无新事件类型、无信封字段变更）。
2. **`api/chat.py`（仅非流式 /send）**：`SendResponse` 增加可选 `pending_approval` 字段；pending 时落库占位 assistant 消息（timeline 含审批卡），后台续跑完成后更新同一条消息（含记忆提取），避免双消息。
3. **`turn_reminder` 单次包裹**：包裹点只保留统一实现内的一处（`_run_stream_events`），`run()` 作为消费者不再包裹；新增测试断言无重复包裹。

## 三、回滚

单分支单 revert（`revert feat/t4-unify-loop` 合并提交即可）；`_legacy_run.py` 兜底一个发布周期。

## 四、聚合语义映射（统一后 content/metadata 的消费端口径）

run() 作为事件流消费者，聚合策略在个别点上与旧实现的"末轮覆写"对齐（均为消费端策略，不涉及流式行为变更）：

1. **content = 非被驳回文本 + 收尾汇报**：完成验证驳回（completion_verify_failed）后的重试文本不叠加累计（对齐旧实现 task_content 末轮覆写）；TaskGraph 逐任务覆写（task_started 重置，最后一个任务的内容胜出，与旧实现一致）；空回复兜底文案沿用旧口径。
2. **耗尽路径（软性缺失）**：统一实现（run_stream）在验证耗尽时 yield 结构化失败汇报文本——旧 run 实现是保留原模型内容不替换。统一后非流式 content 为该汇报（验证结论仍由 metadata.completion.verified 承载）；对应测试断言已更新（test_completion_exhausted_path.py::test_soft_missing_keeps_content，T4 注记在案）。
3. **metadata.completion / usage**：由统一实现写入 context.metadata 私有键（_t4_completion/_t4_usage）交付消费者，SSE 事件协议零变更；agent_id/model_id/personality_level/task_type/intent/confidence/reason/token_watermark/task_graph 等键全部保留。
4. **测试 mock 面适配（断言语义不变，5 个文件）**：主循环模型调用从 call_once 统一为 stream_once（judge/反思/压缩等内部单次调用仍走 call_once，测试双面 mock）。适配文件：test_phase11_self_check.py、test_runtime_task_graph.py、test_task_graph_stabilization_phase_g4c.py、test_completion_exhausted_path.py、test_completion_loop.py、test_self_healing_phase_g4e.py（仅 run 场景补 stream_once 抛错 generator）。共享适配器：tests/_t4_mock_adapter.py。

## 五、验证结果（本机，T7 修复后全量口径）

| 指标 | 合并后 master 基线 | feat/t4-unify-loop |
|---|---|---|
| 全量 pytest | 53 failed / 965 passed / 1 skipped / 70 errors | 53 failed / 974 passed / 1 skipped / 70 errors |
| 逐文件签名（202 模块） | — | **除新增 test_t4_unify_loop 6 个类外逐文件完全一致，零新增失败** |
| 新增测试 | — | tests/test_t4_unify_loop.py 9 项全绿（审批契约×2 / turn_reminder×2 / TaskRouter×1 / 聚合×2 / 抉择×1 / 结构×1） |

- 基线与本单签名存档：E:\智慧项目\mfk-baseline_signature.json（仓库外）、t4_signature.json（worktree）。
- 注：53F/70E 为既有环境噪声（本机部分 async 测试缺 asyncio 标记在 strict 模式下不执行、模型配置依赖本地 DB 等），两轮数字逐文件一致。

### 三条路径回归

1. **TaskGraph**：直接覆盖最充分——test_runtime_task_graph / test_task_graph_stabilization_phase_g4c / test_self_healing_phase_g4e / test_task_graph_builder 全绿且签名与基线一致。
2. **子代理**（services/sub_agent.py:176）：**存量无直接测试**（grep 全 tests/ 无 execute_sub_agent 调用，属既有欠账）。其唯一依赖 `.content`（空时兜底文案），兼容性由聚合测试与 run() 路径回归间接覆盖。
3. **圆桌**（RoundtableRuntime）：调用链独立于 AgentRuntime（圆桌自有 run，不经 run/run_stream），本单零触碰；存量亦无直接测试，回归风险为零。

## 六、回滚

单分支单 revert（`revert` feat/t4-unify-loop 的合并提交即可）；`_legacy_run.py` 兜底一个发布周期。
