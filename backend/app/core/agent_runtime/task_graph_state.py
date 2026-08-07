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
        # G4-C: 当前执行节点追踪（current_step 进度同步，不修改 Plan）
        self._current_task_id: Optional[str] = None

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
            new_status: 新状态字符串（如 running / completed / failed / skipped）

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

        # G4-C: current_step 追踪 — running 记录当前节点；终态清空
        if status_enum == TaskNodeStatus.RUNNING:
            self._current_task_id = task_id
        elif status_enum in (TaskNodeStatus.COMPLETED, TaskNodeStatus.FAILED, TaskNodeStatus.SKIPPED):
            if self._current_task_id == task_id:
                self._current_task_id = None

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

    # ──── G4-C: 失败级联 / 图中断 / 进度同步 ────

    @property
    def current_task_id(self) -> Optional[str]:
        """当前正在执行的节点 ID（无则 None）。"""
        return self._current_task_id

    def get_step_index(self, task_id: str) -> int:
        """节点在图的执行顺序序号（0-based）；不存在返回 -1。"""
        for i, n in enumerate(self._graph.nodes):
            if n.id == task_id:
                return i
        return -1

    @property
    def total_steps(self) -> int:
        return len(self._graph.nodes)

    def mark_failed(self, task_id: str, error: Optional[str] = None) -> list:
        """将节点标记为 failed，并级联跳过所有（直接/间接）依赖它的待执行节点。

        G4-C 状态一致性：单 Task 异常 → 该节点 failed，其后继节点（依赖链）全部
        skipped（不再阻塞于半终态），返回被跳过的节点 ID 列表。

        Args:
            task_id: 失败的节点 ID
            error: 失败原因（记录到节点，透出给事件；不修改 Plan）

        Returns:
            list: 被级联标记为 skipped 的节点 ID 列表（不含 task_id 本身）
        """
        node = self._node_index.get(task_id)
        if node is None:
            return []

        node.status = TaskNodeStatus.FAILED
        if self._current_task_id == task_id:
            self._current_task_id = None

        # 仅对失败节点的后继（依赖链上仍 pending 的节点）标记 skipped
        skipped: list = []
        for dep_id in self._iter_transitive_dependents(task_id):
            dep_node = self._node_index.get(dep_id)
            if dep_node is not None and dep_node.status == TaskNodeStatus.PENDING:
                dep_node.status = TaskNodeStatus.SKIPPED
                skipped.append(dep_id)
        return skipped

    def mark_pending_skipped(self, reason: Optional[str] = None) -> list:
        """将所有仍处于 PENDING 的节点标记为 skipped（图中断兜底）。

        用于：任务循环因阻塞/中断退出时，保证不存在"永远 pending"的悬空节点，
        使 is_all_done() 收敛到 True。

        Returns:
            list: 被标记为 skipped 的节点 ID 列表
        """
        skipped = [
            n.id for n in self._graph.nodes if n.status == TaskNodeStatus.PENDING
        ]
        for task_id in skipped:
            self._node_index[task_id].status = TaskNodeStatus.SKIPPED
        return skipped

    def get_progress(self) -> dict:
        """G4-C 进度快照（供事件/metadata 输出，不修改 Plan）。

        Returns:
            dict: {
                current_task_id, step_index, total_steps,
                completed, failed, skipped, pending, running,
                is_all_done, has_failed
            }
        """
        counts = {status.value: 0 for status in TaskNodeStatus}
        for n in self._graph.nodes:
            counts[n.status.value] = counts.get(n.status.value, 0) + 1
        return {
            "current_task_id": self._current_task_id,
            "step_index": self.get_step_index(self._current_task_id) if self._current_task_id else -1,
            "total_steps": len(self._graph.nodes),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "skipped": counts.get("skipped", 0),
            "pending": counts.get("pending", 0),
            "running": counts.get("running", 0),
            "is_all_done": self.is_all_done(),
            "has_failed": self.has_failed(),
        }

    def _iter_transitive_dependents(self, task_id: str):
        """迭代 task_id 的所有传递后继节点（BFS，按依赖关系向下一层展开）。

        后继定义：存在一条路径 task_id → n（经 depends_on / edges）。
        """
        visited = {task_id}
        queue = [task_id]
        while queue:
            current = queue.pop(0)
            for n in self._graph.nodes:
                if n.id in visited:
                    continue
                if current in n.depends_on:
                    visited.add(n.id)
                    queue.append(n.id)
                    yield n.id

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
