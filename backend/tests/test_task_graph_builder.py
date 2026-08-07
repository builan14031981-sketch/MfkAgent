"""TaskGraphBuilder 单元测试（G3-A）。

验证 Plan → TaskGraph 转换的正确性：
- None Plan / 空 Plan / 单步骤 / 多步骤依赖
- 原 Plan 未被修改
- to_dict() 序列化
- DAG 结构验证
"""

import unittest
from typing import Dict, List

from app.core.planner.models import Plan, PlanStep
from app.core.task_graph.builder import get_task_graph_builder
from app.core.task_graph.models import (
    TaskGraph,
    TaskNode,
    TaskEdge,
    TaskNodeStatus,
)


def _validate_dag(graph: TaskGraph) -> bool:
    """本地 DAG 环检测（DFS 三色标记法）。

    从 TaskGraph.validate() 迁移至测试文件，保持测试逻辑独立。
    """
    if not graph.nodes:
        return True

    node_ids = {n.id for n in graph.nodes}
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {nid: WHITE for nid in node_ids}

    adjacency: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    for edge in graph.edges:
        if edge.from_id in adjacency and edge.to_id in node_ids:
            adjacency[edge.from_id].append(edge.to_id)

    def dfs(node_id: str) -> bool:
        color[node_id] = GRAY
        for neighbor in adjacency.get(node_id, []):
            if color.get(neighbor, BLACK) == GRAY:
                return False
            if color.get(neighbor, BLACK) == WHITE:
                if not dfs(neighbor):
                    return False
        color[node_id] = BLACK
        return True

    for nid in node_ids:
        if color[nid] == WHITE:
            if not dfs(nid):
                return False

    return True


