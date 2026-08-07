"""TaskGraph 基础层单元测试（Phase G3）。

覆盖：
  G3-1 节点创建：TaskNode 字段 / add_node / get_node / has_node / remove_node / 重复拒绝
  G3-2 边关系：TaskEdge 明确结构（非 List[Dict]）/ add_edge / has_edge / from/to 查询 / remove_edge
  G3-3 DAG 正确性：线性链 / 菱形 / 多连通分量 / 单节点 → is_valid
  G3-4 环检测：三节点环 / 自环 / 两节点环 → has_cycle / validate 报告
  G3-5 序列化：to_dict → from_dict round-trip 等价
  G3-6 合法性校验：悬空边 / 重复 id / 重复边报告

运行：
  python backend/tests/test_task_graph_foundation_phase_g3.py

退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import sys
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.task_graph.models import TaskGraph, TaskNode, TaskEdge, TaskNodeStatus  # noqa: E402
from app.core.task_graph.builder import get_task_graph_builder  # noqa: E402
from app.core.planner.models import Plan, PlanStep  # noqa: E402

results = []
failures = []


def run(name, fn):
    import time
    t0 = time.monotonic()
    try:
        detail = fn()
        ok = detail.pop("all_ok", True)
        elapsed = (time.monotonic() - t0) * 1000
        results.append({"name": name, "ok": ok, "detail": detail, "elapsed_ms": round(elapsed)})
        if ok:
            print(f"  PASS  {name}  ({elapsed:.0f}ms)")
        else:
            failures.append(f"{name}: {detail}")
            print(f"  FAIL  {name}  ({elapsed:.0f}ms)")
    except AssertionError as e:
        results.append({"name": name, "ok": False, "detail": str(e), "elapsed_ms": 0})
        failures.append(f"{name}: {e}")
        print(f"  FAIL  {name}\n        {e}")
    except Exception as e:
        results.append({"name": name, "ok": False, "detail": f"异常: {e!r}", "elapsed_ms": 0})
        failures.append(f"{name}: {e!r}")
        print(f"  ERROR {name}\n        {e!r}")


def _node(nid, action="", deps=None, status=TaskNodeStatus.PENDING) -> TaskNode:
    return TaskNode(id=nid, action=action, depends_on=list(deps or []), status=status)


def _linear_graph(n: int) -> TaskGraph:
    """构造线性链 task_0 → task_1 → ... → task_{n-1}。"""
    g = TaskGraph()
    for i in range(n):
        g.add_node(_node(f"task_{i}", f"步骤{i}"))
    for i in range(1, n):
        g.add_edge_by_ids(f"task_{i - 1}", f"task_{i}")
    return g


# ═════════════════════════════════════════════════════════════════════════
# G3-1 节点创建
# ═════════════════════════════════════════════════════════════════════════

def _test_node_creation():
    node = TaskNode(id="task_0", action="读取文件", suggested_tools=["read_file"],
                    status=TaskNodeStatus.PENDING)
    assert node.id == "task_0"
    assert node.action == "读取文件"
    assert node.suggested_tools == ["read_file"]
    assert node.status == TaskNodeStatus.PENDING
    assert node.task_type == "action"
    assert node.assigned_agent == "default_agent"
    return {"id": node.id, "status": node.status.value, "has_action": bool(node.action)}


def _test_add_and_get_node():
    g = TaskGraph()
    g.add_node(_node("a", "动作A"))
    assert g.has_node("a")
    assert g.get_node("a").action == "动作A"
    assert g.get_node("nope") is None
    assert g.node_count == 1
    return {"has": g.has_node("a"), "count": g.node_count}


def _test_add_duplicate_node_rejected():
    g = TaskGraph()
    g.add_node(_node("a"))
    try:
        g.add_node(_node("a"))
    except ValueError:
        return {"duplicate_rejected": True}
    raise AssertionError("重复节点 id 应抛 ValueError")


def _test_add_empty_id_rejected():
    g = TaskGraph()
    try:
        g.add_node(_node(""))
    except ValueError:
        return {"empty_id_rejected": True}
    raise AssertionError("空 id 节点应抛 ValueError")


def _test_remove_node():
    g = _linear_graph(3)
    assert g.remove_node("task_1") is True
    assert not g.has_node("task_1")
    assert g.get_node("task_1") is None
    # 关联边也应被移除（task_0→task_1、task_1→task_2）
    assert not g.has_edge("task_0", "task_1")
    assert not g.has_edge("task_1", "task_2")
    assert g.edge_count == 0, f"关联边应被移除，实际 edges={g.edges}"
    assert g.remove_node("missing") is False
    return {"node_removed": True, "edge_count": g.edge_count}


# ═════════════════════════════════════════════════════════════════════════
# G3-2 边关系
# ═════════════════════════════════════════════════════════════════════════

def _test_typed_edges():
    g = TaskGraph(nodes=[_node("a"), _node("b")], edges=[TaskEdge(from_id="a", to_id="b")])
    assert isinstance(g.edges[0], TaskEdge), "边必须是 TaskEdge 结构化对象，而非 dict"
    assert g.edges[0].from_id == "a" and g.edges[0].to_id == "b"
    assert not isinstance(g.edges[0], dict)
    return {"edge_type": type(g.edges[0]).__name__}


def _test_add_edge_queries():
    g = TaskGraph(nodes=[_node("a"), _node("b"), _node("c")])
    g.add_edge(TaskEdge(from_id="a", to_id="b"))
    g.add_edge_by_ids("a", "c")
    assert g.has_edge("a", "b")
    assert g.has_edge("a", "c")
    assert not g.has_edge("b", "c")
    assert [e.to_id for e in g.get_edges_from("a")] == ["b", "c"]
    assert [e.from_id for e in g.get_edges_to("b")] == ["a"]
    assert g.edge_count == 2
    return {"from_a": [e.to_id for e in g.get_edges_from("a")],
            "to_b": [e.from_id for e in g.get_edges_to("b")]}


def _test_add_edge_rejects_missing_endpoints():
    g = TaskGraph(nodes=[_node("a")])
    for edge in (TaskEdge(from_id="a", to_id="x"), TaskEdge(from_id="x", to_id="a")):
        try:
            g.add_edge(edge)
        except ValueError:
            continue
        raise AssertionError(f"悬空端点边应抛 ValueError: {edge}")
    return {"missing_endpoint_rejected": True}


def _test_add_edge_rejects_self_loop_and_duplicate():
    g = TaskGraph(nodes=[_node("a"), _node("b")])
    try:
        g.add_edge_by_ids("a", "a")
    except ValueError:
        pass
    else:
        raise AssertionError("自环边应抛 ValueError")
    g.add_edge_by_ids("a", "b")
    try:
        g.add_edge_by_ids("a", "b")
    except ValueError:
        pass
    else:
        raise AssertionError("重复边应抛 ValueError")
    assert g.edge_count == 1
    return {"self_loop_rejected": True, "duplicate_rejected": True}


def _test_remove_edge():
    g = _linear_graph(2)
    assert g.remove_edge("task_0", "task_1") is True
    assert not g.has_edge("task_0", "task_1")
    assert g.remove_edge("task_0", "task_1") is False
    return {"edge_removed": True}


# ═════════════════════════════════════════════════════════════════════════
# G3-3 DAG 正确性
# ═════════════════════════════════════════════════════════════════════════

def _test_dag_linear_chain():
    assert _linear_graph(3).is_valid(), "线性链应为合法 DAG"
    assert _linear_graph(1).is_valid()
    return {"linear_ok": True}


def _test_dag_diamond():
    g = TaskGraph()
    for nid in ("t0", "t1", "t2", "t3"):
        g.add_node(_node(nid))
    g.add_edge_by_ids("t0", "t1")
    g.add_edge_by_ids("t0", "t2")
    g.add_edge_by_ids("t1", "t3")
    g.add_edge_by_ids("t2", "t3")
    assert g.is_valid(), "菱形依赖应为合法 DAG"
    return {"diamond_ok": True}


def _test_dag_disconnected():
    g = TaskGraph(nodes=[_node("a"), _node("b"), _node("c")])
    g.add_edge_by_ids("a", "b")  # c 孤立
    assert g.is_valid(), "多连通分量（无环）应为合法 DAG"
    return {"disconnected_ok": True}


def _test_dag_empty_and_single():
    assert TaskGraph().is_valid()
    assert TaskGraph(nodes=[_node("only")]).is_valid()
    return {"empty_ok": True, "single_ok": True}


# ═════════════════════════════════════════════════════════════════════════
# G3-4 环检测
# ═════════════════════════════════════════════════════════════════════════

def _test_cycle_three_nodes():
    g = TaskGraph(nodes=[_node("a", deps=["c"]), _node("b", deps=["a"]), _node("c", deps=["b"])])
    g.add_edge_by_ids("a", "b")
    g.add_edge_by_ids("b", "c")
    g.add_edge_by_ids("c", "a")  # 回边 → 环
    assert g.has_cycle() is True
    errors = g.validate()
    assert any("环" in e for e in errors), f"validate 应报告环，实际: {errors}"
    assert g.is_valid() is False
    return {"has_cycle": True, "errors": errors}


def _test_cycle_self_loop():
    # 直接构造自环（add_edge 结构性拒绝，构造器允许以便校验发现）
    g = TaskGraph(nodes=[_node("a")], edges=[TaskEdge(from_id="a", to_id="a")])
    assert g.has_cycle() is True
    assert g.is_valid() is False
    return {"self_loop_detected": True}


def _test_cycle_two_nodes():
    g = TaskGraph(nodes=[_node("a"), _node("b")])
    g.add_edge_by_ids("a", "b")
    g.add_edge_by_ids("b", "a")
    assert g.has_cycle() is True
    return {"two_node_cycle": True}


def _test_no_cycle_forward_edges():
    g = _linear_graph(4)
    assert g.has_cycle() is False
    return {"forward_edges_ok": True}


# ═════════════════════════════════════════════════════════════════════════
# G3-5 序列化
# ═════════════════════════════════════════════════════════════════════════

def _test_roundtrip_manual():
    g = TaskGraph()
    g.add_node(_node("t0", "A"))
    g.add_node(_node("t1", "B", deps=["t0"], status=TaskNodeStatus.COMPLETED))
    g.add_edge_by_ids("t0", "t1")
    g.metadata = {"goal": "手动图", "mode": "build"}

    d = g.to_dict()
    assert d["edges"][0] == {"from": "t0", "to": "t1"}
    g2 = TaskGraph.from_dict(d)

    assert g2.node_count == 2
    assert g2.edge_count == 1
    assert g2.get_node("t1").status == TaskNodeStatus.COMPLETED
    assert g2.get_node("t1").depends_on == ["t0"]
    assert g2.has_edge("t0", "t1")
    assert g2.metadata == {"goal": "手动图", "mode": "build"}
    # round-trip 后再校验仍是合法 DAG
    assert g2.is_valid()
    # to_dict 输出稳定
    assert g2.to_dict() == d
    return {"roundtrip_ok": True, "nodes": g2.node_count, "edges": g2.edge_count}


def _test_roundtrip_builder_output():
    plan = Plan(
        goal="构建",
        steps=[
            PlanStep(action="安装依赖", suggested_tools=["run_command"]),
            PlanStep(action="编译", suggested_tools=["run_command"]),
            PlanStep(action="测试", suggested_tools=["run_command"]),
        ],
        mode="build",
        planner_source="heuristic",
    )
    graph = get_task_graph_builder().build(plan)
    restored = TaskGraph.from_dict(graph.to_dict())

    assert restored.to_dict() == graph.to_dict(), "round-trip 后 to_dict 应完全一致"
    assert restored.node_count == 3
    assert restored.get_node("task_1").depends_on == ["task_0"]
    assert restored.get_node("task_2").task_type == "code"
    assert restored.get_node("task_2").assigned_agent == "coding_agent"
    return {"roundtrip_equal": restored.to_dict() == graph.to_dict()}


def _test_to_dict_metadata_preserved():
    g = TaskGraph(nodes=[_node("a")], metadata={"goal": "g", "constraints": ["c"]})
    d = g.to_dict()
    assert d["metadata"] == {"goal": "g", "constraints": ["c"]}
    assert TaskGraph.from_dict(d).metadata == {"goal": "g", "constraints": ["c"]}
    return {"metadata_preserved": True}


# ═════════════════════════════════════════════════════════════════════════
# G3-6 合法性校验报告
# ═════════════════════════════════════════════════════════════════════════

def _test_validate_dangling_edge():
    g = TaskGraph(nodes=[_node("a")], edges=[TaskEdge(from_id="a", to_id="ghost")])
    errors = g.validate()
    assert any("ghost" in e for e in errors), f"应报告悬空端点，实际: {errors}"
    return {"dangling_reported": errors}


def _test_validate_duplicate_id():
    g = TaskGraph(nodes=[_node("a"), _node("a")])
    errors = g.validate()
    assert any("重复" in e for e in errors), f"应报告重复 id，实际: {errors}"
    return {"dup_id_reported": errors}


def _test_validate_duplicate_edge():
    g = TaskGraph(nodes=[_node("a"), _node("b")],
                  edges=[TaskEdge(from_id="a", to_id="b"), TaskEdge(from_id="a", to_id="b")])
    errors = g.validate()
    assert any("重复边" in e for e in errors), f"应报告重复边，实际: {errors}"
    return {"dup_edge_reported": errors}


def _test_builder_output_always_dag():
    builder = get_task_graph_builder()
    for plan in (None, Plan(steps=[]), Plan(steps=[PlanStep(action="A")]),
                 Plan(steps=[PlanStep(action="A"), PlanStep(action="B"), PlanStep(action="C")])):
        g = builder.build(plan)
        assert g.validate() == [], f"Builder 输出应合法 DAG，实际: {g.validate()}"
    return {"builder_always_dag": True}


def main() -> int:
    print("=" * 70)
    print("MfkAgent TaskGraph 基础层 单元测试（Phase G3）")
    print("=" * 70)

    run("G3-1a 节点创建字段", _test_node_creation)
    run("G3-1b add/get/has 节点", _test_add_and_get_node)
    run("G3-1c 重复节点拒绝", _test_add_duplicate_node_rejected)
    run("G3-1d 空 id 节点拒绝", _test_add_empty_id_rejected)
    run("G3-1e remove 节点（含关联边）", _test_remove_node)
    run("G3-2a 边为明确结构 TaskEdge", _test_typed_edges)
    run("G3-2b add/has/from/to 边查询", _test_add_edge_queries)
    run("G3-2c 悬空端点边拒绝", _test_add_edge_rejects_missing_endpoints)
    run("G3-2d 自环/重复边拒绝", _test_add_edge_rejects_self_loop_and_duplicate)
    run("G3-2e remove 边", _test_remove_edge)
    run("G3-3a DAG 线性链", _test_dag_linear_chain)
    run("G3-3b DAG 菱形", _test_dag_diamond)
    run("G3-3c DAG 多连通分量", _test_dag_disconnected)
    run("G3-3d DAG 空/单节点", _test_dag_empty_and_single)
    run("G3-4a 三节点环检测", _test_cycle_three_nodes)
    run("G3-4b 自环检测", _test_cycle_self_loop)
    run("G3-4c 两节点环检测", _test_cycle_two_nodes)
    run("G3-4d 前向边无环", _test_no_cycle_forward_edges)
    run("G3-5a to_dict/from_dict 手工图", _test_roundtrip_manual)
    run("G3-5b Builder 输出 round-trip", _test_roundtrip_builder_output)
    run("G3-5c metadata 序列化保留", _test_to_dict_metadata_preserved)
    run("G3-6a 悬空边报告", _test_validate_dangling_edge)
    run("G3-6b 重复 id 报告", _test_validate_duplicate_id)
    run("G3-6c 重复边报告", _test_validate_duplicate_edge)
    run("G3-6d Builder 输出恒为 DAG", _test_builder_output_always_dag)

    report_path = BACKEND_DIR / "tests" / "phase_g3_taskgraph_report.md"
    lines = [
        "# MfkAgent TaskGraph 基础层 测试报告（Phase G3）\n",
        "## 结果总览\n",
        "| # | 用例 | 结果 | 耗时 |",
        "|---|------|------|------|",
    ]
    for i, r in enumerate(results, 1):
        lines.append(
            f"| {i} | {r['name']} | {'✅ PASS' if r['ok'] else '❌ FAIL'} | {r['elapsed_ms']}ms |"
        )
    passed = sum(1 for r in results if r["ok"])
    lines.append(f"\n**通过率: {passed}/{len(results)}**\n")
    lines.append("## 验证明细\n")
    for i, r in enumerate(results, 1):
        lines.append(f"### {i}. {r['name']}\n")
        d = r["detail"]
        if isinstance(d, dict):
            for k, v in d.items():
                lines.append(f"- {k}: {v}")
        else:
            lines.append(f"- 说明: {d}")
        lines.append("")
        if not r["ok"]:
            lines.append(f"> 失败: {d}\n")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n报告已生成:", report_path)

    print(f"结果: {passed}/{len(results)} 通过")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
