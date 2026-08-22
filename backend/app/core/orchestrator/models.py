"""Agent Orchestration 数据结构 — 任务规划与子代理编排的数据层。

纯数据定义，不包含工具控制/执行逻辑，供 OrchestrationPlanner / OrchestrationRunner 使用。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class TaskComplexity(str, Enum):
    """任务复杂度分级 — 决定是否需要子代理编排。

    SIMPLE   — 单一步骤可完成（问答/单个文件操作），不编排，主 Agent 直接执行
    MODERATE — 需多步骤但单 Agent 可完成（启发式或单子代理）
    COMPLEX  — 跨领域/多阶段/大型工程，需 Orchestrator 拆分并并行 spawn 子代理
    """

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class SubTaskSpec:
    """一个子任务：委派给某角色的子代理执行。

    Attributes:
        role: 角色 ID（须存在于 ORCHESTRATION_ROLES，如 architecture / backend）
        task: 自包含的任务描述（子代理看不到主会话历史）
        output_format: 期望输出格式（如 "架构决策清单" / "实现计划"）
        depends_on: 依赖的其他子任务 role（预留并行拓扑，V1 全并行不启用）
        max_tokens: 该子任务单次执行 token 上限
    """

    role: str = ""
    task: str = ""
    output_format: str = ""
    depends_on: List[str] = field(default_factory=list)
    max_tokens: int = 4096


@dataclass
class OrchestrationPlan:
    """编排规划结果：Planner 输出。"""

    complexity: TaskComplexity = TaskComplexity.SIMPLE
    need_orchestration: bool = False
    subtasks: List[SubTaskSpec] = field(default_factory=list)
    reason: str = ""                      # 判定依据（人类可读）
    planner_source: str = "heuristic"     # heuristic / llm


@dataclass
class SubTaskResult:
    """单个子代理的执行结果（结构化回传主 Agent）。"""

    role: str = ""
    status: str = "completed"             # completed / failed
    summary: str = ""                     # 结果摘要
    key_findings: List[str] = field(default_factory=list)  # 关键发现/结论要点
    error: str = ""


@dataclass
class OrchestrationReport:
    """编排执行报告：汇总所有子代理产出，交回主 Agent。"""

    plan: OrchestrationPlan = field(default_factory=OrchestrationPlan)
    results: List[SubTaskResult] = field(default_factory=list)
    synthesis: str = ""                   # 交叉综合：决策要点 + 建议下一步
    duration_ms: int = 0

    def to_tool_output(self) -> str:
        """渲染为工具结果文本（主 Agent 可见）。"""
        lines = ["【子代理编排报告】"]
        lines.append(f"复杂度: {self.plan.complexity.value}")
        lines.append(f"判定: {self.plan.reason}")
        if not self.results:
            lines.append("（无需编排，主 Agent 直接执行）")
            return "\n".join(lines)
        lines.append(f"参与角色 ({len(self.results)}): " +
                     "、".join(r.role for r in self.results))
        lines.append("")
        for r in self.results:
            status = "✓" if r.status == "completed" else "✗"
            lines.append(f"{status} [{r.role}] {r.summary or '(无摘要)'}")
            if r.key_findings:
                for k in r.key_findings:
                    lines.append(f"    - {k}")
            if r.error:
                lines.append(f"    错误: {r.error}")
        if self.synthesis:
            lines.append("")
            lines.append("【综合结论】")
            lines.append(self.synthesis)
        return "\n".join(lines)