class TestTaskGraphBuilder(unittest.TestCase):
    """TaskGraphBuilder 转换逻辑测试。"""

    def setUp(self):
        self.builder = get_task_graph_builder()

    # ══════════════════════════════════════════════════════════════
    # 边界情况
    # ══════════════════════════════════════════════════════════════

    def test_none_plan_returns_empty_graph(self):
        """None Plan 应返回空 TaskGraph。"""
        graph = self.builder.build(None)

        self.assertIsInstance(graph, TaskGraph)
        self.assertEqual(len(graph.nodes), 0)
        self.assertEqual(len(graph.edges), 0)
        self.assertIsNone(graph.metadata)

    def test_empty_plan_steps(self):
        """空 steps 的 Plan 应返回空节点列表。"""
        plan = Plan(goal="test", steps=[])
        graph = self.builder.build(plan)

        self.assertEqual(len(graph.nodes), 0)
        self.assertEqual(len(graph.edges), 0)
        self.assertEqual(graph.metadata["goal"], "test")

    # ══════════════════════════════════════════════════════════════
    # 单步骤
    # ══════════════════════════════════════════════════════════════

    def test_single_step_plan(self):
        """单步骤 Plan：1 个节点，无依赖，无边，status 为 PENDING。"""
        step = PlanStep(action="读取 README.md", suggested_tools=["read_file"])
        plan = Plan(goal="分析文件", steps=[step])
        graph = self.builder.build(plan)

        self.assertEqual(len(graph.nodes), 1)
        self.assertEqual(len(graph.edges), 0)

        node = graph.nodes[0]
        self.assertEqual(node.id, "task_0")
        self.assertEqual(node.action, "读取 README.md")
        self.assertEqual(node.suggested_tools, ["read_file"])
        self.assertEqual(node.depends_on, [])
        self.assertEqual(node.status, TaskNodeStatus.PENDING)

    # ══════════════════════════════════════════════════════════════
    # 多步骤依赖
    # ══════════════════════════════════════════════════════════════

    def test_multi_step_dependency_chain(self):
        """多步骤 Plan：验证线性依赖链 task_0 ← task_1 ← task_2。"""
        plan = Plan(
            steps=[
                PlanStep(action="步骤1", suggested_tools=["tool1"]),
                PlanStep(action="步骤2", suggested_tools=["tool2"]),
                PlanStep(action="步骤3", suggested_tools=["tool3"]),
            ]
        )
        graph = self.builder.build(plan)

        # 节点数量
        self.assertEqual(len(graph.nodes), 3)

        # task_0：无依赖
        self.assertEqual(graph.nodes[0].id, "task_0")
        self.assertEqual(graph.nodes[0].action, "步骤1")
        self.assertEqual(graph.nodes[0].depends_on, [])

        # task_1：依赖 task_0
        self.assertEqual(graph.nodes[1].id, "task_1")
        self.assertEqual(graph.nodes[1].action, "步骤2")
        self.assertEqual(graph.nodes[1].depends_on, ["task_0"])

        # task_2：依赖 task_1
        self.assertEqual(graph.nodes[2].id, "task_2")
        self.assertEqual(graph.nodes[2].action, "步骤3")
        self.assertEqual(graph.nodes[2].depends_on, ["task_1"])

        # 边（TaskEdge 对象）
        self.assertEqual(len(graph.edges), 2)
        self.assertEqual(graph.edges[0].from_id, "task_0")
        self.assertEqual(graph.edges[0].to_id, "task_1")
        self.assertEqual(graph.edges[1].from_id, "task_1")
        self.assertEqual(graph.edges[1].to_id, "task_2")

    # ══════════════════════════════════════════════════════════════
    # 原 Plan 不可变
    # ══════════════════════════════════════════════════════════════

    def test_plan_unchanged_after_build(self):
        """转换后原 Plan 对象不应被修改。"""
        steps = [PlanStep(action="原始步骤", suggested_tools=["tool"])]
        plan = Plan(goal="test", steps=steps, mode="build", constraints=["c1"])

        original_action = plan.steps[0].action
        original_tools = list(plan.steps[0].suggested_tools)
        original_goal = plan.goal

        self.builder.build(plan)

        self.assertEqual(plan.goal, original_goal)
        self.assertEqual(plan.steps[0].action, original_action)
        self.assertEqual(plan.steps[0].suggested_tools, original_tools)
        self.assertEqual(len(plan.steps), 1)
        self.assertIs(plan.steps[0], steps[0])

    # ══════════════════════════════════════════════════════════════
    # metadata 传递
    # ══════════════════════════════════════════════════════════════

    def test_metadata_preserves_plan_fields(self):
        """metadata 应包含 goal / mode / constraints / planner_source。"""
        plan = Plan(
            goal="构建项目",
            steps=[PlanStep(action="安装依赖")],
            constraints=["保留兼容性"],
            mode="build",
            planner_source="llm",
        )
        graph = self.builder.build(plan)

        self.assertIsNotNone(graph.metadata)
        self.assertEqual(graph.metadata["goal"], "构建项目")
        self.assertEqual(graph.metadata["mode"], "build")
        self.assertEqual(graph.metadata["constraints"], ["保留兼容性"])
        self.assertEqual(graph.metadata["planner_source"], "llm")

    # ══════════════════════════════════════════════════════════════
    # 序列化 to_dict()
    # ══════════════════════════════════════════════════════════════

    def test_to_dict_empty_graph(self):
        """空 TaskGraph 的 to_dict() 输出。"""
        graph = TaskGraph()
        d = graph.to_dict()

        self.assertEqual(d["nodes"], [])
        self.assertEqual(d["edges"], [])
        self.assertIsNone(d["metadata"])

    def test_to_dict_single_node(self):
        """单节点 TaskGraph 的 to_dict() 输出。"""
        node = TaskNode(
            id="task_0",
            action="读文件",
            suggested_tools=["read"],
            status=TaskNodeStatus.PENDING,
        )
        graph = TaskGraph(nodes=[node], metadata={"goal": "test"})
        d = graph.to_dict()

        self.assertEqual(len(d["nodes"]), 1)
        self.assertEqual(d["nodes"][0]["id"], "task_0")
        self.assertEqual(d["nodes"][0]["action"], "读文件")
        self.assertEqual(d["nodes"][0]["suggested_tools"], ["read"])
        self.assertEqual(d["nodes"][0]["depends_on"], [])
        self.assertEqual(d["nodes"][0]["status"], "pending")
        self.assertEqual(d["edges"], [])
        self.assertEqual(d["metadata"], {"goal": "test"})

    def test_to_dict_with_edges(self):
        """带边的 TaskGraph to_dict() 输出。"""
        graph = TaskGraph(
            nodes=[
                TaskNode(id="task_0", action="A"),
                TaskNode(id="task_1", action="B", depends_on=["task_0"]),
            ],
            edges=[TaskEdge(from_id="task_0", to_id="task_1")],
            metadata={"mode": "build"},
        )
        d = graph.to_dict()

        self.assertEqual(len(d["nodes"]), 2)
        self.assertEqual(len(d["edges"]), 1)
        self.assertEqual(d["edges"][0], {"from": "task_0", "to": "task_1"})
        self.assertEqual(d["metadata"], {"mode": "build"})

    def test_to_dict_builder_output(self):
        """Builder 构建的 TaskGraph 能正确序列化。"""
        plan = Plan(
            goal="构建",
            steps=[
                PlanStep(action="步骤1", suggested_tools=["t1"]),
                PlanStep(action="步骤2", suggested_tools=["t2"]),
            ],
            mode="build",
            planner_source="heuristic",
        )
        graph = self.builder.build(plan)
        d = graph.to_dict()

        # 节点
        self.assertEqual(len(d["nodes"]), 2)
        self.assertEqual(d["nodes"][0]["id"], "task_0")
        self.assertEqual(d["nodes"][0]["status"], "pending")
        self.assertEqual(d["nodes"][1]["id"], "task_1")
        self.assertEqual(d["nodes"][1]["depends_on"], ["task_0"])

        # 边
        self.assertEqual(len(d["edges"]), 1)
        self.assertEqual(d["edges"][0], {"from": "task_0", "to": "task_1"})

        # metadata
        self.assertEqual(d["metadata"]["goal"], "构建")
        self.assertEqual(d["metadata"]["mode"], "build")
        self.assertEqual(d["metadata"]["planner_source"], "heuristic")

    def test_to_dict_status_values(self):
        """to_dict 中 status 输出为字符串值。"""
        node = TaskNode(id="t", status=TaskNodeStatus.FAILED)
        graph = TaskGraph(nodes=[node])
        d = graph.to_dict()

        self.assertEqual(d["nodes"][0]["status"], "failed")

    # ══════════════════════════════════════════════════════════════
    # DAG 结构验证
    # ══════════════════════════════════════════════════════════════

    def test_validate_empty_graph(self):
        """空图应通过 DAG 验证。"""
        graph = TaskGraph()
        self.assertTrue(_validate_dag(graph))

    def test_validate_single_node(self):
        """单节点图应通过 DAG 验证。"""
        graph = TaskGraph(nodes=[TaskNode(id="task_0")])
        self.assertTrue(_validate_dag(graph))

    def test_validate_linear_chain(self):
        """线性链（task_0 → task_1 → task_2）应通过 DAG 验证。"""
        plan = Plan(
            steps=[
                PlanStep(action="A"),
                PlanStep(action="B"),
                PlanStep(action="C"),
            ]
        )
        graph = self.builder.build(plan)
        self.assertTrue(_validate_dag(graph))

    def test_validate_diamond_dag(self):
        """菱形依赖（task_0 → task_1, task_0 → task_2, task_1 → task_3, task_2 → task_3）应通过。"""
        graph = TaskGraph(
            nodes=[
                TaskNode(id="task_0"),
                TaskNode(id="task_1", depends_on=["task_0"]),
                TaskNode(id="task_2", depends_on=["task_0"]),
                TaskNode(id="task_3", depends_on=["task_1", "task_2"]),
            ],
            edges=[
                TaskEdge(from_id="task_0", to_id="task_1"),
                TaskEdge(from_id="task_0", to_id="task_2"),
                TaskEdge(from_id="task_1", to_id="task_3"),
                TaskEdge(from_id="task_2", to_id="task_3"),
            ],
        )
        self.assertTrue(_validate_dag(graph))

    def test_validate_cycle_detected(self):
        """存在环的图应被 DAG 检测到。"""
        graph = TaskGraph(
            nodes=[
                TaskNode(id="task_0", depends_on=["task_2"]),
                TaskNode(id="task_1", depends_on=["task_0"]),
                TaskNode(id="task_2", depends_on=["task_1"]),
            ],
            edges=[
                TaskEdge(from_id="task_0", to_id="task_1"),
                TaskEdge(from_id="task_1", to_id="task_2"),
                TaskEdge(from_id="task_2", to_id="task_0"),  # 回边 → 环
            ],
        )
        self.assertFalse(_validate_dag(graph))

    def test_validate_self_loop(self):
        """自环应被 DAG 检测到。"""
        graph = TaskGraph(
            nodes=[TaskNode(id="task_0", depends_on=["task_0"])],
            edges=[TaskEdge(from_id="task_0", to_id="task_0")],
        )
        self.assertFalse(_validate_dag(graph))

    def test_validate_builder_output_is_dag(self):
        """Builder 构建的所有图都应通过 DAG 验证。"""
        # 单步骤
        plan1 = Plan(steps=[PlanStep(action="A")])
        self.assertTrue(_validate_dag(self.builder.build(plan1)))

        # 多步骤
        plan2 = Plan(steps=[PlanStep(action="A"), PlanStep(action="B"), PlanStep(action="C")])
        self.assertTrue(_validate_dag(self.builder.build(plan2)))

        # 空
        self.assertTrue(_validate_dag(self.builder.build(None)))


if __name__ == "__main__":
    unittest.main()