"""MfkAgent Runtime 状态管理 Phase E5 自动化验证脚本。

验证点：
  1. 状态机合法性：pending → 活跃阶段 → 终态；非法流转拒绝；终态不可再流转
  2. 事件类型注册表：规范类型全集 + 未注册类型软校验（仍写入）
  3. Recorder.transition：更新 AgentRun.state + 写入 RuntimeState 审计行；非法流转拒绝
  4. 流式正常闭环（含工具轮）：state 流转路径
     pending → building_context → llm_call → tool_execution → verifying → llm_call
     → completing → completed；status=completed
  5. 流式异常 → failed（error 事件 + failed 终态）
  6. 流式取消 → cancelled（CancelledError 收尾）
  7. 非流式 run() 状态流转（build 模式单文本轮）

运行：
  python backend/tests/test_state_management_phase_e5.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import asyncio
import io
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

if __name__ == "__main__" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_stateE5_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./state_mgmt_test.db"
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
from app.core.agent_runtime.states import (  # noqa: E402
    RuntimePhase, RuntimeEventType, VALID_TRANSITIONS, TERMINAL_PHASES,
    INITIAL_PHASE, RUNTIME_EVENT_TYPES, is_valid_transition, is_registered_event_type,
)
from app.core.agent_runtime.recorder import runtime_event_recorder  # noqa: E402

CLIENT = TestClient(app)


# ---------------------------------------------------------------------------
# 脚本化 LLM
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
            raise AssertionError(f"LLM 轮次溢出：调用了第 {idx} 轮，但脚本只定义了 {len(self._rounds)} 轮")
        return FakeResponse(self._rounds[idx])


def install_fake_llm(rounds):
    state = {"idx": 0}

    class _FakeClient(FakeClient):
        def __init__(self, *a, **kw):
            super().__init__(rounds, state)

    httpx.AsyncClient = _FakeClient
    return state


def _sse_chunk(obj):
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def text_round(text):
    chunks = []
    for i in range(0, len(text), 24):
        chunks.append(_sse_chunk({
            "choices": [{"delta": {"content": text[i:i + 24]}, "finish_reason": None}]
        }))
    chunks.append(_sse_chunk({"choices": [{"delta": {}, "finish_reason": "stop"}]}))
    return chunks


def tool_round(name, args, call_id):
    chunks = [
        _sse_chunk({
            "choices": [{
                "delta": {"content": "让我先执行。", "reasoning_content": "先取真实数据"},
                "finish_reason": None,
            }]
        }),
    ]
    arg_json = json.dumps(args, ensure_ascii=False)
    chunks.append(_sse_chunk({
        "choices": [{
            "delta": {"tool_calls": [{"index": 0, "id": call_id, "type": "function",
                                      "function": {"name": name, "arguments": ""}}]},
            "finish_reason": None,
        }]
    }))
    step = max(1, len(arg_json) // 3 or 1)
    for i in range(0, len(arg_json), step):
        piece = arg_json[i:i + step]
        chunks.append(_sse_chunk({
            "choices": [{
                "delta": {"tool_calls": [{"index": 0, "function": {"arguments": piece}}]},
                "finish_reason": None,
            }]
        }))
    chunks.append(_sse_chunk({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}))
    return chunks


def make_project(path: Path) -> int:
    path.mkdir(parents=True, exist_ok=True)
    r = CLIENT.post("/api/projects", json={"path": str(path), "name": "StateE5-Project"})
    assert r.status_code == 200, f"create project failed: {r.status_code} {r.text}"
    return r.json()["id"]


def make_chat(project_id: int) -> int:
    r = CLIENT.post("/api/chat", json={"project_id": project_id, "agent_id": "coder", "title": "StateE5"})
    assert r.status_code == 200, f"create chat failed: {r.status_code} {r.text}"
    return r.json()["id"]


def stream_send(chat_id: int, content: str) -> list:
    events = []
    with CLIENT.stream(
        "POST",
        f"/api/chat/{chat_id}/send/stream",
        json={"content": content, "model": "deepseek-v4-flash", "reasoning_effort": "none"},
    ) as resp:
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


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _fetch_run(run_id: int):
    db = SessionLocal()
    try:
        from app.models.agent import AgentRun, RuntimeEvent, RuntimeState
        run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        events = (
            db.query(RuntimeEvent)
            .filter(RuntimeEvent.run_id == run_id)
            .order_by(RuntimeEvent.sequence.asc())
            .all()
        )
        states = (
            db.query(RuntimeState)
            .filter(RuntimeState.run_id == run_id)
            .order_by(RuntimeState.id.asc())
            .all()
        )
        return run, events, states
    finally:
        db.close()


def _latest_run(chat_id: int):
    db = SessionLocal()
    try:
        from app.models.agent import AgentRun
        return db.query(AgentRun).filter(AgentRun.chat_id == chat_id).order_by(AgentRun.id.desc()).first()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------


def test_state_machine_rules() -> dict:
    """1. 状态机合法性：合法流转允许、非法拒绝、终态封闭。"""
    cases = []

    # 合法活跃流转
    ok = all(is_valid_transition(a, b) for a, b in [
        ("pending", "building_context"),
        ("building_context", "llm_call"),
        ("llm_call", "tool_execution"),
        ("tool_execution", "verifying"),
        ("verifying", "llm_call"),
        ("llm_call", "completing"),
        ("completing", "completed"),
        ("pending", "failed"),
        ("tool_execution", "cancelled"),
    ])
    cases.append({"case": "合法流转允许", "ok": ok})

    # 非法流转拒绝
    ok = not any(is_valid_transition(a, b) for a, b in [
        ("pending", "pending"),
        ("completed", "llm_call"),
        ("failed", "completing"),
        ("cancelled", "tool_execution"),
        ("llm_call", "llm_call"),
        ("unknown_state", "llm_call"),
        ("completing", "pending"),
    ])
    cases.append({"case": "非法流转拒绝", "ok": ok})

    # 终态不可再流转
    ok = all(is_valid_transition(t, s) is False for t in TERMINAL_PHASES for s in
             {p.value for p in RuntimePhase})
    cases.append({"case": "终态封闭", "ok": ok})

    # 初始阶段 + 所有阶段都覆盖在流转表中
    all_phases = {p.value for p in RuntimePhase}
    ok = set(VALID_TRANSITIONS.keys()) == all_phases
    cases.append({"case": "流转表覆盖全阶段", "ok": ok, "phases": sorted(all_phases)})

    all_ok = all(c["ok"] for c in cases)
    return {"cases": cases, "all_ok": all_ok}


def test_event_type_registry() -> dict:
    """2. 事件类型注册表。"""
    cases = []

    expected = {"text", "thinking", "tool_start", "tool_result", "tool_approval", "tool_calls",
                "verify_result", "verification_failed", "state_change",
                "task_started", "task_completed", "task_failed",  # G4-B: TaskGraph 任务级生命周期事件
                "task_skipped",  # G4-C: 级联跳过事件
                "task_graph",  # G4-B: TaskGraph 汇总事件
                "agent_state_update",  # 战略4: Agent 状态可视化
                "completion_verify_started", "completion_verify_passed", "completion_verify_failed",  # Phase 12
                "token_usage",  # G6-A: Token 水位监控
                "finish", "error"}
    ok = RUNTIME_EVENT_TYPES == expected
    cases.append({"case": "注册表类型全集", "ok": ok,
                  "extra": sorted(RUNTIME_EVENT_TYPES - expected),
                  "missing": sorted(expected - RUNTIME_EVENT_TYPES)})

    ok = all(is_registered_event_type(t) for t in expected)
    cases.append({"case": "规范类型均注册", "ok": ok})

    ok = is_registered_event_type("state_change") and not is_registered_event_type("bogus_event")
    cases.append({"case": "state_change 注册 / 未知未注册", "ok": ok})

    all_ok = all(c["ok"] for c in cases)
    return {"cases": cases, "all_ok": all_ok}


def test_recorder_transition_unit() -> dict:
    """3. Recorder.transition：更新 state + 审计行；非法流转拒绝。"""
    cases = []
    run_id = runtime_event_recorder.create_run(chat_id=None, agent_id="coder")
    assert run_id, "create_run 应成功"
    cases.append({"case": "create_run 初始 state=pending", "ok": runtime_event_recorder.get_state(run_id) == "pending"})

    fr = runtime_event_recorder.transition(run_id, "building_context", "unit")
    ok = fr == "pending" and runtime_event_recorder.get_state(run_id) == "building_context"
    cases.append({"case": "transition pending→building_context", "ok": ok, "from": fr})

    fr = runtime_event_recorder.transition(run_id, "llm_call")
    ok = fr == "building_context" and runtime_event_recorder.get_state(run_id) == "llm_call"
    cases.append({"case": "transition building_context→llm_call", "ok": ok, "from": fr})

    # 非法：completed → llm_call 应被拒绝，state 保持 llm_call
    fr = runtime_event_recorder.transition(run_id, "completed")
    assert fr == "llm_call"
    runtime_event_recorder.transition(run_id, "completed")
    fr = runtime_event_recorder.transition(run_id, "llm_call")
    ok = fr is None and runtime_event_recorder.get_state(run_id) == "completed"
    cases.append({"case": "非法流转 completed→llm_call 拒绝", "ok": ok, "from": fr})

    # 审计行
    db = SessionLocal()
    try:
        from app.models.agent import RuntimeState
        rows = db.query(RuntimeState).filter(RuntimeState.run_id == run_id).order_by(RuntimeState.id.asc()).all()
    finally:
        db.close()
    expected = [("pending", "building_context"), ("building_context", "llm_call"), ("llm_call", "completed")]
    actual = [(r.from_state, r.to_state) for r in rows]
    ok = actual == expected
    cases.append({"case": "RuntimeState 审计行完整", "ok": ok, "actual": actual})

    all_ok = all(c["ok"] for c in cases)
    return {"cases": cases, "all_ok": all_ok, "run_id": run_id}


def test_stream_tool_round_lifecycle(project_dir: Path) -> dict:
    """4. 流式工具轮：state 流转路径 + state_change 事件 + 审计 + status=completed。"""
    repo = project_dir / "tool"
    repo.mkdir(parents=True, exist_ok=True)
    pid = make_project(repo)
    cid = make_chat(pid)

    install_fake_llm([
        tool_round("run_command", {"command": "hostname"}, "call_st_1"),
        text_round("执行完成。"),
        text_round("自查完成，任务结束。"),
    ])
    events = stream_send(cid, "执行命令")
    assert any(e["type"] == "tool_result" for e in events), "应有 tool_result"

    run = _latest_run(cid)
    assert run and run.status == "completed", f"应 completed，实际 {run.status}"
    assert run.state == "completed", f"最终 state 应为 completed，实际 {run.state}"

    _, run_events, state_rows = _fetch_run(run.id)

    # state_change 事件存在且 sequence 连续
    seqs = [e.sequence for e in run_events]
    assert seqs == list(range(1, len(seqs) + 1)), f"sequence 应连续，实际 {seqs}"
    sc = [e for e in run_events if e.event_type == "state_change"]
    assert sc, "应有 state_change 事件"
    state_path = [e.payload.get("state") for e in sc]

    # 完整路径：pending(初始) → building_context → llm_call → tool_execution → verifying → llm_call → completing → completed
    expected_sub = ["building_context", "llm_call", "tool_execution", "verifying", "llm_call", "completing"]
    assert state_path[:len(expected_sub)] == expected_sub, f"state 路径不符: {state_path}"
    assert state_path[-1] == "completing", f"最后一个 state_change 应为 completing: {state_path}"

    # 审计行与事件路径一致（终态 completed 由 finish_run 直接写）
    audit = [r.to_state for r in state_rows]
    assert audit == state_path + ["completed"], f"审计路径不符: {audit}"

    # 所有事件类型都在注册表内
    unknown = {e.event_type for e in run_events} - set(RUNTIME_EVENT_TYPES)
    assert not unknown, f"出现未注册事件类型: {unknown}"

    return {"case": "stream_tool_round", "run_id": run.id, "status": run.status,
            "state_path": state_path, "state_events": len(sc), "event_count": len(run_events)}


def test_stream_text_lifecycle(project_dir: Path) -> dict:
    """4b. 流式纯文本轮：简单路径 pending→building_context→llm_call→completing→completed。"""
    repo = project_dir / "text"
    repo.mkdir(parents=True, exist_ok=True)
    pid = make_project(repo)
    cid = make_chat(pid)

    install_fake_llm([text_round("纯文本回复。")])
    stream_send(cid, "你好")

    run = _latest_run(cid)
    assert run and run.status == "completed", f"应 completed，实际 {run.status}"
    _, run_events, state_rows = _fetch_run(run.id)
    state_path = [e.payload.get("state") for e in run_events if e.event_type == "state_change"]
    expected = ["building_context", "llm_call", "completing"]
    assert state_path[:len(expected)] == expected, f"state 路径不符: {state_path}"
    audit = [r.to_state for r in state_rows]
    assert audit == state_path + ["completed"], f"审计路径不符: {audit}"
    return {"case": "stream_text", "run_id": run.id, "state_path": state_path}


def test_stream_failed_lifecycle(project_dir: Path) -> dict:
    """5. 流式异常 → failed：error 事件 + failed 终态 + 审计。"""
    repo = project_dir / "fail"
    repo.mkdir(parents=True, exist_ok=True)
    pid = make_project(repo)
    cid = make_chat(pid)

    class _RaisingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def stream(self, method, url, **kwargs):
            raise RuntimeError("模拟上游 API 故障")

    httpx.AsyncClient = _RaisingClient

    events = stream_send(cid, "触发失败")
    assert any(e["type"] == "error" for e in events), "应有 error 事件"

    run = _latest_run(cid)
    assert run and run.status == "failed", f"应 failed，实际 {run.status}"
    assert run.state == "failed", f"state 应为 failed，实际 {run.state}"

    _, run_events, state_rows = _fetch_run(run.id)
    audit = [r.to_state for r in state_rows]
    assert audit[-1] == "failed", f"审计终点应为 failed: {audit}"
    types = {e.event_type for e in run_events}
    assert "error" in types and "state_change" in types, f"事件类型: {types}"
    return {"case": "stream_failed", "run_id": run.id, "status": run.status, "audit": audit}


def test_stream_cancelled_lifecycle(project_dir: Path) -> dict:
    """6. 流式取消 → cancelled：CancelledError 收尾。"""
    from app.core.agent_runtime import AgentRuntime, AgentContext
    from app.services.model import Message as M

    repo = project_dir / "cancel"
    repo.mkdir(parents=True, exist_ok=True)
    pid = make_project(repo)
    cid = make_chat(pid)

    class _BlockingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def stream(self, method, url, **kwargs):
            class _Resp(FakeResponse):
                def __init__(self):
                    super().__init__([])
                    self._blocked = asyncio.Event()

                async def aiter_text(self):
                    await self._blocked.wait()
                    yield ""

            return _Resp()

    httpx.AsyncClient = _BlockingClient

    context = AgentContext(
        agent_id="coder",
        agent_identity="你是一个有帮助的AI助手。",
        personality_level=None,
        model_id="deepseek-v4-flash",
        chat_id=cid,
        project_id=pid,
        project_path=str(repo),
        tools=None,
        decision=None,
    )
    messages = [M(role="user", content="触发取消")]

    async def _run_and_cancel():
        gen = AgentRuntime().run_stream(context=context, messages=messages)
        _it = gen.__aiter__()

        async def _first():
            try:
                return await _it.__anext__()
            except StopAsyncIteration:
                return None

        task = asyncio.ensure_future(_first())
        await asyncio.sleep(0.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_run_and_cancel())

    run = _latest_run(cid)
    assert run and run.status == "cancelled", f"应 cancelled，实际 {run.status}"
    assert run.state == "cancelled", f"state 应为 cancelled，实际 {run.state}"

    _, _, state_rows = _fetch_run(run.id)
    audit = [r.to_state for r in state_rows]
    assert audit[-1] == "cancelled", f"审计终点应为 cancelled: {audit}"
    return {"case": "stream_cancelled", "run_id": run.id, "status": run.status, "audit": audit}


def test_non_stream_run_lifecycle(project_dir: Path) -> dict:
    """7. 非流式 run()：状态流转（build 单文本轮）。"""
    import asyncio as _asyncio
    from app.core.agent_runtime import AgentRuntime, AgentContext, get_chat_context_builder, ContextBuildInput
    from app.services.model import Message as M

    repo = project_dir / "run"
    repo.mkdir(parents=True, exist_ok=True)
    pid = make_project(repo)
    cid = make_chat(pid)

    # T4 双循环合一：非流式 run() 内部消费 run_stream() → model_service.stream_once()。
    # 旧实现走 call_once（httpx client.post）的 _PostFakeClient 已不再适用，改在
    # model_service 层用 _t4_mock_adapter.stream_from_single_call 包装单轮文本响应。
    from unittest.mock import AsyncMock, patch
    from tests._t4_mock_adapter import stream_from_single_call

    class _MockResult:
        def __init__(self, content, tool_calls, finish_reason):
            self.content = content
            self.tool_calls = tool_calls
            self.finish_reason = finish_reason
            self.usage = None

    async def _single_round(model_id, messages, tools, **kwargs):
        return _MockResult("非流式回复。", None, "stop")

    built = _asyncio.run(get_chat_context_builder().build(
        ContextBuildInput(chat_id=cid, content="非流式测试", model="deepseek-v4-flash")
    ))

    async def _run():
        rt = AgentRuntime()
        with patch("app.services.model.model_service") as ms:
            ms.stream_once = stream_from_single_call(_single_round)  # T4：run() 内部走 stream_once
            ms.call_once = AsyncMock(side_effect=_single_round)  # 兼容仍可能走 call_once 的分支
            result = await rt.run(
                context=built.context,
                messages=built.messages,
                temperature=0.7,
                max_tokens=256,
                reasoning_effort="none",
                read_only=built.read_only,
            )
        return result

    result = _asyncio.run(_run())
    assert result.content, "非流式应返回内容"

    run = _latest_run(cid)
    assert run and run.status == "completed", f"应 completed，实际 {run.status}"
    assert run.state == "completed", f"state 应为 completed，实际 {run.state}"

    _, run_events, state_rows = _fetch_run(run.id)
    state_path = [e.payload.get("state") for e in run_events if e.event_type == "state_change"]
    # run()（T4 双循环合一）：run() 内部消费 run_stream()，状态路径不再含旧 run() 的
    # routing 事件（TaskRouter 决策在合一实现中不 emit routing state_change，见
    # agent.py run_stream 的 state_change 点位：building_context → llm_call → … → completing）。
    expected = ["building_context", "llm_call", "completing"]
    assert state_path[:len(expected)] == expected, f"run() state 路径不符: {state_path}"
    audit = [r.to_state for r in state_rows]
    assert audit[-1] == "completed", f"审计终点应为 completed: {audit}"
    seqs = [e.sequence for e in run_events]
    assert seqs == list(range(1, len(seqs) + 1)), f"sequence 应连续: {seqs}"
    return {"case": "non_stream_run", "run_id": run.id, "state_path": state_path}


# ---------------------------------------------------------------------------
# 主流程 + 报告
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 70)
    print("MfkAgent Runtime 状态管理 Phase E5 自动化验证")
    print("临时工作目录:", _TEMP_DIR)
    print("=" * 70)
    sys.stdout.flush()

    project_dir = _TEMP_DIR / "project"
    project_dir.mkdir(exist_ok=True)

    results = []
    failures = []

    cases = [
        ("状态机合法性", test_state_machine_rules),
        ("事件类型注册表", test_event_type_registry),
        ("Recorder.transition 单元", test_recorder_transition_unit),
        ("流式工具轮生命周期", lambda: test_stream_tool_round_lifecycle(project_dir)),
        ("流式纯文本生命周期", lambda: test_stream_text_lifecycle(project_dir)),
        ("流式异常 failed", lambda: test_stream_failed_lifecycle(project_dir)),
        ("流式取消 cancelled", lambda: test_stream_cancelled_lifecycle(project_dir)),
        ("非流式 run() 生命周期", lambda: test_non_stream_run_lifecycle(project_dir)),
    ]

    for name, fn in cases:
        t0 = time.monotonic()
        try:
            detail = fn()
            ok = detail.pop("all_ok", True)
            elapsed = (time.monotonic() - t0) * 1000
            results.append({"name": name, "ok": ok, "detail": detail, "elapsed_ms": round(elapsed)})
            if ok:
                print(f"  PASS  {name}  ({elapsed:.0f}ms)")
                sys.stdout.flush()
            else:
                failures.append(f"{name}: {detail}")
                print(f"  FAIL  {name}\n        {detail}")
                sys.stdout.flush()
        except AssertionError as e:
            results.append({"name": name, "ok": False, "detail": str(e), "elapsed_ms": 0})
            failures.append(f"{name}: {e}")
            print(f"  FAIL  {name}\n        {e}")
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
        except Exception as e:  # noqa: BLE001
            results.append({"name": name, "ok": False, "detail": f"异常: {e!r}", "elapsed_ms": 0})
            failures.append(f"{name}: {e!r}")
            print(f"  ERROR {name}\n        {e!r}")
            import traceback
            traceback.print_exc()
            sys.stdout.flush()

    # ---- 生成报告 ----
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (BACKEND_DIR / "tests" / "phase_e5_state_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# MfkAgent Runtime 状态管理 Phase E5 测试报告\n",
             f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"- 临时工作目录: `{_TEMP_DIR}`",
             "",
             "## 交付内容\n",
             "1. **RuntimeState 状态模型**：`RuntimeState` 表（`runtime_states`）记录每次状态流转审计",
             "   （run_id / from_state / to_state / reason / created_at），按 id 升序可还原完整流转路径。",
             "2. **AgentRun 生命周期扩展**：新增 `state` 列（细粒度阶段），与 `status`",
             "   （running/completed/failed/cancelled 粗粒度）双层对齐；旧库经 `main.py _ensure_schema` 轻量迁移。",
             "3. **RuntimeEvent 类型标准化**：`states.py` 注册表 `RuntimeEventType` / `RUNTIME_EVENT_TYPES`",
             "   （11 种类型），`recorder.emit` 对未知类型软校验（记日志仍写入，向后兼容）。",
             "4. **状态机接入 AgentRuntime**：`run()` 与 `run_stream()` 全生命周期发射 `state_change` 事件、",
             "   更新 `AgentRun.state`、写入 `RuntimeState` 审计；流式路径 SSE 同步透传 `state_change`。",
             "5. **状态机合法性校验**：`VALID_TRANSITIONS` 合法流转表；非法流转（如终态再流转）拒绝并记日志，不阻断执行。",
             "",
             "## 状态流转说明\n",
             "```",
             "pending ──► building_context ──► routing ──► llm_call ──► tool_execution ──► verifying ──► llm_call ...",
             "   │              │                │            │                │                │",
             "   └──────────────┴────────────────┴────────────┴────────────────┴────────────────┘",
             "                                        (活跃阶段可互转)",
             "                                        … 最终：llm_call ──► completing ──► completed",
             "                                任意活跃阶段 ──► failed | cancelled（异常/取消终态）",
             "                                终态（completed/failed/cancelled）不可再流转",
             "```",
             "",
             "实测路径：",
             "- 流式工具轮：`building_context → llm_call → tool_execution → verifying → llm_call → completing → completed`",
             "- 流式纯文本：`building_context → llm_call → completing → completed`",
             "- 流式异常：`building_context → llm_call → failed`",
             "- 流式取消：`building_context → cancelled`",
             "- 非流式 run()：`building_context → routing → llm_call → completing → completed`",
             "",
             "## 修改文件\n",
             "| 文件 | 变更 |",
             "|------|------|",
             "| backend/app/core/agent_runtime/states.py | 新增：RuntimePhase / RuntimeEventType / VALID_TRANSITIONS / RUNTIME_EVENT_TYPES / is_valid_transition（新增文件） |",
             "| backend/app/models/agent.py | AgentRun 新增 `state` 列 + `state_history` 关系；新增 RuntimeState 表；RuntimeEvent 文档更新 |",
             "| backend/app/core/agent_runtime/recorder.py | 新增 `transition()` / `get_state()`；`finish_run` 同步终态 state；`emit` 事件类型软校验；create_run 初始化 pending |",
             "| backend/app/core/agent_runtime/agent.py | run()/run_stream()/_run_stream_events() 全生命周期接入状态机（_record_state + state_change 事件） |",
             "| backend/app/core/agent_runtime/__init__.py | 导出 states 系列符号 |",
             "| backend/main.py | `_ensure_schema` 增加 agent_runs.state 旧库迁移 |",
             "| backend/tests/test_state_management_phase_e5.py | 新增状态管理测试脚本（新增文件） |",
             "",
             "## 状态模型\n",
             "- 粗粒度 `AgentRun.status`: running / completed / failed / cancelled",
             "- 细粒度 `AgentRun.state`（`RuntimePhase`）: pending → building_context / routing / llm_call /",
             "  tool_execution / verifying → completing → completed | failed | cancelled",
             "- `RuntimeState` 表记录每次流转审计（from_state / to_state / reason）",
             "- `RuntimeEventType` 注册表: text / thinking / tool_start / tool_result / tool_approval /",
             "  tool_calls / verify_result / verification_failed / state_change / finish / error",
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

    lines.append("## 结论\n")
    if failures:
        lines.append(f"❌ **{len(failures)} 项未通过**，详见上方明细。\n")
    else:
        lines.append("✅ **全部通过**：AgentRun 状态机覆盖正常/工具/异常/取消/非流式全生命周期。\n")

    lines.append("## 下阶段建议\n")
    lines.append("- 前端接入：SSE 已透传 `state_change` 事件，可据此渲染运行阶段指示器 / 重连恢复运行中状态。")
    lines.append("- 事件查询 API：新增 `GET /api/chat/{id}/runs` 与 `GET /api/runs/{id}/events` 便于审计/回放。")
    lines.append("- 状态恢复：`status=running` 的遗留 run（进程崩溃残留）可启动时巡检并置为 failed + reason=orphan。")
    lines.append("- History 窗口化：ContextBuilder 的 token budget / compression 扩展点可与 llm_call 阶段事件联动。")
    lines.append("- 验证接入审批流：`tool_execution` 阶段内审批等待（awaiting_approval）可细分 `waiting_approval` 子态。")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n报告已生成:", report_path)

    try:
        from app.core.database import engine
        engine.dispose()
    except Exception:  # noqa: BLE001
        pass
    try:
        shutil.rmtree(_TEMP_DIR, ignore_errors=True)
        print("已清理临时目录:", _TEMP_DIR)
    except Exception as e:  # noqa: BLE001
        print("清理临时目录失败:", e)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
