# 修复方案：Completion 验证假阴性 (P1) + 只读意图越权 (P2)

- 起草: 后端 Backend Agent，2026-08-13
- 依据: 实测 `docs/coder_agent_glm51_benchmark_report_0813.md`（T1/T2 用例现场复现）
- 状态: **已实施并回归通过**（2026-08-13，实现 + 单测 + 真实端到端回归全绿）
- 实施清单
  - `completion/tool_check.py`：`_build_last_healthy_records`（按工具族 last-wins 聚合，run_command/execute_command 合并为 command 族）+ `_is_intercepted`（策略拦截/错误前缀降级，不判 missing）
  - `context_builder.py`：`_READ_ONLY_PATTERNS`/`_is_read_only_request` 只读意图检测；工具过滤到 `READ_ONLY_TOOLS`；`read_only=(chat_mode=="plan" or read_only_request)`
  - `completion/rules.py`：**追加修复**（回归中发现）— `_TEST_NEGATION_KEYWORDS` 跳过测试守卫；`exit_code` 非全绿判定支持**基线豁免**（仅 ≥2 次执行且失败 ⊆ 首次基线才豁免）；`_ALL_GREEN_KEYWORDS` 扩充"修复/通过验证"等
- 备份: `_backup/fix_p1p2_pre/`（rules.py、tool_check.py、context_builder.py 改前 SHA 校验一致）

## 一、P1 Completion 验证假阴性

### 1.1 现象（T2 实测铁证）
修复任务中 Agent 首次命令被 risk_engine 拦截（`;` 危险字符），重试后 pytest 全绿（RC=0, 2 passed），但最终汇报"【任务未完全完成】execute_command: 执行失败"。

### 1.2 根因链
```
all_tool_calls 累积全部轮次记录（含被拦截的失败命令 status="failed"）
        ↓
completion/tool_check.py:46-49  遍历所有记录，status != "success" → 计入 missing_items
        ↓
completion/pipeline.py:52-60    tool 层短路返回 failure
        ↓
rule 层 test_scope_guard（只看最后一次 pytest exit_code）永远无法执行 → 假阴性固化
```

关键文件：
- `backend/app/core/agent_runtime/completion/tool_check.py`（缺陷主因）
- `backend/app/core/agent_runtime/completion/pipeline.py`（层序短路）
- `backend/app/core/agent_runtime/completion/test_history.py`（已有正确语义，但被短路）
- `backend/app/core/agent_runtime/agent.py:922-932`（组装 tool_records）

### 1.3 修复设计（**最终状态成功豁免**）

**原则**：tool 层校验的是「动作最终是否健康」，而非「历史上有没有碰过壁」。命令被策略拦截→重试→最终成功 = 最终状态成功，不构成未完成项。

修改 `tool_check.py` 的 `verify()`：

```python
def _build_last_healthy_records(records):
    """按工具名聚合：仅保留该工具最后一次出现的记录。
    早先的失败/拦截记录被后续成功覆盖时自动豁免（重试成功语义）。
    """
    order = []
    seen = {}
    for r in records or []:
        name = r.get("tool") or r.get("name") or "?"
        if name not in seen:
            seen[name] = r
            order.append(name)
        else:
            seen[name] = r
    # 维持首次出现顺序，仅校验每个工具「最后一次」记录
    return (seen[n] for n in order)
```

`verify()` 主循环改为遍历 `_build_last_healthy_records(records)`，其余逻辑不变（仍复用 Phase E4 程序化验证）。

**理由（why before how）**：
- 对 `run_command/execute_command`：重复执行同命令是常见重试路径（字面命令可能不同，如第一次 `pytest; pip install`、第二次 `pytest`）。在 run 场景直接聚合到最近一次执行。
- 对 `write_file`：先写错路径→重写正确路径，最终终止状态正确即通过。
- rule 层 `test_scope_guard` 已精确保留「最后一次 pytest 全绿 + 防逃逸」语义，tool 层放权后它能真正兜底（本就不该抢判）。

