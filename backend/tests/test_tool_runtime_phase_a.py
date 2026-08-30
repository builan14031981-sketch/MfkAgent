"""MfkAgent Tool Runtime Phase A 自动化验证脚本。

验证目标（对应 Phase A：Tool Event Stream + ToolCallCard v2 后端部分）：
  1. 网络诊断工具调用（run_command → ipconfig）
  2. 文件读取工具调用（read_file）
  3. Git 工具调用（git_status）
  4. 文件写入工具调用（write_file）

验证方式：
  - 在临时工作目录启动独立 FastAPI TestClient（临时 SQLite，不触碰真实 mfkagent.db）
  - 在 httpx 网络层注入"脚本化 LLM 响应"，驱动真实 executor + 事件源 + chat.py SSE 管道
    （executor / ToolEventSource / model_service.chat_stream / chat.py 全部为生产代码，未被 mock）
  - 捕获 SSE 事件，验证：tool_start / tool_result / tool_call_id 配对 / duration_ms / success
  - 验证持久化 Message.tool_calls 同时含新旧字段（tool/status/duration_ms + name/success）
  - 测试数据使用临时目录，结束自动清理（含 DB / uploads / chroma / 项目目录）

运行：
  python backend/tests/test_tool_runtime_phase_a.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

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

# 标准输出以 UTF-8 打印，避免 Windows GBK 控制台报错
if __name__ == "__main__" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# 临时环境隔离：必须在 import main 之前完成（config 在导入时读取路径/DB）
# ---------------------------------------------------------------------------
_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_phaseA_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./phase_a_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# 预创建表结构：main 导入时 model_service 会读 settings 表，
# 全新临时 DB 尚未建表会报 "no such table"，故先注册模型并 create_all。
import app.models.agent as _agent_models  # noqa: F401, E402  注册模型到 Base
from app.core.database import engine as _engine, Base as _Base  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from main import app  # noqa: E402

from app.core.tool_runtime.approval import approval_registry  # noqa: E402


# 模块级审批模式：pytest 不调用 main()，需显式设为 SAFE
from app.core.tool_runtime.approval_policy import set_approval_mode, ApprovalMode
set_approval_mode(ApprovalMode.SAFE)
CLIENT = TestClient(app, base_url="http://127.0.0.1")  # 回环 host，豁免移动端配对认证

# ---------------------------------------------------------------------------
# 脚本化 LLM：替换 httpx.AsyncClient，按调用顺序返回脚本化 SSE 轮次
# ---------------------------------------------------------------------------


class FakeResponse:
    """模拟 OpenAI 兼容流式响应（每轮一个响应对象）。"""

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
    """模拟 httpx.AsyncClient：每次 .stream() 按共享计数器返回下一轮脚本。"""

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
    """安装脚本化 LLM（每轮一个 httpx.AsyncClient 实例，共享计数器）。"""
    state = {"idx": 0}

    class _FakeClient(FakeClient):
        def __init__(self, *a, **kw):
            super().__init__(rounds, state)

    httpx.AsyncClient = _FakeClient


def _sse_chunk(obj):
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def tool_round(name, args, call_id):
    """构造"工具调用轮"的 SSE 增量块（含思考段 + 参数分段累积）。"""
    chunks = [
        _sse_chunk({
            "choices": [{
                "delta": {"content": "让我先检查一下。", "reasoning_content": "需要真实数据支撑回答"},
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


def text_round(text):
    """构造"纯文本收尾轮"的 SSE 增量块。"""
    chunks = []
    for i in range(0, len(text), 24):
        chunks.append(_sse_chunk({
            "choices": [{"delta": {"content": text[i:i + 24]}, "finish_reason": None}]
        }))
    chunks.append(_sse_chunk({"choices": [{"delta": {}, "finish_reason": "stop"}]}))
    return chunks


# ---------------------------------------------------------------------------
# API 辅助
# ---------------------------------------------------------------------------


def make_project(path: str) -> int:
    r = CLIENT.post("/api/projects", json={"path": str(path), "name": "PhaseA-Project"})
    assert r.status_code == 200, f"create project failed: {r.status_code} {r.text}"
    return r.json()["id"]


def make_chat(project_id: int) -> int:
    r = CLIENT.post("/api/chat", json={"project_id": project_id, "agent_id": "coder", "permission_mode": "safe", "title": "PhaseA"})
    assert r.status_code == 200, f"create chat failed: {r.status_code} {r.text}"
    return r.json()["id"]


def stream_send(chat_id: int, content: str) -> list:
    """发送消息并捕获完整 SSE 事件流。"""
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
    """轮询审批注册表，返回首个 pending approval_id。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if state.get("error"):
            raise AssertionError(f"流异常终止: {state['error']}")
        p = approval_registry.pending()
        if p:
            return p[0]
        time.sleep(0.05)
    raise AssertionError(f"{timeout}s 内审批未注册。state={state}")


