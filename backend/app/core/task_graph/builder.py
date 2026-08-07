"""Plan → TaskGraph 转换器（G3-A 基础版 + G5-A 路由分配）。

将线性的 Plan 步骤转换为具有依赖关系的 TaskGraph，
并根据 suggested_tools / action 文本推断 task_type 与 assigned_agent。
"""

from typing import Optional, Tuple, List

from app.core.planner.models import Plan
from .models import TaskGraph, TaskNode, TaskEdge


# ──── G5-A: 路由推断规则表 ────

# 工具名 → (task_type, assigned_agent) 映射
_TOOL_ROUTING: dict[str, Tuple[str, str]] = {
    # 代码执行类 → coding_agent
    "bash": ("code", "coding_agent"),
    "python_REPL": ("code", "coding_agent"),
    "python_repl": ("code", "coding_agent"),
    "run_command": ("code", "coding_agent"),
    "git": ("code", "coding_agent"),
    "write_file": ("code", "coding_agent"),
    "read_file": ("code", "coding_agent"),
    "edit_file": ("code", "coding_agent"),
    "list_files": ("code", "coding_agent"),
    "search_files": ("code", "coding_agent"),
    # 信息检索类 → research_agent
    "search": ("retrieve", "research_agent"),
    "web_search": ("retrieve", "research_agent"),
    "read_webpage": ("retrieve", "research_agent"),
    "fetch_url": ("retrieve", "research_agent"),
    "tavily": ("retrieve", "research_agent"),
}

# action 文本关键词 → (task_type, assigned_agent)
_ACTION_KEYWORDS: list[Tuple[str, Tuple[str, str]]] = [
    ("搜索", ("retrieve", "research_agent")),
    ("检索", ("retrieve", "research_agent")),
    ("查询", ("retrieve", "research_agent")),
    ("查找", ("retrieve", "research_agent")),
    ("分析", ("analyze", "default_agent")),
    ("评估", ("analyze", "default_agent")),
    ("总结", ("analyze", "default_agent")),
    ("部署", ("code", "coding_agent")),
    ("构建", ("code", "coding_agent")),
    ("修复", ("code", "coding_agent")),
    ("编写", ("code", "coding_agent")),
    ("运行", ("code", "coding_agent")),
    ("执行", ("code", "coding_agent")),
    ("对话", ("chat", "default_agent")),
    ("回答", ("chat", "default_agent")),
]


def _infer_task_type_and_agent(
    action: str,
    suggested_tools: List[str],
) -> Tuple[str, str]:
    """根据 suggested_tools 和 action 文本推断 task_type 与 assigned_agent。

    优先级：suggested_tools 精确匹配 > action 关键词 > 兜底 default。

    Args:
        action: 任务动作描述
        suggested_tools: 建议工具列表

    Returns:
        (task_type, assigned_agent)
    """
    # 1. 工具精确匹配（优先）
    for tool in suggested_tools:
        if tool in _TOOL_ROUTING:
            return _TOOL_ROUTING[tool]

    # 2. action 关键词模糊匹配
    for keyword, routing in _ACTION_KEYWORDS:
        if keyword in action:
            return routing

    # 3. 兜底
    return ("action", "default_agent")


class TaskGraphBuilder:
    """Plan → TaskGraph 转换器。

    将 Plan 的线性步骤按顺序转换为有依赖关系的 TaskNode 链：
    - step0 → task_0（无依赖）
    - step1 → task_1（depends_on task_0）
    - step2 → task_2（depends_on task_1）
    - ...

    G5-A：转换时自动推断 task_type 与 assigned_agent。
    """

    @staticmethod
    def build(plan: Optional[Plan]) -> TaskGraph:
        """将 Plan 转换为线性依赖的 TaskGraph。

        Args:
            plan: 输入 Plan，为 None 时返回空 TaskGraph

        Returns:
            TaskGraph: 节点按步骤顺序，边表示依赖关系。
            原 Plan 对象不会被修改。
        """
        if not plan:
            return TaskGraph()

        nodes: list[TaskNode] = []
        edges: list[TaskEdge] = []
        prev_node_id: Optional[str] = None

        for i, step in enumerate(plan.steps):
            node_id = f"task_{i}"
            tools = list(step.suggested_tools)
            task_type, assigned_agent = _infer_task_type_and_agent(step.action, tools)

            node = TaskNode(
                id=node_id,
                action=step.action,
                suggested_tools=tools,
                depends_on=[prev_node_id] if prev_node_id else [],
                task_type=task_type,
                assigned_agent=assigned_agent,
            )
            nodes.append(node)

            if prev_node_id:
                edges.append(TaskEdge(from_id=prev_node_id, to_id=node_id))

            prev_node_id = node_id

        return TaskGraph(
            nodes=nodes,
            edges=edges,
            metadata={
                "goal": plan.goal,
                "mode": plan.mode,
                "constraints": list(plan.constraints),
                "planner_source": plan.planner_source,
            },
        )


# 全局单例
_builder = TaskGraphBuilder()


def get_task_graph_builder() -> TaskGraphBuilder:
    """获取全局 TaskGraphBuilder 单例。"""
    return _builder