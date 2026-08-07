"""TaskGraph 模块（G3-A 基础版）。

纯数据结构与 Plan→TaskGraph 转换器，不接入 Runtime。
"""

from .models import TaskNode, TaskNodeStatus, TaskEdge, TaskGraph
from .builder import TaskGraphBuilder, get_task_graph_builder

__all__ = [
    "TaskNode",
    "TaskNodeStatus",
    "TaskEdge",
    "TaskGraph",
    "TaskGraphBuilder",
    "get_task_graph_builder",
]