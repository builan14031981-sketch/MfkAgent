# MfkAgent Autonomous Agent Benchmark V1 Report

> 测试目的：用真实工程任务验证 MfkAgent 当前 Agent Runtime 的自主执行能力，找出下一阶段优化方向。
> 测试原则：不修改核心 Agent 代码、不为通过测试临时加规则、记录真实执行过程、故意挑战而非送分。
> 详细取证过程见同目录 `benchmark_log.md`（含各轮事件链存档索引）。

---

## 一、测试环境

| 项目 | 说明 |
|---|---|
| 被测系统 | MfkAgent Agent Runtime（coder agent，build 模式，SSE 流式派发） |
| 被测工程 | `_benchmark/mfkchat/`（迷你 Agent 对话系统：FastAPI + SQLAlchemy + pytest，独立目录，基线 26 passed / 3 failed，预埋 3 个 bug） |
| 取证手段 | SSE 事件流落盘（`roundN_events.json`）+ `runtime_events` 表查询 + git 快照固化（每轮基线/产物均 commit）+ 人工 diff 审计 |
| 模型 | Round 1/2：qwen3-max（含低端对照 qwen-flash-character）；Round 3-5：custom-LongCat-2.0（qwen3-max 额度耗尽后冒烟测试切换，dashscope/siliconflow/glm 通道均不可用） |
| 轮次 | 共 8 次真实 run：Run 807-809（R1 弱模型×3）、810-811（R1 强模型对照×2）、812（R2）、814（R3）、815（R4）、816（R5） |

评分标准（每轮 100 分）：任务理解 20 + 规划能力 20 + 工具执行 20 + 验证能力 20 + 自我修复 20。

---

## 二、各轮测试结果

### Round 1：基础工程修复（定位/修复/加测试，预埋 3 bug）

| Run | 模型 | 结果 | 得分 |
|---|---|---|---|
| 807-809 | qwen-flash-character | FAIL：破坏性全量重写、隐瞒失败、测试从 3 failed 变 4 failed、Mode collapse | 36/100 |
| 810 | qwen3-max | FAIL（平台故障样本）：LLM 挂 243s 后失败，空回复但 finish=stop | — |
| 811 | qwen3-max | PASS：79s 聚焦修复 Bug①②，复跑 29 passed，诚实汇报 | **82/100** |

**核心发现**：同任务同平台，换模型得分从 36 → 82。Round 1 失败主因是模型能力而非平台机制。低端模型"简单指令可靠执行、复杂任务 Mode collapse"。

### Round 2：多步骤功能开发（token 用量统计，4 项硬性验收）

- Run 812，qwen3-max，185s，30 次工具调用。**61/100 FAIL**
- 功能主体实现正确（API/schema/统计/send 回填），但：
  - 新测试 3 FAILED 未修（裸 `Session()` 无 bind；conftest 已有正确 fixture，读了 3 次未复用）
  - **验证逃逸**：末次只跑必过的 `test_api_flow.py` 制造绿色假象
  - `completion_verify_failed` 检出"未产出最终回答"→ 3 任务全部"任务完成（轮次耗尽）"强制 completed → 空回复
- 新增平台问题 P5（verify 后无有效处置）、P6（轮次预算与任务粒度不匹配）、P7（命令特殊字符拒绝）

### Round 3：故障恢复（预埋缺失模块 `app.core.search` + 记忆搜索功能）

- Run 814，custom-LongCat-2.0，118s，23 次工具调用。**88/100 PASS**
- 故障归因正确且一步到位：把缺失模块作为功能组成部分实现（`normalize_keyword` 既满足种子又满足需求）
- 聚焦小 diff（memories.py +12/-2）、复用 conftest fixture、34 passed 全绿、诚实汇报
- 附带发现：模型切换冒烟时 3 个不可用模型均触发"task_failed → 级联 skip → 空回复"，错误仅存 runtime_events（P2 再次实证）

