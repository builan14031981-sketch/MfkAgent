"""T2 压缩止血 — 手动压缩不再删除任何数据（feat/t2-compaction-safe）。

覆盖：
  T1. /compress 后 messages 行数不变，被压缩消息的 tool_calls/attachments/timeline 仍在，
      chats.summary + chats.compaction_boundary_message_id 正确写入
  T2. 未触发压缩（middle < min_middle）→ 不写边界、不调摘要模型、行数不变
  T3. 压缩后 build() 视图层：边界前折叠为【历史摘要】，边界后原文保留；
      追问"刚才改了哪些文件"所需信息（a.py/b.py）在摘要 payload 中可用
  T4. 回归：无边界老会话 build() 行为与之前完全一致（全量历史）
  T5. 回滚闸 view_compaction_enabled=false：build() 全量历史，/compress 响应不裁剪
      （写入侧仍安全：只记摘要+边界，不删行）
  T6. _maybe_auto_compress 复用同一摘要函数（compress_history）、保持只改内存、
      session_compressed 事件照发、触发阈值未改
  T7. 二次压缩幂等：边界前移、行数只增不减

运行：
  pytest backend/tests/test_t2_compaction_safe.py
  或 python backend/tests/test_t2_compaction_safe.py

退出码：0 = 全部通过；1 = 存在失败。
"""

import asyncio
import io
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

if "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# ──── 临时 DB 环境（先于 app 导入设置，隔离生产库）────
_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_t2_compaction_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./t2_compaction.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import app.models.agent  # noqa: F401, E402
import app.models.persona  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base, SessionLocal  # noqa: E402

_Base.metadata.create_all(bind=_engine)

from app.models.agent import Agent, Chat, Message, Project, Setting  # noqa: E402
from app.core.agent_runtime import get_chat_context_builder, ContextBuildInput  # noqa: E402
from app.core.agent_runtime.agent import (
    AgentRuntime,
    COMPRESS_WATERMARK_THRESHOLD,
    runtime_event_recorder,
)  # noqa: E402
from app.api.chat import CompressRequest, compress_chat  # noqa: E402
from app.services.model import SingleCallResult  # noqa: E402

AGENT_ID = "t2_compaction_agent"
SUMMARY_TEXT = "用户此前修改了 a.py 和 b.py 两个文件，后端采用 FastAPI 架构。"
PRE_BOUNDARY_SECRET = "MIDDLE-SECRET-a.py-修改记录"
POST_BOUNDARY_MARK = "RECENT-WINDOW-保持原文"

results = []
failures = []


def run(name, fn):
    t0 = time.monotonic()
    try:
        fn()
        results.append({"name": name, "ok": True})
        print(f"  PASS  {name}  ({(time.monotonic() - t0) * 1000:.0f}ms)")
    except AssertionError as e:
        results.append({"name": name, "ok": False, "detail": str(e)})
        failures.append(f"{name}: {e}")
        print(f"  FAIL  {name}\n        {e}")
    except Exception as e:
        results.append({"name": name, "ok": False, "detail": repr(e)})
        failures.append(f"{name}: {e!r}")
        print(f"  ERROR {name}\n        {e!r}")


# ──── 夹具：真实 DB + mock 摘要模型（零真实 LLM）────

def _make_agent(db) -> None:
    if db.query(Agent).filter(Agent.agent_id == AGENT_ID).first():
        return
    db.add(Agent(agent_id=AGENT_ID, name="T2 Compaction Agent", identity="测试 Agent"))
    db.commit()


def _seed_chat(db, n_messages: int = 12, with_json_fields: bool = True) -> int:
    """构造 chat + n 条 user/assistant 交替历史（created_at 显式递增保证顺序）。"""
    _make_agent(db)
    chat = Chat(agent_id=AGENT_ID, title="T2-Chat", mode="build")
    db.add(chat)
    db.commit()
    db.refresh(chat)
    base = datetime.utcnow() - timedelta(hours=1)
    for i in range(n_messages):
        role = "user" if i % 2 == 0 else "assistant"
        if i < n_messages - 4:
            content = f"中间消息-{i}：{PRE_BOUNDARY_SECRET}" if i == 3 else f"中间消息-{i}：修改了 a.py 与 b.py"
        else:
            content = f"近期消息-{i}：{POST_BOUNDARY_MARK}"
        msg = Message(
            chat_id=chat.id,
            role=role,
            content=content,
            created_at=base + timedelta(seconds=i),
        )
        if with_json_fields and i == 5:
            # 被压缩段中带 JSON 扩展字段的行 —— 旧实现会永久丢失它们
            msg.tool_calls = [{
                "id": "call_t2_1", "type": "function",
                "function": {"name": "write_file", "arguments": '{"path": "a.py"}'},
            }]
            msg.attachments = [{"name": "note.txt", "type": "text"}]
            msg.timeline = [{"ts": i, "event": "tool_executed"}]
        db.add(msg)
    db.commit()
    return chat.id


