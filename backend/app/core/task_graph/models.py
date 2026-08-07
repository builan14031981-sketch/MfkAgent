"""TaskGraph 数据结构（G3 基础层）。

纯数据定义 + 图基础能力，不依赖 Runtime、AgentRuntime、PlannerService。
提供：
  - TaskNode / TaskEdge / TaskGraph 结构化定义
  - TaskGraph: nodes / edges 管理、DAG 校验、环检测、序列化
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict


class TaskNodeStatus(str, Enum):
    """任务节点状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskNode:
    """任务节点：TaskGraph 的基本单元。

    Attributes:
        id: 稳定节点标识（如 task_0、task_1）
        action: 任务动作描述
        suggested_tools: 建议的工具列表
        depends_on: 依赖的前置节点 ID 列表
        status: 节点当前状态
    """

    id: str = ""
    action: str = ""
    suggested_tools: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    status: TaskNodeStatus = TaskNodeStatus.PENDING
    # G5-A: 多 Agent 路由字段
    task_type: str = "action"            # chat / retrieve / code / analyze / action
    assigned_agent: str = "default_agent"  # default_agent / coding_agent / research_agent


@dataclass
class TaskEdge:
    """任务边：表示节点间的依赖关系。

    Attributes:
        from_id: 源节点 ID
        to_id: 目标节点 ID
    """

    from_id: str = ""
    to_id: str = ""