**不采纳替代方案及理由**：
1. 仅调整 pipeline 层序（rule 先于 tool）：改变「动作健康性优先」的原语义，且 rule 层依赖 tool 层提供的文件校验，因果倒置，**否决**。
2. 给被拦截命令打 `intercepted` 标记跳过：判断"被策略拦截"需要原始命令文本二次解析，脆弱；且不覆盖 write_file 写错路径的重试，**否决**。
3. 清空本轮 tool_records 只留最后一轮：丢失"曾失败文件需复跑"的防逃逸依据（rule 层依赖多轮历史），**否决**。

### 1.4 影响面
- `completion/tool_check.py`：唯一被改文件，纯函数级改造，方法头部加 docstring。
- `pipeline.py / rules.py / test_history.py`：不改，但 tool 层放权后 rule 层实际开始兜底（期望行为，T2 场景 rule 层本轮即正确放行）。
- 副作用风险：若同工具多次失败且最后一次也失败 → 仍拦截（正确）。若不同工具各失败一次 → 各自拦截（正确）。

## 二、P2 只读意图越权

### 2.1 现象（T1 实测铁证）
用户明令"只读，禁止修改文件"，Agent 仍 `write_file` 修改了 calc.py。

### 2.2 根因链
```
chat.py:614/934  read_only = (chat.mode == "plan")
        用户文本"只读"不改变 chat_mode（默认 build）→ read_only=False
        ↓
context_builder.py:756-774  工具目录全量注入（含 write_file）
        ↓
executor.py:87  mode = "plan" if read_only else "build" → "build" 放行写操作
```

关键文件：
- `backend/app/core/agent_runtime/context_builder.py:756-774`（工具目录过滤）、`:934`（read_only）
- `backend/app/core/tool_runtime/risk_engine.py:421-431`（READ_ONLY_TOOLS 单一事实来源）

### 2.3 修复设计（**只读意图 → 工具目录降权 + read_only 传导**）

**原则**：权限模型已有答案（plan 模式），缺的只是「从用户指令识别只读意图」这一环。复用既有 `READ_ONLY_TOOLS` / `PLAN_FORBIDDEN_TOOLS`，不新建清单。

**改动 1**：`context_builder.py` 新增只读意图检测（仿 `_is_casual_chat` 模式）：

```python
# 只读请求触发词：命中任一即视为只读任务（不注入写工具）
_READ_ONLY_PATTERNS = [
    r"只读", r"只查看", r"只看", r"仅阅读", r"仅分析",
    r"禁止修改", r"不要修改", r"不许修改", r"不允许修改",
    r"不要改文件", r"别改.*文件", r"禁止改动",
]

_READ_ONLY_RE = re.compile("|".join(_READ_ONLY_PATTERNS))

def _is_read_only_request(message: str) -> bool:
    return bool(message and _READ_ONLY_RE.search(message))
```

**改动 2**：`build()` 内工具目录注入处（756 行附近）：
```python
read_only_request = _is_read_only_request(input.content)
is_chat = _is_casual_chat(input.content)
if input.use_tools and not is_chat:
    tool_context = tool_runtime.process(...)
    if tool_context.get("need_tools"):
        tools_arg = tool_context["tools"]
    # P2: 只读意图 → 过滤到只读工具集（复用 plan 白名单派生，单一事实来源）
    if read_only_request and tools_arg:
        tools_arg = [
            t for t in tools_arg
            if t.get("function", {}).get("name") in READ_ONLY_TOOLS
        ]
        if not tools_arg:
            tools_arg = None
```

**改动 3**：`read_only` 传导（934 行）：
```python
read_only=(chat_mode == "plan" or read_only_request),
```

**语义**：只读意图命中时
- 工具目录只剩 `read_file/list_files/search_files/git_status/...`（无 `write_file`/`run_command`/`git_commit`），LLM 无法发起写调用；
- `AgentContext.read_only=True` → executor `mode="plan"`，即使模型硬发写工具也会被 risk_engine deny（**纵深防御二层**）。

**理由（why before how）**：
- 只做工具目录过滤而不同步 `read_only=True`：单层防线，模型可用 `run_command` 手工改文件（命令走白名单外的决策路径），**不彻底**；
- 只做 `read_only=True` 而不过滤工具目录：浪费模型一轮"硬试→被拒"，且干扰 tool_guidance 注入，**不经济**；
- 两层叠加 = 权限模型既有机制（plan）的语义复刻，无新概念、无新清单。