def _patched_summary(captured: dict):
    """mock model_service.call_once：返回固定摘要并捕获【首次】摘要调用的 prompt。

    T91 缓存友好默认开 → 压缩会触发 2 次调用（摘要 + 自批评）。断言关心的是摘要调用
    （复用主对话前缀 + 追加摘要指令）的 prompt 形状，故只捕获首次调用；
    自批评调用在其后追加 assistant(v1) + 自批评指令，不在此断言范围。
    """

    async def _fake_call_once(model_id, prompt_messages, **kwargs):
        if "messages" not in captured:
            captured["model_id"] = model_id
            captured["messages"] = prompt_messages
        return SingleCallResult(content=SUMMARY_TEXT)

    return patch("app.services.model.model_service.call_once", new=_fake_call_once)


def _rows(db, chat_id: int):
    return (
        db.query(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )


def _set_flag(db, value: str) -> None:
    db.add(Setting(key="view_compaction_enabled", value=value))
    db.commit()


def _clear_flag(db) -> None:
    db.query(Setting).filter(Setting.key == "view_compaction_enabled").delete()
    db.commit()


# ═════════════════════════════════════════════════════════════════════════
# T1: /compress 不删行、JSON 字段保留、summary + boundary 写入
# ═════════════════════════════════════════════════════════════════════════

def test_compress_preserves_rows_and_json_fields():
    db = SessionLocal()
    try:
        chat_id = _seed_chat(db, n_messages=12)
        before_rows = _rows(db, chat_id)
        assert len(before_rows) == 12
        expected_boundary_id = before_rows[7].id  # 12 - keep_recent(4) - 1
        seeded_json_row = before_rows[5]

        captured: dict = {}
        with _patched_summary(captured):
            resp = asyncio.run(compress_chat(chat_id, CompressRequest(keep_recent=4)))

        assert resp.compressed is True, "应发生压缩"
        assert resp.tokens_before > 0 and resp.tokens_after > 0, "响应应含前后估算 token"
        assert resp.tokens_after < resp.tokens_before, "压缩后估算 token 应下降"

        after_rows = _rows(db, chat_id)
        assert len(after_rows) == len(before_rows), "messages 行数必须不变（不删任何行）"
        for b, a in zip(before_rows, after_rows):
            assert (b.id, b.role, b.content) == (a.id, a.role, a.content), "原始行内容不得被改写"

        json_row = next(m for m in after_rows if m.id == seeded_json_row.id)
        assert json_row.tool_calls == seeded_json_row.tool_calls, "被压缩消息的 tool_calls 必须仍在"
        assert json_row.attachments == seeded_json_row.attachments, "attachments 必须仍在"
        assert json_row.timeline == seeded_json_row.timeline, "timeline 必须仍在"

        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        assert chat.summary == SUMMARY_TEXT, "chats.summary 应写入纯摘要"
        assert chat.compaction_boundary_message_id == expected_boundary_id, "边界应为 middle 段最后一条"

        assert len(resp.messages) == 5, "响应视图 = 摘要节点 + keep_recent 条原文"
        head = resp.messages[0]
        assert head.role == "user" and head.content == f"【历史摘要】\n{SUMMARY_TEXT}"
        assert head.id == 0, "摘要节点为视图合成消息（非 DB 行）"
        # T91 缓存友好默认开：prompt = 完整对话前缀原样 + 追加 1 条摘要指令；
        # 中间段原文位于前缀中（逐字节复用主循环上一轮请求 → 命中 provider 前缀缓存）。
        # 更新依据：旧断言检查最后一条消息含 a.py，新路径下最后一条是摘要指令，
        # 中间段原文在前缀内 —— 改为校验完整 prompt 含中间段原文。
        _prompt_all = "\n".join((m.get("content") or "") for m in captured["messages"])
        assert "a.py" in _prompt_all, "摘要模型应收到中间段原文"
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════════════
# T2: 未触发压缩 → 不写边界、不调模型
# ═════════════════════════════════════════════════════════════════════════

def test_compress_not_triggered_writes_nothing():
    db = SessionLocal()
    try:
        chat_id = _seed_chat(db, n_messages=6)  # middle = 6-4 = 2 < min_middle(4)
        before_rows = _rows(db, chat_id)

        called: dict = {}

        async def _must_not_call(*a, **k):
            called["hit"] = True
            return SingleCallResult(content=SUMMARY_TEXT)

        with patch("app.services.model.model_service.call_once", new=_must_not_call):
            resp = asyncio.run(compress_chat(chat_id, CompressRequest(keep_recent=4)))

        assert not called, "未达阈值不应调用摘要模型"
        assert resp.compressed is False
        assert len(_rows(db, chat_id)) == len(before_rows)
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        assert chat.compaction_boundary_message_id is None, "不应写边界"
        assert chat.summary is None, "不应写摘要"
        assert resp.tokens_before == resp.tokens_after > 0
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════════════
# T3: build() 视图层裁剪 + 追问可从摘要作答
# ═════════════════════════════════════════════════════════════════════════

def test_view_trims_history_and_summary_is_answerable():
    db = SessionLocal()
    try:
        chat_id = _seed_chat(db, n_messages=12)
        captured: dict = {}
        with _patched_summary(captured):
            resp = asyncio.run(compress_chat(chat_id, CompressRequest(keep_recent=4)))
        assert resp.compressed is True
        recent_rows = _rows(db, chat_id)[-4:]

        built = asyncio.run(get_chat_context_builder().build(
            ContextBuildInput(chat_id=chat_id, content="刚才改了哪些文件？", use_tools=False)
        ))

        msgs = built.messages
        assert msgs[0].role == "system"
        assert msgs[1].role == "user" and msgs[1].content == f"【历史摘要】\n{SUMMARY_TEXT}"
        assert "a.py" in msgs[1].content and "b.py" in msgs[1].content, \
            "追问'刚才改了哪些文件'所需信息必须能从摘要节点获得"
        assert len(msgs) == 6, "system + 摘要 + 4 条近期原文"
        for i, row in enumerate(recent_rows, start=2):
            assert msgs[i].role == row.role and msgs[i].content == row.content, \
                "边界之后的消息必须原文保留"
        for m in msgs:
            assert PRE_BOUNDARY_SECRET not in (m.content or ""), "边界前原文不得再进 payload"

        hist = built.context.history
        assert hist[0] == {"role": "user", "content": f"【历史摘要】\n{SUMMARY_TEXT}"}
        assert len(hist) == 5
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════════════
# T4: 回归 — 无边界老会话 build() 全量历史（行为与之前完全一致）
# ═════════════════════════════════════════════════════════════════════════

def test_view_without_boundary_unchanged():
    db = SessionLocal()
    try:
        chat_id = _seed_chat(db, n_messages=12)
        rows = _rows(db, chat_id)

        built = asyncio.run(get_chat_context_builder().build(
            ContextBuildInput(chat_id=chat_id, content="继续", use_tools=False)
        ))

        msgs = built.messages
        assert len(msgs) == 13, "system + 12 条全量历史"
        for i, row in enumerate(rows, start=1):
            assert msgs[i].role == row.role and msgs[i].content == row.content
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════════════
# T5: 回滚闸 view_compaction_enabled=false → 视图全量（写入侧仍安全）
# ═════════════════════════════════════════════════════════════════════════

def test_flag_off_falls_back_to_full_history():
    db = SessionLocal()
    try:
        chat_id = _seed_chat(db, n_messages=12)
        _set_flag(db, "false")
        try:
            captured: dict = {}
            with _patched_summary(captured):
                resp = asyncio.run(compress_chat(chat_id, CompressRequest(keep_recent=4)))

            assert resp.compressed is True, "开关只回滚视图，不回滚安全写入"
            assert len(_rows(db, chat_id)) == 12, "关闭开关也不得删行"
            chat = db.query(Chat).filter(Chat.id == chat_id).first()
            assert chat.compaction_boundary_message_id is not None
            assert all(m.role != "user" or "【历史摘要】" not in (m.content or "")
                       for m in resp.messages), "关闭开关时响应不得裁剪"

            built = asyncio.run(get_chat_context_builder().build(
                ContextBuildInput(chat_id=chat_id, content="继续", use_tools=False)
            ))
            assert len(built.messages) == 13, "关闭开关时 build() 返回全量历史（旧行为）"
        finally:
            _clear_flag(db)
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════════════
# T6: _maybe_auto_compress — 同一摘要函数 / 只改内存 / 事件照发 / 阈值未改
# ═════════════════════════════════════════════════════════════════════════

def test_auto_compress_memory_only_and_event_intact():
    assert COMPRESS_WATERMARK_THRESHOLD == 50.0, "自动压缩触发阈值不得更改"

    rt = AgentRuntime()
    messages = [{"role": "system", "content": "系统设定"}]
    messages += [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"中间消息-{i}：修改了 a.py 与 b.py"}
        for i in range(8)
    ]
    messages += [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"近期消息-{i}"}
        for i in range(4)
    ]
    before_snapshot = [dict(m) for m in messages]

    captured: dict = {}
    events: list = []

    def _spy(run_id, event_type, payload=None):
        events.append((run_id, event_type, payload))

    with _patched_summary(captured), patch.object(runtime_event_recorder, "emit", side_effect=_spy):
        changed = asyncio.run(rt._maybe_auto_compress(
            run_id=None,
            messages=messages,
            usage={"prompt_tokens": 200000},  # 未知模型默认 256K 窗口 → 水位 78% ≥ 50%
            model_id="t2-test-model",
        ))

    assert changed is True
    assert len(messages) == 6, "内存中应为 system + 摘要 + 4 条近期"
    assert messages[1]["content"] == f"【历史记忆摘要】\n{SUMMARY_TEXT}"
    assert [dict(m) for m in messages[-4:]] == before_snapshot[-4:], "近期消息原样保留"
    assert any(
        ev == "session_compressed" and payload.get("mode") == "llm_summary"
        and payload.get("before") == 13 and payload.get("after") == 6
        for _, ev, payload in events
    ), "session_compressed 事件必须照发"
    # 与 /compress 同一个摘要函数：T91 缓存友好默认开 →
    # prompt = 完整对话前缀原样（system + 中间 + 近期）+ 追加 1 条摘要指令。
    # 更新依据：旧断言编码旧路径"独立两条消息 prompt"形状；新路径前缀复用完整对话，
    # 指令为追加的最后一条 user 消息，前缀逐字节命中主循环缓存。
    # 长度对照压缩前快照（_maybe_auto_compress 会原地改写 messages，须用 before_snapshot）。
    assert captured["messages"][0]["role"] == "system"
    assert len(captured["messages"]) == len(before_snapshot) + 1
    assert captured["messages"][-1]["role"] == "user"
    assert "除最后4条消息之外" in captured["messages"][-1]["content"]


