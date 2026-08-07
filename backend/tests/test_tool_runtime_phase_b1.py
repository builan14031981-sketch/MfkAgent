"""MfkAgent Tool Runtime Phase B-1 自动化验证脚本（Risk Engine + Approval Flow）。

验证目标：
  1. approve 路径：危险命令（git reset --hard HEAD）→ tool_start → tool_approval → 批准 → 真实执行 → tool_result
  2. deny 路径：拒绝 → tool_result(success=False)，命令未执行
  3. plan 模式：危险命令直接拒绝，不发 tool_approval，也不执行
  4. 审批 API：POST /api/chat/{id}/tool-approval（200 / 422 / 404 / 409）

验证方式（与 Phase A 同框架）：
  - 临时目录 + 独立 TestClient（临时 SQLite），脚本化 LLM（httpx 层注入）
  - executor / risk_engine / approval / model_service.chat_stream / chat.py 全为生产代码
  - 审批在流进行中被批准：后台线程驱动流，主线程检测 tool_approval 后 resolve
  - 测试数据使用临时目录，结束自动清理

运行：python backend/tests/test_tool_runtime_phase_b1.py
退出码：0 = 全部通过；1 = 存在失败。
"""

import asyncio
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_phaseB1_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./phase_b1_test.db"
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
from app.core.tool_runtime.approval import approval_registry  # noqa: E402

CLIENT = TestClient(app)

# 确保审批注册表干净
assert approval_registry.pending() == []


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
            raise AssertionError(f"LLM 轮次溢出：第 {idx} 轮，脚本只有 {len(self._rounds)} 轮")
        return FakeResponse(self._rounds[idx])


def install_fake_llm(rounds):
    state = {"idx": 0}

    class _FakeClient(FakeClient):
        def __init__(self, *a, **kw):
            super().__init__(rounds, state)

    httpx.AsyncClient = _FakeClient


def _sse_chunk(obj):
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def tool_round(name, args, call_id):
    chunks = [
        _sse_chunk({"choices": [{"delta": {"content": "我来处理。", "reasoning_content": "先取真实数据"}, "finish_reason": None}]}),
    ]
    arg_json = json.dumps(args, ensure_ascii=False)
    chunks.append(_sse_chunk({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": call_id, "type": "function",
                                                                      "function": {"name": name, "arguments": ""}}]}, "finish_reason": None}]}))
    step = max(1, len(arg_json) // 3 or 1)
    for i in range(0, len(arg_json), step):
        chunks.append(_sse_chunk({"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": arg_json[i:i + step]}}]}, "finish_reason": None}]}))
    chunks.append(_sse_chunk({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}))
    return chunks


def text_round(text):
    chunks = []
    for i in range(0, len(text), 24):
        chunks.append(_sse_chunk({"choices": [{"delta": {"content": text[i:i + 24]}, "finish_reason": None}]}))
    chunks.append(_sse_chunk({"choices": [{"delta": {}, "finish_reason": "stop"}]}))
    return chunks


def make_project(path: Path) -> int:
    path.mkdir(parents=True, exist_ok=True)
    r = CLIENT.post("/api/projects", json={"path": str(path), "name": "PhaseB1-Project"})
    assert r.status_code == 200, f"create project failed: {r.status_code} {r.text}"
    return r.json()["id"]


def make_chat(project_id: int, mode: str = "build") -> int:
    body = {"project_id": project_id, "agent_id": "coder", "title": "PhaseB1", "mode": mode}
    r = CLIENT.post("/api/chat", json=body)
    assert r.status_code == 200, f"create chat failed: {r.status_code} {r.text}"
    return r.json()["id"]


def stream_send_bg(chat_id: int, content: str, events: list, state: dict):
    """后台线程：驱动 SSE 流并收集事件（用于流中被审批的场景）。"""
    try:
        with CLIENT.stream(
            "POST",
            f"/api/chat/{chat_id}/send/stream",
            json={"content": content, "model": "deepseek-v4-flash", "reasoning_effort": "none"},
        ) as resp:
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


