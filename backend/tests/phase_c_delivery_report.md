# MfkAgent Phase C 交付报告

> 阶段：Phase C — Agent Intelligence Stabilization（Agent 智能稳定性加固）
> 目标：解决模型非标准工具调用静默失败、非流式审批泄漏、旧阶段 Prompt 限制
> 状态：**全部完成，V1 Runtime 冻结基线**
> 日期：2026-08-05

---

## 1. C-1 Tool Call Normalizer

### 1.1 背景与问题

审计（Phase C-0）确认 Q2 问题：模型（deepseek-v4-flash）在流式路径上有时会输出 **非标准格式** 的工具调用，包括：

- Anthropic 风格 XML：`<invoke name="X">JSON</invoke>`
- 通用 XML：`<tool_call><name>..</name><arguments>..</arguments></tool_call>`
- 明确文本：`调用 run_command: ipconfig`（块状 / 行内）
- 甚至带 ```` ```json ```` 围栏的 JSON

旧管线只识别 OpenAI 结构化 `tool_calls`，其余一律 **静默丢弃** → 用户看到"模型说要执行但什么都没发生"。

### 1.2 实现（新增 `backend/app/core/tool_runtime/normalizer.py`）

核心函数：

```python
normalize_tool_call_text(content: str, available_tools: set) -> {"calls": [...], "issues": [...]}
```

识别范围（宁缺毋滥，只认明确格式）：

| 格式 | 示例 | 说明 |
|------|------|------|
| `<invoke name="X">…</invoke>` | `<invoke name="run_command">{"command":"ipconfig"}</invoke>` | Anthropic 风格 |
| `<tool_call><name>…</name><arguments>…</arguments></tool_call>` | git_status | 通用 XML |
| `<tool>` 变体 | `<tool>run_command</tool>` | 简化标签 |
| 文本块 | `调用 run_command:\nipconfig` | 明确引导词 |
| 文本行内 | `调用 run_command: ipconfig` | 单行 |
| JSON 围栏 | ```` ```json {…} ``` ```` | 支持包裹 |

关键设计：

- **不静默**：解析失败 → 记入 `issues`，由 `_normalizer_feedback()` 构造结构化错误文本回喂模型重新生成。
- **run_command 裸文本 fallback**：非 JSON 参数直接作为 `command`。
- **参数校验**：`write_file` 等工具非 JSON 参数 → issue，不猜测。

### 1.3 集成（`backend/app/services/model.py`）

- 新增 `_exec_tool_calls()`：统一承载结构化 + 归一化的工具执行、事件透传、审批闭环。
- 新增 `_normalizer_feedback(issues)`：解析失败结构化回馈，禁止静默。
- **流式路径**（`chat_stream`）：每轮累积 `round_text`，无结构化 `tool_calls` 但有文本时做归一化；`calls` 命中 → 执行并 `continue`；`issues` 存在 → 回馈错误 `continue`。
- **非流式路径**（`_chat_openai_compatible`）：同样接入归一化。

### 1.4 F2 非流式审批泄漏修复

原问题：非流式路径遇 `awaiting_approval` 用空 `result` 回喂模型 → 模型把空结果当"执行成功"继续，审批泄漏且结果失真。

修复（`model.py:697-708`）：非流式路径遇审批 → `resolve(id,"cancelled")` + `remove(id)`，构造显式拒绝结果 `"错误: 该操作需要用户审批，但非流式接口不支持审批，已拒绝执行。"` 回喂，审批注册表无残留。

---

## 2. C-2 Benchmark 三项真实验收

> 环境：真实 uvicorn（127.0.0.1:8001）+ 真实 deepseek-v4-flash + 自动审批驱动，无 mock。
> 工作目录：`C:\Users\Asus\AppData\Local\Temp\acc_phasec_fxfxlqnq`

### T1 项目修复

**任务**：`我的 Python 项目启动失败，帮我检查并修复`

| 指标 | 值 |
|------|-----|
| 耗时 | 9.9s |
| 工具序列 | list_files → read_file×3 → run_command → write_file → run_command×3 |
| 审批数 | 3（`python main.py`×2、write_file） |
| 结果 | ✅ 定位 `helper.py` NameError（`print(missing_var)`）→ 删除 → `python main.py` 退出码 0 |

**观察**：Agent 自主完成 查结构 → 读代码 → 跑验证 → 修复 → 再验证 完整闭环；模型曾尝试 `python -m py_compile ... && python main.py` 被注入防护拒绝后自动拆成两条命令继续，恢复良好。

### T2 网络诊断

**任务**：`我的代理配置可能有问题，帮我排查`

| 指标 | 值 |
|------|-----|
| 耗时 | 12.1s |
| 工具序列 | run_command×15（全命令） |
| 审批数 | 4 |
| 结果 | ✅ 只读诊断，最终以 netsh/reg/curl 完成排查 |

**观察**：Windows 环境误发 `echo/env/printenv/grep/printenv` 等 Unix 命令（报"找不到命令"后自适应切回 Windows 命令）；模型在总结段输出过一次 `<invoke name="run_command">curl …</invoke>` XML，被 normalizer 识别执行 —— **验证了 C-1 在真实场景生效**。

### T3 项目优化

**任务**：`帮我优化这个项目性能`

| 指标 | 值 |
|------|-----|
| 耗时 | 13.9s |
| 工具序列 | list_files → read_file×2 → write_file → run_command×2 → git_diff |
| 审批数 | 2（write_file、python app.py） |
| 结果 | ✅ 改写为 v1 loop / v2 listcomp / v3 map 三版本 + 基准对比（23% 提速）+ 编译验证 |

**观察**：完整的 分析 → 找瓶颈 → 改造 → 实测验证 → 总结 闭环。

### C-2 结论

三条真实任务全部成功闭环，验证了 V1 的 执行-审批-回馈 核心链路在真实模型下稳定工作。

---

## 3. C-3 Prompt / Policy 优化

### 3.1 删除死代码

`chat.py` 中 `_VERIFY_WORKFLOW_PROMPT`（约 10 行）已删除，全仓库确认无残留引用。

### 3.2 run_command 描述修正

`backend/app/core/command_tools.py`：

- 旧：暗示"只读命令"，误导模型。
- 新：`执行系统命令。支持两类场景：… 只读命令自动执行；危险或修改性操作（写文件、安装、删除等）会先请求用户确认，批准后才会执行。` 参数描述同步去掉"只读命令"字样。

### 3.3 Agent 行为规范（`backend/app/core/tool_runtime/policy.py`）

`get_default_policy()` 新增五条强制规范（注入 System Prompt 末尾）：

1. 优先使用工具获取真实信息，不猜测环境状态；无法获取时明确说明。
2. 修改文件前先读上下文（相关文件内容 / git 状态），避免盲目覆盖。
3. 需要修改或执行有副作用操作时，先简要说明计划。
4. 危险操作会先请求用户审批；审批通过后才继续，等待审批结果，不重复发起同一调用。
5. 完成任务后用简短摘要总结做了什么、结果如何。

---

## 4. 全部测试结果汇总

| 套件 | 用例数 | 结果 | 说明 |
|------|--------|------|------|
| Phase A | 5/5 | ✅ PASS | 网络诊断、read_file、git_status、write_file、持久化 |
| Phase B-1 | 4/4 | ✅ PASS | 审批批准执行 / 拒绝 / plan 拒绝 / API 状态码 |
| Phase B-2 | 6/6 | ✅ PASS | 权限目录、只读自动、git_commit 审批、write_file plan 拒绝、注册表无残留 |
| Phase C | 5/5 | ✅ PASS | Normalizer 单元、XML 集成、纯文本集成、解析失败回馈、非流式审批拒绝 |
| **合计** | **20/20** | ✅ **全绿** | |

**Phase C 自动化用例明细**：

| # | 用例 | 结果 |
|---|------|------|
| 1 | Normalizer 单元用例（invoke / tool_call / 文本块 / 文本行内 / JSON 围栏 / 未知工具 / 非 JSON / 空名 / 无调用 / 多调用混合） | ✅ |
| 2 | 集成：XML `<invoke name="git_status">` 归一化真实执行（无审批） | ✅ |
| 3 | 集成：纯文本 `调用 run_command: ipconfig` 归一化执行 | ✅ |
| 4 | 集成：解析失败回馈重生成（不执行、不静默） | ✅ |
| 5 | 非流式审批明确拒绝（注册表无残留、模型看到拒绝原因） | ✅ |

运行命令：

```bash
python backend/tests/test_tool_runtime_phase_a.py
python backend/tests/test_tool_runtime_phase_b1.py
python backend/tests/test_tool_runtime_phase_b2.py
python backend/tests/test_tool_runtime_phase_c.py
```

报告产物：`backend/tests/phase_{a,b1,b2,c}_test_report.md`（注：B-1 独立生成 4/4 报告，未落入 phase_b1_test_report.md 文件命名，建议后续统一）。

---

## 5. 当前 Agent Runtime 架构图

```
用户输入
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│ chat.py  (/api/chat/{id}/send/stream)                        │
│   • 权限层：PermissionFilter.resolve(chat) → 会话可见工具全集 │
│     （与消息内容无关；build=全量 / plan=只读）                 │
│   • 意图层：IntentAnalyzer.analyze → 软提示注入 System Prompt │
│     （不 gate 工具，仅建议）                                  │
│   • 策略层：build_policy → Agent 行为规范（C-3 五条）          │
└──────────────────────────────┬───────────────────────────────┘
                               │ SSE 事件信封
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ model_service.chat_stream  多轮工具环 (≤ max_tool_rounds)     │
│   ├─ 结构化 tool_calls ──► 直接执行                           │
│   ├─ 非标准格式 ──► Normalizer ──► 执行 / issues 回馈重生成    │
│   │                    (C-1)        (C-1)                     │
│   └─ 无工具 ──► finish + 工具汇总                              │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ executor.execute_tool（统一执行闸）                           │
│   ├─ 风险判定：run_command → command_risk_engine              │
│   │            文件/git/搜索 → evaluate_tool                  │
│   │    ALLOW ──► _run_tool 实体执行                           │
│   │    ASK   ──► ApprovalRegistry 登记 + tool_approval 事件    │
│   │    DENY  ──► 拒绝结果回喂（plan 模式只读）                 │
│   └─ 兜底异常保护（C-1）：异常 → tool_result(success=false)     │
│        绝不打断 Agent loop                                    │
└──────────────┬────────────────────────────┬──────────────────┘
               │                            │
               ▼                            ▼
    file_tools / git_tools /       前端 ApprovalCard
    command_tools / search_tools   /api/chat/{id}/tool-approval
    tool_registry（通用工具）         approve/deny → 完成闭环
```

**关键演进**：`V1` = B-1 审批闭环 + B-2 权限目录 + C-1 调用归一化 + C-3 行为规范，构成完整的"权限 → 决策 → 执行 → 审批 → 回馈"单 Agent 工具运行时。
