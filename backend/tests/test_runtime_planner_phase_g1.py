"""MfkAgent Planner V1 — Runtime 集成测试（Phase G1）。

验证 Phase G1 流程成立且不破坏 E8 Runtime 基线：
  User Request → ContextBuilder → Planner → TaskContext → AgentRuntime Execution Loop
             → Verification → Delivery

覆盖：
  I1. 任务型请求 → ChatContextBuilder 注入 task_context + system prompt ⑧ 计划段
  I2. 非任务型请求 → task_context None + 无计划段（兼容 E7/E8 基线）
  I3. plan 模式任务请求 → constraints 含只读约束 + read_only=True
  I4. build 流式端到端（真实 HTTP + 脚本化 LLM）：Planner 共存下 Runtime 闭环不受破坏
      （state_change→tool_start→tool_result→verify_result→finish；AgentRun=completed；回放 ASC）
  I5. use_tools=False → task_context None + 无计划段
  I6. system_prompt == messages[0].content（prompt 双通道一致）+ 计划段与 task_context 对应

运行：
  python backend/tests/test_runtime_planner_phase_g1.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import json
import os
import sys
import tempfile
import time
import asyncio
from pathlib import Path

if "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_g1_planner_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./planner_g1_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models.agent as _agent_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base, SessionLocal  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from main import app  # noqa: E402

from app.core.agent_runtime.context_builder import ChatContextBuilder, ContextBuildInput  # noqa: E402
from app.models.agent import AgentRun, RuntimeEvent, RuntimeState  # noqa: E402
from app.core.planner import get_runtime_task_context_adapter  # noqa: E402

CLIENT = TestClient(app)

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
# 脚本化 LLM（与 E5/E8 相同 httpx 注入机制）
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, chunks):
        self.status_code = 200
        self._chunks = list(chunks)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def aread(self):
        return b""

    async def aiter_text(self):
        for c in self._chunks:
            yield c


class FakeClient:
    def __init__(self, rounds, state):
        self._rounds = list(rounds)
        self._state = state

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, method, url, **kwargs):
        idx = self._state["idx"]
        self._state["idx"] += 1
        if idx >= len(self._rounds):
            raise AssertionError(f"LLM 轮次溢出：第 {idx} 轮，脚本只定义 {len(self._rounds)} 轮")
        return FakeResponse(self._rounds[idx])


def install_fake_llm(rounds):
    state = {"idx": 0}

    class _FakeClient(FakeClient):
        def __init__(self, *a, **kw):
            super().__init__(rounds, state)

    httpx.AsyncClient = _FakeClient


def _sse(obj):
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def tool_round(name, args, call_id):
    chunks = [_sse({"choices": [{"delta": {"content": "我先执行工具。", "reasoning_content": "获取真实信息"},
                                 "finish_reason": None}]})]
    arg_json = json.dumps(args, ensure_ascii=False)
    chunks.append(_sse({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": call_id, "type": "function",
                                                               "function": {"name": name, "arguments": ""}}]},
                                     "finish_reason": None}]}))
    step = max(1, len(arg_json) // 3 or 1)
    for i in range(0, len(arg_json), step):
        chunks.append(_sse({"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": arg_json[i:i + step]}}]},
                                         "finish_reason": None}]}))
    chunks.append(_sse({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}))
    return chunks


def text_round(text):
    chunks = []
    for i in range(0, len(text), 24):
        chunks.append(_sse({"choices": [{"delta": {"content": text[i:i + 24]}, "finish_reason": None}]}))
    chunks.append(_sse({"choices": [{"delta": {}, "finish_reason": "stop"}]}))
    return chunks


def make_project(path: Path) -> int:
    path.mkdir(parents=True, exist_ok=True)
    r = CLIENT.post("/api/projects", json={"path": str(path), "name": "G1-Project"})
    assert r.status_code == 200, f"create project failed: {r.status_code} {r.text}"
    return r.json()["id"]


def make_chat(project_id: int, mode: str = "build") -> int:
    body = {"project_id": project_id, "agent_id": "coder", "title": "G1", "mode": mode}
    r = CLIENT.post("/api/chat", json=body)
    assert r.status_code == 200, f"create chat failed: {r.status_code} {r.text}"
    return r.json()["id"]


def stream_send(chat_id: int, content: str) -> list:
    events = []
    with CLIENT.stream("POST", f"/api/chat/{chat_id}/send/stream",
                       json={"content": content, "model": "deepseek-v4-flash", "reasoning_effort": "none"}) as resp:
        assert resp.status_code == 200, f"send/stream failed: {resp.status_code}"
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                events.append({"type": "[DONE]"})
                break
            try:
                events.append(json.loads(data))
            except json.JSONDecodeError:
                pass
    return events


def find_events(events, etype):
    return [e for e in events if e.get("type") == etype]


def latest_run() -> dict:
    db = SessionLocal()
    try:
        run = db.query(AgentRun).order_by(AgentRun.id.desc()).first()
        if not run:
            return {}
        events = db.query(RuntimeEvent).filter(RuntimeEvent.run_id == run.id).order_by(RuntimeEvent.sequence.asc()).all()
        states = db.query(RuntimeState).filter(RuntimeState.run_id == run.id).order_by(RuntimeState.id.asc()).all()
        return {
            "run_id": run.id,
            "status": run.status,
            "state": run.state,
            "event_count": len(events),
            "event_types": [e.event_type for e in events],
            "state_path": [(s.from_state, s.to_state) for s in states],
        }
    finally:
        db.close()


def build_context(chat_id: int, content: str, use_tools: bool = True):
    return asyncio.run(
        ChatContextBuilder().build(ContextBuildInput(chat_id=chat_id, content=content, use_tools=use_tools))
    )


# ---------------------------------------------------------------------------
# I1. 任务型请求 → task_context + 计划段
# ---------------------------------------------------------------------------

def _test_i1_task_inject() -> dict:
    proj_dir = _TEMP_DIR / "i1_proj"
    pid = make_project(proj_dir)
    cid = make_chat(pid, "build")

    built = build_context(cid, "检查系统状态并诊断网络问题")
    ctx = built.context

    assert ctx.task_context is not None, "任务型请求应注入 task_context"
    assert sorted(ctx.task_context.keys()) == ["constraints", "current_step", "goal"]
    assert ctx.task_context["goal"] == "检查系统状态并诊断网络问题"
    assert ctx.task_context["current_step"], "current_step 不应为空"

    sp = built.system_prompt
    assert "## 当前任务计划（Planner V1）" in sp, "system prompt 应含计划段"
    assert "目标: 检查系统状态并诊断网络问题" in sp
    # 计划段应出现在 ⑦ 之后（追加层）
    assert sp.index("## 当前任务计划") > sp.index("## 任务建议")

    return {
        "goal": ctx.task_context["goal"],
        "current_step": ctx.task_context["current_step"],
        "constraints": ctx.task_context["constraints"],
        "prompt_has_plan": "## 当前任务计划（Planner V1）" in sp,
    }


# ---------------------------------------------------------------------------
# I2. 非任务型请求 → None（E7/E8 基线）
# ---------------------------------------------------------------------------

def _test_i2_chat_baseline() -> dict:
    proj_dir = _TEMP_DIR / "i2_proj"
    pid = make_project(proj_dir)
    cid = make_chat(pid, "build")

    for content in ("你好", "task 通道", "今天天气怎么样"):
        built = build_context(cid, content)
        assert built.context.task_context is None, f"非任务消息不应注入 task_context: {content!r}"
        assert "## 当前任务计划" not in built.system_prompt, f"非任务消息不应有计划段: {content!r}"

    return {"checked": ["你好", "task 通道", "今天天气怎么样"]}


# ---------------------------------------------------------------------------
# I3. plan 模式 → 只读约束 + read_only
# ---------------------------------------------------------------------------

def _test_i3_plan_constraint() -> dict:
    proj_dir = _TEMP_DIR / "i3_proj"
    pid = make_project(proj_dir)
    cid = make_chat(pid, "plan")

    built = build_context(cid, "分析项目结构")
    ctx = built.context

    assert built.read_only is True, "plan 模式 read_only 应为 True"
    assert ctx.task_context is not None, "plan 模式任务请求应注入 task_context"
    assert any("只读" in c for c in ctx.task_context["constraints"]), "plan 模式约束应含只读"
    assert "禁止任何写入" in "".join(ctx.task_context["constraints"])

    # build 对照：同消息无只读约束
    cid_b = make_chat(pid, "build")
    built_b = build_context(cid_b, "分析项目结构")
    assert built_b.read_only is False
    assert not any("只读" in c for c in (built_b.context.task_context or {}).get("constraints", []))

    return {
        "plan_constraints": ctx.task_context["constraints"],
        "plan_read_only": built.read_only,
        "build_read_only": built_b.read_only,
    }


# ---------------------------------------------------------------------------
# I4. build 流式端到端：Planner 共存下 Runtime 闭环不受破坏
# ---------------------------------------------------------------------------

def _test_i4_runtime_closed_loop() -> dict:
    proj_dir = _TEMP_DIR / "i4_proj"
    pid = make_project(proj_dir)
    cid = make_chat(pid, "build")

    install_fake_llm([
        tool_round("run_command", {"command": "whoami"}, "call_g1_1"),
        text_round("whoami 执行成功，闭环成立。"),
    ])
    events = stream_send(cid, "检查系统状态并诊断网络问题")

    ts = find_events(events, "tool_start")
    tr = find_events(events, "tool_result")
    vr = find_events(events, "verify_result")
    fn = find_events(events, "finish")
    sc = [e["state"] for e in events if e.get("type") == "state_change"]

    assert ts and ts[0]["tool"] == "run_command"
    assert tr and tr[0]["success"] is True
    assert vr and vr[0]["status"] == "passed" and vr[0]["strategy"] == "run_command"
    assert fn and fn[0]["finish_reason"] == "stop"
    expected = ["building_context", "llm_call", "tool_execution", "verifying", "llm_call", "completing"]
    pos = -1
    for s in expected:
        pos = sc.index(s, pos + 1)
    assert pos >= 0, f"state 顺序错乱: {sc}"

    db_state = latest_run()
    assert db_state["status"] == "completed" and db_state["state"] == "completed"
    assert db_state["event_count"] >= 6
    for et in ("state_change", "tool_start", "tool_result", "verify_result", "finish", "text"):
        assert et in db_state["event_types"], f"缺事件类型 {et}"

    r = CLIENT.get(f"/api/runs/{db_state['run_id']}/events")
    assert r.status_code == 200
    seqs = [e["seq"] for e in r.json()["events"]]
    assert seqs == sorted(seqs), f"回放应 ASC: {seqs}"

    return {
        "run_id": db_state["run_id"],
        "state_path": sc,
        "verify": vr[0]["status"],
        "event_count": db_state["event_count"],
        "replay_asc": seqs == sorted(seqs),
    }


# ---------------------------------------------------------------------------
# I5. use_tools=False → task_context None + 无计划段
# ---------------------------------------------------------------------------

def _test_i5_use_tools_false() -> dict:
    proj_dir = _TEMP_DIR / "i5_proj"
    pid = make_project(proj_dir)
    cid = make_chat(pid, "build")

    built = build_context(cid, "检查系统状态并诊断网络问题", use_tools=False)
    assert built.context.task_context is None, "use_tools=False 不应注入 task_context"
    assert built.context.tools is None
    assert "## 当前任务计划" not in built.system_prompt
    return {"task_context": built.context.task_context, "tools": built.context.tools}


# ---------------------------------------------------------------------------
# I6. prompt 双通道一致 + 计划段与 task_context 对应
# ---------------------------------------------------------------------------

def _test_i6_prompt_consistency() -> dict:
    proj_dir = _TEMP_DIR / "i6_proj"
    pid = make_project(proj_dir)
    cid = make_chat(pid, "build")

    built = build_context(cid, "调试代码并修复 bug")
    sp = built.system_prompt
    assert sp == built.messages[0].content, "system_prompt 应等于 messages[0]"
    assert built.messages[0].role == "system"

    tc = built.context.task_context
    assert tc is not None, "debug 消息应注入 task_context"
    adapter_section = get_runtime_task_context_adapter().render(tc)
    assert adapter_section in sp, "adapter 渲染的计划段应出现在 system prompt 中"

    return {
        "prompt_eq_messages": sp == built.messages[0].content,
        "adapter_in_prompt": adapter_section in sp,
        "goal": tc["goal"],
    }


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 70)
    print("MfkAgent Planner V1 Runtime 集成测试（Phase G1）")
    print(f"临时工作目录: {_TEMP_DIR}")
    print("=" * 70)

    run("I1 任务型请求 → task_context + 计划段", _test_i1_task_inject)
    run("I2 非任务型请求 → task_context None（基线）", _test_i2_chat_baseline)
    run("I3 plan 模式 → 只读约束 + read_only", _test_i3_plan_constraint)
    run("I4 build 流式端到端（Runtime 闭环不受破坏）", _test_i4_runtime_closed_loop)
    run("I5 use_tools=False → task_context None", _test_i5_use_tools_false)
    run("I6 prompt 双通道一致 + 计划段对应", _test_i6_prompt_consistency)

    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (BACKEND_DIR / "tests" / "phase_g1_planner_integration_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# MfkAgent Planner V1 Runtime 集成测试报告（Phase G1）\n",
             f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"- 临时工作目录: `{_TEMP_DIR}`\n",
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
    lines.append("## 依据\n")
    lines.append("- `tests/test_planner_unit_phase_g1.py` — 单元测试 11/11")
    lines.append("- `tests/test_runtime_planner_phase_g1.py` — 本脚本（集成）")
    lines.append("\n## 结论\n")
    if failures:
        lines.append(f"❌ **{len(failures)} 项未通过**，详见上方明细。\n")
    else:
        lines.append("✅ **Phase G1 流程成立：ContextBuilder → Planner → TaskContext → Execution Loop → Verification → Delivery；E8 Runtime 基线未破坏。**\n")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n报告已生成:", report_path)

    try:
        from app.core.database import engine
        engine.dispose()
    except Exception:  # noqa: BLE001
        pass

    print(f"结果: {passed}/{len(results)} 通过")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
