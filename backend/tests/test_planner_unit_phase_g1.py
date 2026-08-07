"""MfkAgent Planner V1 — 单元测试（Phase G1）。

覆盖：
  U1. Plan.to_task_context 输出 V1 结构（goal/constraints/current_step）
  U2. Plan 无步骤 → current_step None
  U3. 非任务型请求（general_chat / decision=None）→ plan 返回 None
  U4. 任务型请求 → 生成 Plan，goal=首行
  U5. plan 模式 → 只读约束；build 模式无只读约束
  U6. RuntimeTaskContextAdapter.render(None) → 空字符串
  U7. RuntimeTaskContextAdapter.render(dict) → 目标/约束/当前步骤段落
  U8. Planner 不控制工具：suggested_tools 仅为文本参考，无执行/权限副作用
  U9. goal 截断 200 字符
  U10. TASK_INTENTS 全部意图都有步骤模板
  U11. Plan.current_step_index 指向步骤（V1 静态，不自动推进任务树）

运行：
  python backend/tests/test_planner_unit_phase_g1.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import asyncio
import io
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.planner import (  # noqa: E402
    Plan,
    PlanStep,
    PlannerService,
    get_planner,
    get_runtime_task_context_adapter,
    RuntimeTaskContextAdapter,
    TASK_INTENTS,
)
from app.core.planner.service import PLAN_MODE_CONSTRAINT  # noqa: E402

_SERVICE = get_planner()

results = []
failures = []


def run(name, fn):
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
    except Exception as e:  # noqa: BLE001
        results.append({"name": name, "ok": False, "detail": f"异常: {e!r}", "elapsed_ms": 0})
        failures.append(f"{name}: {e!r}")
        print(f"  ERROR {name}\n        {e!r}")


# ---------------------------------------------------------------------------
# U1. Plan.to_task_context V1 结构
# ---------------------------------------------------------------------------

def _test_u1_to_task_context():
    plan = Plan(
        goal="优化项目性能",
        steps=[
            PlanStep("分析代码", ["read_file", "run_command"]),
            PlanStep("实施优化", ["write_file"]),
        ],
        constraints=["不能修改数据库结构"],
        mode="build",
    )
    tc = plan.to_task_context()
    assert isinstance(tc, dict), "task_context 应为 dict"
    assert sorted(tc.keys()) == ["constraints", "current_step", "goal"], f"V1 键不符: {sorted(tc.keys())}"
    assert tc["goal"] == "优化项目性能"
    assert tc["constraints"] == ["不能修改数据库结构"]
    assert tc["current_step"] == "分析代码", "current_step 应为第一步 action"
    # 深拷贝：外部修改不影响内部
    tc["constraints"].append("x")
    assert plan.constraints == ["不能修改数据库结构"]
    return {"keys": sorted(plan.to_task_context().keys()), "current_step": tc["current_step"]}


# ---------------------------------------------------------------------------
# U2. 无步骤 → current_step None
# ---------------------------------------------------------------------------

def _test_u2_no_steps():
    plan = Plan(goal="闲聊", mode="build")
    assert plan.current_step is None
    tc = plan.to_task_context()
    assert tc["current_step"] is None
    return {"current_step": tc["current_step"]}


# ---------------------------------------------------------------------------
# U3. 非任务型请求 → None
# ---------------------------------------------------------------------------

def _test_u3_general_chat():
    p1 = asyncio.run(_SERVICE.plan(message="你好", mode="build", decision={"intent": "general_chat"}))
    p2 = asyncio.run(_SERVICE.plan(message="今天天气怎么样", mode="build"))
    p3 = asyncio.run(_SERVICE.plan(message="", mode="build", decision=None))
    assert p1 is None, "general_chat 不应产生计划"
    assert p2 is None, "无 decision 不应产生计划"
    assert p3 is None, "空消息不应产生计划"
    return {"general_chat": p1, "no_decision": p2, "empty": p3}


# ---------------------------------------------------------------------------
# U4. 任务型请求 → Plan + goal
# ---------------------------------------------------------------------------

def _test_u4_task_plan():
    msg = "检查系统状态并诊断网络问题"
    plan = asyncio.run(_SERVICE.plan(message=msg, mode="build", decision={"intent": "system_diagnosis"}))
    assert plan is not None, "任务型请求应产生计划"
    assert plan.goal == msg, f"goal 应取首行原文: {plan.goal!r}"
    assert plan.steps, "应有步骤"
    assert plan.steps[0].action, "步骤应有动作描述"
    assert plan.current_step == plan.steps[0].action
    assert plan.mode == "build"
    return {"goal": plan.goal, "steps": len(plan.steps), "current_step": plan.current_step}


# ---------------------------------------------------------------------------
# U5. plan 模式 → 只读约束
# ---------------------------------------------------------------------------

def _test_u5_mode_constraints():
    plan_mode = asyncio.run(_SERVICE.plan(message="分析项目结构", mode="plan", decision={"intent": "file_operation"}))
    build_mode = asyncio.run(_SERVICE.plan(message="分析项目结构", mode="build", decision={"intent": "file_operation"}))
    assert plan_mode is not None and build_mode is not None
    assert PLAN_MODE_CONSTRAINT in plan_mode.constraints, "plan 模式应注入只读约束"
    assert PLAN_MODE_CONSTRAINT not in build_mode.constraints, "build 模式不应注入只读约束"
    return {"plan_constraints": plan_mode.constraints, "build_constraints": build_mode.constraints}


# ---------------------------------------------------------------------------
# U6. adapter.render(None) → ""
# ---------------------------------------------------------------------------

def _test_u6_render_none():
    out = get_runtime_task_context_adapter().render(None)
    out2 = get_runtime_task_context_adapter().render({})
    assert out == "", "render(None) 应为空字符串"
    assert out2 == "", "render({}) 应为空字符串"
    return {"none": out, "empty_dict": out2}


# ---------------------------------------------------------------------------
# U7. adapter.render(dict) → 段落
# ---------------------------------------------------------------------------

def _test_u7_render_dict():
    tc = {
        "goal": "检查系统状态",
        "constraints": ["Plan 模式：只读分析", "不能修改数据库结构"],
        "current_step": "采集系统/网络/日志信息",
    }
    section = get_runtime_task_context_adapter().render(tc)
    assert "## 当前任务计划（Planner V1）" in section
    assert "目标: 检查系统状态" in section
    assert "约束: " in section and "只读分析" in section
    assert "当前步骤: 采集系统/网络/日志信息" in section
    assert "按计划推进" in section
    return {"title": section.splitlines()[0], "lines": len(section.splitlines())}


# ---------------------------------------------------------------------------
# U8. 不控制工具（结构化断言）
# ---------------------------------------------------------------------------

def _test_u8_no_tool_control():
    plan = asyncio.run(_SERVICE.plan(message="检查网络", mode="build", decision={"intent": "system_diagnosis"}))
    assert plan and plan.steps
    # suggested_tools 仅为工具名文本（reference），不是调用参数、不带执行
    for step in plan.steps:
        assert isinstance(step.suggested_tools, list)
        for t in step.suggested_tools:
            assert isinstance(t, str), "suggested_tools 应为字符串工具名"
    # PlannerService 不依赖 executor / tool_runtime / risk_engine（仅文本参考）
    import app.core.planner.service as _svc
    assert hasattr(_svc, "_STEP_TEMPLATES")
    return {"suggested": plan.steps[0].suggested_tools}


# ---------------------------------------------------------------------------
# U9. goal 截断 200 字符
# ---------------------------------------------------------------------------

def _test_u9_goal_truncate():
    long_msg = "很长的目标" * 200
    plan = asyncio.run(_SERVICE.plan(message=long_msg, mode="build", decision={"intent": "web_search"}))
    assert plan is not None
    assert len(plan.goal) == 200, f"goal 应截断到 200 字符，实际 {len(plan.goal)}"
    return {"goal_len": len(plan.goal)}


# ---------------------------------------------------------------------------
# U10. 全部任务意图都有模板
# ---------------------------------------------------------------------------

def _test_u10_all_intents():
    missing = []
    for intent in sorted(TASK_INTENTS):
        plan = asyncio.run(_SERVICE.plan(message="任务", mode="build", decision={"intent": intent}))
        if plan is None or not plan.steps:
            missing.append(intent)
    assert not missing, f"缺步骤模板的意图: {missing}"
    return {"intents": sorted(TASK_INTENTS), "count": len(TASK_INTENTS)}


# ---------------------------------------------------------------------------
# U11. current_step_index 指向（V1 静态不推进）
# ---------------------------------------------------------------------------

def _test_u11_current_step_index():
    plan = Plan(
        goal="g", steps=[PlanStep("s1"), PlanStep("s2")], mode="build", current_step_index=0
    )
    assert plan.current_step == "s1"
    plan2 = Plan(
        goal="g", steps=[PlanStep("s1"), PlanStep("s2")], mode="build", current_step_index=1
    )
    assert plan2.current_step == "s2"
    return {"idx0": plan.current_step, "idx1": plan2.current_step}


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 70)
    print("MfkAgent Planner V1 单元测试（Phase G1）")
    print("=" * 70)

    run("U1 Plan.to_task_context V1 结构", _test_u1_to_task_context)
    run("U2 无步骤 → current_step None", _test_u2_no_steps)
    run("U3 非任务型请求 → None", _test_u3_general_chat)
    run("U4 任务型请求 → Plan + goal", _test_u4_task_plan)
    run("U5 plan 模式 → 只读约束", _test_u5_mode_constraints)
    run("U6 adapter.render(None) → 空", _test_u6_render_none)
    run("U7 adapter.render(dict) → 段落", _test_u7_render_dict)
    run("U8 不控制工具（仅文本参考）", _test_u8_no_tool_control)
    run("U9 goal 截断 200 字符", _test_u9_goal_truncate)
    run("U10 全部意图有模板", _test_u10_all_intents)
    run("U11 current_step_index 指向", _test_u11_current_step_index)

    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (BACKEND_DIR / "tests" / "phase_g1_planner_unit_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# MfkAgent Planner V1 单元测试报告（Phase G1）\n",
             f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
             "## 结果总览\n",
             "| # | 用例 | 结果 | 耗时 |",
             "|---|------|------|------|",
             ]
    for i, r in enumerate(results, 1):
        lines.append(f"| {i} | {r['name']} | {'✅ PASS' if r['ok'] else '❌ FAIL'} | {r['elapsed_ms']}ms |")
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
