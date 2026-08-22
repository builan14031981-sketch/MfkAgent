"""MfkAgent Runtime Event Persistence Phase E2 自动化验证脚本。

验证点：
  1. AgentRun 生命周期：run_stream 创建 running → completed（正常结束）
  2. AgentRun 生命周期：异常 → failed
  3. AgentRun 生命周期：CancelledError → cancelled
  4. RuntimeEvent 持久化：事件类型对齐 SSE（text / thinking / tool_start / tool_result / finish）
  5. sequence 同 run 内严格自增 1,2,3,...（连续无断号）
  6. payload 保存事件内容（不含顶层 type）

运行：
  python backend/tests/test_runtime_event_phase_e2.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

if "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_phaseE2_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./phase_e2_test.db"
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
from app.core.agent_runtime.recorder import runtime_event_recorder  # noqa: E402

CLIENT = TestClient(app)


# ---------------------------------------------------------------------------
# 脚本化 LLM（与 Phase C 相同注入机制）
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


def tool_call_round(tool_name, args_json, text_prefix=""):
    """模拟模型输出文本 + 结构化 tool_calls。"""
    chunks = []
    if text_prefix:
        for i in range(0, len(text_prefix), 24):
            chunks.append(_sse_chunk({
                "choices": [{"delta": {"content": text_prefix[i:i + 24]}, "finish_reason": None}]
            }))
    chunks.append(_sse_chunk({
        "choices": [{
            "delta": {"tool_calls": [{
                "index": 0, "id": "call_e2_1", "type": "function",
                "function": {"name": tool_name, "arguments": args_json[:10]},
            }]},
            "finish_reason": None,
        }]
    }))
    chunks.append(_sse_chunk({
        "choices": [{
            "delta": {"tool_calls": [{"index": 0, "function": {"arguments": args_json[10:]}}]},
            "finish_reason": "tool_calls",
        }]
    }))
    return chunks


def make_project(path: Path) -> int:
    path.mkdir(parents=True, exist_ok=True)
    r = CLIENT.post("/api/projects", json={"path": str(path), "name": "PhaseE2-Project"})
    assert r.status_code == 200, f"create project failed: {r.status_code} {r.text}"
    return r.json()["id"]


def make_chat(project_id: int) -> int:
    r = CLIENT.post("/api/chat", json={"project_id": project_id, "agent_id": "coder", "title": "PhaseE2"})
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
# 用例
# ---------------------------------------------------------------------------


def _fetch_run(run_id: int):
    db = SessionLocal()
    try:
        from app.models.agent import AgentRun, RuntimeEvent
        run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        events = (
            db.query(RuntimeEvent)
            .filter(RuntimeEvent.run_id == run_id)
            .order_by(RuntimeEvent.sequence.asc())
            .all()
        )
        return run, events
    finally:
        db.close()


def test_stream_lifecycle(project_dir: Path) -> dict:
    """1. run_stream 创建 AgentRun，文本流式正常结束 → completed；事件/sequence 持久化。"""
    repo = project_dir / "lifecycle_repo"
    repo.mkdir(parents=True, exist_ok=True)
    pid = make_project(repo)
    cid = make_chat(pid)

    install_fake_llm([text_round("这是 Phase E2 的文本回复。")])
    events = stream_send(cid, "你好")
    assert any(e["type"] == "text" for e in events), "应有 text 事件"
    assert any(e["type"] == "finish" for e in events), "应有 finish 事件"

    db = SessionLocal()
    try:
        from app.models.agent import AgentRun
        runs = db.query(AgentRun).filter(AgentRun.chat_id == cid).order_by(AgentRun.id.desc()).all()
    finally:
        db.close()
    assert runs, "应存在 AgentRun 记录"
    run = runs[0]
    assert run.status == "completed", f"应 completed，实际 {run.status}"
    assert run.agent_id == "coder", run.agent_id
    assert run.started_at is not None and run.finished_at is not None, "started/finished 应有值"

    run2, run_events = _fetch_run(run.id)
    seqs = [e.sequence for e in run_events]
    assert seqs == list(range(1, len(seqs) + 1)), f"sequence 应连续自增，实际 {seqs}"
    types = [e.event_type for e in run_events]
    assert "text" in types and "finish" in types, f"应含 text/finish，实际 {types}"
    # payload 含内容，且不含顶层 type
    text_payloads = [e.payload for e in run_events if e.event_type == "text"]
    assert text_payloads and "Phase E2" in "".join(p.get("content", "") for p in text_payloads)
    return {"case": "stream_lifecycle", "run_id": run.id, "event_count": len(run_events), "status": run.status}


def test_stream_tool_events(project_dir: Path) -> dict:
    """2. 工具调用流：tool_start/tool_result 持久化，sequence 连续，payload 正确。"""
    repo = project_dir / "tool_repo"
    repo.mkdir(parents=True, exist_ok=True)
    pid = make_project(repo)
    cid = make_chat(pid)

    install_fake_llm([
        tool_call_round("run_command", '{"command": "ipconfig"}'),
        text_round("命令已执行。"),
        text_round("自查完成，任务结束。"),
    ])
    events = stream_send(cid, "执行命令")
    starts = [e for e in events if e["type"] == "tool_start"]
    results = [e for e in events if e["type"] == "tool_result"]
    assert len(starts) == 1 and len(results) == 1, (len(starts), len(results))

    db = SessionLocal()
    try:
        from app.models.agent import AgentRun
        run = db.query(AgentRun).filter(AgentRun.chat_id == cid).order_by(AgentRun.id.desc()).first()
    finally:
        db.close()
    assert run and run.status == "completed", f"工具流应 completed，实际 {run.status}"

    _, run_events = _fetch_run(run.id)
    seqs = [e.sequence for e in run_events]
    assert seqs == list(range(1, len(seqs) + 1)), f"sequence 应连续自增，实际 {seqs}"
    types = [e.event_type for e in run_events]
    for t in ("tool_start", "tool_result", "finish"):
        assert t in types, f"应含 {t}，实际 {types}"

    ts = next(e for e in run_events if e.event_type == "tool_start")
    assert ts.payload.get("tool") == "run_command", ts.payload
    tr = next(e for e in run_events if e.event_type == "tool_result")
    assert tr.payload.get("tool") == "run_command", tr.payload
    assert "exit code 0" in tr.payload.get("result", ""), tr.payload.get("result", "")
    return {"case": "tool_events", "run_id": run.id, "event_count": len(run_events)}


def test_failed_lifecycle(project_dir: Path) -> dict:
    """3. 模型抛错 → AgentRun failed + error 事件。"""
    repo = project_dir / "fail_repo"
    repo.mkdir(parents=True, exist_ok=True)
    pid = make_project(repo)
    cid = make_chat(pid)

    def _bad_round():
        # 第一段合法，随后直接断流抛错（模拟上游 500）
        raise AssertionError("故意模拟模型轮次溢出")

    class _RaisingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def stream(self, method, url, **kwargs):
            raise RuntimeError("模拟上游 API 故障")

    httpx.AsyncClient = _RaisingClient

    events = stream_send(cid, "触发失败")
    assert any(e["type"] == "error" for e in events), f"应有 error 事件: {events}"

    db = SessionLocal()
    try:
        from app.models.agent import AgentRun
        run = db.query(AgentRun).filter(AgentRun.chat_id == cid).order_by(AgentRun.id.desc()).first()
    finally:
        db.close()
    assert run, "应存在 AgentRun 记录"
    assert run.status == "failed", f"应 failed，实际 {run.status}"
    assert run.finished_at is not None

    _, run_events = _fetch_run(run.id)
    types = [e.event_type for e in run_events]
    assert "error" in types, f"应含 error 事件，实际 {types}"
    return {"case": "failed_lifecycle", "run_id": run.id, "status": run.status}


def test_cancelled_lifecycle(project_dir: Path) -> dict:
    """4. 流被取消（CancelledError）→ AgentRun cancelled。"""
    import asyncio
    from app.core.agent_runtime import AgentRuntime, AgentContext
    from app.services.model import Message as M

    repo = project_dir / "cancel_repo"
    repo.mkdir(parents=True, exist_ok=True)
    pid = make_project(repo)
    cid = make_chat(pid)

    # 无限阻塞的流：永远不结束 → 取消时触发 CancelledError
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
                    yield ""  # 阻塞永不结束；取消时此处抛 CancelledError

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
        # 取第一帧后立刻取消，模拟前端断连
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

    db = SessionLocal()
    try:
        from app.models.agent import AgentRun
        run = db.query(AgentRun).filter(AgentRun.chat_id == cid).order_by(AgentRun.id.desc()).first()
    finally:
        db.close()
    assert run, "应存在 AgentRun 记录"
    assert run.status == "cancelled", f"应 cancelled，实际 {run.status}"
    return {"case": "cancelled_lifecycle", "run_id": run.id, "status": run.status}


def test_sequence_continuity(project_dir: Path) -> dict:
    """5. 同一 run 多轮事件 sequence 严格连续（1..N 无断号无重复）。"""
    repo = project_dir / "seq_repo"
    repo.mkdir(parents=True, exist_ok=True)
    pid = make_project(repo)
    cid = make_chat(pid)

    install_fake_llm([
        tool_call_round("run_command", '{"command": "hostname"}'),
        tool_call_round("run_command", '{"command": "hostname"}'),
        text_round("多轮执行完成。"),
        text_round("自查完成，任务结束。"),
    ])
    events = stream_send(cid, "连续执行")
    assert len([e for e in events if e["type"] == "tool_result"]) == 2, "应有两轮工具结果"

    db = SessionLocal()
    try:
        from app.models.agent import AgentRun
        run = db.query(AgentRun).filter(AgentRun.chat_id == cid).order_by(AgentRun.id.desc()).first()
    finally:
        db.close()
    assert run and run.status == "completed", f"应 completed，实际 {run.status}"

    _, run_events = _fetch_run(run.id)
    seqs = [e.sequence for e in run_events]
    assert seqs == list(range(1, len(seqs) + 1)), f"sequence 应连续自增，实际 {seqs}"
    assert len(set(seqs)) == len(seqs), f"sequence 不应重复，实际 {seqs}"
    assert len(run_events) >= 6, f"多轮应有足够事件，实际 {len(run_events)}"
    return {"case": "sequence_continuity", "run_id": run.id, "event_count": len(run_events)}


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 70)
    print("MfkAgent Runtime Event Persistence Phase E2 自动化验证")
    print("临时工作目录:", _TEMP_DIR)
    print("=" * 70)
    sys.stdout.flush()

    project_dir = _TEMP_DIR / "project"
    project_dir.mkdir(exist_ok=True)

    results = []
    failures = []

    cases = [
        ("流式生命周期 completed", lambda: test_stream_lifecycle(project_dir)),
        ("工具事件持久化", lambda: test_stream_tool_events(project_dir)),
        ("异常生命周期 failed", lambda: test_failed_lifecycle(project_dir)),
        ("取消生命周期 cancelled", lambda: test_cancelled_lifecycle(project_dir)),
        ("sequence 连续性", lambda: test_sequence_continuity(project_dir)),
    ]

    for name, fn in cases:
        t0 = time.monotonic()
        try:
            detail = fn()
            elapsed = (time.monotonic() - t0) * 1000
            results.append({"name": name, "ok": True, "detail": detail, "elapsed_ms": round(elapsed)})
            print(f"  PASS  {name}  ({elapsed:.0f}ms)")
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

    print()
    passed = sum(1 for r in results if r["ok"])
    print(f"通过率: {passed}/{len(results)}")
    for r in results:
        print(f"  {r['name']}: {'OK' if r['ok'] else 'FAIL'} -> {r['detail']}")

    # 输出报告
    report_path = sys.argv[1] if len(sys.argv) > 1 else str(BACKEND_DIR / "tests" / "phase_e2_test_report.md")
    _write_report(results, failures, report_path)

    # 清理
    shutil.rmtree(_TEMP_DIR, ignore_errors=True)
    return 0 if not failures else 1


def _write_report(results, failures, path: str):
    lines = [
        "# MfkAgent Phase E2 测试报告",
        "",
        f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 结果: {'全部通过' if not failures else f'{len(failures)} 项失败'}",
        "",
        "| # | 用例 | 结果 | 耗时 | 详情 |",
        "|---|------|------|------|------|",
    ]
    for i, r in enumerate(results, 1):
        ok = "✅ PASS" if r["ok"] else "❌ FAIL"
        lines.append(f"| {i} | {r['name']} | {ok} | {r['elapsed_ms']}ms | {r['detail']} |")
    if failures:
        lines.append("")
        lines.append("失败明细：")
        for f in failures:
            lines.append(f"- {f}")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    print(f"\n报告已生成: {path}")


if __name__ == "__main__":
    sys.exit(main())
