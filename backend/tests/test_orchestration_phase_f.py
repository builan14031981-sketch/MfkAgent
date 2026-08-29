"""MfkAgent Orchestration Phase — 单元测试（2026-08-16）。

覆盖：
  O1. 角色目录完整性：7 个角色、必要字段、身份模板含协作提示
  O2. 启发式兜底：复杂任务关键词 → COMPLEX；短任务 → SIMPLE；空 → SIMPLE
  O3. LLM JSON 解析：纯 JSON / markdown 包裹 / 非法输入
  O4. _build_subtasks：合法角色保留、非法角色过滤、缺字段过滤
  O5. 编排报告渲染：to_tool_output 含各角色结论与综合建议
  O6. 工具注册：spawn_orchestration / delegate_sub_agent 已在 tool_registry
  O7. PermissionFilter：spawn_orchestration 出现在会话工具目录
  O8. OrchestrationPlan 默认值（SIMPLE / need_orchestration=False）
  O9. 并行上限常量（MAX_CONCURRENCY=4）

运行：
  python backend/tests/test_orchestration_phase_f.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import asyncio
import io
import sys
import time
from pathlib import Path

if __name__ == "__main__" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.orchestrator.models import (  # noqa: E402
    OrchestrationPlan,
    OrchestrationReport,
    SubTaskResult,
    SubTaskSpec,
    TaskComplexity,
)
from app.core.orchestrator.planner import (  # noqa: E402
    _build_subtasks,
    _heuristic_fallback,
    _parse_llm_json,
)
from app.core.orchestrator.roles import (  # noqa: E402
    ORCHESTRATION_ROLES,
    ROLE_TO_TEMPLATE_ID,
    get_orchestration_role,
    list_orchestration_roles,
    role_ids,
)
from app.core.orchestrator.runner import MAX_CONCURRENCY  # noqa: E402
from app.core.orchestrator.runner import _synthesize  # noqa: E402
from app.services.tools import tool_registry  # noqa: E402

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
            failures.append(name)
            print(f"  FAIL  {name}  ({elapsed:.0f}ms)  {detail}")
    except Exception as e:
        failures.append(name)
        results.append({"name": name, "ok": False, "detail": {"error": str(e)}})
        print(f"  ERROR {name}  {e!r}")


# ── O1: 角色目录 ────────────────────────────────────────────────────────────

def t_roles():
    all_ok = True
    detail = {}
    rids = role_ids()
    detail["count"] = len(rids)
    detail["roles"] = rids
    if len(rids) < 5:
        all_ok = False
    required = {"architecture", "backend", "frontend", "testing", "security"}
    missing = required - set(rids)
    detail["missing"] = list(missing)
    if missing:
        all_ok = False
    for rid in rids:
        r = get_orchestration_role(rid)
        if not r or not r.name or not r.description or not r.identity_template:
            all_ok = False
            detail.setdefault("invalid", []).append(rid)
    return {"all_ok": all_ok, **detail}


# ── O1b: 角色 → 内置模板映射对齐 ──────────────────────────────────────────────

def t_role_template_map():
    all_ok = True
    detail = {}
    all_roles = set(ORCHESTRATION_ROLES.keys())
    mapped = set(ROLE_TO_TEMPLATE_ID.keys())
    detail["role_count"] = len(all_roles)
    detail["mapped_count"] = len(mapped)
    if all_roles != mapped:
        all_ok = False
        detail["unmapped"] = sorted(all_roles - mapped)
        detail["extra"] = sorted(mapped - all_roles)
    # 每个模板 id 必须以 sub_ 开头（agents 表内置模板命名约定）
    bad = [v for v in ROLE_TO_TEMPLATE_ID.values() if not str(v).startswith("sub_")]
    detail["bad_template_ids"] = bad
    if bad:
        all_ok = False
    # 全部映射角色仍可解析（DB 兜底或内存）
    missing = [rid for rid in mapped if get_orchestration_role(rid) is None]
    detail["unresolvable"] = missing
    if missing:
        all_ok = False
    return {"all_ok": all_ok, **detail}


# ── O2: 启发式兜底 ──────────────────────────────────────────────────────────

def t_heuristic():
    all_ok = True
    detail = {}
    p1 = _heuristic_fallback("帮我开发一个完整的商城系统，需要前端和后端")
    detail["complex"] = p1.complexity.value
    if p1.complexity != TaskComplexity.COMPLEX:
        all_ok = False
    p2 = _heuristic_fallback("当前时间是多少")
    detail["simple"] = p2.complexity.value
    if p2.complexity != TaskComplexity.SIMPLE:
        all_ok = False
    p3 = _heuristic_fallback("")
    detail["empty"] = p3.complexity.value
    if p3.complexity != TaskComplexity.SIMPLE:
        all_ok = False
    return {"all_ok": all_ok, **detail}


# ── O3: LLM JSON 解析 ───────────────────────────────────────────────────────

def t_json_parse():
    all_ok = True
    detail = {}
    r1 = _parse_llm_json('{"complexity": "complex", "reason": "x", "subtasks": []}')
    detail["plain"] = bool(r1)
    if not r1 or r1.get("complexity") != "complex":
        all_ok = False
    r2 = _parse_llm_json('```json\n{"a": 1}\n```')
    detail["fence"] = bool(r2)
    if not r2 or r2.get("a") != 1:
        all_ok = False
    r3 = _parse_llm_json("garbage text no json")
    detail["invalid"] = r3
    if r3 is not None:
        all_ok = False
    return {"all_ok": all_ok, **detail}


# ── O4: 子任务构建与角色过滤 ────────────────────────────────────────────────

def t_subtasks():
    all_ok = True
    detail = {}
    raw = [
        {"role": "architecture", "task": "设计架构", "output_format": "决策清单"},
        {"role": "backend", "task": "实现后端", "output_format": ""},
        {"role": "not_exist_role", "task": "非法角色", "output_format": ""},
        {"role": "frontend", "task": "", "output_format": ""},   # 空 task → 过滤
        "not-a-dict",                                            # 非法类型 → 过滤
    ]
    subs = _build_subtasks(raw)
    detail["count"] = len(subs)
    detail["roles"] = [s.role for s in subs]
    if len(subs) != 2 or subs[0].role != "architecture" or subs[1].role != "backend":
        all_ok = False
    # 非法角色/空任务绝不进入（安全：不注入任意身份）
    if any(s.role == "not_exist_role" for s in subs):
        all_ok = False
    # max_tokens 继承角色定义
    backend = get_orchestration_role("backend")
    if subs[1].max_tokens != backend.max_tokens:
        all_ok = False
        detail["max_tokens_mismatch"] = True
    return {"all_ok": all_ok, **detail}


# ── O5: 报告渲染 ────────────────────────────────────────────────────────────

def t_report_render():
    all_ok = True
    detail = {}
    plan = OrchestrationPlan(
        complexity=TaskComplexity.COMPLEX,
        need_orchestration=True,
        subtasks=[SubTaskSpec(role="architecture", task="设计", output_format="决策")],
        reason="跨领域任务",
    )
    report = OrchestrationReport(
        plan=plan,
        results=[
            SubTaskResult(role="architecture", status="completed",
                          summary="采用微服务架构", key_findings=["分层清晰"]),
            SubTaskResult(role="security", status="failed", error="模型不可用"),
        ],
        synthesis="综合：架构可行，需复核安全项。",
    )
    out = report.to_tool_output()
    detail["has_roles"] = ("architecture" in out and "security" in out)
    detail["has_status"] = ("✓" in out and "✗" in out)
    detail["has_synthesis"] = ("综合结论" in out)
    detail["has_error"] = ("模型不可用" in out)
    if not (detail["has_roles"] and detail["has_status"] and detail["has_synthesis"] and detail["has_error"]):
        all_ok = False
    # 无编排 → 直接提示不编排
    simple_plan = OrchestrationPlan()
    simple_out = OrchestrationReport(plan=simple_plan).to_tool_output()
    detail["skip"] = ("无需编排" in simple_out)
    if "无需编排" not in simple_out:
        all_ok = False
    return {"all_ok": all_ok, **detail}


# ── O6: 工具注册 ────────────────────────────────────────────────────────────

def t_tool_registration():
    all_ok = True
    detail = {}
    names = [t.name for t in tool_registry.get_all()]
    detail["spawn_orchestration"] = "spawn_orchestration" in names
    detail["delegate_sub_agent"] = "delegate_sub_agent" in names
    if "spawn_orchestration" not in names or "delegate_sub_agent" not in names:
        all_ok = False
    # 工具定义含参数 schema
    defs = {t["function"]["name"]: t for t in tool_registry.get_definitions()}
    spawn = defs.get("spawn_orchestration")
    detail["spawn_schema"] = bool(spawn and spawn["function"]["parameters"].get("properties", {}).get("task"))
    if not detail["spawn_schema"]:
        all_ok = False
    return {"all_ok": all_ok, **detail}


# ── O7: 权限目录 ────────────────────────────────────────────────────────────

def t_permission():
    all_ok = True
    detail = {}
    from app.core.tool_runtime.permission import PermissionFilter

    class _Chat:
        mode = "build"
        project_path = "/tmp/proj"

    tools = PermissionFilter().resolve(_Chat())
    detail["in_dir"] = "spawn_orchestration" in tools
    if "spawn_orchestration" not in tools:
        all_ok = False
    return {"all_ok": all_ok, **detail}


# ── O8: 默认值 ──────────────────────────────────────────────────────────────

def t_defaults():
    all_ok = True
    detail = {}
    p = OrchestrationPlan()
    detail["complexity"] = p.complexity.value
    detail["need"] = p.need_orchestration
    if p.complexity != TaskComplexity.SIMPLE or p.need_orchestration:
        all_ok = False
    return {"all_ok": all_ok, **detail}


# ── O9: 并行上限 ────────────────────────────────────────────────────────────

def t_concurrency():
    return {"all_ok": MAX_CONCURRENCY == 4, "max_concurrency": MAX_CONCURRENCY}


# ── O10: 汇总合成 ───────────────────────────────────────────────────────────

def t_synthesize():
    all_ok = True
    detail = {}
    results = [
        SubTaskResult(role="architecture", status="completed", summary="架构A方案"),
        SubTaskResult(role="security", status="failed", error="调用失败"),
    ]
    s = _synthesize(results)
    detail["has_counts"] = ("2 个子代理" in s and "1 成功、1 失败" in s)
    detail["has_both"] = ("[architecture]" in s and "[security]" in s)
    if not (detail["has_counts"] and detail["has_both"]):
        all_ok = False
    empty = _synthesize([])
    if "未产生" not in empty:
        all_ok = False
    return {"all_ok": all_ok, **detail}


def main():
    print("Orchestration Phase F 单元测试")
    print("=" * 60)
    run("O1 角色目录", t_roles)
    run("O1b 角色模板映射", t_role_template_map)
    run("O2 启发式兜底", t_heuristic)
    run("O3 JSON 解析", t_json_parse)
    run("O4 子任务过滤", t_subtasks)
    run("O5 报告渲染", t_report_render)
    run("O6 工具注册", t_tool_registration)
    run("O7 权限目录", t_permission)
    run("O8 默认值", t_defaults)
    run("O9 并行上限", t_concurrency)
    run("O10 汇总合成", t_synthesize)

    print("=" * 60)
    passed = len(results) - len(failures)
    print(f"结果: {passed}/{len(results)} 通过")
    for f in failures:
        print(f"  失败: {f}")

    # 报告输出（可选参数指定路径，缺省 tests 目录下同名字 .report.json）
    out_path = None
    if len(sys.argv) > 1:
        out_path = sys.argv[1]
    else:
        out_path = str(Path(__file__).with_suffix(".report.json"))
    import json

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "suite": "orchestration_phase_f",
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "passed": passed,
            "total": len(results),
            "failures": failures,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"报告已写入: {out_path}")

    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()