def get_persisted_tool_calls(chat_id: int) -> list:
    msgs = CLIENT.get(f"/api/chat/{chat_id}/messages").json()
    for m in msgs:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            return m["tool_calls"]
    return []


# ---------------------------------------------------------------------------
# 断言辅助
# ---------------------------------------------------------------------------


def find_events(events, etype):
    return [e for e in events if e.get("type") == etype]


def verify_tool_pair(events, expected_tool, call_id=None, check_result=True):
    """验证 tool_start / tool_result 配对与核心字段。"""
    starts = find_events(events, "tool_start")
    results = find_events(events, "tool_result")
    assert starts, f"缺少 tool_start 事件（tool={expected_tool}）"
    assert results, f"缺少 tool_result 事件（tool={expected_tool}）"

    s = starts[0]
    r = results[0]
    assert s.get("tool") == expected_tool, f"tool_start.tool={s.get('tool')} != {expected_tool}"
    assert r.get("tool") == expected_tool, f"tool_result.tool={r.get('tool')} != {expected_tool}"
    assert s.get("tool_call_id"), "tool_start.tool_call_id 为空"
    assert r.get("tool_call_id"), "tool_result.tool_call_id 为空"
    assert s["tool_call_id"] == r["tool_call_id"], f"tool_call_id 不配对: {s['tool_call_id']} vs {r['tool_call_id']}"
    assert isinstance(r.get("duration_ms"), int) and r["duration_ms"] >= 0, f"duration_ms 缺失/非法: {r.get('duration_ms')}"
    if call_id is not None:
        assert s["tool_call_id"] == call_id, f"tool_call_id 与脚本不符: {s['tool_call_id']} != {call_id}"
    # tool_start 必须出现在其 tool_result 之前
    assert events.index(s) < events.index(r), "tool_start 未出现在 tool_result 之前"
    if check_result:
        assert isinstance(r.get("result"), str) and r["result"], "tool_result.result 为空"
    return s, r


# ---------------------------------------------------------------------------
# 四个测试用例
# ---------------------------------------------------------------------------


def test_network_diagnosis(project_dir: Path) -> dict:
    """1. 网络诊断：run_command 执行 ipconfig。"""
    install_fake_llm([
        tool_round("run_command", {"command": "ipconfig"}, "call_net_1"),
        text_round("网络诊断完成，你的网络配置如下。"),
    ])
    pid = make_project(project_dir)
    cid = make_chat(pid)
    events = stream_send(cid, "检查我的网络代理")
    s, r = verify_tool_pair(events, "run_command", call_id="call_net_1")
    assert r["success"] is True, f"ipconfig 应成功，实际 success={r['success']}, result={r['result'][:120]!r}"
    return {
        "tool": "run_command",
        "call_id": s["tool_call_id"],
        "success": r["success"],
        "duration_ms": r["duration_ms"],
        "has_thinking": bool(find_events(events, "thinking")),
        "has_text": bool(find_events(events, "text")),
        "has_finish": bool(find_events(events, "finish")),
        "chat_id": cid,
    }


def test_read_file(project_dir: Path, notes: Path) -> dict:
    """2. 文件读取：read_file 读取 notes.txt。"""
    install_fake_llm([
        tool_round("read_file", {"relative_path": "notes.txt"}, "call_read_1"),
        text_round("文件内容读取完成。"),
    ])
    pid = make_project(project_dir)
    cid = make_chat(pid)
    events = stream_send(cid, "读取 notes.txt 文件内容")
    s, r = verify_tool_pair(events, "read_file", call_id="call_read_1")
    assert r["success"] is True, f"read_file 应成功，实际 success={r['success']}"
    assert notes.name in r["result"] or "Phase A" in r["result"], f"读取内容与预期不符: {r['result'][:100]!r}"
    return {
        "tool": "read_file",
        "call_id": s["tool_call_id"],
        "success": r["success"],
        "duration_ms": r["duration_ms"],
        "content_hit": True,
        "chat_id": cid,
    }


