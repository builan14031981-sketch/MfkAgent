"""MfkAgent Runtime Stabilization — Phase E7 自动化验证脚本。

范围：
  E7-1 封堵 /api/tools/call 绕过 Runtime
        - 原只读工具列表 API（GET /api/tools、/api/tools/definitions）保持不变
        - POST /api/tools/call 移除（404，绕行闭环被阻断）
        - 裸工具执行移至 devtools router（/api/devtools/tools/call），仅 DEBUG 模式可用
        - Runtime 层权限闸不受影响（Plan 拒绝 add_memory / write_file，只读放行）
  E7-2 AgentContext 增加 task_context（V1: goal / constraints / current_step，Planner 预留）
  E7-3 Runtime Event Replay API：GET /api/runs/{run_id}/events（sequence ASC 排序）

运行：
  python backend/tests/test_runtime_stabilization_phase_e7.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import os
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# 临时环境隔离：必须在 import main 之前完成
# ---------------------------------------------------------------------------
_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_stabE7_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./stab_e7_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

import app.models.agent as _agent_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base, SessionLocal  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from main import app  # noqa: E402
import app.api.devtools as _devtools_mod  # noqa: E402

from app.core.agent_runtime.context import AgentContext  # noqa: E402
from app.core.agent_runtime.context_builder import ChatContextBuilder, ContextBuildInput  # noqa: E402
from app.core.agent_runtime.recorder import runtime_event_recorder  # noqa: E402
from app.core.tool_runtime.risk_engine import evaluate_tool, Verdict  # noqa: E402
from app.core.tool_runtime.executor import execute_tool  # noqa: E402
from app.models.agent import AgentRun, RuntimeEvent, Chat  # noqa: E402

CLIENT = TestClient(app)

# ---------------------------------------------------------------------------
# 测试运行器
# ---------------------------------------------------------------------------
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
# E7-1: 封堵 Tool API 绕过
# ---------------------------------------------------------------------------

def _test_tools_list_works():
    r = CLIENT.get("/api/tools")
    assert r.status_code == 200, f"GET /api/tools 状态码 {r.status_code}"
    data = r.json()
    names = {t["name"] for t in data.get("tools", [])}
    assert "add_memory" in names, "工具列表应包含 add_memory"
    assert "web_search" in names and "fetch_url" in names, "工具列表应包含只读工具"
    return {"count": len(data.get("tools", [])), "has_add_memory": "add_memory" in names}


def _test_tools_definitions_works():
    r = CLIENT.get("/api/tools/definitions")
    assert r.status_code == 200, f"GET /api/tools/definitions 状态码 {r.status_code}"
    defs = r.json().get("definitions", [])
    names = {d["function"]["name"] for d in defs}
    assert "add_memory" in names, "definitions 应包含 add_memory"
    return {"count": len(defs)}


def _test_tools_call_blocked():
    r = CLIENT.post("/api/tools/call", json={"tool_name": "get_datetime", "arguments": {}})
    assert r.status_code == 404, f"POST /api/tools/call 应 404，实际 {r.status_code}"
    return {"status_code": r.status_code}


def _test_dev_call_gate_on():
    _devtools_mod.settings.DEBUG = True
    try:
        r = CLIENT.post("/api/devtools/tools/call", json={"tool_name": "get_datetime", "arguments": {}})
        assert r.status_code == 200, f"DEBUG 下 dev call 应 200，实际 {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("success") is True, f"get_datetime 应成功: {data}"
        return {"status_code": r.status_code, "output": data.get("output", "")}
    finally:
        _devtools_mod.settings.DEBUG = True


def _test_dev_call_gate_off():
    _devtools_mod.settings.DEBUG = False
    try:
        r = CLIENT.post("/api/devtools/tools/call", json={"tool_name": "get_datetime", "arguments": {}})
        assert r.status_code == 404, f"非 DEBUG 下 dev call 应 404，实际 {r.status_code}"
        return {"status_code": r.status_code}
    finally:
        _devtools_mod.settings.DEBUG = True


def _test_plan_permission_intact():
    """Runtime 层权限闸不受 E7-1 影响：Plan 仍拒绝写工具，放行只读。"""
    assert evaluate_tool("add_memory", "plan").verdict == Verdict.DENY
    assert evaluate_tool("write_file", "plan").verdict == Verdict.DENY
    assert evaluate_tool("read_file", "plan").verdict == Verdict.ALLOW
    assert evaluate_tool("add_memory", "build").verdict == Verdict.ALLOW

    # 执行闸级联验证：Plan 模式 execute_tool 拒绝 add_memory 且不写库
    db = SessionLocal()
    before = db.query(_agent_models.MemoryItem).count()
    db.close()

    async def _go():
        return await execute_tool(
            tool_call={"function": {"name": "add_memory", "arguments": "{}"}, "id": "e7-1"},
            project_path=None,
            read_only=True,  # plan 模式
            ctx={},
        )
    import asyncio
    record = asyncio.run(_go())

    assert record["status"] == "failed", f"Plan add_memory 应 failed: {record}"
    assert "拒绝" in record["result"] or "plan" in record["result"].lower(), record["result"]
    db = SessionLocal()
    after = db.query(_agent_models.MemoryItem).count()
    db.close()
    assert after == before, "Plan 模式 add_memory 不应写库"
    return {"status": record["status"], "memory_before": before, "memory_after": after}


# ---------------------------------------------------------------------------
# E7-2: AgentContext.task_context
# ---------------------------------------------------------------------------

def _test_task_context_default_none():
    ctx = AgentContext(agent_id="a", agent_identity="id", personality_level=None, model_id="m")
    assert ctx.task_context is None, "默认 task_context 应为 None"
    return {"task_context": ctx.task_context}


def _test_task_context_v1_structure():
    task = {
        "goal": "优化Python项目性能",
        "constraints": ["不能修改数据库结构"],
        "current_step": "分析代码",
    }
    ctx = AgentContext(
        agent_id="a", agent_identity="id", personality_level=None, model_id="m",
        task_context=task,
    )
    assert ctx.task_context == task
    assert ctx.task_context["goal"] == "优化Python项目性能"
    assert isinstance(ctx.task_context["constraints"], list)
    assert ctx.task_context["current_step"] == "分析代码"
    assert ctx.identity == "id", "identity 别名不受影响"
    return {"keys": sorted(task.keys())}


def _test_chat_builder_task_context_none():
    db = SessionLocal()
    chat = Chat(agent_id="general", title="E7 task ctx", mode="build")
    db.add(chat)
    db.commit()
    chat_id = chat.id
    db.close()

    import asyncio
    built = asyncio.run(
        ChatContextBuilder().build(ContextBuildInput(chat_id=chat_id, content="你好"))
    )
    assert built.context.task_context is None, "本阶段 Planner 未注入，task_context 应为 None"
    assert built.context.vision_context is None
    return {"task_context": built.context.task_context, "chat_id": chat_id}


# ---------------------------------------------------------------------------
# E7-3: Runtime Event Replay API
# ---------------------------------------------------------------------------

def _seed_run_events():
    """插入一条 run + 乱序 sequence 的事件，验证 ASC 排序。"""
    db = SessionLocal()
    try:
        run = AgentRun(chat_id=None, agent_id="general", status="completed", state="completed")
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

        rows = [
            RuntimeEvent(run_id=run_id, event_type="text", payload={"content": "hi"}, sequence=5),
            RuntimeEvent(run_id=run_id, event_type="state_change", payload={"state": "llm_call"}, sequence=1),
            RuntimeEvent(run_id=run_id, event_type="tool_start", payload={"tool": "read_file"}, sequence=3),
            RuntimeEvent(run_id=run_id, event_type="verify_result", payload={"status": "passed"}, sequence=4),
            RuntimeEvent(run_id=run_id, event_type="thinking", payload={"content": "..."}, sequence=2),
        ]
        for row in rows:
            db.add(row)
        db.commit()
        return run_id
    finally:
        db.close()


def _test_replay_api_404():
    r = CLIENT.get("/api/runs/9999999/events")
    assert r.status_code == 404, f"不存在的 run 应 404，实际 {r.status_code}"
    return {"status_code": r.status_code}


def _test_replay_api_sorted_asc():
    run_id = _seed_run_events()
    r = CLIENT.get(f"/api/runs/{run_id}/events")
    assert r.status_code == 200, f"GET /api/runs/{run_id}/events 状态码 {r.status_code}"
    data = r.json()
    assert data["run_id"] == run_id
    events = data["events"]
    seqs = [e["seq"] for e in events]
    assert seqs == [1, 2, 3, 4, 5], f"sequence 应 ASC 排序，实际 {seqs}"
    types = [e["type"] for e in events]
    assert types == ["state_change", "thinking", "tool_start", "verify_result", "text"]
    # payload 字段展开到事件顶层
    assert events[0]["state"] == "llm_call", "payload 应展开到事件顶层"
    assert events[3]["status"] == "passed"
    assert data["run"]["status"] == "completed"
    return {"run_id": run_id, "seqs": seqs, "types": types}


def _test_replay_api_run_summary():
    run_id = _seed_run_events()
    r = CLIENT.get(f"/api/runs/{run_id}/events")
    data = r.json()
    run = data["run"]
    assert run["agent_id"] == "general"
    assert run["state"] == "completed"
    assert "started_at" in run and "finished_at" in run
    return {"run_keys": sorted(run.keys()), "events": len(data["events"])}


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("MfkAgent Runtime Stabilization Phase E7 自动化验证")
    print(f"临时工作目录: {_TEMP_DIR}")
    print("=" * 70)

    run("原工具列表 API 保持不变 (GET /api/tools)", _test_tools_list_works)
    run("原工具定义 API 保持不变 (GET /api/tools/definitions)", _test_tools_definitions_works)
    run("旁路封堵 (POST /api/tools/call → 404)", _test_tools_call_blocked)
    run("dev 裸工具调用 DEBUG 开启可用", _test_dev_call_gate_on)
    run("dev 裸工具调用 DEBUG 关闭 404", _test_dev_call_gate_off)
    run("Runtime 权限闸不受影响 (Plan 拒绝写/放行只读)", _test_plan_permission_intact)
    run("AgentContext.task_context 默认 None", _test_task_context_default_none)
    run("AgentContext.task_context V1 结构", _test_task_context_v1_structure)
    run("ChatContextBuilder task_context 预留位", _test_chat_builder_task_context_none)
    run("Replay API 不存在 run → 404", _test_replay_api_404)
    run("Replay API sequence ASC 排序 + payload 展开", _test_replay_api_sorted_asc)
    run("Replay API run 摘要字段", _test_replay_api_run_summary)

    # ---- 生成报告 ----
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (BACKEND_DIR / "tests" / "phase_e7_test_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# MfkAgent Runtime Stabilization Phase E7 测试报告\n",
             f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"- 临时工作目录: `{_TEMP_DIR}`",
             "",
             "## 交付内容\n",
             "- **E7-1 封堵 Tool API 绕过**：移除 `POST /api/tools/call`（404）；裸工具执行移至",
             "  `/api/devtools/tools/call`，仅 `settings.DEBUG=True` 可用；只读列表/定义接口保留。",
             "- **E7-2 AgentContext.task_context**：新增 `task_context: dict | None` 字段",
             "  （V1: goal / constraints / current_step，Planner 预留），ContextBuilder 填充 None。",
             "- **E7-3 Runtime Event Replay API**：`GET /api/runs/{run_id}/events`，sequence ASC 排序，",
             "  payload 展开到事件顶层，附 run 摘要（status/state/started_at/finished_at）。",
             "",
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

    lines.append("## 修改文件\n")
    lines.append("| 文件 | 变更 |")
    lines.append("|------|------|")
    lines.append("| backend/app/api/tools.py | 移除 POST /call 执行端点；仅保留只读列表/定义 |")
    lines.append("| backend/app/api/devtools.py | 新增 /tools/call 开发执行端点（DEBUG 门控） |")
    lines.append("| backend/app/core/agent_runtime/context.py | AgentContext 新增 task_context 字段 |")
    lines.append("| backend/app/core/agent_runtime/context_builder.py | AgentContext 构造注入 task_context=None 预留位 |")
    lines.append("| backend/app/api/runs.py | 新增（E7-3）Replay API：GET /api/runs/{id}/events |")
    lines.append("| backend/main.py | 注册 runs router |")
    lines.append("| backend/tests/test_runtime_stabilization_phase_e7.py | 新增测试脚本（本文件） |")

    lines.append("\n## 结论\n")
    if failures:
        lines.append(f"❌ **{len(failures)} 项未通过**，详见上方明细。\n")
    else:
        lines.append("✅ **全部通过**：Tool API 旁路已封堵（dev 门控）、task_context 就位、事件回放 API 可用。\n")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n报告已生成:", report_path)

    try:
        from app.core.database import engine
        engine.dispose()
    except Exception:  # noqa: BLE001
        pass

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