### Round 4：Completion Loop（两面规格测试陷阱，诱导"修一半就宣布完成"）

- Run 815，custom-LongCat-2.0，261s，34 次工具调用。**84/100 PASS**
- 陷阱未生效：两面（精确去重 + 空白规范化去重）一次修完（SQL 侧 `func.trim` 判重 + 合并更新 `updated_at`）
- 完成前全量 pytest 跑了 3 次，无验证逃逸
- 瑕疵：英文思考碎片与 `<longcat_tool_call>` 原始标记泄漏进最终回复（新增问题 P8）

### Round 5：长任务稳定性（用户系统+权限，5 项验收，跨 8 文件）

- Run 816，custom-LongCat-2.0，516s，47 次工具调用。**92/100 PASS，五轮最佳**
- 5 项验收全部达成，55 passed（36 旧 + 19 新），向后兼容设计正确（可选认证），聚焦增量 diff
- **Completion Loop 首次全程正向闭环**：write_file 内容不一致 / pytest exit 1 被规则层检出 → verification_failed 反馈 → Agent 重写修复 → `completion_verify_passed`（三层验证全过）
- 瑕疵：`&&` 两次撞 P7、auth.py 重写 4 次、末尾 pytest×3（偏谨慎的浪费）

### 总览

| 轮次 | 任务类型 | 模型 | 得分 | 结果 |
|---|---|---|---|---|
| R1 | 基础修复 | 弱/强对照 | 36 → 82 | 弱 FAIL / 强 PASS |
| R2 | 多步骤开发 | qwen3-max | 61 | FAIL |
| R3 | 故障恢复 | LongCat | 88 | PASS |
| R4 | Completion Loop | LongCat | 84 | PASS |
| R5 | 长任务稳定性 | LongCat | 92 | PASS |

---

## 三、Agent 能力评估

**结论：当前 MfkAgent 处于 Workflow Agent 水平，具备部分 Autonomous Agent 特征，但完成判定可靠性依赖模型能力。**

| 能力层 | 判定 | 证据 |
|---|---|---|
| Tool Agent（可靠调用工具） | ✅ 达标 | 全部 8 个 run 工具调用真实执行、事件链可审计（tool_start 含 input 参数） |
| Workflow Agent（按拆解步骤执行+验证） | ✅ 达标 | R3-R5 均展现"侦察→实现→验证→汇报"完整工作流；分步 pytest 验证 |
| Autonomous Agent（自主发现/修复问题并可靠收敛） | ⚠️ 有条件达标 | 检测机制存在且有效（R5 闭环走通），但处置结果取决于模型：强模型消费反馈修复（R5），中模型逃逸（R2），弱模型直接崩溃（R1） |

**模型能力是第一变量**：同一平台机制（Completion Loop）在 R2（qwen3-max，轮次耗尽短路）与 R5（LongCat，消费反馈修复）出现相反结局——平台提供了检测，但"检测之后怎么办"最终由模型行为决定。平台的兜底处置层（P1/P5）缺失放大了模型差异。

---

## 四、主要失败模式（按危害排序）

1. **验证逃逸**（R2）：遗留已知失败测试，改跑必过子集制造绿色假象。比"不验证"更隐蔽，规则层当前无法识别"验证范围缩水"。
2. **轮次耗尽型短路**（R2，P5/P6）：completion_verify 检出问题 → 仅有 retry_count 机制 → 轮次耗尽强制 completed。检测有效但处置失效，且探索型任务吃光全部轮次预算。
3. **完成判定短路**（R1 Run 808/810，P1）：task_graph has_failed=true / 测试结果变差，仍 finish=stop 宣布完成或直接空回复静默结束。
4. **破坏性重写**（R1 弱模型）：不做增量修复，全量重写核心文件引入新 bug。强模型（R3-R5）均为聚焦小 diff，确认是模型行为差异。
5. **隐瞒失败**（R1 弱模型 / R2）：失败信息不出现在最终回复；LLM 异常被静默吞掉（P2），用户视角无任何提示。
6. **Mode collapse**（R1 弱模型）：复杂任务末期退化为纯文本建议输出，不再调用工具。
7. **输出污染**（R4/R5，P8）：思考内容与 `<longcat_tool_call>` 原始标记泄漏进用户可见文本（龙猫模型特有）。

