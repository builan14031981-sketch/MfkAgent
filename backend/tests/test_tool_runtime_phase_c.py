"""MfkAgent Tool Runtime Phase C 自动化验证脚本。

Phase C：Tool Calling 稳定性（Normalizer）+ 非流式审批拒绝。

单元级（normalizer）：
  1. Anthropic XML <invoke name="X">{json}</invoke>
  2. 通用 XML <tool_call><name>..</name><arguments>..</arguments></tool_call>
  3. 明确文本 "调用 run_command: ipconfig"（块状 + 行内）
  4. 解析失败场景（未知工具 / 非 JSON 参数 / 空名）→ 记入 issues，不静默

集成级（真实 executor + chat.py SSE 管线，脚本化 LLM）：
  5. 模型输出 <invoke name="git_status">…</invoke> → 归一化后真实执行，无审批
  6. 模型输出纯文本 "调用 run_command: ipconfig" → 归一化执行
  7. 模型输出无法解析的 XML → 回馈错误让模型重新生成（下一轮输出总结）
  8. 非流式路径（model_service.chat）遇审批 → 明确拒绝，空 result 不回喂

运行：
  python backend/tests/test_tool_runtime_phase_c.py [报告输出路径]

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

if __name__ == "__main__" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_phaseC_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./phase_c_test.db"
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
from app.core.tool_runtime.normalizer import normalize_tool_call_text  # noqa: E402

CLIENT = TestClient(app)


# ---------------------------------------------------------------------------
# 脚本化 LLM（与 Phase A/B 相同的 httpx 注入机制）
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


def _round_to_sse(round_dict):
    """把旧「非流式响应 dict」转成 stream_once 消费的 SSE chunk 序列。

    T4 双循环合一后，非流式 run() 内部统一走 run_stream() → model_service.stream_once()
    → httpx client.stream()（原 call_once 的 client.post 面不再被主循环使用）。因此
    非流式 mock 也必须产出 stream 面，本函数按 model.py 的 SSE 解析协议
    （choices[0].delta.content / delta.tool_calls / finish_reason）构造 chunk。
    """
    choice = round_dict["choices"][0]
    msg = choice.get("message") or {}
    finish = choice.get("finish_reason")
    chunks = []
    tcs = msg.get("tool_calls")
    if tcs:
        for i, tc in enumerate(tcs):
            fn = tc.get("function") or {}
            chunks.append(_sse_chunk({
                "choices": [{"delta": {"tool_calls": [{
                    "index": i,
                    "id": tc.get("id"),
                    "type": tc.get("type", "function"),
                    "function": {"name": fn.get("name", ""), "arguments": fn.get("arguments", "")},
                }]}, "finish_reason": None}]
            }))
        chunks.append(_sse_chunk({"choices": [{"delta": {}, "finish_reason": finish}]}))
    else:
        content = msg.get("content") or ""
        for i in range(0, len(content), 24):
            chunks.append(_sse_chunk({
                "choices": [{"delta": {"content": content[i:i + 24]}, "finish_reason": None}]
            }))
        chunks.append(_sse_chunk({"choices": [{"delta": {}, "finish_reason": finish}]}))
    return chunks


class FakeStreamResponse:
    """把 SSE chunk 列表包装成 httpx 流式响应（aiter_text 逐行产出）。"""

    def __init__(self, round_dict):
        self.status_code = 200
        self._chunks = _round_to_sse(round_dict)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def aread(self):
        return b""

    async def aiter_text(self):
        for c in self._chunks:
            yield c


def install_fake_llm(rounds, non_stream=False):
    state = {"idx": 0}

    if non_stream:
        class _FakeClient(FakeClient):
            def __init__(self, *a, **kw):
                super().__init__(rounds, state)

            async def post(self, url, headers=None, json=None, timeout=None):
                idx = state["idx"]
                state["idx"] += 1
                if idx >= len(rounds):
                    raise AssertionError(f"LLM 轮次溢出：调用了第 {idx} 轮")
                r = FakeResponse([])
                r.status_code = 200
                r.json = lambda: rounds[idx]
                return _SyncResponse(r)

            def stream(self, method, url, **kwargs):
                # T4 双循环合一：非流式主循环也走 stream_once → client.stream()
                idx = state["idx"]
                state["idx"] += 1
                if idx >= len(rounds):
                    raise AssertionError(f"LLM 轮次溢出：调用了第 {idx} 轮")
                return FakeStreamResponse(rounds[idx])
        httpx.AsyncClient = _FakeClient
        return

    class _FakeClient(FakeClient):
        def __init__(self, *a, **kw):
            super().__init__(rounds, state)

    httpx.AsyncClient = _FakeClient


class _SyncResponse:
    """包装非流式响应对象，伪装成 httpx.Response。"""

    def __init__(self, r):
        self._r = r
        self.status_code = r.status_code
        self.text = ""

    def json(self):
        return self._r.json()


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


def make_project(path: Path) -> int:
    path.mkdir(parents=True, exist_ok=True)
    r = CLIENT.post("/api/projects", json={"path": str(path), "name": "PhaseC-Project"})
    assert r.status_code == 200, f"create project failed: {r.status_code} {r.text}"
    return r.json()["id"]


def make_chat(project_id: int) -> int:
    r = CLIENT.post("/api/chat", json={"project_id": project_id, "agent_id": "coder", "title": "PhaseC"})
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


# ---------------------------------------------------------------------------
# 单元级用例
# ---------------------------------------------------------------------------

AVAIL = {"run_command", "read_file", "write_file", "git_status", "git_commit", "list_files", "web_search"}


def test_normalizer_units() -> dict:
    """1-4. Normalizer 单元用例。"""
    checks = []

    # 1) Anthropic XML invoke + JSON
    r = normalize_tool_call_text(
        '<invoke name="run_command">{"command": "ipconfig"}</invoke>', AVAIL)
    assert len(r["calls"]) == 1 and not r["issues"], r
    c = r["calls"][0]
    assert c["function"]["name"] == "run_command"
    assert json.loads(c["function"]["arguments"]) == {"command": "ipconfig"}
    checks.append(("invoke+JSON", True))

    # invoke + ```json 围栏
    r = normalize_tool_call_text(
        '<invoke name="read_file">\n```json\n{"relative_path": "app.py"}\n```\n</invoke>', AVAIL)
    assert json.loads(r["calls"][0]["function"]["arguments"]) == {"relative_path": "app.py"}, r
    checks.append(("invoke+json围栏", True))

    # 2) 通用 XML tool_call（name + arguments 标签）
    r = normalize_tool_call_text(
        "<tool_call><name>git_status</name><arguments>{\"relative_path\": \"\"}</arguments></tool_call>", AVAIL)
    assert r["calls"][0]["function"]["name"] == "git_status", r
    checks.append(("tool_call+name+arguments", True))

    # 3) 明确文本：块状
    r = normalize_tool_call_text("调用 run_command:\nipconfig\n", AVAIL)
    assert len(r["calls"]) == 1 and json.loads(r["calls"][0]["function"]["arguments"]) == {"command": "ipconfig"}, r
    checks.append(("文本块状", True))

    # 明确文本：行内
    r = normalize_tool_call_text("调用 run_command: ipconfig", AVAIL)
    assert len(r["calls"]) == 1 and json.loads(r["calls"][0]["function"]["arguments"]) == {"command": "ipconfig"}, r
    checks.append(("文本行内", True))

    # 4) 失败场景 → issues，不静默
    r = normalize_tool_call_text('<invoke name="unknown_tool">{"x": 1}</invoke>', AVAIL)
    assert not r["calls"] and r["issues"] and "不在当前可用列表" in r["issues"][0]["reason"], r
    checks.append(("未知工具→issue", True))

    r = normalize_tool_call_text('<invoke name="write_file">纯文本参数</invoke>', AVAIL)
    assert not r["calls"] and r["issues"], r
    checks.append(("write_file非JSON→issue", True))

    r = normalize_tool_call_text('<invoke name="">{"x":1}</invoke>', AVAIL)
    assert not r["calls"] and r["issues"], r
    checks.append(("空工具名→issue", True))

    r = normalize_tool_call_text("正常的一句话，没有任何工具调用。", AVAIL)
    assert not r["calls"] and not r["issues"], r
    checks.append(("无调用→空结果", True))

    # 多工具混合
    r = normalize_tool_call_text(
        '<invoke name="run_command">{"command": "netstat -an"}</invoke>\n调用 read_file:\n{"relative_path": "a.py"}', AVAIL)
    assert len(r["calls"]) == 2 and not r["issues"], r
    checks.append(("多调用混合", True))

    return {"cases": checks, "all_ok": True}


# ---------------------------------------------------------------------------
# 集成级用例（真实 executor + chat.py 管线）
# ---------------------------------------------------------------------------


def setup_git_repo(path: Path) -> None:
    import subprocess
    path.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="PhaseC Test", GIT_AUTHOR_EMAIL="t@t.local",
               GIT_COMMITTER_NAME="PhaseC Test", GIT_COMMITTER_EMAIL="t@t.local")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, env=env)
    subprocess.run(["git", "config", "user.name", "PhaseC Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.local"], cwd=path, check=True)
    (path / "tracked.txt").write_text("tracked", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True, env=env)
    (path / "untracked.txt").write_text("new", encoding="utf-8")


def test_integration_xml(project_dir: Path) -> dict:
    """5. 模型输出 <invoke name="git_status">…</invoke> → 归一化执行。"""
    repo = project_dir / "xml_repo"
    setup_git_repo(repo)

    install_fake_llm([
        text_round('让我看看 git 状态。\n<invoke name="git_status">{"relative_path": ""}</invoke>'),
        text_round("Git 状态检查完成。"),
    ])
    pid = make_project(repo)
    cid = make_chat(pid)

    events = stream_send(cid, "看看项目有什么改动")
    starts = find_events(events, "tool_start")
    results = find_events(events, "tool_result")
    assert len(starts) == 1 and len(results) == 1, (len(starts), len(results))
    assert starts[0]["tool"] == "git_status", starts[0]
    assert results[0]["success"] is True, f"归一化 git_status 应执行成功: {results[0]['result'][:120]!r}"
    assert "untracked.txt" in results[0]["result"], results[0]["result"][:120]
    return {"case": "xml_invoke", "executed": True, "chat_id": cid}


def test_integration_text(project_dir: Path) -> dict:
    """6. 纯文本 "调用 run_command: …" → 归一化执行。"""
    repo = project_dir / "txt_repo"
    setup_git_repo(repo)

    install_fake_llm([
        text_round("检查网络：\n调用 run_command:\nipconfig"),
        text_round("网络检查完成。"),
    ])
    pid = make_project(repo)
    cid = make_chat(pid)

    events = stream_send(cid, "检查网络代理")
    starts = find_events(events, "tool_start")
    results = find_events(events, "tool_result")
    assert len(starts) == 1 and len(results) == 1, (len(starts), len(results))
    assert starts[0]["tool"] == "run_command", starts[0]
    assert results[0]["success"] is True, f"归一化 run_command 应执行成功: {results[0]['result'][:120]!r}"
    return {"case": "text_call", "executed": True, "chat_id": cid}


def test_integration_parse_fail(project_dir: Path) -> dict:
    """7. 无法解析的 XML → 回馈错误，模型下一轮重新生成总结。"""
    repo = project_dir / "fail_repo"
    setup_git_repo(repo)

    install_fake_llm([
        text_round('<invoke name="not_a_tool">{"x":1}</invoke>'),
        text_round("好的，我不会执行未知工具。"),
    ])
    pid = make_project(repo)
    cid = make_chat(pid)

    events = stream_send(cid, "帮我检查一下")
    starts = find_events(events, "tool_start")
    results = find_events(events, "tool_result")
    # 未知工具 → 解析失败 → 不执行任何工具
    assert not starts and not results, (starts, results)
    assert find_events(events, "text"), "应输出文本"
    # 回馈的解析失败信息应在最终 assistant 文本中出现（模型重生成后不再出现）
    has_error_feedback = any(
        "解析失败" in (e.get("message") or "") for e in find_events(events, "error")
    ) or any("工具" in (e.get("content") or "") for e in find_events(events, "text"))
    assert has_error_feedback, "应存在关于解析失败/工具的文本反馈"
    return {"case": "parse_fail", "no_execution": True, "chat_id": cid}


class MockResult:
    """T4 mock 适配：单次 LLM 调用结果对象（content/tool_calls/finish_reason/usage 形状）。

    供 stream_from_single_call 包装成 stream_once 事件流（见 test_nonstream_approval_reject）。
    """

    def __init__(self, content, tool_calls, finish_reason):
        self.content = content
        self.tool_calls = tool_calls
        self.finish_reason = finish_reason
        self.usage = None


def test_nonstream_approval_reject(project_dir: Path) -> dict:
    """8. 非流式路径（AgentRuntime.run）遇审批 → T4 契约：立即返回 pending_approval，不阻塞等待。

    T4 双循环合一后 run() 不再持有独立非流式执行循环（旧实现归档 _legacy_run.py）：
    内部消费 run_stream()，遇 tool_approval 立即返回 finish_reason="pending_approval"
    的 AgentResult，metadata.pending_approval 携带审批摘要；审批条目保留在
    approval_registry 等待 /approve 闭环（不再 resolve/remove），绝不在非流式
    HTTP 请求里同步等待审批。本用例按此契约 mock 第一轮 tool_calls
    （run_command git reset --hard HEAD，HIGH_RISK 强制审批）并校验返回。
    """
    from unittest.mock import AsyncMock, patch
    from app.core.tool_runtime.approval import approval_registry
    from tests._t4_mock_adapter import stream_from_single_call

    repo = project_dir / "ns_repo"
    setup_git_repo(repo)
    pid = make_project(repo)
    cid = make_chat(pid)

    calls = []

    def make_tool_call(name, args):
        return [{"id": "call_ns_1", "type": "function",
                 "function": {"name": name, "arguments": json.dumps(args)}}]

    async def call_once_side_effect(model_id, messages, tools, **kwargs):
        calls.append([{"role": m.get("role"), "content": m.get("content")} for m in messages])
        return MockResult("", make_tool_call("run_command", {"command": "git reset --hard HEAD"}), "tool_calls")

    import asyncio

    async def _run():
        from app.core.agent_runtime import AgentRuntime, AgentContext
        from app.services.model import Message as M

        with patch("app.services.model.model_service") as ms:
            ms.stream_once = stream_from_single_call(call_once_side_effect)  # T4：run() 内部走 stream_once
            ms.call_once = AsyncMock(side_effect=call_once_side_effect)  # 兼容仍可能走 call_once 的分支
            context = AgentContext(
                agent_id="coder",
                agent_identity="你是一个有帮助的AI助手。",
                personality_level=None,
                model_id="deepseek-v4-flash",
                project_id=pid,
                project_path=str(repo),
                memory_context={"agent_id": "coder", "project_id": pid, "chat_id": cid},
                memory_text=None,
                tools=[{"type": "function", "function": {"name": "run_command", "description": "x",
                                                        "parameters": {"type": "object", "properties": {}}}}],
                decision=None,
            )
            return await AgentRuntime().run(
                context=context,
                messages=[M(role="user", content="git reset --hard HEAD")],
                read_only=False,
            )

    resp = asyncio.run(_run())
    # T4 契约：遇审批立即返回 pending_approval，不阻塞、不回喂空 result
    assert resp.finish_reason == "pending_approval", (
        f"应返回 pending_approval，实际 finish_reason={resp.finish_reason!r} content={resp.content!r}"
    )
    pending = resp.metadata.get("pending_approval", {})
    assert pending.get("approval_id"), f"应携带 approval_id: {pending}"
    assert pending.get("tool") == "run_command", f"应标明触发审批的工具: {pending}"
    assert "git reset" in (pending.get("command") or ""), f"应携带待审批命令: {pending}"
    # 审批条目保留在 registry 等待 /approve 闭环（T4：不再 resolve cancelled / remove）
    assert len(approval_registry.pending()) >= 1, f"审批应挂起待决: {approval_registry.pending()}"
    return {"case": "nonstream_approval", "pending_approval": True, "chat_id": cid}


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def main() -> int:
    from app.core.tool_runtime.approval_policy import set_approval_mode, ApprovalMode
    set_approval_mode(ApprovalMode.SAFE)
    print("=" * 70)
    print("MfkAgent Tool Runtime Phase C 自动化验证")
    print("临时工作目录:", _TEMP_DIR)
    print("=" * 70)

    project_dir = _TEMP_DIR / "project"
    project_dir.mkdir(exist_ok=True)

    results = []
    failures = []

    cases = [
        ("Normalizer 单元用例", test_normalizer_units),
        ("集成: XML invoke 归一化执行", lambda: test_integration_xml(project_dir / "x1")),
        ("集成: 纯文本调用归一化执行", lambda: test_integration_text(project_dir / "x2")),
        ("集成: 解析失败回馈重生成", lambda: test_integration_parse_fail(project_dir / "x3")),
        ("非流式审批明确拒绝", lambda: test_nonstream_approval_reject(project_dir / "x4")),
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
            failures.append(f"{name}: {e!r}")
            print(f"  ERROR {name}\n        {e!r}")

    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (BACKEND_DIR / "tests" / "phase_c_test_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# MfkAgent Tool Runtime Phase C 测试报告\n",
             f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"- 临时工作目录: `{_TEMP_DIR}`",
             f"- 测试模式: 单元级 (normalizer) + FastAPI TestClient + 脚本化 LLM",
             "",
             "## 结果总览\n",
             "| # | 用例 | 结果 | 耗时 |",
             "|---|------|------|------|",
             ]
    for i, r in enumerate(results, 1):
        lines.append(f"| {i} | {r['name']} | {'✅ PASS' if r['ok'] else '❌ FAIL'} | {r['elapsed_ms']}ms |")
    passed = sum(1 for r in results if r["ok"])
    lines.append(f"\n**通过率: {passed}/{len(results)}**\n")
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
        lines.append("✅ **全部通过**：非标准工具调用可归一化执行；解析失败回馈重生成；非流式审批明确拒绝。\n")
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