def test_git_status(project_dir: Path) -> dict:
    """3. Git 工具：git_status 查看临时仓库状态。"""
    project_dir.mkdir(parents=True, exist_ok=True)
    # 预置 git 仓库：一次提交 + 一个未跟踪文件（保证 status 有输出）
    env = dict(os.environ, GIT_AUTHOR_NAME="PhaseA Test", GIT_AUTHOR_EMAIL="t@t.local",
               GIT_COMMITTER_NAME="PhaseA Test", GIT_COMMITTER_EMAIL="t@t.local")
    subprocess.run(["git", "init", "-q"], cwd=project_dir, check=True, env=env)
    (project_dir / "tracked.txt").write_text("tracked", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=project_dir, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=project_dir, check=True, env=env)
    (project_dir / "untracked.txt").write_text("new", encoding="utf-8")

    install_fake_llm([
        tool_round("git_status", {}, "call_git_1"),
        text_round("Git 状态检查完成。"),
    ])
    pid = make_project(project_dir)
    cid = make_chat(pid)
    events = stream_send(cid, "git 状态看看有什么改动")
    s, r = verify_tool_pair(events, "git_status", call_id="call_git_1")
    assert r["success"] is True, f"git_status 应成功，实际 success={r['success']}, result={r['result'][:120]!r}"
    assert "untracked.txt" in r["result"], f"git_status 输出应包含未跟踪文件: {r['result'][:120]!r}"
    return {
        "tool": "git_status",
        "call_id": s["tool_call_id"],
        "success": r["success"],
        "duration_ms": r["duration_ms"],
        "output_hit": True,
        "chat_id": cid,
    }


def test_write_file(project_dir: Path) -> dict:
    """4. 文件写入：write_file 触发审批，批准后落盘新文件（Phase B-2 风险策略）。"""
    target = project_dir / "output" / "written.txt"
    install_fake_llm([
        tool_round("write_file", {"relative_path": "output/written.txt", "content": "Phase A write test"}, "call_write_1"),
        text_round("文件写入完成。"),
    ])
    pid = make_project(project_dir)
    cid = make_chat(pid)

    events, state = [], {}
    t = threading.Thread(target=stream_send_bg, args=(cid, "把内容写入 output/written.txt 这个文件", events, state), daemon=True)
    t.start()

    aid = wait_pending(state)
    info = approval_registry.get(aid)
    assert info is not None and info["tool"] == "write_file", f"tool 不符: {info}"
    assert info["risk_level"] == "write", f"write_file 风险等级应为 write: {info['risk_level']}"
    assert info["tool_call_id"] == "call_write_1", f"tool_call_id 不符: {info['tool_call_id']}"

    assert approval_registry.resolve(aid, "approve"), "resolve(approve) 失败"
    t.join(timeout=25)
    assert not t.is_alive(), "流未在 25s 内结束"

    starts = find_events(events, "tool_start")
    results = find_events(events, "tool_result")
    apps = find_events(events, "tool_approval")
    assert len(starts) == 1 and len(results) == 1 and len(apps) == 1, (len(starts), len(results), len(apps))
    assert apps[0]["approval_id"] == aid, "tool_approval 的 approval_id 与注册表不符"
    assert apps[0]["command"] == "写入文件: output/written.txt", f"tool_approval command 不符: {apps[0]['command']}"
    assert starts[0]["tool_call_id"] == apps[0]["tool_call_id"] == results[0]["tool_call_id"], "tool_call_id 链路不一致"
    assert events.index(starts[0]) < events.index(apps[0]) < events.index(results[0]), "事件顺序错误"

    r = results[0]
    assert r["success"] is True, f"批准后 write_file 应成功，实际 success={r['success']}, result={r['result'][:120]!r}"
    assert target.exists(), "write_file 未在磁盘创建文件"
    assert target.read_text(encoding="utf-8") == "Phase A write test", "写入内容与预期不符"
    return {
        "tool": "write_file",
        "call_id": starts[0]["tool_call_id"],
        "success": r["success"],
        "duration_ms": r["duration_ms"],
        "file_created": True,
        "approval_gate": True,
        "chat_id": cid,
    }


def verify_persistence(chat_ids: list) -> dict:
    """验证持久化记录同时含新旧字段。"""
    ok = True
    checked = 0
    for cid in chat_ids:
        calls = get_persisted_tool_calls(cid)
        for rec in calls:
            checked += 1
            for key in ("tool", "status", "duration_ms", "tool_call_id", "name", "success", "result", "arguments"):
                if key not in rec:
                    ok = False
                    break
    return {"persisted_records_checked": checked, "all_fields_present": ok}


