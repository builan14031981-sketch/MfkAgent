"""MfkAgent Verification Phase E4 自动化验证脚本。

Phase E4：Runtime 基础验证框架。
  - Action → Observation → Verification → Decision → Finish / Retry
  - 程序化验证优先（write_file 重读磁盘 / run_command 退出码），不让 LLM 自己判断。

覆盖（7 项）：
  1. 验证策略单元（write_file passed/failed/need_retry；run_command 0/非零/失败；default）
  2. 流式：write_file 验证通过 → verify_result passed + 文件落盘
  3. 流式：run_command 退出码 0 → verify_result passed
  4. 流式：run_command 非零退出 → verify_result need_retry + verification_failed +
     【验证反馈】注入下一轮 LLM 消息
  5. 流式：普通工具（git_status）默认通过（verify_result strategy=default）
  6. 非流式（AgentRuntime.run 真实 executor）：write_file 通过，无反馈注入
  7. 非流式：run_command 非零退出 → 反馈注入下一轮 call_once 消息

运行：
  python backend/tests/test_verification_phase_e4.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

if "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_phaseE4_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./phase_e4_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models.agent as _agent_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from main import app  # noqa: E402
from app.core.verification import verifier, PASSED, FAILED, NEED_RETRY  # noqa: E402
from app.core.tool_runtime.approval import approval_registry  # noqa: E402

CLIENT = TestClient(app)

# 每轮模型请求消息捕获（验证反馈注入断言用）
CAPTURED: dict = {"rounds": []}


# ---------------------------------------------------------------------------
# 脚本化 LLM（E2/C 同款注入机制 + 请求消息捕获）
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
        body = kwargs.get("json") or {}
        CAPTURED["rounds"].append(body.get("messages", []))
        if idx >= len(self._rounds):
            raise AssertionError(f"LLM 轮次溢出：调用了第 {idx} 轮，但脚本只定义了 {len(self._rounds)} 轮")
        return FakeResponse(self._rounds[idx])


def install_fake_llm(rounds):
    CAPTURED["rounds"] = []
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


def tool_call_round(tool_name, args_json):
    chunks = []
    chunks.append(_sse_chunk({
        "choices": [{
            "delta": {"tool_calls": [{
                "index": 0, "id": "call_e4_1", "type": "function",
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
    r = CLIENT.post("/api/projects", json={"path": str(path), "name": "PhaseE4-Project"})
    assert r.status_code == 200, f"create project failed: {r.status_code} {r.text}"
    return r.json()["id"]


def make_chat(project_id: int) -> int:
    r = CLIENT.post("/api/chat", json={"project_id": project_id, "agent_id": "coder", "title": "PhaseE4"})
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


def find_events(events, etype):
    return [e for e in events if e.get("type") == etype]


def _stream_send_bg(chat_id: int, content: str, events: list, state: dict):
    """后台线程驱动 SSE 流（用于流中被审批的写入类工具）。"""
    try:
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
        state["ok"] = True
    except Exception as e:  # noqa: BLE001
        state["error"] = repr(e)


def stream_send_auto_approve(chat_id: int, content: str) -> list:
    """流式发送 + 自动批准首个审批（write_file 写入工具场景）。"""
    events = []
    state = {"ok": False, "error": None}
    t = threading.Thread(target=_stream_send_bg, args=(chat_id, content, events, state), daemon=True)
    t.start()
    # 轮询审批注册表，出现即批准
    deadline = time.time() + 20
    aid = None
    while time.time() < deadline:
        if state.get("error"):
            raise AssertionError(f"流异常终止: {state['error']}")
        pending = approval_registry.pending()
        if pending:
            aid = pending[0]
            break
        time.sleep(0.05)
    if not aid:
        raise AssertionError(f"{20}s 内未注册审批。state={state}")
    r = CLIENT.post(f"/api/chat/{chat_id}/tool-approval", json={"approval_id": aid, "action": "approve"})
    assert r.status_code == 200, f"approve failed: {r.status_code} {r.text}"
    t.join(timeout=30)
    assert state.get("ok"), f"流未正常结束: {state}"
    return events


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------


def test_verify_strategy_units(project_dir: Path) -> dict:
    """1. 验证策略单元：write_file / run_command / default。"""
    checks = []

    # write_file：不存在 → failed
    r = verifier.verify({"tool": "write_file", "status": "success", "arguments": {
        "relative_path": "nope.txt", "content": "x"}}, str(project_dir))
    assert r.status == FAILED and "未创建" in r.message, r.to_dict()
    checks.append(("write_file 缺失→failed", True))

    # write_file：写入后重读一致 → passed
    project_dir.mkdir(parents=True, exist_ok=True)
    target = project_dir / "a.txt"
    target.write_text("hello", encoding="utf-8")
    r = verifier.verify({"tool": "write_file", "status": "success", "tool_call_id": "c1", "arguments": {
        "relative_path": "a.txt", "content": "hello"}}, str(project_dir))
    assert r.status == PASSED and r.strategy == "write_file", r.to_dict()
    assert r.evidence.get("size") == 5, r.to_dict()
    checks.append(("write_file 一致→passed", True))

    # write_file：内容不一致 → need_retry
    r = verifier.verify({"tool": "write_file", "status": "success", "arguments": {
        "relative_path": "a.txt", "content": "WORLD"}}, str(project_dir))
    assert r.status == NEED_RETRY and r.strategy == "write_file", r.to_dict()
    checks.append(("write_file 不一致→need_retry", True))

    # write_file：缺项目路径 → need_retry
    r = verifier.verify({"tool": "write_file", "status": "success", "arguments": {
        "relative_path": "a.txt", "content": "x"}}, None)
    assert r.status == NEED_RETRY, r.to_dict()
    checks.append(("write_file 缺项目→need_retry", True))

    # run_command：exit 0 → passed
    r = verifier.verify({"tool": "run_command", "status": "success", "result": "$ ipconfig\n[exit code 0]\n..."}, None)
    assert r.status == PASSED and r.evidence.get("exit_code") == 0, r.to_dict()
    checks.append(("run_command exit0→passed", True))

    # run_command：exit 1 → need_retry
    r = verifier.verify({"tool": "run_command", "status": "success", "result": "$ npm test\n[exit code 1]\nFAILED"}, None)
    assert r.status == NEED_RETRY and r.evidence.get("exit_code") == 1, r.to_dict()
    checks.append(("run_command exit1→need_retry", True))

    # run_command：工具失败（无退出码标记）→ failed
    r = verifier.verify({"tool": "run_command", "status": "failed", "success": False, "result": "错误: 找不到命令"}, None)
    assert r.status == FAILED, r.to_dict()
    checks.append(("run_command 失败→failed", True))

    # default：普通工具 → passed
    r = verifier.verify({"tool": "git_status", "status": "success", "result": "ok"}, None)
    assert r.status == PASSED and r.strategy == "default", r.to_dict()
    checks.append(("default 普通工具→passed", True))

    # verify_all：只验证 status==success
    rs = verifier.verify_all([
        {"tool": "git_status", "status": "success", "result": "ok"},
        {"tool": "write_file", "status": "failed", "arguments": {"relative_path": "x", "content": "y"}},
    ], str(project_dir))
    assert len(rs) == 1, f"应只验证成功动作，实际 {len(rs)}"
    checks.append(("verify_all 过滤非成功", True))

    return {"cases": checks, "all_ok": True}


def test_stream_write_file_passed(project_dir: Path) -> dict:
    """2. 流式：write_file 验证通过 → verify_result passed + 文件落盘（自动审批）。"""
    pid = make_project(project_dir / "wf_repo")
    cid = make_chat(pid)

    install_fake_llm([
        tool_call_round("write_file", '{"relative_path": "hello.txt", "content": "hello-e4"}'),
        text_round("文件已写入。"),
    ])
    events = stream_send_auto_approve(cid, "写文件 hello.txt，内容 hello-e4")

    results = find_events(events, "verify_result")
    assert results, "应发射 verify_result 事件"
    assert results[0]["status"] == PASSED, results[0]
    assert results[0]["strategy"] == "write_file", results[0]

    target = project_dir / "wf_repo" / "hello.txt"
    assert target.is_file(), f"文件应落盘: {target}"
    assert target.read_text(encoding="utf-8") == "hello-e4", "内容应一致"

    assert not find_events(events, "verification_failed"), "验证通过不应发射 verification_failed"
    # 下一轮不应注入反馈
    assert len(CAPTURED["rounds"]) >= 2
    assert not any("验证反馈" in (m.get("content") or "") for m in CAPTURED["rounds"][1]), "不应注入反馈"

    return {"case": "stream_write_file_passed", "chat_id": cid}


def test_stream_run_command_passed(project_dir: Path) -> dict:
    """3. 流式：run_command 退出码 0 → verify_result passed。"""
    pid = make_project(project_dir / "cmd_repo")
    cid = make_chat(pid)

    install_fake_llm([
        tool_call_round("run_command", '{"command": "hostname"}'),
        text_round("命令已执行。"),
    ])
    events = stream_send(cid, "执行 hostname")

    results = find_events(events, "verify_result")
    assert results, "应发射 verify_result 事件"
    assert results[0]["status"] == PASSED, results[0]
    assert results[0]["strategy"] == "run_command", results[0]
    assert results[0]["evidence"].get("exit_code") == 0, results[0]

    return {"case": "stream_run_command_passed", "chat_id": cid}


def test_stream_run_command_need_retry(project_dir: Path) -> dict:
    """4. 流式：run_command 非零退出 → need_retry + verification_failed + 反馈注入下一轮。"""
    pid = make_project(project_dir / "retry_repo")
    cid = make_chat(pid)

    missing = project_dir / "retry_repo" / "missing_module.py"
    args = json.dumps({"command": f"python -m py_compile {missing.name}"})
    install_fake_llm([
        tool_call_round("run_command", args),
        text_round("命令失败，我已检查原因。"),
    ])
    events = stream_send(cid, "编译缺失文件")

    results = find_events(events, "verify_result")
    assert results and results[0]["status"] == NEED_RETRY, results

    failed_events = find_events(events, "verification_failed")
    assert failed_events, "应发射 verification_failed 事件"
    assert "验证反馈" in failed_events[0]["message"], failed_events[0]
    assert failed_events[0]["results"][0]["status"] == NEED_RETRY, failed_events[0]

    # 反馈应注入下一轮 LLM 消息
    assert len(CAPTURED["rounds"]) >= 2, f"应有两轮模型请求，实际 {len(CAPTURED['rounds'])}"
    round2_text = "\n".join(m.get("content") or "" for m in CAPTURED["rounds"][1])
    assert "【验证反馈】" in round2_text, f"下一轮应看到验证反馈，实际: {round2_text[:200]}"

    # 流程仍正常结束
    assert find_events(events, "text"), "应有最终文本"

    return {"case": "stream_run_command_need_retry", "chat_id": cid}


def test_stream_default_tool_passed(project_dir: Path) -> dict:
    """5. 流式：普通工具（git_status）默认通过（strategy=default）。"""
    repo = project_dir / "git_repo"
    repo.mkdir(parents=True, exist_ok=True)
    import subprocess
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
    pid = make_project(repo)
    cid = make_chat(pid)

    install_fake_llm([
        tool_call_round("git_status", '{"relative_path": ""}'),
        text_round("仓库状态已查看。"),
    ])
    events = stream_send(cid, "查看仓库状态")

    results = find_events(events, "verify_result")
    assert results and results[0]["status"] == PASSED, results
    assert results[0]["strategy"] == "default", results[0]
    assert not find_events(events, "verification_failed"), "默认通过不应发射 verification_failed"

    return {"case": "stream_default_tool_passed", "chat_id": cid}


def test_nonstream_run_command_passed(project_dir: Path) -> dict:
    """6. 非流式（AgentRuntime.run 真实 executor）：run_command 退出码0 → 通过，无反馈注入。"""
    import asyncio
    from unittest.mock import AsyncMock, patch
    from app.core.agent_runtime import AgentRuntime, AgentContext
    from app.services.model import Message as M

    def make_tool_call(name, args):
        return [{"id": "call_ns", "type": "function",
                 "function": {"name": name, "arguments": json.dumps(args)}}]

    repo = project_dir / "ns_cmd_repo"
    repo.mkdir(parents=True, exist_ok=True)
    pid = make_project(repo)

    calls = []

    async def call_once_side_effect(model_id, messages, tools, **kwargs):
        calls.append([{"role": m.get("role"), "content": m.get("content")} for m in messages])
        if len(calls) == 1:
            return MockResult("", make_tool_call("run_command", {"command": "hostname"}), "tool_calls")
        return MockResult("命令已执行，验证通过。", None, "stop")

    with patch("app.services.model.model_service") as ms:
        ms.call_once = AsyncMock(side_effect=call_once_side_effect)

        async def _run():
            ctx = AgentContext(
                agent_id="coder", agent_identity="help", personality_level=None,
                model_id="deepseek-v4-flash", chat_id=None, project_id=pid,
                project_path=str(repo),
                tools=[{"type": "function", "function": {"name": "run_command", "description": "x"}}],
                decision=None,
            )
            return await AgentRuntime().run(context=ctx, messages=[M(role="user", content="执行命令")])

        result = asyncio.run(_run())

    assert "验证通过" in result.content, result.content
    # 工具轮 + 总结轮 + Phase 11 自查轮 = 3 轮 call_once
    assert len(calls) == 3, f"应有 3 轮 call_once（工具+总结+自查），实际 {len(calls)}"
    round2_text = "\n".join(m.get("content") or "" for m in calls[1])
    assert "验证反馈" not in round2_text, "验证通过不应注入反馈"

    return {"case": "nonstream_run_command_passed", "project_id": pid}


def test_nonstream_run_command_need_retry(project_dir: Path) -> dict:
    """7. 非流式：run_command 非零退出 → 反馈注入下一轮 call_once 消息。"""
    import asyncio
    from unittest.mock import AsyncMock, patch
    from app.core.agent_runtime import AgentRuntime, AgentContext
    from app.services.model import Message as M

    def make_tool_call(name, args):
        return [{"id": "call_ns2", "type": "function",
                 "function": {"name": name, "arguments": json.dumps(args)}}]

    repo = project_dir / "ns_retry_repo"
    repo.mkdir(parents=True, exist_ok=True)
    pid = make_project(repo)

    calls = []

    async def call_once_side_effect(model_id, messages, tools, **kwargs):
        calls.append([{"role": m.get("role"), "content": m.get("content")} for m in messages])
        if len(calls) == 1:
            return MockResult("", make_tool_call("run_command", {
                "command": "python -m py_compile missing_e4.py"}), "tool_calls")
        return MockResult("编译失败，文件缺失。", None, "stop")

    with patch("app.services.model.model_service") as ms:
        ms.call_once = AsyncMock(side_effect=call_once_side_effect)

        async def _run():
            ctx = AgentContext(
                agent_id="coder", agent_identity="help", personality_level=None,
                model_id="deepseek-v4-flash", chat_id=None, project_id=pid,
                project_path=str(repo),
                tools=[{"type": "function", "function": {"name": "run_command", "description": "x"}}],
                decision=None,
            )
            return await AgentRuntime().run(context=ctx, messages=[M(role="user", content="编译")])

        result = asyncio.run(_run())

    assert "编译失败" in result.content, result.content
    # 工具轮 + 反馈重试轮 + Phase 11 自查轮 = 3 轮 call_once
    assert len(calls) == 3, f"应有 3 轮 call_once（工具+重试+自查），实际 {len(calls)}"
    round2_text = "\n".join(m.get("content") or "" for m in calls[1])
    assert "【验证反馈】" in round2_text, f"下一轮应看到验证反馈，实际: {round2_text[:200]}"

    return {"case": "nonstream_run_command_need_retry", "project_id": pid}


class MockResult:
    def __init__(self, content, tool_calls, finish_reason):
        self.content = content
        self.tool_calls = tool_calls
        self.finish_reason = finish_reason
        self.usage = None


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 70)
    print("MfkAgent Verification Phase E4 自动化验证")
    print("临时工作目录:", _TEMP_DIR)
    print("=" * 70)

    from app.core.tool_runtime.approval_policy import set_approval_mode, ApprovalMode
    set_approval_mode(ApprovalMode.SAFE)

    project_dir = _TEMP_DIR / "project"
    project_dir.mkdir(exist_ok=True)

    results = []
    failures = []

    cases = [
        ("验证策略单元", lambda: test_verify_strategy_units(project_dir / "u1")),
        ("流式 write_file 通过", lambda: test_stream_write_file_passed(project_dir)),
        ("流式 run_command 退出码0", lambda: test_stream_run_command_passed(project_dir)),
        ("流式 run_command 非零→重试反馈", lambda: test_stream_run_command_need_retry(project_dir)),
        ("流式 普通工具默认通过", lambda: test_stream_default_tool_passed(project_dir)),
        ("非流式 run_command 通过", lambda: test_nonstream_run_command_passed(project_dir)),
        ("非流式 run_command 重试反馈", lambda: test_nonstream_run_command_need_retry(project_dir)),
    ]

    for name, fn in cases:
        t0 = time.monotonic()
        try:
            detail = fn()
            ok = detail.pop("all_ok", True)
            elapsed = (time.monotonic() - t0) * 1000
            results.append({"name": name, "ok": ok, "detail": detail, "elapsed_ms": round(elapsed)})
            print(f"  PASS  {name}  ({elapsed:.0f}ms)")
        except AssertionError as e:
            results.append({"name": name, "ok": False, "detail": str(e), "elapsed_ms": 0})
            failures.append(f"{name}: {e}")
            print(f"  FAIL  {name}\n        {e}")
        except Exception as e:  # noqa: BLE001
            results.append({"name": name, "ok": False, "detail": f"异常: {e!r}", "elapsed_ms": 0})
            failures.append(f"{name}: 异常 {e!r}")
            print(f"  ERROR {name}\n        {e!r}")

    total_ok = len(results) - len(failures)
    print("\n" + "=" * 70)
    print(f"结果: {total_ok}/{len(results)} 通过")
    if failures:
        print("失败明细:")
        for f in failures:
            print(f"  - {f}")
    print("=" * 70)

    if sys.argv[1:]:
        report = Path(sys.argv[1])
        report.write_text(
            "\n".join([
                "# Phase E4 — Verification 基础验证框架 测试报告",
                "",
                f"- 通过: {total_ok}/{len(results)}",
                f"- 用时: {sum(r['elapsed_ms'] for r in results)}ms",
                "",
                "| 用例 | 结果 | 用时 |",
                "| --- | --- | --- |",
            ] + [
                f"| {r['name']} | {'PASS' if r['ok'] else 'FAIL'} | {r['elapsed_ms']}ms |"
                for r in results
            ]),
            encoding="utf-8",
        )
        print(f"报告已写入: {report}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