def wait_pending(state: dict, timeout: float = 20.0) -> str:
    """轮询审批注册表，返回首个 pending approval_id。

    说明：executor 在发射 tool_approval 事件之前就先 register()，因此轮询
    注册表可在流式传输被 TestClient 缓冲的情况下可靠获知"已进入待审批"。
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if state.get("error"):
            raise AssertionError(f"流异常终止: {state['error']}")
        p = approval_registry.pending()
        if p:
            return p[0]
        time.sleep(0.05)
    raise AssertionError(f"{timeout}s 内审批未注册。state={state}")


def find_events(events, etype):
    return [e for e in events if e.get("type") == etype]


def setup_git_repo(path: Path) -> None:
    """预置 git 仓库：一次提交 + 一个未跟踪文件。"""
    path.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="PhaseB1 Test", GIT_AUTHOR_EMAIL="t@t.local",
               GIT_COMMITTER_NAME="PhaseB1 Test", GIT_COMMITTER_EMAIL="t@t.local")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, env=env)
    (path / "tracked.txt").write_text("tracked", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True, env=env)
    (path / "untracked.txt").write_text("new", encoding="utf-8")


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------


def test_approve(project_dir: Path) -> dict:
    """1. approve 路径：git reset --hard HEAD 经批准后真实执行。"""
    repo = project_dir / "git_approve"
    setup_git_repo(repo)

    install_fake_llm([
        tool_round("run_command", {"command": "git reset --hard HEAD"}, "call_ask_1"),
        text_round("已重置到 HEAD。"),
    ])
    pid = make_project(repo)
    cid = make_chat(pid, mode="build")

    events, state = [], {}
    t = threading.Thread(target=stream_send_bg, args=(cid, "检查我的网络代理", events, state), daemon=True)
    t.start()

    aid = wait_pending(state)
    info = approval_registry.get(aid)
    assert info is not None and info["tool"] == "run_command", f"tool 不符: {info}"
    assert info["command"] == "git reset --hard HEAD", f"command 不符: {info['command']}"
    assert info["risk_level"] == "destructive", f"risk_level 不符: {info['risk_level']}"
    assert info["tool_call_id"] == "call_ask_1", f"tool_call_id 不符: {info['tool_call_id']}"
    assert info["chat_id"] == cid, f"chat_id 不符: {info['chat_id']}"

    assert approval_registry.resolve(aid, "approve"), "resolve(approve) 失败"
    t.join(timeout=25)
    assert not t.is_alive(), "流未在 25s 内结束"

    starts = find_events(events, "tool_start")
    results = find_events(events, "tool_result")
    apps = find_events(events, "tool_approval")
    assert len(starts) == 1 and len(results) == 1 and len(apps) == 1, (len(starts), len(apps), len(results))
    assert apps[0]["approval_id"] == aid, "tool_approval 的 approval_id 与注册表不符"
    assert apps[0]["command"] == "git reset --hard HEAD", "tool_approval command 不符"
    assert starts[0]["tool_call_id"] == apps[0]["tool_call_id"] == results[0]["tool_call_id"], "tool_call_id 链路不一致"
    assert events.index(starts[0]) < events.index(apps[0]) < events.index(results[0]), "事件顺序错误"
    r = results[0]
    assert r["success"] is True, f"批准后应执行成功，实际 success={r['success']}, result={r['result'][:120]!r}"
    assert "HEAD is now at" in r["result"], f"git reset 输出不符: {r['result'][:120]!r}"
    return {"case": "approve", "tool_call_id": r["tool_call_id"], "success": r["success"], "chat_id": cid}


def test_deny(project_dir: Path) -> dict:
    """2. deny 路径：拒绝后不执行，注入拒绝结果。"""
    repo = project_dir / "git_deny"
    setup_git_repo(repo)

    install_fake_llm([
        tool_round("run_command", {"command": "git reset --hard HEAD"}, "call_ask_2"),
        text_round("好的，未执行该操作。"),
    ])
    pid = make_project(repo)
    cid = make_chat(pid, mode="build")

    events, state = [], {}
    t = threading.Thread(target=stream_send_bg, args=(cid, "检查我的网络代理", events, state), daemon=True)
    t.start()

    aid = wait_pending(state)
    assert approval_registry.resolve(aid, "deny"), "resolve(deny) 失败"
    t.join(timeout=25)
    assert not t.is_alive(), "流未在 25s 内结束"

    apps = find_events(events, "tool_approval")
    assert apps and apps[0]["approval_id"] == aid, "tool_approval 缺失或 approval_id 不符"
    r = find_events(events, "tool_result")[0]
    assert r["success"] is False, f"拒绝后 success 应为 False: {r}"
    assert "用户拒绝" in r["result"], f"拒绝文案不符: {r['result'][:120]!r}"
    # 验证命令确实未执行：工作区应保留 untracked.txt 且 tracked.txt 内容未变
    assert (repo / "untracked.txt").exists(), "拒绝后不应有任何 git 副作用"
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "tracked", "拒绝后不应有 git 副作用"
    return {"case": "deny", "tool_call_id": r["tool_call_id"], "success": r["success"], "chat_id": cid}


def test_plan_mode_deny(project_dir: Path) -> dict:
    """3. plan 模式：危险命令直接拒绝，无 tool_approval，不执行。"""
    repo = project_dir / "git_plan"
    setup_git_repo(repo)

    install_fake_llm([
        tool_round("run_command", {"command": "git reset --hard HEAD"}, "call_ask_3"),
        text_round("plan 模式下不能修改。"),
    ])
    pid = make_project(repo)
    cid = make_chat(pid, mode="plan")

    events, state = [], {}
    t = threading.Thread(target=stream_send_bg, args=(cid, "检查我的网络代理", events, state), daemon=True)
    t.start()
    t.join(timeout=25)
    assert not t.is_alive(), "流未在 25s 内结束"
    assert state.get("error") is None, state.get("error")

    assert not find_events(events, "tool_approval"), "plan 模式不应发射 tool_approval"
    r = find_events(events, "tool_result")[0]
    assert r["success"] is False, f"plan 模式 success 应为 False: {r}"
    assert "plan 只读模式" in r["result"], f"plan 拒绝文案不符: {r['result'][:120]!r}"
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "tracked", "plan 模式不应有副作用"
    return {"case": "plan_deny", "tool_call_id": r["tool_call_id"], "success": r["success"], "chat_id": cid}


def test_approval_endpoint(project_dir: Path) -> dict:
    """4. 审批 API：200 / 422 / 404 / 409。"""
    # 正常 chat 上下文
    repo = project_dir / "ep_proj"
    repo.mkdir(parents=True, exist_ok=True)
    pid = make_project(repo)
    cid = make_chat(pid, mode="build")

    # 用独立事件循环注册一条 pending 审批（register 需要 running loop）
    loop = asyncio.new_event_loop()
    try:
        container = {}

        def _do():
            aid, inf = approval_registry.register(
                "call_ep_1", "run_command", "git reset --hard HEAD",
                "destructive", "need", chat_id=cid, timeout=30,
            )
            container["aid"] = aid
            container["info"] = inf

        loop.run_until_complete(_async_void(_do))
        approval_id = container["aid"]
        info = container["info"]

        # 200 approve
        r = CLIENT.post(f"/api/chat/{cid}/tool-approval", json={"approval_id": approval_id, "action": "approve"})
        assert r.status_code == 200, f"approve 应 200，实际 {r.status_code} {r.text}"
        assert r.json()["action"] == "approve"
        loop.run_until_complete(_async_void(lambda: None))
        assert info["future"].done() and info["future"].result() == "approve", "future 未解析为 approve"

        # 409 已处理
        r2 = CLIENT.post(f"/api/chat/{cid}/tool-approval", json={"approval_id": approval_id, "action": "deny"})
        assert r2.status_code == 409, f"重复处理应 409，实际 {r2.status_code} {r2.text}"

        # 422 非法 action
        r3 = CLIENT.post(f"/api/chat/{cid}/tool-approval", json={"approval_id": approval_id, "action": "run"})
        assert r3.status_code == 422, f"非法 action 应 422，实际 {r3.status_code} {r3.text}"

        # 404 不属于该会话
        container2 = {}

        def _do2():
            aid2, info2 = approval_registry.register(
                "call_ep_2", "run_command", "echo hi", "write", "need", chat_id=cid + 9999, timeout=30,
            )
            container2["aid"] = aid2

        loop.run_until_complete(_async_void(_do2))
        r4 = CLIENT.post(f"/api/chat/{cid}/tool-approval", json={"approval_id": container2["aid"], "action": "approve"})
        assert r4.status_code == 404, f"跨会话审批应 404，实际 {r4.status_code} {r4.text}"
        approval_registry.remove(container2["aid"])
        return {"case": "endpoint", "ok": True, "chat_id": cid}
    finally:
        loop.close()


async def _async_void(fn):
    fn()


def main() -> int:
    print("=" * 70)
    print("MfkAgent Tool Runtime Phase B-1 自动化验证")
    print("临时工作目录:", _TEMP_DIR)
    print("=" * 70)

    project_dir = _TEMP_DIR / "project"
    results = []
    failures = []

    cases = [
        ("审批批准后真实执行 (approve)", lambda: test_approve(project_dir)),
        ("审批拒绝不执行 (deny)", lambda: test_deny(project_dir)),
        ("plan 模式直接拒绝 (plan_deny)", lambda: test_plan_mode_deny(project_dir)),
        ("审批 API 状态码 (endpoint)", lambda: test_approval_endpoint(project_dir)),
    ]

    for name, fn in cases:
        t0 = time.monotonic()
        try:
            detail = fn()
            elapsed = (time.monotonic() - t0) * 1000
            results.append({"name": name, "ok": True, "detail": detail, "elapsed_ms": round(elapsed)})
            print(f"  PASS  {name}  ({elapsed:.0f}ms)")
        except AssertionError as e:
            results.append({"name": name, "ok": False, "detail": str(e), "elapsed_ms": 0})
            failures.append(f"{name}: {e}")
            print(f"  FAIL  {name}\n        {e}")
        except Exception as e:  # noqa: BLE001
            results.append({"name": name, "ok": False, "detail": f"异常: {e!r}", "elapsed_ms": 0})
            failures.append(f"{name}: {e!r}")
            print(f"  ERROR {name}\n        {e!r}")

    print()
    passed = sum(1 for r in results if r["ok"])
    print(f"通过率: {passed}/{len(results)}")
    for r in results:
        print(f"  {r['name']}: {'OK' if r['ok'] else 'FAIL'} -> {r['detail']}")

    # 审批注册表无残留
    leftover = approval_registry.pending()
    if leftover:
        print(f"  警告: 审批注册表存在残留 {leftover}")

    cleanup()
    return 1 if failures else 0


def cleanup():
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


if __name__ == "__main__":
    sys.exit(main())
