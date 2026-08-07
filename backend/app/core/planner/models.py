"""Planner V1 数据结构（Phase G1 → G2-B）。

纯数据定义，不包含任何工具控制/执行逻辑。
Plan 通过 to_task_context() 输出到 AgentContext.task_context（V1 结构）。

G2-B 新增：PlanningLevel — 控制 Planner 使用 heuristic 还是 LLM 辅助。
"""

from dataclasses import dataclass, field
from typing import List, Optional


class PlanningLevel:
    """Planner 层级控制。

    Level 0/1: 纯启发式规则模板（heuristic-only）
    Level >=2: 允许 LLM 辅助规划（LLM 失败时自动 fallback heuristic）
    """

    HEURISTIC = 0
    BASIC = 1
    LLM = 2

    # 允许 LLM 的最低 Level
    LLM_THRESHOLD = 2

    @classmethod
    def allow_llm(cls, level: Optional[int]) -> bool:
        """判断给定 Level 是否允许调用 LLM Planner。"""
        return (level or 0) >= cls.LLM_THRESHOLD


@dataclass
class PlanStep:
    """计划步骤（供模型参考的文本，不 gate 工具）。"""

    action: str = ""
    suggested_tools: List[str] = field(default_factory=list)


@dataclass
class Plan:
    """最小任务计划。

    mode: "plan" / "build"
    current_step_index: 当前步骤指针（V1 静态停留在第一步，不自动推进任务树）
    planner_source: "llm" / "heuristic" — G2-C 可观测性：实际规划的来源
    """

    goal: str = ""
    steps: List[PlanStep] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    mode: str = "build"
    current_step_index: int = 0
    planner_source: str = "heuristic"

    @property
    def current_step(self) -> Optional[str]:
        """当前步骤描述（无步骤时返回 None）。"""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index].action
        return None

    def to_task_context(self) -> dict:
        """输出 AgentContext.task_context V1 结构（兼容 E7-2 契约）。"""
        return {
            "goal": self.goal,
            "constraints": list(self.constraints),
            "current_step": self.current_step,
        }
