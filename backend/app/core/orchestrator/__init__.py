"""Agent Orchestration — 任务规划 + 子代理编排 + 结果汇总。

模块：
  - models:  数据结构（OrchestrationPlan / SubTaskSpec / SubTaskResult / OrchestrationReport）
  - roles:   动态子代理角色目录（身份模板 + 工具白名单）
  - planner: OrchestrationPlanner（复杂度分级 + 角色推荐 + 子任务拆分）
  - runner:  OrchestrationRunner（并行 spawn + 结果收集 + 汇总）
"""

from app.core.orchestrator.models import (
    OrchestrationPlan,
    OrchestrationReport,
    SubTaskResult,
    SubTaskSpec,
    TaskComplexity,
)
from app.core.orchestrator.planner import orchestration_plan
from app.core.orchestrator.runner import run_orchestration

__all__ = [
    "OrchestrationPlan",
    "OrchestrationReport",
    "SubTaskResult",
    "SubTaskSpec",
    "TaskComplexity",
    "orchestration_plan",
    "run_orchestration",
]