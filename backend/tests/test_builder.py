"""TaskGraphBuilder 单元测试（G3-B）。

聚焦 Builder 转换逻辑的正确性验证：
- 空 Plan / None Plan 边界处理
- 单步骤 Plan 节点映射与 status 初始值
- 多步骤线性 Plan 的 depends_on 与 TaskEdge 构造
- to_dict() 序列化结构合法性
"""

import unittest

from app.core.planner.models import Plan, PlanStep
from app.core.task_graph.builder import TaskGraphBuilder
from app.core.task_graph.models import (
    TaskGraph,
    TaskNode,
    TaskEdge,
    TaskNodeStatus,
)


class TestBuilderEmptyPlan(unittest.TestCase):
    """边界情况：None 与空 Plan。"""

    def setUp(self):
        self.builder = TaskGraphBuilder()

    def test_none_plan_returns_empty_graph(self):
        """None Plan → 空 TaskGraph，无节点无边无 metadata。"""
        graph = self.builder.build(None)

        self.assertIsInstance(graph, TaskGraph)
        self.assertEqual(len(graph.nodes), 0)
        self.assertEqual(len(graph.edges), 0)
        self.assertIsNone(graph.metadata)

    def test_empty_steps_returns_empty_nodes(self):
        """空 steps 的 Plan → 0 节点、0 边，metadata 仍保留 goal。"""
        plan = Plan(goal="空计划", steps=[])
        graph = self.builder.build(plan)

        self.assertEqual(len(graph.nodes), 0)
        self.assertEqual(len(graph.edges), 0)
        self.assertEqual(graph.metadata["goal"], "空计划")


class TestBuilderSingleStep(unittest.TestCase):
    """单步骤 Plan：验证字段映射与初始状态。"""

    def setUp(self):
        self.builder = TaskGraphBuilder()

    def test_node_count_and_edge_count(self):
        """单步骤 → 1 节点、0 边。"""
        plan = Plan(
            goal="分析",
            steps=[PlanStep(action="读取文件", suggested_tools=["read_file"])],
        )
        graph = self.builder.build(plan)

        self.assertEqual(len(graph.nodes), 1)
        self.assertEqual(len(graph.edges), 0)

    def test_node_field_mapping(self):
        """PlanStep 字段正确映射到 TaskNode。"""
        plan = Plan(
            goal="分析",
            steps=[PlanStep(action="读取文件", suggested_tools=["read_file"])],
        )
        graph = self.builder.build(plan)
        node = graph.nodes[0]

        self.assertEqual(node.id, "task_0")
        self.assertEqual(node.action, "读取文件")
        self.assertEqual(node.suggested_tools, ["read_file"])
        self.assertEqual(node.depends_on, [])

    def test_node_initial_status_pending(self):
        """所有节点初始 status 为 PENDING。"""
        plan = Plan(steps=[PlanStep(action="A")])
        graph = self.builder.build(plan)

        self.assertEqual(graph.nodes[0].status, TaskNodeStatus.PENDING)
        self.assertEqual(graph.nodes[0].status.value, "pending")