### 2.4 待确认边界
只读意图检测用正则命中，需确认行为期望：
1. "只读"是否等价于"禁止写死代码"（如代码审查任务）？→ 是，禁用 write_file。
2. 只读模式下 `run_command` 是否保留？→ **不保留**（executor plan 路径下 run_command 非白名单命令也会被拒）。若产品希望"只读但可跑测试"，需单独放开 pytest → 提给计划 AI 决策。
3. 用户"只读分析 + 明确补充'可以修改' "的复合指令如何裁决？→ 现方案只看首条消息原文，若含"可以修改"则建议豁免（可加否定词探测，二期）。

## 三、测试验证计划（复测 T1/T2）

修复后用**同一沙箱**（基线备份 `_backup/coder_glm51_baseline/`）回归：

| 用例 | 输入 | 期望 |
|---|---|---|
| P1-T2 回归 | 修复任务（明确授权修改） | 修复后 pytest 全绿，Agent 汇报"已完成"而非"未完成" |
| P2-T1 回归 | "只读，禁止修改"诊断任务 | 不调用 write_file；timeline 无 write 工具 |
| P2-附加 | Topic: "帮我写一个 analyze.py" | 不误伤：写意图正常，write_file 可用 |
| 规则层回归 | 故意只跑通过的子集 | 仍被 test_scope_guard 拦截（防逃逸不回退） |

### 3.1 实施后回归结果（全通过）

| 用例 | 结果 | 证据 |
|---|---|---|
| P1/T2 修复闭环 | **PASS** | Agent 汇报「修复完成…2 passed」，`pytest` RC=0（修复前误报"任务未完全完成"） |
| P2/T1 只读 | **PASS** | 仅调用 read_file，文件 SHA 未变（修复前会偷写） |
| 写任务回归 | **PASS** | 创建 helper.py 正常，未被误禁；规则层正确豁免"不要运行测试"意图 |
| 规则层单测 | **PASS** | `_t_rules2.py` 6 场景全绿：基线豁免/新增失败拦截/否定意图跳过/全绿强制/单次红拦截/修复意图拦截 |
| tool_check 单测 | **PASS** | `_t_static5.py` 4 场景全绿：拦截降级/真失败拦截/命令族归一/族内最后成功 |
| 存量单测 | **PASS** | `test_completion_{exhausted_path,loop,scope_guard}.py` 共 20 passed |

注：`tests/test_task_verify_fix.py` 为**既存损坏**（import `VERIFICATION_FEEDBACK_PREFIX`，该常量在 d2766fb 已移除，早于本次改动），与本次修复无关，建议后续修复该测试引用。

## 四、文档与交接
- 修复落地后更新《交接文档》：本方案 P1/P2 为**后端独立修复**，无 API 面变化、无前端依赖。
- 对前端影响：零（不改变任何接口契约）。
- 回归用例结果写回 `docs/coder_agent_glm51_benchmark_report_0813.md` 附录。
- 实施后注意事项：
  1. 服务以无 `--reload` 方式运行，改后端代码需重启 `uvicorn main:app --port 8001`（本次已重启 3 次验证）。
  2. P1 二次升级引入**命令族聚合**：`run_command`/`execute_command` 视为同一工具族 last-wins，避免同命令两种执行路径互相误伤。
  3. 规则层新增**否定测试意图**豁免："不要运行测试"不再触发测试守卫；**基线豁免**使基线红的工程不再被永久卡死，但"修复/必须通过"类意图仍强制全绿。

## 五、回滚保障
- 修改文件 3 个：`completion/tool_check.py`、`context_builder.py`、`completion/rules.py`。
- 改前由 Backend Agent 执行：git 已完成基线（当前 HEAD d2766fb），改动前将文件复制进 `_backup/fix_p1p2_pre/<相对路径>/`，确认后即可随时还原（SHA 已校验一致）。
- 全程遵循 NO-DELETE + 备份确认协议。