# ═════════════════════════════════════════════════════════════════════════
# T7: 二次压缩幂等 — 边界前移，行数只增不减
# ═════════════════════════════════════════════════════════════════════════

def test_recompress_moves_boundary_and_keeps_rows():
    db = SessionLocal()
    try:
        chat_id = _seed_chat(db, n_messages=12)
        captured: dict = {}
        with _patched_summary(captured):
            asyncio.run(compress_chat(chat_id, CompressRequest(keep_recent=4)))

        # 新增 8 条消息后再次压缩
        base = datetime.utcnow()
        for j in range(8):
            db.add(Message(
                chat_id=chat_id,
                role="user" if j % 2 == 0 else "assistant",
                content=f"新增消息-{j}",
                created_at=base + timedelta(seconds=j),
            ))
        db.commit()
        assert len(_rows(db, chat_id)) == 20

        with _patched_summary(captured):
            resp = asyncio.run(compress_chat(chat_id, CompressRequest(keep_recent=4)))
        assert resp.compressed is True

        rows = _rows(db, chat_id)
        assert len(rows) == 20, "二次压缩同样不得删行"
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        assert chat.compaction_boundary_message_id == rows[15].id, "边界应前移到新 middle 末尾"
        assert chat.summary == SUMMARY_TEXT

        built = asyncio.run(get_chat_context_builder().build(
            ContextBuildInput(chat_id=chat_id, content="刚才改了哪些文件？", use_tools=False)
        ))
        assert built.messages[1].content == f"【历史摘要】\n{SUMMARY_TEXT}"
        assert len(built.messages) == 6
    finally:
        db.close()


# ──── 独立运行入口 ────

if __name__ == "__main__":
    print("=" * 72)
    print("T2 压缩止血测试 — feat/t2-compaction-safe")
    print("=" * 72)
    run("T1 /compress 不删行 + JSON 字段保留 + summary/boundary 写入",
        test_compress_preserves_rows_and_json_fields)
    run("T2 未触发压缩 → 不写边界不调模型", test_compress_not_triggered_writes_nothing)
    run("T3 build() 视图层裁剪 + 摘要可答追问", test_view_trims_history_and_summary_is_answerable)
    run("T4 回归：无边界老会话全量历史不变", test_view_without_boundary_unchanged)
    run("T5 回滚闸 view_compaction_enabled=false", test_flag_off_falls_back_to_full_history)
    run("T6 auto 压缩只改内存 + 事件照发 + 阈值未改", test_auto_compress_memory_only_and_event_intact)
    run("T7 二次压缩幂等：边界前移行数不减", test_recompress_moves_boundary_and_keeps_rows)

    passed = sum(1 for r in results if r["ok"])
    print("-" * 72)
    print(f"通过 {passed}/{len(results)}")
    if failures:
        print("失败项：")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    sys.exit(0)
