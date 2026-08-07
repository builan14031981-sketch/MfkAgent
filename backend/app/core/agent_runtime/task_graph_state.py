"""TaskGraph 状态机引擎（G4-A）。

在 AgentRuntime 内部管理 TaskGraph 的节点状态，提供 DAG 就绪检查与状态更新。
不修改现有执行循环、Tool Runtime、LLM 逻辑、RuntimeEvent、数据库。
"""

from typing import Optional, Dict

from app.core.planner.models import Plan
from app.core.task_graph.builder import TaskGraphBuilder
from app.core.task_graph.models import TaskGraph, TaskNode, TaskNodeStatus


class TaskGraphState:
    """TaskGraph 状态机 — 管理节点就绪检查与状态流转。

    职责：
      1. 持有当前 TaskGraph 实例
      2. get_next_ready_task() — 找到第一个可执行节点（pending + 依赖全 completed）
      3. update_task_status() — 更新节点状态
      4. 查询辅助方法（is_all_done / has_failed 等）
    """

    def __init__(self, graph: Optional[TaskGraph] = None):
        self._graph: TaskGraph = graph or TaskGraph()
        self._node_index: Dict[str, TaskNode] = {
            n.id: n for n in self._graph.nodes
        }

    # ──── 状态初始化 ────

    @classmethod
    def from_plan(cls, plan: Optional[Plan]) -> "TaskGraphState":
        """从 Plan 构建 TaskGraph 并初始化状态机。"""
        graph = TaskGraphBuilder.build(plan)
        return cls(graph)

    def set_graph(self, graph: TaskGraph) -> None:
        """替换当前 TaskGraph（重建索引）。"""
        self._graph = graph
        self._node_index = {n.id: n for n in graph.nodes}

    @property
    def graph(self) -> TaskGraph:
        return self._graph

    @property
    def node_count(self) -> int:
        return len(self._graph.nodes)

    # ──── 核心调度方法 ────

    def get_next_ready_task(self) -> Optional[TaskNode]:
        """寻找第一个满足执行条件的节点。

        条件：
          a) status == PENDING
          b) depends_on 中所有依赖节点 status == COMPLETED

        返回：
          找到的 TaskNode，或 None（全部完成 / 被阻塞）
        """
        for node in self._graph.nodes:
            if node.status != TaskNodeStatus.PENDING:
                continue

            # 检查所有依赖节点是否已完成
            if self._deps_all_completed(node):
                return node

        return None

    def update_task_status(self, task_id: str, new_status: str) -> bool:
        """更新指定节点的状态。

        Args:
            task_id: 节点 ID（如 task_0）
            new_status: 新状态字符串（如 running / completed / failed）

        Returns:
            bool: True 表示更新成功，False 表示节点未找到
        """
        node = self._node_index.get(task_id)
        if node is None:
            return False

        # 字符串 → 枚举转换
        try:
            status_enum = TaskNodeStatus(new_status)
        except ValueError:
            return False

        node.status = status_enum
        return True

    # ──── 查询辅助 ────

    def is_all_done(self) -> bool:
        """所有节点都处于终态（completed / failed / skipped）。"""
        if not self._graph.nodes:
            return True
        terminal = {TaskNodeStatus.COMPLETED, TaskNodeStatus.FAILED, TaskNodeStatus.SKIPPED}
        return all(n.status in terminal for n in self._graph.nodes)

    def has_failed(self) -> bool:
        """是否存在失败节点。"""
        return any(n.status == TaskNodeStatus.FAILED for n in self._graph.nodes)

    def get_blocked_tasks(self) -> list:
        """获取因依赖未满足而阻塞的 pending 节点。"""
        return [
            n for n in self._graph.nodes
            if n.status == TaskNodeStatus.PENDING and not self._deps_all_completed(n)
        ]

    def get_task(self, task_id: str) -> Optional[TaskNode]:
        """按 ID 获取节点。"""
        return self._node_index.get(task_id)

    # ──── 内部方法 ────

    def _deps_all_completed(self, node: TaskNode) -> bool:
        """检查节点的所有依赖是否均为 COMPLETED。无依赖 → True。"""
        if not node.depends_on:
            return True

        for dep_id in node.depends_on:
            dep_node = self._node_index.get(dep_id)
            if dep_node is None or dep_node.status != TaskNodeStatus.COMPLETED:
                return False

        return True
