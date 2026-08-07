# MfkAgent V1 Runtime Stability Report

> **性质**：下一阶段开发的基线（Baseline）。
> **范围**：单 Agent 工具运行时（Phase A / B-1 / B-2 / C）。
> **冻结结论**：V1 Runtime 稳定，可冻结。后续阶段在此基础上扩展，不重做权限/执行/审批/归一化核心。
> **日期**：2026-08-05 ｜ **后端进程**：uvicorn 127.0.0.1:8001（PID 15692，已加载全部 C 阶段代码）

---

## 1. 稳定性证据

### 1.1 自动化测试（最终复核全绿）

| 套件 | 结果 | 关键覆盖 |
|------|------|----------|
| Phase A | 5/5 ✅ | 工具调用真实执行 + 持久化 |
| Phase B-1 | 4/4 ✅ | 审批 批准/拒绝/plan 拒绝/API |
| Phase B-2 | 6/6 ✅ | 权限目录、只读自动、git_commit 审批、plan 拒绝、注册表无残留 |
| Phase C | 5/5 ✅ | Normalizer 单元、XML/文本归一化执行、解析失败回馈、非流式审批拒绝 |
| **合计** | **20/20 ✅** | 全部通过 |

复核命令（均为独立运行、退出码 0）：
```
python backend/tests/test_tool_runtime_phase_a.py
python backend/tests/test_tool_runtime_phase_b1.py
python backend/tests/test_tool_runtime_phase_b2.py
python backend/tests/test_tool_runtime_phase_c.py
```

### 1.2 真实 Agent 验收（真实 uvicorn + deepseek-v4-flash）

| 任务 | 耗时 | 工具序列 | 审批 | 结果 |
|------|------|----------|------|------|
| T1 项目修复 | 9.9s | 结构→读码×3→验证→write_file→复验 | 3 | ✅ 修复+退出码 0 |
| T2 网络诊断 | 12.1s | run_command×15 | 4 | ✅ 只读排查完成 |
| T3 项目优化 | 13.9s | 读码→write_file→基准→编译→git_diff | 2 | ✅ 提速 23% 验证 |

### 1.3 稳定性设计（本轮加固要点）

1. **不静默**：解析失败 → 结构化错误回馈模型重生成（C-1）
2. **执行兜底**：工具异常 → `tool_result(success=false)`，绝不打断 Agent loop（C-1）
3. **审批闭环**：approve/deny/timeout/cancelled 四态收敛，注册表幂等清理（B-1）
4. **无泄漏**：非流式遇审批 → 显式拒绝 + 无残留（C-1 F2）
5. **行为规范**：五条 Agent 行为规范强制注入 System Prompt（C-3）

---

## 2. 代码健康检查结果（只读审计，未修改）

### 2.1 未使用 import：33 处（均为装饰性，无功能影响）

- **关键路径 0 处**：Phase C 修改文件（normalizer.py / executor.py / model.py / chat.py / command_tools.py / policy.py）全部干净。
- 活跃代码中的代表项：`core/tool_runtime/events.py:22 Callable`、`core/tool_runtime/selector.py:6 Optional`、`api/tools.py:1 HTTPException`、`services/tools.py:2-3 subprocess/os`。
- 其余集中在**已废弃目录**（见 2.2）。
- 注：`approval.py` / `risk_engine.py` 的 `from __future__ import annotations` 是生效的 future import，非未使用。

### 2.2 死代码 / 旧 Runtime 残留

| 路径 | 性质 | 建议 |
|------|------|------|
| `app/services/tool_runtime/`（v4 时代全包） | 无任何 import，完全废弃 | 下一阶段删除 |
| `app/services/tool_runtime_v5/`（V5 前身全包） | 无任何 import，完全废弃 | 下一阶段删除 |
| `app/core/tool_runtime/observer.py` | 未 import（计划书v3.txt 已登记为已知死代码） | 下一阶段删除 |
| `app/services/memory.py` | 空壳 MemoryService，未 import（API 直连 DB） | 下一阶段删除 |

⚠️ **命名冲突注意**：活跃运行时 `app/core/tool_runtime/`（docstring 标注 "V5 Final"）与废弃目录 `services/tool_runtime_v5/` 都自称 V5，维护时易混淆。下一阶段建议删除废弃目录 + 统一命名。

### 2.3 异常日志

- `uvicorn_c2_err.log`、`uvicorn_b2_err.log`：无 `ERROR` / `Traceback` / `Exception`。
- 后端启动正常，docs 200，健康检查通过。

### 2.4 测试遗漏（见 `v1_capability_boundaries.md §5.3`）

6 项已知缺口（executor 异常兜底、web_search、混合调用、`<tool>` 变体、非流式解析失败、plan 命令审批），均不阻塞冻结，列入下一阶段首轮补测。

---

## 3. 冻结基线（下一阶段的输入）

### 3.1 架构（稳定契约）

```
用户输入 → chat.py（权限目录 resolve + 意图软提示 + 行为规范策略）
        → model_service.chat_stream（多轮工具环 ≤ max_tool_rounds）
              ├ 结构化 tool_calls → 执行
              ├ 非标准格式 → normalizer → 执行 / issues 回馈重生成
              └ 无工具 → finish
        → executor.execute_tool（风险三态闸 ALLOW/ASK/DENY + 异常兜底）
              ├ ALLOW → _run_tool（file/git/command/search/registry）
              ├ ASK  → approval_registry + tool_approval → 前端审批 API → complete_approval
              └ DENY → 拒绝文本回喂
        → SSE 事件信封（tool_start/tool_approval/tool_result/text/thinking/finish/tool_calls/error）
```

### 3.2 冻结的范围与边界

- ✅ **已冻结**：权限目录、风险三态判定、审批闭环、归一化执行、错误回馈、Agent 行为规范、SSE 事件协议。
- ❌ **不进入**（明确排除）：多 Agent、MCP 重构、沙箱、长期记忆、并行工具调用、自动规划系统。

### 3.3 下一阶段起点（建议按序）

1. **代码清理**（低风险）：删 `services/tool_runtime/`、`services/tool_runtime_v5/`、`core/tool_runtime/observer.py`、`services/memory.py`；清 33 处未使用 import；引入 ruff 作为统一 lint 基线。
2. **补测 6 项缺口**（T1-T6）。
3. **功能扩展**（从已冻结边界出发）：多 Agent 编排 / 沙箱 / 长期记忆 / 并行工具调用 / 自动规划。

---

## 4. 风险登记

| 风险 | 等级 | 缓解 |
|------|------|------|
| 审批仅内存，重启/多 worker 丢失 | 中 | V1 单 worker 可接受；多 worker 需落库 |
| 命令白名单偏 Windows 语义 | 中 | 跨平台需扩白名单/平台探测 |
| 模型偶发输出未执行 `<invoke>`（T2） | 低 | 观察；可加"总结段去 XML"清洗 |
| 两个 V5 命名并存 | 低 | 下一阶段删废弃目录 |

---

*本报告与 `phase_c_delivery_report.md`、`v1_capability_boundaries.md`、`backend/tests/phase_{a,b2,c}_test_report.md` 共同构成 V1 冻结交付物。*