@dataclass
class TaskGraph:
    """任务图：有向无环图表示的任务计划（G3 基础层）。

    基础能力：
      - nodes 管理：add_node / get_node / has_node / remove_node
      - edges 管理：add_edge / has_edge / get_edges_from / get_edges_to / remove_edge
      - DAG 校验：has_cycle / validate / is_valid
      - 序列化：to_dict / from_dict（round-trip）

    Attributes:
        nodes: 任务节点列表（List[TaskNode]）
        edges: 边列表（List[TaskEdge]，明确数据结构，不使用 List[Dict]）
        metadata: 预留扩展字段（目标、模式、约束、规划来源等）
    """

    nodes: List[TaskNode] = field(default_factory=list)
    edges: List[TaskEdge] = field(default_factory=list)
    metadata: Optional[Dict] = None

    # ──── nodes 管理 ────

    def add_node(self, node: TaskNode) -> None:
        """添加节点；id 为空或重复时抛 ValueError。"""
        if not node.id:
            raise ValueError("TaskNode.id 不能为空")
        if self.has_node(node.id):
            raise ValueError(f"节点已存在: {node.id}")
        self.nodes.append(node)

    def get_node(self, node_id: str) -> Optional[TaskNode]:
        """按 id 获取节点；不存在返回 None。"""
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def has_node(self, node_id: str) -> bool:
        """节点是否存在。"""
        return self.get_node(node_id) is not None

    def remove_node(self, node_id: str) -> bool:
        """移除节点及其关联边；不存在返回 False。"""
        if not self.has_node(node_id):
            return False
        self.nodes = [n for n in self.nodes if n.id != node_id]
        self.edges = [e for e in self.edges if e.from_id != node_id and e.to_id != node_id]
        return True

    # ──── edges 管理 ────

    def add_edge(self, edge: TaskEdge) -> None:
        """添加边；端点不存在 / 自环 / 重复边时抛 ValueError。"""
        self._require_edge(edge)
        if self.has_edge(edge.from_id, edge.to_id):
            raise ValueError(f"边已存在: {edge.from_id} → {edge.to_id}")
        self.edges.append(edge)

    def add_edge_by_ids(self, from_id: str, to_id: str) -> TaskEdge:
        """便捷添加边（返回新建的 TaskEdge）。"""
        edge = TaskEdge(from_id=from_id, to_id=to_id)
        self.add_edge(edge)
        return edge

    def has_edge(self, from_id: str, to_id: str) -> bool:
        """是否存在 from_id → to_id 边。"""
        return any(e.from_id == from_id and e.to_id == to_id for e in self.edges)

    def get_edges_from(self, node_id: str) -> List[TaskEdge]:
        """以 node_id 为源节点的所有边。"""
        return [e for e in self.edges if e.from_id == node_id]

    def get_edges_to(self, node_id: str) -> List[TaskEdge]:
        """以 node_id 为目标节点的所有边。"""
        return [e for e in self.edges if e.to_id == node_id]

    def remove_edge(self, from_id: str, to_id: str) -> bool:
        """移除 from_id → to_id 边；不存在返回 False。"""
        for i, e in enumerate(self.edges):
            if e.from_id == from_id and e.to_id == to_id:
                self.edges.pop(i)
                return True
        return False

    def _require_edge(self, edge: TaskEdge) -> None:
        """边结构性校验：端点存在、非自环。"""
        if not self.has_node(edge.from_id):
            raise ValueError(f"源节点不存在: {edge.from_id}")
        if not self.has_node(edge.to_id):
            raise ValueError(f"目标节点不存在: {edge.to_id}")
        if edge.from_id == edge.to_id:
            raise ValueError(f"不允许自环边: {edge.from_id}")

    # ──── DAG 校验 ────

    def has_cycle(self) -> bool:
        """是否存在环（含自环）；使用 DFS 三色标记法。

        仅遍历 nodes 中存在的端点边；悬空边由 validate() 单独报告。
        """
        node_ids = [n.id for n in self.nodes]
        adjacency: Dict[str, List[str]] = {nid: [] for nid in node_ids}
        for e in self.edges:
            if e.from_id in adjacency and e.to_id in adjacency:
                adjacency[e.from_id].append(e.to_id)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {nid: WHITE for nid in node_ids}

        def _dfs(nid: str) -> bool:
            color[nid] = GRAY
            for neighbor in adjacency.get(nid, []):
                if color[neighbor] == GRAY:
                    return True  # 后向边 → 环
                if color[neighbor] == WHITE and _dfs(neighbor):
                    return True
            color[nid] = BLACK
            return False

        for nid in node_ids:
            if color[nid] == WHITE and _dfs(nid):
                return True
        return False

    def validate(self) -> List[str]:
        """校验图结构，返回错误信息列表；空列表 = 合法 DAG。

        检查项：空 id / 重复 id / 悬空边端点 / 自环 / 重复边 / 环。
        """
        errors: List[str] = []

        seen = set()
        for n in self.nodes:
            if not n.id:
                errors.append("存在空 id 节点")
            elif n.id in seen:
                errors.append(f"重复节点 id: {n.id}")
            else:
                seen.add(n.id)

        for e in self.edges:
            if not self.has_node(e.from_id):
                errors.append(f"边源节点不存在: {e.from_id}")
            if not self.has_node(e.to_id):
                errors.append(f"边目标节点不存在: {e.to_id}")
            if e.from_id == e.to_id:
                errors.append(f"自环边: {e.from_id}")

        edge_pairs = [(e.from_id, e.to_id) for e in self.edges]
        if len(set(edge_pairs)) != len(edge_pairs):
            errors.append("存在重复边")

        if self.has_cycle():
            errors.append("图中存在环（非 DAG）")

        return errors

    def is_valid(self) -> bool:
        """是否为合法 DAG（等价于 validate() 返回空列表）。"""
        return not self.validate()

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    # ──── 序列化 ────

    def to_dict(self) -> dict:
        """将 TaskGraph 序列化为字典。

        Returns:
            dict: 包含 nodes、edges、metadata 的字典
        """
        return {
            "nodes": [
                {
                    "id": node.id,
                    "action": node.action,
                    "suggested_tools": list(node.suggested_tools),
                    "depends_on": list(node.depends_on),
                    "status": node.status.value,
                    "task_type": node.task_type,
                    "assigned_agent": node.assigned_agent,
                }
                for node in self.nodes
            ],
            "edges": [
                {"from": edge.from_id, "to": edge.to_id}
                for edge in self.edges
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskGraph":
        """从 to_dict() 输出重建 TaskGraph（round-trip）。"""
        nodes = [
            TaskNode(
                id=node.get("id", ""),
                action=node.get("action", ""),
                suggested_tools=list(node.get("suggested_tools") or []),
                depends_on=list(node.get("depends_on") or []),
                status=TaskNodeStatus(node.get("status", "pending")),
                task_type=node.get("task_type", "action"),
                assigned_agent=node.get("assigned_agent", "default_agent"),
            )
            for node in data.get("nodes", [])
        ]
        edges = [
            TaskEdge(from_id=edge["from"], to_id=edge["to"])
            for edge in data.get("edges", [])
        ]
        return cls(nodes=nodes, edges=edges, metadata=data.get("metadata"))

    