class TestBuilderMultiStep(unittest.TestCase):
    """多步骤线性 Plan：验证依赖链与 Edge 构造。"""

    def setUp(self):
        self.builder = TaskGraphBuilder()

    def test_node_count(self):
        """3 步骤 → 3 节点。"""
        plan = Plan(steps=[
            PlanStep(action="A"),
            PlanStep(action="B"),
            PlanStep(action="C"),
        ])
        graph = self.builder.build(plan)

        self.assertEqual(len(graph.nodes), 3)

    def test_edge_count(self):
        """3 步骤 → 2 条边（task_0→task_1, task_1→task_2）。"""
        plan = Plan(steps=[
            PlanStep(action="A"),
            PlanStep(action="B"),
            PlanStep(action="C"),
        ])
        graph = self.builder.build(plan)

        self.assertEqual(len(graph.edges), 2)

    def test_depends_on_chain(self):
        """depends_on 形成线性链：task_0 无依赖，task_1←task_0，task_2←task_1。"""
        plan = Plan(steps=[
            PlanStep(action="A"),
            PlanStep(action="B"),
            PlanStep(action="C"),
        ])
        graph = self.builder.build(plan)

        self.assertEqual(graph.nodes[0].depends_on, [])
        self.assertEqual(graph.nodes[1].depends_on, ["task_0"])
        self.assertEqual(graph.nodes[2].depends_on, ["task_1"])

    def test_edge_from_to(self):
        """TaskEdge 的 from_id / to_id 正确配对。"""
        plan = Plan(steps=[
            PlanStep(action="A"),
            PlanStep(action="B"),
        ])
        graph = self.builder.build(plan)

        self.assertIsInstance(graph.edges[0], TaskEdge)
        self.assertEqual(graph.edges[0].from_id, "task_0")
        self.assertEqual(graph.edges[0].to_id, "task_1")

    def test_node_ids_stable(self):
        """Node ID 按 task_0, task_1, ... 稳定生成。"""
        plan = Plan(steps=[
            PlanStep(action="X"),
            PlanStep(action="Y"),
            PlanStep(action="Z"),
        ])
        graph = self.builder.build(plan)

        self.assertEqual(graph.nodes[0].id, "task_0")
        self.assertEqual(graph.nodes[1].id, "task_1")
        self.assertEqual(graph.nodes[2].id, "task_2")

    def test_all_nodes_status_pending(self):
        """多步骤 Plan 中所有节点初始 status 均为 PENDING。"""
        plan = Plan(steps=[
            PlanStep(action="A"),
            PlanStep(action="B"),
            PlanStep(action="C"),
        ])
        graph = self.builder.build(plan)

        for node in graph.nodes:
            self.assertEqual(node.status, TaskNodeStatus.PENDING)


class TestBuilderSerialization(unittest.TestCase):
    """to_dict() 序列化结构合法性。"""

    def setUp(self):
        self.builder = TaskGraphBuilder()

    def test_to_dict_structure(self):
        """to_dict() 输出包含 nodes / edges / metadata 三键。"""
        plan = Plan(
            goal="构建",
            steps=[PlanStep(action="步骤1", suggested_tools=["t1"])],
            mode="build",
        )
        graph = self.builder.build(plan)
        d = graph.to_dict()

        self.assertIn("nodes", d)
        self.assertIn("edges", d)
        self.assertIn("metadata", d)

    def test_to_dict_node_fields(self):
        """to_dict() 中 node 包含 id / action / suggested_tools / depends_on / status。"""
        plan = Plan(steps=[
            PlanStep(action="A", suggested_tools=["tool_a"]),
            PlanStep(action="B", suggested_tools=["tool_b"]),
        ])
        graph = self.builder.build(plan)
        d = graph.to_dict()

        node0 = d["nodes"][0]
        self.assertEqual(node0["id"], "task_0")
        self.assertEqual(node0["action"], "A")
        self.assertEqual(node0["suggested_tools"], ["tool_a"])
        self.assertEqual(node0["depends_on"], [])
        self.assertEqual(node0["status"], "pending")

        node1 = d["nodes"][1]
        self.assertEqual(node1["id"], "task_1")
        self.assertEqual(node1["depends_on"], ["task_0"])
        self.assertEqual(node1["status"], "pending")

    def test_to_dict_edge_fields(self):
        """to_dict() 中 edge 包含 from / to 键。"""
        plan = Plan(steps=[
            PlanStep(action="A"),
            PlanStep(action="B"),
        ])
        graph = self.builder.build(plan)
        d = graph.to_dict()

        self.assertEqual(len(d["edges"]), 1)
        self.assertEqual(d["edges"][0], {"from": "task_0", "to": "task_1"})

    def test_to_dict_metadata(self):
        """to_dict() 中 metadata 保留 goal / mode / constraints / planner_source。"""
        plan = Plan(
            goal="目标",
            steps=[PlanStep(action="A")],
            constraints=["约束1"],
            mode="plan",
            planner_source="llm",
        )
        graph = self.builder.build(plan)
        d = graph.to_dict()

        self.assertEqual(d["metadata"]["goal"], "目标")
        self.assertEqual(d["metadata"]["mode"], "plan")
        self.assertEqual(d["metadata"]["constraints"], ["约束1"])
        self.assertEqual(d["metadata"]["planner_source"], "llm")


