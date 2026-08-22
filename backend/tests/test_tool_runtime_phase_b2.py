"""MfkAgent Tool Runtime Phase B-2 自动化验证脚本。

Phase B-2 架构验证：权限决定工具可见性，模型决定调用。
  1. 权限目录组合（PermissionFilter.resolve）：
     - build + 项目 → 13 个基础工具全集
     - plan + 项目 → 移除写入/有副作用工具
     - 无项目 → 移除项目专有工具
  2. 工具目录与消息内容无关（意图只做软提示，不 gate）：
     - "帮我安装依赖"（旧版 need_tools=False 场景）仍返回完整目录
  3. 工具级风险策略（executor 唯一执行闸）：
     - git_status（只读）→ 自动执行，无审批事件
     - git_commit（写入）→ 触发审批，批准后真实提交
     - write_file（写入）→ build 触发审批 / plan 直接拒绝（无审批、不落盘）
  4. 审批记录与事件链：tool_start → tool_approval → tool_result 顺序 / approval_id 配对

运行：
  python backend/tests/test_tool_runtime_phase_b2.py [报告输出路径]

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
from types import SimpleNamespace

# 标准输出以 UTF-8 打印，避免 Windows GBK 控制台报错
if "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# 临时环境隔离：必须在 import main 之前完成（config 在导入时读取路径/DB）
# ---------------------------------------------------------------------------
_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_phaseB2_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./phase_b2_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# 预创建表结构：main 导入时 model_service 会读 settings 表
import app.models.agent as _agent_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from main import app  # noqa: E402
from app.core.tool_runtime import tool_runtime  # noqa: E402
from app.core.tool_runtime.permission import PermissionFilter  # noqa: E402
from app.core.tool_runtime.approval import approval_registry  # noqa: E402

CLIENT = TestClient(app)

BASE_TOOL_NAMES = set(PermissionFilter.BASE_TOOLS)

# ---------------------------------------------------------------------------
# 脚本化 LLM（与 Phase A 相同的 httpx 注入机制）
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


def _sse_chunk(obj):
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def tool_round(name, args, call_id):
    """构造"工具调用轮"的 SSE 增量块（含思考段 + 参数分段累积）。"""
    chunks = [
        _sse_chunk({
            "choices": [{
                "delta": {"content": "让我先看一下。", "reasoning_content": "需要真实数据支撑回答"},
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


def make_project(path: Path) -> int:
    path.mkdir(parents=True, exist_ok=True)
    r = CLIENT.post("/api/projects", json={"path": str(path), "name": "PhaseB2-Project"})
    assert r.status_code == 200, f"create project failed: {r.status_code} {r.text}"
    return r.json()["id"]


def make_chat(project_id: int, mode: str = "build") -> int:
    body = {"project_id": project_id, "agent_id": "coder", "title": "PhaseB2", "mode": mode}
    r = CLIENT.post("/api/chat", json=body)
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


def stream_send_bg(chat_id: int, content: str, events: list, state: dict):
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
    path.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GIT_AUTHOR_NAME="PhaseB2 Test", GIT_AUTHOR_EMAIL="t@t.local",
               GIT_COMMITTER_NAME="PhaseB2 Test", GIT_COMMITTER_EMAIL="t@t.local")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, env=env)
    subprocess.run(["git", "config", "user.name", "PhaseB2 Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.local"], cwd=path, check=True)
    (path / "tracked.txt").write_text("tracked", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True, env=env)
    (path / "tracked.txt").write_text("tracked v2", encoding="utf-8")  # 留一个未提交改动


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------


def test_permission_catalog() -> dict:
    """1. 权限目录组合。"""
    cases = []

    build_proj = SimpleNamespace(mode="build", project_path="/x")
    plan_proj = SimpleNamespace(mode="plan", project_path="/x")
    build_none = SimpleNamespace(mode="build", project_path=None)
    plan_none = SimpleNamespace(mode="plan", project_path=None)

    pf = PermissionFilter()

    names_build = set(pf.resolve(build_proj))
    names_plan = set(pf.resolve(plan_proj))
    names_build_none = set(pf.resolve(build_none))
    names_plan_none = set(pf.resolve(plan_none))

    assert names_build == BASE_TOOL_NAMES, f"build+项目 应为全集，实际差异: {BASE_TOOL_NAMES ^ names_build}"

    write_tools = {"write_file", "git_commit", "git_restore"}
    assert write_tools <= names_build, "build 模式应包含写入工具"
    assert not (write_tools & names_plan), f"plan 模式应移除写入工具，剩余: {write_tools & names_plan}"
    assert {"git_status", "git_diff", "git_log"} <= names_plan, "plan 模式应保留 git 只读工具"

    project_tools = {"read_file", "write_file", "list_files", "git_status", "search_files"}
    assert not (project_tools & names_build_none), f"无项目应移除项目专有工具: {project_tools & names_build_none}"
    assert {"run_command", "web_search", "fetch_url", "github_search"} <= names_build_none, "无项目应保留通用工具"
    assert names_plan_none <= names_build_none, "plan 无项目目录应为 build 无项目的子集"

    cases.append({"case": "build+项目=全集", "ok": names_build == BASE_TOOL_NAMES})
    cases.append({"case": "plan 移除写入工具", "ok": not (write_tools & names_plan)})
    cases.append({"case": "plan 保留 git 只读", "ok": {"git_status", "git_diff", "git_log"} <= names_plan})
    cases.append({"case": "无项目移除项目工具", "ok": not (project_tools & names_build_none)})
    return {"cases": cases, "all_ok": all(c["ok"] for c in cases)}


def test_runtime_message_independent() -> dict:
    """2. 工具目录与消息无关（意图仅软提示）。"""
    chat = SimpleNamespace(mode="build", project_path="/x", agent_id="coder", project_id=1)

    ctx_install = tool_runtime.process("帮我安装python依赖并配置环境", chat=chat)
    ctx_greet = tool_runtime.process("你好", chat=chat)
    ctx_delete = tool_runtime.process("帮我删除那个没有用的文件", chat=chat)

    for label, ctx in (("安装类消息", ctx_install), ("普通问候", ctx_greet), ("删除类消息", ctx_delete)):
        assert ctx["need_tools"] is True, f"{label} 应可见工具（need_tools=True）"
        schema_names = {t["function"]["name"] for t in ctx["tools"]}
        assert "run_command" in schema_names, f"{label} 目录应包含 run_command: {schema_names}"
        assert "write_file" in schema_names, f"{label} 目录应包含 write_file: {schema_names}"
        assert "web_search" in schema_names, f"{label} 目录应包含 web_search: {schema_names}"

    return {"install_need_tools": ctx_install["need_tools"], "greet_need_tools": ctx_greet["need_tools"],
            "delete_need_tools": ctx_delete["need_tools"], "all_ok": True}


def test_git_status_auto(project_dir: Path) -> dict:
    """3. git_status（只读）自动执行，无审批事件。"""
    repo = project_dir / "git_status"
    setup_git_repo(repo)

    install_fake_llm([
        tool_round("git_status", {}, "call_gs_1"),
        text_round("Git 状态检查完成。"),
    ])
    pid = make_project(repo)
    cid = make_chat(pid, mode="build")

    events = stream_send(cid, "看看项目有什么改动")
    starts = find_events(events, "tool_start")
    results = find_events(events, "tool_result")
    apps = find_events(events, "tool_approval")

    assert len(starts) == 1 and len(results) == 1, (len(starts), len(results))
    assert not apps, "只读工具不应触发审批"
    assert results[0]["success"] is True, f"git_status 应自动执行成功: {results[0]['result'][:120]!r}"
    assert "tracked.txt" in results[0]["result"], f"git_status 输出应包含改动: {results[0]['result'][:120]!r}"
    return {"tool": "git_status", "auto_executed": True, "no_approval": True, "chat_id": cid}


def test_git_commit_approval(project_dir: Path) -> dict:
    """4. git_commit（写入）触发审批，批准后真实提交。"""
    repo = project_dir / "git_commit"
    setup_git_repo(repo)

    install_fake_llm([
        tool_round("git_commit", {"message": "提交改动 v2"}, "call_gc_1"),
        text_round("已提交。"),
        text_round("自查完成，任务结束。"),
    ])
    pid = make_project(repo)
    cid = make_chat(pid, mode="build")

    events, state = [], {}
    t = threading.Thread(target=stream_send_bg, args=(cid, "把改动提交一下", events, state), daemon=True)
    t.start()

    aid = wait_pending(state)
    info = approval_registry.get(aid)
    assert info is not None and info["tool"] == "git_commit", f"tool 不符: {info}"
    assert info["risk_level"] == "write", f"git_commit 风险等级应为 write: {info['risk_level']}"
    assert "提交改动 v2" in info["command"], f"command 描述应含提交信息: {info['command']}"

    assert approval_registry.resolve(aid, "approve"), "resolve(approve) 失败"
    t.join(timeout=25)
    assert not t.is_alive(), "流未在 25s 内结束"

    starts = find_events(events, "tool_start")
    results = find_events(events, "tool_result")
    apps = find_events(events, "tool_approval")
    assert len(starts) == 1 and len(results) == 1 and len(apps) == 1, (len(starts), len(results), len(apps))
    assert apps[0]["approval_id"] == aid, "tool_approval approval_id 不符"
    assert events.index(starts[0]) < events.index(apps[0]) < events.index(results[0]), "事件顺序错误"
    assert results[0]["success"] is True, f"批准后 git_commit 应成功: {results[0]['result'][:120]!r}"
    assert "已提交" in results[0]["result"], f"git_commit 输出不符: {results[0]['result'][:120]!r}"

    # 验证真实提交落库
    log = subprocess.run(["git", "log", "--oneline", "-1"], cwd=repo, capture_output=True,
                         text=True, encoding="utf-8", errors="replace").stdout
    assert "提交改动 v2" in log, f"git log 应包含新提交: {log!r}"
    return {"tool": "git_commit", "approval_gate": True, "committed": True, "chat_id": cid}


def test_write_file_plan_deny(project_dir: Path) -> dict:
    """5. write_file 在 plan 模式直接拒绝：无审批事件、不落盘。"""
    target = project_dir / "blocked" / "x.txt"

    install_fake_llm([
        tool_round("write_file", {"relative_path": "blocked/x.txt", "content": "should not exist"}, "call_wf_1"),
        text_round("plan 模式不能写入。"),
    ])
    pid = make_project(project_dir)
    cid = make_chat(pid, mode="plan")

    events = stream_send(cid, "把内容写入 blocked/x.txt")
    starts = find_events(events, "tool_start")
    results = find_events(events, "tool_result")
    apps = find_events(events, "tool_approval")

    assert len(starts) == 1 and len(results) == 1, (len(starts), len(results))
    assert not apps, "plan 模式不应触发审批"
    assert results[0]["success"] is False, "plan 模式 write_file 应失败"
    assert "plan" in results[0]["result"], f"拒绝原因应说明 plan 模式: {results[0]['result'][:120]!r}"
    assert not target.exists(), "plan 模式 write_file 不应落盘"
    return {"tool": "write_file", "plan_denied": True, "no_approval": True, "no_file": True, "chat_id": cid}


# ---------------------------------------------------------------------------
# 主流程 + 报告
# ---------------------------------------------------------------------------


def main() -> int:
    from app.core.tool_runtime.approval_policy import set_approval_mode, ApprovalMode
    set_approval_mode(ApprovalMode.SAFE)
    print("=" * 70)
    print("MfkAgent Tool Runtime Phase B-2 自动化验证")
    print("临时工作目录:", _TEMP_DIR)
    print("=" * 70)

    project_dir = _TEMP_DIR / "project"
    project_dir.mkdir(exist_ok=True)

    results = []
    chat_ids = []
    failures = []

    cases = [
        ("权限目录组合 (permission.resolve)", test_permission_catalog),
        ("目录与消息无关 (意图软提示)", test_runtime_message_independent),
        ("git_status 只读自动执行", lambda: test_git_status_auto(project_dir / "gs")),
        ("git_commit 触发审批并提交", lambda: test_git_commit_approval(project_dir / "gc")),
        ("write_file plan 直接拒绝", lambda: test_write_file_plan_deny(project_dir / "wf")),
    ]

    for name, fn in cases:
        label = f"[{name}]"
        t0 = time.monotonic()
        try:
            detail = fn()
            ok = detail.pop("all_ok", True)
            chat_ids.append(detail.get("chat_id"))
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

    # 审批注册表残留检查
    try:
        leftover = approval_registry.pending()
        ok = not leftover
        results.append({"name": "审批注册表无残留", "ok": ok, "detail": f"pending={len(leftover)}", "elapsed_ms": 0})
        print(f"  {'PASS' if ok else 'FAIL'}  审批注册表无残留 (pending={len(leftover)})")
        if not ok:
            failures.append("审批注册表存在残留")
    except Exception as e:  # noqa: BLE001
        results.append({"name": "审批注册表无残留", "ok": False, "detail": f"异常: {e!r}", "elapsed_ms": 0})
        failures.append(f"审批注册表: {e!r}")
        print(f"  ERROR 审批注册表 {e!r}")

    # ---- 生成报告 ----
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (BACKEND_DIR / "tests" / "phase_b2_test_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# MfkAgent Tool Runtime Phase B-2 测试报告\n",
             f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"- 临时工作目录: `{_TEMP_DIR}`",
             f"- 测试模式: 单元级 (permission/runtime) + FastAPI TestClient + 脚本化 LLM",
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
        lines.append("✅ **全部通过**：权限决定工具可见性、模型决定调用，写入类工具统一走审批/拒绝。\n")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n报告已生成:", report_path)

    # ---- 清理 ----
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
    code = main()
    sys.exit(code)