# ---------------------------------------------------------------------------
# 主流程 + 报告
# ---------------------------------------------------------------------------


def main() -> int:
    from app.core.tool_runtime.approval_policy import set_approval_mode, ApprovalMode
    set_approval_mode(ApprovalMode.SAFE)
    print("=" * 70)
    print("MfkAgent Tool Runtime Phase A 自动化验证")
    print("临时工作目录:", _TEMP_DIR)
    print("=" * 70)

    # 临时项目目录（每个用例独立子目录，git 用例预置仓库）
    project_dir = _TEMP_DIR / "project"
    project_dir.mkdir(exist_ok=True)
    notes = project_dir / "notes.txt"
    notes.write_text("Phase A test notes\nline2", encoding="utf-8")

    results = []
    chat_ids = []
    failures = []

    cases = [
        ("网络诊断工具调用 (run_command)", lambda: test_network_diagnosis(project_dir)),
        ("文件读取工具调用 (read_file)", lambda: test_read_file(project_dir, notes)),
        ("Git 工具调用 (git_status)", lambda: test_git_status(project_dir / "git_repo")),
        ("文件写入工具调用 (write_file)", lambda: test_write_file(project_dir)),
    ]

    for name, fn in cases:
        label = f"[{name}]"
        t0 = time.monotonic()
        try:
            detail = fn()
            chat_ids.append(detail.get("chat_id"))
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

    # 持久化兼容验证
    try:
        persist = verify_persistence(chat_ids)
        results.append({"name": "持久化 Message.tool_calls 新旧字段兼容", "ok": persist["all_fields_present"],
                        "detail": persist, "elapsed_ms": 0})
        print(f"  {'PASS' if persist['all_fields_present'] else 'FAIL'}  持久化兼容 (检查 {persist['persisted_records_checked']} 条记录)")
        if not persist["all_fields_present"]:
            failures.append("持久化记录缺少新/旧字段")
    except Exception as e:  # noqa: BLE001
        results.append({"name": "持久化兼容", "ok": False, "detail": f"异常: {e!r}", "elapsed_ms": 0})
        failures.append(f"持久化兼容: {e!r}")
        print(f"  ERROR 持久化兼容 {e!r}")

    # ---- 生成报告 ----
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (BACKEND_DIR / "tests" / "phase_a_test_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# MfkAgent Tool Runtime Phase A 测试报告\n",
             f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"- 临时工作目录: `{_TEMP_DIR}`",
             f"- 测试模式: FastAPI TestClient + 脚本化 LLM（httpx 层注入），executor / 事件源 / SSE 管道均为生产代码",
             f"- 模型占位: `deepseek-v4-flash`（LLM 响应为脚本化数据，不依赖真实 API）",
             "",
             "## 结果总览\n",
             "| # | 用例 | 结果 | 耗时 |",
             "|---|------|------|------|",
             ]
    for i, r in enumerate(results, 1):
        lines.append(f"| {i} | {r['name']} | {'✅ PASS' if r['ok'] else '❌ FAIL'} | {r['elapsed_ms']}ms |")
    passed = sum(1 for r in results if r["ok"])
    lines.append(f"\n**通过率: {passed}/{len(results)}**\n")

    lines.append("## 事件验证明细\n")
    for i, r in enumerate(results, 1):
        lines.append(f"### {i}. {r['name']}\n")
        d = r["detail"]
        if isinstance(d, dict) and "tool" in d:
            lines.append(f"- tool: `{d['tool']}`")
            lines.append(f"- tool_call_id: `{d['call_id']}`")
            lines.append(f"- success: {d['success']}")
            lines.append(f"- duration_ms: {d['duration_ms']}")
            for k, v in d.items():
                if k not in ("tool", "call_id", "success", "duration_ms"):
                    lines.append(f"- {k}: {v}")
        elif isinstance(d, dict):
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
        lines.append("✅ **全部通过**：tool_start / tool_result / tool_call_id 配对 / duration_ms 均按 Phase A 协议工作。\n")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n报告已生成:", report_path)

    # ---- 清理 ----
    cleanup()
    return 1 if failures else 0


def cleanup():
    """清理临时工作目录（DB / uploads / chroma / 项目数据）。"""
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
    code = main()
    sys.exit(code)
