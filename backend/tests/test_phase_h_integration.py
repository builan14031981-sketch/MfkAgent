"""Phase H 集成冒烟骨架：真实后端全链路（TestClient + 临时 SQLite + 脚本化 LLM）。

覆盖：
  1. send/stream 全链路：工具调用（find_files）→ 收尾 → AgentRun 持久化 completed
  2. GET /api/chat/{id}/runs：run 历史 + parent_run_id 血缘
  3. checkpoint：二次 send 带 parent_run_id → 新 run.parent_run_id 正确
  4. 工具目录注册：find_files/edit_file/apply_patch/generate_image 均在工具候选集中

运行：python backend/tests/test_phase_h_integration.py
退出码：0 = 全部通过；1 = 存在失败。
"""
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

if __name__ == "__main__" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_phaseH_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./phase_h_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = "dummy-qwen-key"
os.environ["GOOGLE_API_KEY"] = ""

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models.agent as _agent_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from main import app  # noqa: E402

CLIENT = TestClient(app)

# ---------------------------------------------------------------------------
# 脚本化 LLM（与 test_tool_runtime_phase_a 同手法）
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
            raise AssertionError(f"LLM 轮次溢出：第 {idx} 轮未定义（共 {len(self._rounds)} 轮）")
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
    chunks = [_sse_chunk({"choices": [{"delta": {"content": "开始处理", "reasoning_content": "先查文件"},
                                        "finish_reason": None}]})]
    arg_json = json.dumps(args, ensure_ascii=False)
    chunks.append(_sse_chunk({"choices": [{"delta": {"tool_calls": [
        {"index": 0, "id": call_id, "type": "function", "function": {"name": name, "arguments": ""}}]},
        "finish_reason": None}]}))
    step = max(1, len(arg_json) // 3 or 1)
    for i in range(0, len(arg_json), step):
        chunks.append(_sse_chunk({"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments": arg_json[i:i + step]}}]}, "finish_reason": None}]}))
    chunks.append(_sse_chunk({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}))
    return chunks


def text_round(text):
    chunks = []
    for i in range(0, len(text), 24):
        chunks.append(_sse_chunk({"choices": [{"delta": {"content": text[i:i + 24]}, "finish_reason": None}]}))
    chunks.append(_sse_chunk({"choices": [{"delta": {}, "finish_reason": "stop"}]}))
    return chunks


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

_PROJ = _TEMP_DIR / "HProject"


def make_project() -> int:
    _PROJ.mkdir(exist_ok=True)
    r = CLIENT.post("/api/projects", json={"path": str(_PROJ), "name": "PhaseH-Project"})
    assert r.status_code == 200, f"create project failed: {r.status_code} {r.text}"
    return r.json()["id"]


def make_chat(project_id: int) -> int:
    r = CLIENT.post("/api/chat", json={"project_id": project_id, "agent_id": "coder", "title": "PhaseH"})
    assert r.status_code == 200, f"create chat failed: {r.status_code} {r.text}"
    return r.json()["id"]


def stream_send(chat_id: int, content: str, parent_run_id=None) -> list:
    body = {"content": content, "model": "deepseek-v4-flash", "reasoning_effort": "none"}
    if parent_run_id is not None:
        body["parent_run_id"] = parent_run_id
    events = []
    with CLIENT.stream("POST", f"/api/chat/{chat_id}/send/stream", json=body) as resp:
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


def get_runs(chat_id: int) -> list:
    r = CLIENT.get(f"/api/chat/{chat_id}/runs")
    assert r.status_code == 200, f"runs failed: {r.status_code} {r.text}"
    return r.json()["runs"]


def get_last_message(chat_id: int) -> dict:
    r = CLIENT.get(f"/api/chat/{chat_id}/messages")
    assert r.status_code == 200, f"messages failed: {r.status_code}"
    msgs = r.json() if isinstance(r.json(), list) else r.json().get("messages", [])
    assert msgs, "messages empty"
    return msgs[-1]


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------

FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def test_full_flow_and_runs():
    install_fake_llm([
        tool_round("find_files", {"pattern": "**/*.py"}, "call_h1"),
        text_round("完成，共找到文件若干。"),
    ])
    proj_id = make_project()
    chat_id = make_chat(proj_id)
    events = stream_send(chat_id, "列出项目中的 python 文件")
    types = [e.get("type") for e in events]
    check("send/stream 结束事件", "finish" in types, f"types={types}")
    check("send/stream 工具执行事件", "tool_start" in types and "tool_result" in types, f"types={types}")
    check("消息持久化", "完成" in get_last_message(chat_id).get("content", ""))
    runs = get_runs(chat_id)
    check("runs 返回 1 条 completed", len(runs) == 1 and runs[0]["status"] == "completed",
          f"runs={runs}")
    check("首条 run parent_run_id=None", runs[0]["parent_run_id"] is None)
    return chat_id, runs[0]["id"]


def test_checkpoint_lineage():
    install_fake_llm([
        tool_round("find_files", {"pattern": "**/*.ts"}, "call_h2"),
        text_round("第二轮完成。"),
    ])
    chat_id = make_chat(make_project())
    stream_send(chat_id, "首次执行")
    runs1 = get_runs(chat_id)
    parent_id = runs1[0]["id"]
    stream_send(chat_id, "断点续跑", parent_run_id=parent_id)
    runs2 = get_runs(chat_id)
    check("续跑产生新 run", len(runs2) == 2, f"runs={len(runs2)}")
    check("续跑 run.parent_run_id 血缘正确", runs2[0]["parent_run_id"] == parent_id,
          f"parent={runs2[0]['parent_run_id']} expect={parent_id}")


def test_tool_catalog_phase_h():
    from app.core.tool_runtime.selector import ToolSelector
    from app.core.tool_runtime.permission import PermissionFilter
    from app.core.tool_runtime.risk_engine import TOOL_RISK_POLICY, Verdict
    project_only = ToolSelector()._project_only_tools
    check("project 工具含 find_files/edit_file/apply_patch",
          {"find_files", "edit_file", "apply_patch"} <= set(project_only))
    check("BASE_TOOLS 含 4 个新工具",
          {"find_files", "edit_file", "apply_patch", "generate_image"} <= set(PermissionFilter.BASE_TOOLS))
    check("风险策略：edit_file/apply_patch/generate_image 需审批",
          all(TOOL_RISK_POLICY[t][0] == Verdict.REQUIRE_APPROVAL
              for t in ("edit_file", "apply_patch", "generate_image")))
    check("风险策略：find_files 不在审批清单（只读放行）",
          "find_files" not in TOOL_RISK_POLICY)


if __name__ == "__main__":
    print("=== Phase H 集成冒烟 ===")
    test_full_flow_and_runs()
    test_checkpoint_lineage()
    test_tool_catalog_phase_h()
    print(f"\n结果: {len(FAILURES)} 失败 / 全部完成")
    shutil.rmtree(_TEMP_DIR, ignore_errors=True)
    sys.exit(1 if FAILURES else 0)