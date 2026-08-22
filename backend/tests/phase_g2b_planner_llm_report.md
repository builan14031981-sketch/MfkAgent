# MfkAgent Planner LLM 测试报告（Phase G2-B）

- 时间: 2026-08-18 14:32:14

## 结果总览

| # | 用例 | 结果 | 耗时 |
|---|------|------|------|
| 1 | T1  PlanningLevel.allow_llm() 层级判断 | ✅ PASS | 0ms |
| 2 | T2  LLMPlanner.plan() 成功 → 生成 Plan | ✅ PASS | 2ms |
| 3 | T3  LLM 调用失败 → fallback heuristic | ✅ PASS | 2ms |
| 4 | T4  JSON 解析失败 → fallback heuristic | ✅ PASS | 2ms |
| 5 | T5  空 steps → fallback heuristic | ✅ PASS | 1ms |
| 6 | T6  Level 0/1 → 仅 heuristic | ✅ PASS | 1ms |
| 7 | T7  PlannerService LLM 成功路径 | ✅ PASS | 2ms |
| 8 | T8  非任务型请求 → None | ✅ PASS | 1ms |
| 9 | T9  AgentRuntime 执行链回归 | ✅ PASS | 44ms |
| 10 | T10 ContextBuilder planning_level 传递 | ✅ PASS | 0ms |
| 11 | T11 LLM ```json 包裹解析 | ✅ PASS | 0ms |
| 12 | T12 LLM plan 模式只读约束 | ✅ PASS | 1ms |
| 13 | T13 LLM prompt 包含 intent | ✅ PASS | 1ms |
| 14 | T14 Plan.planner_source LLM 成功 | ✅ PASS | 1ms |
| 15 | T15 Plan.planner_source fallback | ✅ PASS | 1ms |
| 16 | T16 Plan.planner_source heuristic | ✅ PASS | 1ms |
| 17 | T17 AgentContext.metadata planner 字段 | ✅ PASS | 0ms |
| 18 | T18 AgentResult.metadata 透传 | ✅ PASS | 0ms |

**通过率: 18/18**

## 验证明细

### 1. T1  PlanningLevel.allow_llm() 层级判断

- HEURISTIC: 0
- BASIC: 1
- LLM: 2
- THRESHOLD: 2
- level_0: False
- level_1: False
- level_2: True
- level_none: False

### 2. T2  LLMPlanner.plan() 成功 → 生成 Plan

- goal: 分析项目性能瓶颈
- steps: 3
- constraints: ['不能修改数据库']
- call_once_called: True

### 3. T3  LLM 调用失败 → fallback heuristic

- plan_not_none: True
- goal: 检查系统状态并诊断网络问题
- steps: 3
- llm_called: True
- fallback_to_heuristic: True

### 4. T4  JSON 解析失败 → fallback heuristic

- plan_not_none: True
- goal: 分析项目结构
- steps: 1
- llm_called: True
- fallback_to_heuristic: True

### 5. T5  空 steps → fallback heuristic

- plan_not_none: True
- steps: 1
- fallback: True

### 6. T6  Level 0/1 → 仅 heuristic

- level_0_llm_called: False
- level_1_llm_called: False
- level_none_llm_called: False
- all_heuristic: True

### 7. T7  PlannerService LLM 成功路径

- goal: 分析项目性能瓶颈
- steps: 2
- llm_called: True
- source: LLM

### 8. T8  非任务型请求 → None

- plan_is_none: True
- llm_not_called: True

### 9. T9  AgentRuntime 执行链回归

- MAX_ROUNDS: 10
- has_router: True
- has_run: True
- has_run_stream: True
- planning_level_field: 2
- agent_result_ok: True

### 10. T10 ContextBuilder planning_level 传递

- planning_level_passed: True
- default_none: True
- builder_has_planner: True

### 11. T11 LLM ```json 包裹解析

- goal: 分析项目
- steps: 1
- code_fence_parsed: True

### 12. T12 LLM plan 模式只读约束

- mode: plan
- has_readonly_constraint: True

### 13. T13 LLM prompt 包含 intent

- user_prompt_has_intent: True
- system_prompt_ok: True

### 14. T14 Plan.planner_source LLM 成功

- planner_source: llm
- source_is_llm: True

### 15. T15 Plan.planner_source fallback

- planner_source: heuristic
- source_is_heuristic: True

### 16. T16 Plan.planner_source heuristic

- level_0_source: heuristic
- level_1_source: heuristic
- llm_not_called: True

### 17. T17 AgentContext.metadata planner 字段

- planner_source: llm
- planner_level: 2
- planner_goal: 分析项目结构
- planner_steps: 3

### 18. T18 AgentResult.metadata 透传

- planner_source_passed: True
- planner_level_passed: True
- planner_goal_passed: True
- planner_steps_passed: True
- existing_fields_ok: True
