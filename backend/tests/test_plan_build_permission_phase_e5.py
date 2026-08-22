"""MfkAgent Plan / Build 权限模型修正 — Phase E5 自动化验证脚本。

背景：修正前 Plan 权限模型存在两处核心缺陷：
  P1. 执行闸 fail-open：evaluate_tool 对未声明工具一律 ALLOW，Plan 模式下
      add_memory（写数据库）等工具可被调用 → 违反「Plan 禁止修改数据库」。
  P2. 权限清单漂移：PermissionFilter._plan_write_tools 与 risk_engine.TOOL_RISK_POLICY
      是两处独立硬编码，新增写入工具易漏注册 → Plan 静默放行。

修正方案（单一事实来源）：
  - READ_ONLY_TOOLS：只读工具白名单（Plan / Build 均放行）
  - TOOL_RISK_POLICY：写入/有副作用工具（Build 按表审批，Plan 一律 deny）
  - evaluate_tool 对未声明工具：Plan fail-closed deny、Build 放行
  - PermissionFilter._plan_write_tools 派生自 PLAN_FORBIDDEN_TOOLS，消除漂移

验证点：
  1. evaluate_tool 三态矩阵（只读 allow / 写入 plan-deny build-ask / 未知 fail-closed）
  2. 命令引擎（只读命令 plan allow / 写入命令 plan deny build ask）
  3. 权限目录（plan 保留只读、移除写入；清单与风险引擎同步）
  4. E2E: plan 只读工具正常执行（read_file）
  5. E2E: plan 禁止写入（write_file 拒绝、不落盘、无审批）
  6. E2E: plan 禁止修改数据库（add_memory 拒绝、不写库）
  7. E2E: build 写入按审批放行（add_memory 直接允许落库）

运行：
  python backend/tests/test_plan_build_permission_phase_e5.py [报告输出路径]

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

# 标准输出以 UTF-8 打印，避免 Windows GBK 控制台报错
if "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# 临时环境隔离：必须在 import main 之前完成（config 在导入时读取路径/DB）
# ---------------------------------------------------------------------------
_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_permE5_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./plan_build_perm_test.db"
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
from app.core.tool_runtime.risk_engine import (  # noqa: E402
    evaluate_tool, command_risk_engine, READ_ONLY_TOOLS,
    TOOL_RISK_POLICY, PLAN_FORBIDDEN_TOOLS, Verdict,
)
from app.core.tool_runtime.permission import PermissionFilter  # noqa: E402
from app.core.tool_runtime.approval import approval_registry  # noqa: E402
from app.models.agent import MemoryItem  # noqa: E402

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
        _sse_chunk({
            "choices": [{
                "delta": {"content": "我先处理一下。", "reasoning_content": "先拿真实数据"},
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
    r = CLIENT.post("/api/projects", json={"path": str(path), "name": "PermE5-Project"})
    assert r.status_code == 200, f"create project failed: {r.status_code} {r.text}"
    return r.json()["id"]


def make_chat(project_id: int, mode: str = "build") -> int:
    body = {"project_id": project_id, "agent_id": "coder", "title": "PermE5", "mode": mode}
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


def find_events(events, etype):
    return [e for e in events if e.get("type") == etype]


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------


def test_evaluate_tool_matrix() -> dict:
    """1. evaluate_tool 三态矩阵。"""
    cases = []

    for tool in ["read_file", "list_files", "search_files", "git_status", "git_diff",
                 "git_log", "web_search", "fetch_url", "github_search"]:
        d_build = evaluate_tool(tool, "build")
        d_plan = evaluate_tool(tool, "plan")
        ok = d_build.verdict == Verdict.ALLOW and d_plan.verdict == Verdict.ALLOW
        cases.append({"case": f"只读 {tool}", "ok": ok, "build": d_build.verdict.value, "plan": d_plan.verdict.value})

    for tool in ["write_file", "git_commit", "git_restore", "git_revert", "delete_file", "rename_file"]:
        d_build = evaluate_tool(tool, "build")
        d_plan = evaluate_tool(tool, "plan")
        # Phase 12: build 模式写入工具 → REQUIRE_APPROVAL 或 HIGH_RISK，plan 一律 DENY
        ok = d_build.verdict in (Verdict.REQUIRE_APPROVAL, Verdict.HIGH_RISK) and d_plan.verdict == Verdict.DENY
        cases.append({"case": f"写入 {tool}", "ok": ok, "build": d_build.verdict.value, "plan": d_plan.verdict.value})

    # add_memory（写数据库）：build 放行 / plan 拒绝
    d_build = evaluate_tool("add_memory", "build")
    d_plan = evaluate_tool("add_memory", "plan")
    ok = d_build.verdict == Verdict.ALLOW and d_plan.verdict == Verdict.DENY
    assert "plan" in d_plan.reason.lower() or "plan" in d_plan.reason
    cases.append({"case": "add_memory(写库)", "ok": ok, "build": d_build.verdict.value, "plan": d_plan.verdict.value})

    # 未声明工具 fail-closed：plan deny / build allow
    for tool in ["future_write_tool", "some_new_registry_tool"]:
        d_build = evaluate_tool(tool, "build")
        d_plan = evaluate_tool(tool, "plan")
        ok = d_build.verdict == Verdict.ALLOW and d_plan.verdict == Verdict.DENY
        cases.append({"case": f"未知 {tool}", "ok": ok, "build": d_build.verdict.value, "plan": d_plan.verdict.value})

    all_ok = all(c["ok"] for c in cases)
    return {"cases": cases, "all_ok": all_ok}


def test_command_engine() -> dict:
    """2. 命令引擎：只读命令 plan 放行 / 写入命令 plan 拒绝。"""
    cases = []

    for cmd in ["pytest", "git status", "git diff", "ipconfig", "systeminfo",
                "python -m py_compile app.py", "npm run test", "reg query HKCU"]:
        d = command_risk_engine.evaluate(cmd, "plan")
        ok = d.verdict == Verdict.ALLOW
        cases.append({"case": f"只读命令 {cmd!r}", "ok": ok, "plan": d.verdict.value})

    for cmd in ["git reset --hard HEAD", "pip install requests", "rm -rf .", "npm install lodash", "taskkill /f /im test.exe"]:
        d_plan = command_risk_engine.evaluate(cmd, "plan")
        d_build = command_risk_engine.evaluate(cmd, "build")
        # Phase 12: build 模式写入命令 → REQUIRE_APPROVAL 或 HIGH_RISK，plan 一律 DENY
        ok = d_plan.verdict == Verdict.DENY and d_build.verdict in (Verdict.REQUIRE_APPROVAL, Verdict.HIGH_RISK)
        cases.append({"case": f"写入命令 {cmd!r}", "ok": ok, "plan": d_plan.verdict.value, "build": d_build.verdict.value})

    all_ok = all(c["ok"] for c in cases)
    return {"cases": cases, "all_ok": all_ok}


def test_permission_catalog_single_source() -> dict:
    """3. 权限目录：plan 保留只读 / 移除写入；清单与风险引擎单一来源。"""
    cases = []

    # 清单同步：PermissionFilter 派生自风险引擎
    ok = set(PermissionFilter._plan_write_tools) == set(PLAN_FORBIDDEN_TOOLS)
    cases.append({"case": "目录过滤与风险引擎清单同步", "ok": ok,
                  "plan_forbidden": sorted(PLAN_FORBIDDEN_TOOLS)})

    from types import SimpleNamespace
    build_proj = SimpleNamespace(mode="build", project_path="/x")
    plan_proj = SimpleNamespace(mode="plan", project_path="/x")

    pf = PermissionFilter()
    names_build = set(pf.resolve(build_proj))
    names_plan = set(pf.resolve(plan_proj))

    ok = names_build == set(PermissionFilter.BASE_TOOLS)
    cases.append({"case": "build+项目 = 基础全集", "ok": ok,
                  "diff": sorted(set(PermissionFilter.BASE_TOOLS) ^ names_build)})

    # plan 保留只读工具（含 git 只读、搜索、网络）
    read_in_plan = set(READ_ONLY_TOOLS) & names_plan
    required_read = {"read_file", "list_files", "search_files", "git_status", "git_diff", "git_log",
                     "run_command", "web_search", "fetch_url", "github_search"}
    ok = required_read <= names_plan
    cases.append({"case": "plan 保留只读工具", "ok": ok, "missing": sorted(required_read - names_plan)})

    # plan 移除写入工具
    write_tools = {"write_file", "git_commit", "git_restore", "git_revert"}
    ok = not (write_tools & names_plan)
    cases.append({"case": "plan 移除写入工具", "ok": ok, "leak": sorted(write_tools & names_plan)})

    all_ok = all(c["ok"] for c in cases)
    return {"cases": cases, "all_ok": all_ok}


def test_plan_read_file_allowed(project_dir: Path) -> dict:
    """4. E2E: plan 只读工具正常执行（read_file）。"""
    target = project_dir / "src" / "app.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("print('hello')\n", encoding="utf-8")

    install_fake_llm([
        tool_round("read_file", {"relative_path": "src/app.py"}, "call_rd_1"),
        text_round("已读取文件。"),
    ])
    pid = make_project(project_dir)
    cid = make_chat(pid, mode="plan")

    events = stream_send(cid, "读一下 src/app.py")
    results = find_events(events, "tool_result")
    apps = find_events(events, "tool_approval")

    ok = len(results) == 1 and results[0]["success"] is True and not apps
    assert ok, f"plan read_file 应自动成功且无审批: {[r['result'][:80] for r in results]} apps={len(apps)}"
    assert "hello" in results[0]["result"], f"read_file 应返回真实内容: {results[0]['result'][:120]!r}"
    return {"tool": "read_file", "plan_allowed": True, "auto_executed": True, "no_approval": True, "chat_id": cid}


def test_plan_write_file_denied(project_dir: Path) -> dict:
    """5. E2E: plan 禁止 write_file：拒绝、不落盘、无审批。"""
    target = project_dir / "blocked" / "x.txt"

    install_fake_llm([
        tool_round("write_file", {"relative_path": "blocked/x.txt", "content": "must not write"}, "call_wf_1"),
        text_round("plan 模式不能写入。"),
    ])
    pid = make_project(project_dir)
    cid = make_chat(pid, mode="plan")

    events = stream_send(cid, "写入 blocked/x.txt")
    results = find_events(events, "tool_result")
    apps = find_events(events, "tool_approval")

    ok = len(results) == 1 and results[0]["success"] is False and not apps
    assert ok, f"plan write_file 应拒绝且无审批: {[r['result'][:80] for r in results]} apps={len(apps)}"
    assert "plan" in results[0]["result"], f"拒绝原因应含 plan: {results[0]['result'][:120]!r}"
    assert not target.exists(), "plan write_file 不应落盘"
    return {"tool": "write_file", "plan_denied": True, "no_approval": True, "no_file": True, "chat_id": cid}


def _count_memories(content_part: str) -> int:
    db = SessionLocal()
    try:
        return db.query(MemoryItem).filter(MemoryItem.content.like(f"%{content_part}%")).count()
    finally:
        db.close()


def test_plan_add_memory_denied(project_dir: Path) -> dict:
    """6. E2E: plan 禁止修改数据库（add_memory 拒绝、不写库）。"""
    install_fake_llm([
        tool_round("add_memory", {"scope": "global", "content": "PLAN-BLOCKED-MEMO"}, "call_am_1"),
        text_round("plan 模式不能写库。"),
    ])
    pid = make_project(project_dir)
    cid = make_chat(pid, mode="plan")

    before = _count_memories("PLAN-BLOCKED-MEMO")
    events = stream_send(cid, "记住一条记忆")
    results = find_events(events, "tool_result")
    apps = find_events(events, "tool_approval")
    after = _count_memories("PLAN-BLOCKED-MEMO")

    ok = len(results) == 1 and results[0]["success"] is False and not apps and after == before
    assert ok, (f"plan add_memory 应拒绝且不写库: {[r['result'][:80] for r in results]} "
                f"apps={len(apps)} before={before} after={after}")
    assert "plan" in results[0]["result"].lower(), f"拒绝原因应含 plan: {results[0]['result'][:120]!r}"
    return {"tool": "add_memory", "plan_denied": True, "no_approval": True, "no_db_write": True, "chat_id": cid}


def test_build_add_memory_allowed(project_dir: Path) -> dict:
    """7. E2E: build 写入允许（add_memory 直接放行落库，不误伤）。"""
    install_fake_llm([
        tool_round("add_memory", {"scope": "global", "content": "BUILD-ALLOWED-MEMO"}, "call_am_2"),
        text_round("记忆已保存。"),
    ])
    pid = make_project(project_dir)
    cid = make_chat(pid, mode="build")

    before = _count_memories("BUILD-ALLOWED-MEMO")
    events = stream_send(cid, "记住一条记忆")
    results = find_events(events, "tool_result")
    after = _count_memories("BUILD-ALLOWED-MEMO")

    ok = len(results) == 1 and results[0]["success"] is True and after == before + 1
    assert ok, f"build add_memory 应放行落库: {[r['result'][:80] for r in results]} before={before} after={after}"
    return {"tool": "add_memory", "build_allowed": True, "db_written": True, "chat_id": cid}


# ---------------------------------------------------------------------------
# 主流程 + 报告
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 70)
    print("MfkAgent Plan / Build 权限模型修正 — Phase E5 自动化验证")
    print("临时工作目录:", _TEMP_DIR)
    print("=" * 70)

    project_dir = _TEMP_DIR / "project"
    project_dir.mkdir(exist_ok=True)

    results = []
    failures = []

    cases = [
        ("evaluate_tool 三态矩阵", test_evaluate_tool_matrix),
        ("命令引擎 Plan 只读约束", test_command_engine),
        ("权限目录 + 单一事实来源", test_permission_catalog_single_source),
        ("E2E: plan 只读 read_file 放行", lambda: test_plan_read_file_allowed(project_dir / "rd")),
        ("E2E: plan write_file 拒绝", lambda: test_plan_write_file_denied(project_dir / "wf")),
        ("E2E: plan add_memory 拒绝(写库)", lambda: test_plan_add_memory_denied(project_dir / "am1")),
        ("E2E: build add_memory 放行", lambda: test_build_add_memory_allowed(project_dir / "am2")),
    ]

    for name, fn in cases:
        label = f"[{name}]"
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
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (BACKEND_DIR / "tests" / "phase_e5_permission_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# MfkAgent Plan / Build 权限模型修正 — Phase E5 测试报告\n",
             f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
             "",
             "## 修正前：Plan 权限实际行为\n",
             "1. 工具目录（PermissionFilter.resolve）：plan 移除写入工具，仍可见 read_file / list_files /",
             "   search_files / run_command / git_status / git_diff / git_log / web_search / fetch_url / github_search。",
             "2. 执行闸（executor.execute_tool）：命令走 CommandRiskEngine（只读白名单 allow，其余 plan deny / build ask），",
             "   非命令工具走 evaluate_tool。",
             "3. 命令引擎：pytest / npm run test / git status / ipconfig 等 plan 自动放行；写命令 plan 拒绝 / build 审批。",
             "4. 写入工具（write_file / git_commit / git_restore / git_revert）：plan 直接拒绝、无审批、不落盘；build 审批。",
             "",
             "## 存在的问题（修正对象）\n",
             "- **P1 执行闸 fail-open（违反 Plan 禁止修改数据库）**：evaluate_tool 对 TOOL_RISK_POLICY 之外的任何工具",
             "  一律 ALLOW（含 plan）。add_memory（写 MemoryItem 库）因此在 plan 可被直接调用写库。",
             "- **P2 权限清单漂移**：PermissionFilter._plan_write_tools 与 TOOL_RISK_POLICY 两处独立硬编码，",
             "  且含不存在的工具名（git_add/git_reset/git_clean/git_push/git_pull）。新增写入工具易漏注册 → plan 静默放行。",
             "- **P3 上下文提示不完整**：plan 模式 system prompt 未明确禁止清单，模型可能尝试写入工具（多耗一轮）。",
             "",
             "## 修正方案（单一事实来源）\n",
             "- risk_engine.py 新增 READ_ONLY_TOOLS（只读白名单）+ TOOL_RISK_POLICY（写入/有副作用）为唯一权限清单。",
             "- evaluate_tool 重写：只读→两模式 ALLOW；写入→build 按表（ASK/ALLOW）、plan DENY；未声明→plan fail-closed DENY、build 放行。",
             "- add_memory 纳入写入分类（build ALLOW / plan DENY）；预留 delete_file / rename_file（注册即被 Plan 拒绝）。",
             "- PermissionFilter._plan_write_tools 派生自 PLAN_FORBIDDEN_TOOLS（消除漂移）。",
             "- policy.py + context_builder.py：plan 模式 prompt 枚举禁止/只读清单。",
             "",
             "## 修改文件\n",
             "| 文件 | 变更 |",
             "|------|------|",
             "| backend/app/core/tool_runtime/risk_engine.py | READ_ONLY_TOOLS / PLAN_FORBIDDEN_TOOLS；evaluate_tool plan fail-closed；add_memory/delete_file/rename_file 注册 |",
             "| backend/app/core/tool_runtime/permission.py | _plan_write_tools 派生自 PLAN_FORBIDDEN_TOOLS |",
             "| backend/app/core/tool_runtime/policy.py | permission_context 枚举禁止/只读清单；build_policy 追加 plan 策略 |",
             "| backend/app/core/agent_runtime/context_builder.py | Chat API prompt 链路追加 plan 只读策略段 |",
             "| backend/tests/test_plan_build_permission_phase_e5.py | 新增测试脚本（新增文件） |",
             "",
             "## 修正要点\n",
             "- 设计原则：Plan 与 Build 的区别不是工具能力区别，而是修改权限区别。",
             "- 单一事实来源：`READ_ONLY_TOOLS`（只读白名单）+ `TOOL_RISK_POLICY`（写入/有副作用）。",
             "- `evaluate_tool` 对未声明工具：Plan 模式 fail-closed 拒绝，Build 模式放行（消除 P1）。",
             "- `PermissionFilter._plan_write_tools` 派生自 `PLAN_FORBIDDEN_TOOLS`，消除清单漂移（P2）。",
             "- `add_memory`（写数据库）纳入写入分类：Plan 拒绝 / Build 放行。",
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
        lines.append("✅ **全部通过**：Plan 只读可用、禁止一切写入（含数据库），Build 写入走审批/放行。\n")
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
    code = main()
    sys.exit(code)