class TestBuilderPlanImmutability(unittest.TestCase):
    """转换后原 Plan 不被修改。"""

    def setUp(self):
        self.builder = TaskGraphBuilder()

    def test_plan_unchanged(self):
        """build() 不修改原 Plan 的任何字段。"""
        steps = [PlanStep(action="原始", suggested_tools=["t"])]
        plan = Plan(goal="g", steps=steps, mode="build", constraints=["c"])

        self.builder.build(plan)

        self.assertEqual(plan.goal, "g")
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].action, "原始")
        self.assertEqual(plan.steps[0].suggested_tools, ["t"])
        self.assertIs(plan.steps[0], steps[0])


# ---------------------------------------------------------------------------
# G5-A: 路由分配测试
# ---------------------------------------------------------------------------

from app.core.task_graph.builder import _infer_task_type_and_agent


class TestInferTaskTypeAndAgent(unittest.TestCase):
    """_infer_task_type_and_agent 路由推断函数测试。"""

    def test_code_tools_route_to_coding_agent(self):
        """包含 bash/git/write_file 等工具 → code / coding_agent"""
        for tool in ["bash", "git", "write_file", "read_file", "edit_file", "run_command", "python_REPL"]:
            task_type, agent = _infer_task_type_and_agent("随便", [tool])
            self.assertEqual(task_type, "code", f"tool={tool}")
            self.assertEqual(agent, "coding_agent", f"tool={tool}")

    def test_retrieve_tools_route_to_research_agent(self):
        """包含 search/read_webpage 等工具 → retrieve / research_agent"""
        for tool in ["search", "web_search", "read_webpage", "fetch_url", "tavily"]:
            task_type, agent = _infer_task_type_and_agent("随便", [tool])
            self.assertEqual(task_type, "retrieve", f"tool={tool}")
            self.assertEqual(agent, "research_agent", f"tool={tool}")

    def test_action_keyword_retrieve(self):
        """action 含搜索/检索/查询/查找 → retrieve / research_agent"""
        for kw in ["搜索资料", "检索文档", "查询状态", "查找文件"]:
            task_type, agent = _infer_task_type_and_agent(kw, [])
            self.assertEqual(task_type, "retrieve", f"action={kw}")
            self.assertEqual(agent, "research_agent", f"action={kw}")

    def test_action_keyword_code(self):
        """action 含部署/构建/修复/编写/运行/执行 → code / coding_agent"""
        for kw in ["部署应用", "构建镜像", "修复bug", "编写代码", "运行测试", "执行脚本"]:
            task_type, agent = _infer_task_type_and_agent(kw, [])
            self.assertEqual(task_type, "code", f"action={kw}")
            self.assertEqual(agent, "coding_agent", f"action={kw}")

    def test_action_keyword_analyze(self):
        """action 含分析/评估/总结 → analyze / default_agent"""
        for kw in ["分析代码", "评估结果", "总结报告"]:
            task_type, agent = _infer_task_type_and_agent(kw, [])
            self.assertEqual(task_type, "analyze", f"action={kw}")
            self.assertEqual(agent, "default_agent", f"action={kw}")

    def test_action_keyword_chat(self):
        """action 含对话/回答 → chat / default_agent"""
        for kw in ["对话交流", "回答问题"]:
            task_type, agent = _infer_task_type_and_agent(kw, [])
            self.assertEqual(task_type, "chat", f"action={kw}")
            self.assertEqual(agent, "default_agent", f"action={kw}")

    def test_fallback_default(self):
        """无匹配工具和关键词 → action / default_agent"""
        task_type, agent = _infer_task_type_and_agent("做一些事情", ["unknown_tool"])
        self.assertEqual(task_type, "action")
        self.assertEqual(agent, "default_agent")

    def test_empty_action_and_tools(self):
        """空 action + 空 tools → 兜底"""
        task_type, agent = _infer_task_type_and_agent("", [])
        self.assertEqual(task_type, "action")
        self.assertEqual(agent, "default_agent")

    def test_tool_priority_over_action(self):
        """工具匹配优先于 action 关键词。"""
        # action 说了"搜索"但工具是 write_file → 应路由到 code/coding_agent
        task_type, agent = _infer_task_type_and_agent("搜索并写入文件", ["write_file"])
        self.assertEqual(task_type, "code")
        self.assertEqual(agent, "coding_agent")

    def test_first_matching_tool_wins(self):
        """多个工具时，第一个匹配的工具决定路由。"""
        task_type, agent = _infer_task_type_and_agent("test", ["search", "write_file"])
        self.assertEqual(task_type, "retrieve")
        self.assertEqual(agent, "research_agent")