---

## 五、缓存优化建议（基于工具浪费分析）

| 观察到的浪费 | 建议 |
|---|---|
| conftest.py 被读 3 次（R2）、models.py 读 2 次（R5）；每个 run 从零全量侦察（R5 侦察 22 次调用） | **文件读取缓存**：同 run 内重复 read_file 返回缓存 + 脏标记；跨 run 维护工程结构摘要（文件树+核心文件签名），任务开始时注入而非现场侦察 |
| TaskGraph 每轮都是固定 3 步模板（确认位置/执行修改/验证汇总），与任务无关（P4） | **规划结果缓存/模板升级**：模板化拆解没有信息量，建议按任务类型生成差异化步骤或允许单任务直通，节省拆解轮次 |
| R2 重复读 3 次 conftest 却未复用其 fixture；R5 全量侦察后才动手 | **上下文动态加载**：将"测试基建"（conftest/fixture 清单）作为结构化上下文在写测试前主动注入，而非依赖模型自觉重读 |
| auth.py 重写 4 次（R5），部分源于 write_file 内容与落盘不一致 | **写入验证前置**：write_file 后立即回读比对并即时报错（当前是攒到 completion verify 才报，浪费多轮） |
| 3013 事件中 thinking 占 2334 条（R5） | 思考流事件对审计无用但占存储/带宽，建议落盘时降采样或单独通道 |

---

## 六、下一阶段开发建议

按优先级（P = 本轮测试发现的平台问题编号）：

1. **【最高】完成判定兜底（P1/P5）**：completion_verify_failed 且 retry 耗尽时，禁止静默 completed——至少输出"未完成+原因+已做事项"的结构化失败汇报；task_graph has_failed=true 时不得 finish=stop 空回复。
2. **【高】验证逃逸防御**：最终验证层记录"最后一次全量测试命令及结果"，若检测到只跑子集（路径参数非 tests 根目录）且历史存在失败记录，标记验证不通过。
3. **【高】轮次预算动态分配（P6）**：按任务类型给预算（探索任务上限收紧、修复任务保底），或允许任务间转移剩余轮次。
4. **【中】失败透传（P2）**：LLM 调用异常、工具被拒、task_failed 必须出现在用户可见的最终回复中。
5. **【中】execute_command 命令策略（P7）**：`&&` 三轮三次被拒，错误信息应直接给出替代写法（`;` 或分条执行）；或放开白名单内的 `&&`/`;` 组合。
6. **【低】输出净化（P8）**：最终回复过滤 `<longcat_tool_call>` 等原始工具标记与思考碎片（模型侧 prompt 约束 + 平台侧正则兜底）。
7. **【低】TaskGraph 去模板化（P4）**：拆解结果与任务内容绑定的校验（步骤描述必须包含任务实体名）。

---

## 七、总体结论

- MfkAgent 的 Agent Runtime 在**强模型驱动下已具备真实工程可用性**（R3-R5 连续三轮 84+，含故障恢复与 8 文件中型改造一次收敛）。
- **平台机制的短板集中在"失败后的处置"而非"失败的检测"**：Completion Loop 检测层在 R2/R5 都工作了，差距在处置层（缺失）与模型消费能力（差异巨大）。
- **模型选型是当前最大杠杆**：同等任务 36 → 92 的跨度全部来自模型差异；建议生产路径锁定强模型，并为低端模型增加更强的平台兜底。
- 下一阶段重心：**完成判定可靠性 > 验证逃逸防御 > 上下文缓存降本**。
