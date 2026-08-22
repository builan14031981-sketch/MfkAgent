# MfkAgent Autonomous Completion Loop V1 — 实现报告

> 目标：Agent 在「LLM 停止调用工具」后走完成验证（Tool → Rule → LLM Judge 三层），
> 失败生成反馈重新进入 Agent Loop（上限 3 次）；TaskGraph 节点完成必须过验证。
> 全程增量扩展，未重写 Planner / Tool Runtime / Memory / ContextBuilder / UI。

## 一、变更文件

### 本次会话新增
| 文件 | 说明 |
|---|---|
| `backend/app/core/agent_runtime/completion/models.py` | 数据模型：`CompletionContext` / `CompletionVerificationResult` |
| `backend/app/core/agent_runtime/completion/base.py` | `CompletionVerifier` 抽象基类 |
| `backend/app/core/agent_runtime/completion/tool_check.py` | 工具层验证（复用 Phase E4 程序化 Verifier） |
| `backend/app/core/agent_runtime/completion/rules.py` | 规则层验证（2 条内置规则） |
| `backend/app/core/agent_runtime/completion/llm_judge.py` | LLM Judge 层（JSON 解析容错） |
| `backend/app/core/agent_runtime/completion/pipeline.py` | 三层验证管道（任一失败即短路） |
| `backend/app/core/agent_runtime/completion/__init__.py` | 包导出 |
| `backend/tests/test_completion_loop.py` | 4 个用例：成功完成 / 失败继续 / 最大重试保护 / TaskGraph 节点状态 |

### 本次会话修改（均落在 agent_runtime 内部）
| 文件 | 改动 |
|---|---|
| `backend/app/core/agent_runtime/agent.py` | 主循环接入完成验证（`run`/`run_stream`）、`DEFAULT_MAX_COMPLETION_RETRY=3`、辅助方法、事件、metadata |
| `backend/app/core/agent_runtime/states.py` | 注册 `COMPLETION_VERIFY_STARTED/PASSED/FAILED` |
| `backend/app/core/agent_runtime/context.py` | `AgentContext` 新增 `completion_verification`、`max_completion_retry` 配置 |

### 工作区预存在未提交改动（非本会话）
`backend/app/api/chat.py`、`context_builder.py`、`expressions.py`、`persona_engine.py`、
`services/memory_extractor.py` 及根目录若干调试/报告文件。**本次未触碰。**

## 二、架构

```
LLM 停止调用工具（完成候选点）
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  CompletionPipeline（三层验证，任一失败即短路）        │
│  1. Tool   复用 Phase E4 程序化 Verifier 复核工具结果 │
│  2. Rule   确定性规则（final_content_present / write_detected）│
│  3. Judge  可选 LLM Judge（仅 completion_verification=True 时启用）│
└─────────────────────────────────────────────────────┘
        │ 通过                                    │ 失败
        ▼                                        ▼
 completion_verify_passed ──► 任务完成         生成反馈（missing/reason/suggestion）
        │                                        │
        ▼                                        ▼
 TaskGraph 节点 completed                  注入 user feedback 消息
 (task_completed 带 completion_verified)    continue 重进 Agent Loop
                                             │
                                  retry_count < 3 → 再验证
                                  retry_count ≥ 3 → completion_exhausted（安全收尾）
```

## 三、实现要点

- **启用语义** `context.completion_verification`：`True`=显式启用（含 LLM Judge）；`False`=禁用；`None`=默认（有 TaskGraph 时启用，且 pipeline 不含 Judge，只走 Tool+Rule）。
- **完成候选点**：无 tool_calls 的非自查分支（Phase 12），以及轮次耗尽后的兜底总结（失败不再重试）。
- **三层短路**：任一失败立即 `return`；`evidence.chain` 记录各层判定，`failure_layer` 标记失败层。
- **重试保护**：`max_completion_retry`（默认 3）。超限 → `finish_reason="completion_exhausted"`，保留已完成内容 + 未完成原因 + 最后失败点（写入 `AgentResult.metadata["completion"]`）。
- **事件**：`completion_verify_started/passed/failed`；TaskGraph 的 `task_completed/task_failed` 附加 `completion_verified`/`completion_reason` 字段。
- **LLM Judge 规范**：返回 JSON `{completed, reason, missing, suggestion}`；`parse_judge_json` 容忍 markdown 围栏与修饰文本；调用失败按 failure 处理、不抛异常。
- **状态体系**：复用既有 `RuntimePhase/VERIFYING` 与 `TaskNodeStatus`，不新建重复状态。

## 四、测试结果

| 测试 | 结果 |
|---|---|
| `tests/test_completion_loop.py`（新增 4 用例） | **4 passed** |
| `tests/test_agent_runtime_phase3.py`（回归，原生 runner） | **7 passed** |
| `tests/test_runtime_task_graph.py` 其余用例 | passed |
| `tests/test_verification_loop.py` | passed |

### 遗留（预存在失败，与本会话无关）
- `test_runtime_task_graph.py::TestModelContextConfig::{test_compute_watermark, test_known_model_exact_match}`：
  断言 `deepseek-chat` 上下文为 64K，但 `model_context_config.py` 现默认 256K（registry 亦无 `deepseek-chat`）。
  该文件本会话未修改。
- `test_agent_runtime_phase3.py` 在 pytest 下报「async def not supported」：测试文件自带 `run_all_tests()` 入口，
  需 `python tests/test_agent_runtime_phase3.py` 运行（已通过），与 pytest 无 asyncio 插件有关。

## 五、当前限制

- LLM Judge 层依赖真实模型（默认 `qwen-flash` 轻量模型，未做真实 API 集成测试；单测全部 mock）。
- 规则层仅 2 条通用规则；领域规则需调用方通过 `extra_rules` 注入。
- 流式路径（`run_stream`）已完成接线，但本次测试覆盖非流式主路径 + TaskGraph 非流式；流式事件流未单独建测。

## 六、下一步建议

1. 修复 `TestModelContextConfig` 两个陈旧断言（对齐 256K 默认 / 注册表）。
2. 为 `run_stream` 完成验证路径补流式事件断言。
3. 真实环境冒烟：`completion_verification=True` 时验证 Judge 返回结构解析与重试反馈的对话质量。
4. 将验证失败反馈文案与 retry 阈值改为可配置（`AgentContext` 已支持）。
