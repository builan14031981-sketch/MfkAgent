"""Planner V1 → G2-B — 任务规划能力（Phase G1 → G2-B）。

职责：
  - Plan / PlanStep 数据结构（纯数据，不控制工具）
  - PlanningLevel：层级控制（0/1=heuristic, >=2=LLM 辅助）
  - PlannerService：基于意图/模式的计划生成（heuristic + LLM fallback）
  - LLMPlanner：LLM 辅助规划器（G2-B 新增）
  - RuntimeTaskContextAdapter：Runtime 接入点（task_context → system prompt 段落）

流程：
  User Request → ContextBuilder → PlannerService.plan → AgentContext.task_context
              → RuntimeTaskContextAdapter.render → Execution Loop（仅提示，不 gate）
"""

from .models import Plan, PlanStep, PlanningLevel
from .service import PlannerService, get_planner, TASK_INTENTS
from .llm_planner import LLMPlanner, get_llm_planner
from .runtime import RuntimeTaskContextAdapter, get_runtime_task_context_adapter

__all__ = [
    "Plan",
    "PlanStep",
    "PlanningLevel",
    "PlannerService",
    "get_planner",
    "TASK_INTENTS",
    "LLMPlanner",
    "get_llm_planner",
    "RuntimeTaskContextAdapter",
    "get_runtime_task_context_adapter",
]