class TestBuilderRoutingIntegration(unittest.TestCase):
    """Builder.build() 中路由分配集成测试。"""

    def setUp(self):
        self.builder = TaskGraphBuilder()

    def test_mixed_steps_get_correct_routing(self):
        """混合步骤的 Plan → 每个节点路由正确。"""
        plan = Plan(steps=[
            PlanStep(action="搜索相关文档", suggested_tools=["search"]),
            PlanStep(action="编写实现代码", suggested_tools=["write_file"]),
            PlanStep(action="分析结果", suggested_tools=[]),
            PlanStep(action="部署服务", suggested_tools=["bash"]),
        ])
        graph = self.builder.build(plan)

        # task_0: search → retrieve / research_agent
        self.assertEqual(graph.nodes[0].task_type, "retrieve")
        self.assertEqual(graph.nodes[0].assigned_agent, "research_agent")

        # task_1: write_file → code / coding_agent
        self.assertEqual(graph.nodes[1].task_type, "code")
        self.assertEqual(graph.nodes[1].assigned_agent, "coding_agent")

        # task_2: "分析" 关键词 → analyze / default_agent
        self.assertEqual(graph.nodes[2].task_type, "analyze")
        self.assertEqual(graph.nodes[2].assigned_agent, "default_agent")

        # task_3: bash → code / coding_agent
        self.assertEqual(graph.nodes[3].task_type, "code")
        self.assertEqual(graph.nodes[3].assigned_agent, "coding_agent")

    def test_to_dict_includes_routing_fields(self):
        """to_dict() 输出包含 task_type 和 assigned_agent。"""
        plan = Plan(steps=[
            PlanStep(action="搜索", suggested_tools=["search"]),
        ])
        graph = self.builder.build(plan)
        d = graph.to_dict()

        self.assertEqual(d["nodes"][0]["task_type"], "retrieve")
        self.assertEqual(d["nodes"][0]["assigned_agent"], "research_agent")

    def test_default_values_for_unmatched(self):
        """无匹配的步骤 → task_type=action, assigned_agent=default_agent"""
        plan = Plan(steps=[
            PlanStep(action="做一些未知操作", suggested_tools=["unknown_tool"]),
        ])
        graph = self.builder.build(plan)

        self.assertEqual(graph.nodes[0].task_type, "action")
        self.assertEqual(graph.nodes[0].assigned_agent, "default_agent")


if __name__ == "__main__":
    unittest.main()