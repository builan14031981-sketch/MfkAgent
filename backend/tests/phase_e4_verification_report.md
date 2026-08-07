# Phase E4 — Verification 基础验证框架 交付报告

## 1. 新增文件

| 文件 | 说明 |
| --- | --- |
| `backend/app/core/verification/__init__.py` | 模块出口：`VerificationResult` / `PASSED` / `FAILED` / `NEED_RETRY` / `Verifier` / `verifier` / `VERIFIERS` |
| `backend/app/core/verification/models.py` | `VerificationResult` 数据类 + 状态常量 + `to_dict()` 序列化 |
| `backend/app/core/verification/strategies.py` | 验证策略：`verify_write_file` / `verify_run_command` / `default_verify` + `VERIFIERS` 路由表 |
| `backend/app/core/verification/verifier.py` | `Verifier` 调度器（按工具名路由，未知工具默认通过）+ 全局单例 `verifier` |
| `backend/tests/test_verification_phase_e4.py` | E4 自动化验证（7 项用例：策略单元 + 流式/非流式集成） |

## 2. VerificationResult 设计

`VerificationResult`（`models.py`）：

```python
@dataclass
class VerificationResult:
    status: str = PASSED        # "passed" | "failed" | "need_retry"
    message: str = ""           # 可读说明（注入 LLM 反馈 / 事件透传）
    evidence: dict = {}         # 结构化证据（exit_code / path / size / output 等）
    strategy: str | None = None # write_file / run_command / default
    tool: str | None = None     # 工具名
    tool_call_id: str | None = None

    @property
    def passed(self) -> bool: ...
    def to_dict(self) -> dict: ...
```

状态语义：
- **passed**：验证通过 → Runtime 正常继续 / 结束。
- **need_retry**：动作已发生但结果不符合预期（如命令非零退出、文件内容不一致）→ 注入反馈，下一轮重新执行。
- **failed**：动作本身未达成（文件未创建 / 无法解析退出码）→ 注入反馈，下一轮修正。

## 3. Runtime 接入位置

`backend/app/core/agent_runtime/agent.py`：

- `AgentRuntime.__init__(context_builder=None, verifier=None)`：新增 `self.verifier`（默认全局单例，可注入替换）。
- 新增 `_exec_tool_calls_with_verification(...)`：包装原 `_exec_tool_calls`，透传工具事件之外追加 `verify_result` / `verification_failed` 事件。
- 非流式 `run()`：工具执行块（原 291 行区域）改走 `_exec_tool_calls_with_verification`。
- 流式 `_run_stream_events()`：结构化 tool_calls 与 Normalizer 两条执行路径均改走 `_exec_tool_calls_with_verification`。

接入点逻辑：
```
_exec_tool_calls（执行 + 回喂）
  → verifier.verify_all(本轮 status=="success" 的 records, project_path)
  → 全部 passed：不注入，流程继续
  → 存在 failed/need_retry：
      - 注入 current_messages {"role":"user","content":"【验证反馈】..."}
      - 下一轮 LLM 据此重新执行（Action → Verify → Retry）
```

验证结果经 `runtime_event_recorder` 与其它事件一并持久化（`verify_result` 事件类型），前端可实时展示。

## 4. 当前执行流程

```
旧：Action → Finish
  Tool执行完成 → 下一轮 LLM（无验证）

新：Action → Verify → Continue / Retry
  Tool执行完成
    → Verification（程序验证优先，LLM 不自行判定）
        ├─ passed      → 继续下一轮 / 结束
        ├─ need_retry  → 注入【验证反馈】→ 下一轮重新执行
        └─ failed      → 注入【验证反馈】→ 下一轮修正
```

第一版验证能力：
- **write_file**：重读磁盘校验「文件是否存在 + 内容是否一致」。
- **run_command**：解析结果内嵌 `[exit code N]`，0 → passed；非零 → need_retry。
- **其它工具**：默认 `default` 策略直接通过（skip/pass，不阻塞）。

## 5. 测试结果

E4 新增（`test_verification_phase_e4.py`）：**7/7 通过**

| 用例 | 结果 |
| --- | --- |
| 验证策略单元（write_file/run_command/default/verify_all 过滤） | PASS |
| 流式 write_file 通过（自动审批 → 落盘 + verify_result passed） | PASS |
| 流式 run_command 退出码 0 → passed | PASS |
| 流式 run_command 非零 → need_retry + verification_failed + 反馈注入下一轮 | PASS |
| 流式 普通工具默认通过（strategy=default） | PASS |
| 非流式 run_command 退出码 0 → 通过，无反馈 | PASS |
| 非流式 run_command 非零 → 【验证反馈】注入下一轮 call_once 消息 | PASS |

回归（全部通过）：

| 套件 | 结果 |
| --- | --- |
| test_runtime_event_phase_e2.py | 5/5 PASS（tool_events 事件数 5→6，新增 verify_result，属预期增量） |
| test_agent_runtime_phase3.py | 7/7 PASS |
| test_tool_runtime_phase_a.py | PASS |
| test_tool_runtime_phase_b1.py | 4/4 PASS |
| test_tool_runtime_phase_c.py | 5/5 PASS |
| test_model_config_phase_d.py | 7/7 PASS |

## 6. 下一阶段建议

1. **验证策略扩展**：git diff/status 一致性校验、测试运行器（pytest/npm test 封装）、资源泄漏检查；新增策略只需在 `strategies.VERIFIERS` 注册。
2. **失败收敛（防无限重试）**：为同一 tool_call 的连续 need_retry 计数，达到阈值后降级为明确失败并停止本轮，避免循环消耗轮次预算。
3. **Verification 结构化入库**：`verify_result` 事件已随 RuntimeEvent 持久化，可将失败证据回写 `AgentRun`/Message timeline，供前端展示验证链路。
4. **验证独立于执行的环境态**：write_file 重读依赖文件系统最终状态，未来可扩展到「目标状态比对」（如期望 diff / 期望测试通过集合）。
5. **Planner 联动**：验证失败时可由 Planner 决策重试策略（改参数重跑 / 换工具 / 放弃），将「Verification → Decision」从固定注入升级为规划驱动。
