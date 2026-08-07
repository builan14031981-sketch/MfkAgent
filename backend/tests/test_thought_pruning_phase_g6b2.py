"""MfkAgent Thought Pruning — Phase G6-B 第二阶段 单元测试。

覆盖：
  T1.  assistant thinking 字段被移除
  T2.  assistant reasoning 字段被移除
  T3.  <thinking> 标签内容被裁剪
  T4.  最终回答 content 保留
  T5.  tool_calls 保留
  T6.  tool_result（tool 消息）保留
  T7.  原始 message 对象没有变化（数据安全）
  T8.  已有 Runtime 测试全部通过（回归）
  T9.  ContextBuilder 集成：DB 历史 → 新 payload 思考段已裁剪
  T10. ModelMessage 输入 → 类型保持 + 思考段裁剪
  T11. ORM Message 重建保留 tool_calls
  T12. 多个 <thinking> 块全部裁剪
  T13. 无思考段消息 → 透传不变

运行：
  python backend/tests/test_thought_pruning_phase_g6b2.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import os
import sys
import time
import asyncio
import tempfile
import subprocess
from pathlib import Path
from copy import deepcopy

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_phaseG6B2_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./phase_g6b2_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import app.models.agent as _agent_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base, SessionLocal  # noqa: E402
_Base.metadata.create_all(bind=_engine)

# T8 子进程回归用独立 DB：ModelService._init_models 在导入时查询 settings/models 表，
# 若子进程继承父进程的 DATABASE_URL 指向不存在文件会崩。这里预建全量表文件。
import sqlalchemy as _sa  # noqa: E402
_SUB_DB = _TEMP_DIR / "g6b2_subprocess.db"
_sub_engine = _sa.create_engine(f"sqlite:///{_SUB_DB}")
_Base.metadata.create_all(bind=_sub_engine)
_sub_engine.dispose()

from app.models.agent import Chat, Agent, Message  # noqa: E402
from app.core.agent_runtime.pruning import prune_thought_history  # noqa: E402
from app.core.agent_runtime import get_chat_context_builder, ContextBuildInput  # noqa: E402
from app.services.model import Message as ModelMessage  # noqa: E402

results = []
failures = []


def run(name, fn):
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
    except Exception as e:
        results.append({"name": name, "ok": False, "detail": f"异常: {e!r}", "elapsed_ms": 0})
        failures.append(f"{name}: {e!r}")
        print(f"  ERROR {name}\n        {e!r}")


# ──── 辅助函数 ────

def _r(messages) -> list:
    """取 (role, content) 对，兼容 dict / pydantic。"""
    return [(m.get("role"), m.get("content")) if isinstance(m, dict) else (m.role, m.content)
            for m in messages]


def _keys(messages) -> set:
    return {k for m in messages if isinstance(m, dict) for k in m.keys()}


def _make_assistant_with_thinking():
    """带 thinking/reasoning 字段 + <thinking> 块 + tool_calls 的 dict 消息。"""
    return {
        "role": "assistant",
        "content": "<thinking>先读文件再分析</thinking>\n最终结论：需要优化 fetch。",
        "thinking": "先读文件再分析",
        "reasoning": "reasoning trace",
        "tool_calls": [{"id": "call_1", "type": "function",
                        "function": {"name": "read_file", "arguments": "{\"path\": \"a.py\"}"}}],
    }


def _make_db_fixtures(db):
    agent = db.query(Agent).filter(Agent.agent_id == "g6b2_coder").first()
    if not agent:
        agent = Agent(agent_id="g6b2_coder", name="G6B2 Coder",
                      identity="你是一名 Python 研发助手。", capabilities=["software_development"])
        db.add(agent)
        db.commit()
        db.refresh(agent)
    chat = Chat(project_id=None, project_path=None, agent_id=agent.agent_id,
                title="G6B2-Chat", personality_level=50, mode="build")
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat.id


# ═════════════════════════════════════════════════════════════════════════
# T1. assistant thinking 字段被移除
# ═════════════════════════════════════════════════════════════════════════

def _test_t1_thinking_field_removed():
    msg = _make_assistant_with_thinking()
    out = prune_thought_history([msg])
    assert "thinking" not in out[0], "thinking 字段应被移除"
    assert "reasoning" not in out[0], "reasoning 字段应被移除"
    assert out[0]["content"] == "最终结论：需要优化 fetch。", \
        f"content 应仅保留最终回答，实际: {out[0]['content']!r}"
    assert out[0]["role"] == "assistant"
    return {"thinking_removed": "thinking" not in out[0],
            "reasoning_removed": "reasoning" not in out[0],
            "content": out[0]["content"]}


# ═════════════════════════════════════════════════════════════════════════
# T2. assistant reasoning 字段被移除（独立于 thinking）
# ═════════════════════════════════════════════════════════════════════════

def _test_t2_reasoning_field_removed():
    msg = {"role": "assistant", "content": "回答。", "reasoning": "long reasoning trace"}
    out = prune_thought_history([msg])
    assert "reasoning" not in out[0], "reasoning 字段应被移除"
    assert out[0]["content"] == "回答。", "content 应保留"
    assert "thinking" not in out[0]
    return {"reasoning_removed": "reasoning" not in out[0], "content_kept": out[0]["content"] == "回答。"}


# ═════════════════════════════════════════════════════════════════════════
# T3. <thinking> 标签内容被裁剪
# ═════════════════════════════════════════════════════════════════════════

def _test_t3_thinking_tags_stripped():
    msg = {"role": "assistant",
           "content": "<thinking>内部推理步骤1\n步骤2</thinking>\n\n最终回答：完成。"}
    out = prune_thought_history([msg])
    assert "<thinking>" not in out[0]["content"], "thinking 块应被移除"
    assert "内部推理步骤" not in out[0]["content"], "thinking 内部内容应被移除"
    assert "最终回答：完成。" in out[0]["content"], "最终回答应保留"
    return {"stripped": "<thinking>" not in out[0]["content"],
            "answer_kept": "最终回答：完成。" in out[0]["content"]}


# ═════════════════════════════════════════════════════════════════════════
# T4. 最终回答 content 保留（非 thinking 内容不受影响）
# ═════════════════════════════════════════════════════════════════════════

def _test_t4_answer_content_preserved():
    msg = {"role": "assistant", "content": "这是正常的回答，没有思考段。"}
    out = prune_thought_history([msg])
    assert out[0]["content"] == "这是正常的回答，没有思考段。", "无思考段 content 应完全不变"
    assert out[0]["content"] == msg["content"]
    return {"content_unchanged": out[0]["content"] == msg["content"]}


# ═════════════════════════════════════════════════════════════════════════
# T5. tool_calls 保留
# ═════════════════════════════════════════════════════════════════════════

def _test_t5_tool_calls_preserved():
    msg = _make_assistant_with_thinking()
    out = prune_thought_history([msg])
    assert "tool_calls" in out[0], "tool_calls 应保留"
    assert out[0]["tool_calls"][0]["function"]["name"] == "read_file", "tool_calls 内容应完整"
    return {"tool_calls_kept": "tool_calls" in out[0],
            "fn": out[0]["tool_calls"][0]["function"]["name"]}


# ═════════════════════════════════════════════════════════════════════════
# T6. tool_result（tool 消息）保留
# ═════════════════════════════════════════════════════════════════════════

def _test_t6_tool_result_preserved():
    tool_msg = {"role": "tool", "content": "cmd output: SUCCESS", "tool_call_id": "call_1"}
    assistant_msg = _make_assistant_with_thinking()
    out = prune_thought_history([assistant_msg, tool_msg])
    assert len(out) == 2, "消息数量应保持不变"
    assert out[1]["role"] == "tool", "tool 消息应保留"
    assert out[1]["content"] == "cmd output: SUCCESS", "tool 结果内容应保留"
    assert out[1]["tool_call_id"] == "call_1", "tool_call_id 应保留"
    return {"tool_role_kept": out[1]["role"] == "tool",
            "tool_content_kept": out[1]["content"] == "cmd output: SUCCESS"}


# ═════════════════════════════════════════════════════════════════════════
# T7. 原始 message 对象没有变化（数据安全）
# ═════════════════════════════════════════════════════════════════════════

def _test_t7_original_unchanged():
    messages = [_make_assistant_with_thinking(),
                {"role": "user", "content": "你好"},
                {"role": "tool", "content": "out"}]
    snapshot = deepcopy(messages)
    prune_thought_history(messages)
    assert messages == snapshot, "原始消息列表/对象不应被修改"
    assert messages[0]["thinking"] == "先读文件再分析", "原始 thinking 字段应保持"
    assert messages[0]["content"] == snapshot[0]["content"], "原始 content 应保持"
    return {"original_untouched": messages == snapshot}


# ═════════════════════════════════════════════════════════════════════════
# T8. 已有 Runtime 测试全部通过（回归）
# ═════════════════════════════════════════════════════════════════════════

_RUNTIME_SUITES = [
    "test_session_compression_phase_g6b.py",
    "test_runtime_final_audit_phase_e8.py",
    "test_planner_llm_phase_g2b.py",
    "test_runtime_event_phase_e2.py",
    "test_runtime_stabilization_phase_e7.py",
]


def _test_t8_runtime_regression():
    all_ok = True
    details = {}
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{_SUB_DB}"
    env["PYTHONIOENCODING"] = "utf-8"
    for name in _RUNTIME_SUITES:
        p = BACKEND_DIR / "tests" / name
        r = subprocess.run(
            [sys.executable, str(p)],
            cwd=str(BACKEND_DIR),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env,
            timeout=300,
        )
        ok = r.returncode == 0
        all_ok = all_ok and ok
        details[name] = {"exit": r.returncode, "ok": ok}
    assert all_ok, f"存在失败的 Runtime 回归: {details}"
    return {"suites": len(_RUNTIME_SUITES), "all_exit_0": True, "details": details}


# ═════════════════════════════════════════════════════════════════════════
# T9. ContextBuilder 集成：DB 历史 → 新 payload 思考段已裁剪
# ═════════════════════════════════════════════════════════════════════════

def _test_t9_context_builder_integration():
    db = SessionLocal()
    try:
        cid = _make_db_fixtures(db)
        # 历史：assistant 带 thinking 字段 + <thinking> 块 + tool_calls；tool 结果；当前 user 消息
        db.add(Message(chat_id=cid, role="assistant",
                       content="<thinking>先读文件</thinking>\n读取完成。",
                       thinking="先读文件",
                       tool_calls=[{"id": "c1", "type": "function",
                                    "function": {"name": "read_file", "arguments": "{}"}}]))
        db.add(Message(chat_id=cid, role="tool", content="file: a.py"))
        db.add(Message(chat_id=cid, role="user", content="继续分析"))
        db.commit()
    finally:
        db.close()

    built = asyncio.run(get_chat_context_builder().build(
        ContextBuildInput(chat_id=cid, content="继续分析", personality_level=50, use_tools=False)
    ))

    payload = built.messages  # [system, assistant, tool, user]
    roles = [m.role for m in payload]
    assert roles[0] == "system"
    assert "assistant" in roles and "tool" in roles and "user" in roles, f"roles: {roles}"

    # assistant payload 无 thinking 字段 / <thinking> 块
    for m in payload:
        assert not hasattr(m, "thinking"), "payload 消息不应携带 thinking 字段"
        if m.role == "assistant":
            assert "<thinking>" not in m.content, "payload assistant content 不应含 thinking 块"
            assert "读取完成。" in m.content, "最终回答应保留"
    # tool 结果保留
    tool_msg = next(m for m in payload if m.role == "tool")
    assert tool_msg.content == "file: a.py", "tool 结果应保留"
    # 当前 user 消息保留
    assert payload[-1].role == "user" and payload[-1].content == "继续分析"

    # DB 原始消息未被修改
    db2 = SessionLocal()
    try:
        rows = db2.query(Message).filter(Message.chat_id == cid).order_by(Message.id.asc()).all()
        assert any(r.content == "<thinking>先读文件</thinking>\n读取完成。" for r in rows), \
            "DB 原始 content 不应被修改"
        assert any(r.thinking == "先读文件" for r in rows), "DB thinking 字段不应被修改"
        assert any(r.role == "tool" and r.content == "file: a.py" for r in rows), "DB tool 结果应保持"
    finally:
        db2.close()

    return {"payload_roles": roles,
            "thinking_stripped": True,
            "db_untouched": True}


# ═════════════════════════════════════════════════════════════════════════
# T10. ModelMessage 输入 → 类型保持 + 思考段裁剪
# ═════════════════════════════════════════════════════════════════════════

def _test_t10_model_message_preserved():
    mm = ModelMessage(role="assistant", content="<thinking>推理</thinking>\n答案")
    out = prune_thought_history([mm])
    assert isinstance(out[0], ModelMessage), "输出应保持 ModelMessage 类型"
    assert out[0].role == "assistant"
    assert out[0].content == "答案", f"thinking 块应被裁剪，实际: {out[0].content!r}"
    assert mm.content == "<thinking>推理</thinking>\n答案", "原始 ModelMessage 不应被修改"
    return {"type_kept": isinstance(out[0], ModelMessage), "content": out[0].content}


# ═════════════════════════════════════════════════════════════════════════
# T11. ORM Message 重建保留 tool_calls
# ═════════════════════════════════════════════════════════════════════════

def _test_t11_orm_tool_calls_preserved():
    orm = Message(
        role="assistant",
        content="<thinking>步骤</thinking>\n完成",
        thinking="步骤",
        tool_calls=[{"id": "x", "function": {"name": "list_files"}}],
    )
    out = prune_thought_history([orm])
    assert isinstance(out[0], Message), "ORM 输入应重建为 Message"
    assert out[0].role == "assistant"
    assert "<thinking>" not in out[0].content, "ORM content 思考块应裁剪"
    assert "完成" in out[0].content
    assert out[0].tool_calls == [{"id": "x", "function": {"name": "list_files"}}], \
        "ORM tool_calls 应保留"
    assert orm.thinking == "步骤", "原始 ORM thinking 字段应保持"
    return {"orm_rebuilt": isinstance(out[0], Message),
            "tool_calls_kept": out[0].tool_calls == [{"id": "x", "function": {"name": "list_files"}}]}


# ═════════════════════════════════════════════════════════════════════════
# T12. 多个 <thinking> 块全部裁剪
# ═════════════════════════════════════════════════════════════════════════

def _test_t12_multiple_blocks():
    msg = {"role": "assistant",
           "content": "<thinking>第一段</thinking>中间话<thinking>第二段</thinking>最终结论"}
    out = prune_thought_history([msg])
    assert "<thinking>" not in out[0]["content"]
    assert "第一段" not in out[0]["content"] and "第二段" not in out[0]["content"]
    assert "最终结论" in out[0]["content"], "最终结论应保留"
    assert "中间话" in out[0]["content"], "非 thinking 内容应保留"
    return {"all_blocks_stripped": "<thinking>" not in out[0]["content"],
            "final_kept": "最终结论" in out[0]["content"]}


# ═════════════════════════════════════════════════════════════════════════
# T13. 无思考段消息 → 透传不变
# ═════════════════════════════════════════════════════════════════════════

def _test_t13_clean_passthrough():
    messages = [
        {"role": "system", "content": "设定"},
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "普通回复"},
        {"role": "tool", "content": "ok"},
    ]
    out = prune_thought_history(messages)
    assert len(out) == len(messages)
    assert _r(out) == _r(messages), "无思考段消息应完全透传"
    return {"passthrough": _r(out) == _r(messages), "len": len(out)}


# ═════════════════════════════════════════════════════════════════════════
# 执行
# ═════════════════════════════════════════════════════════════════════════

def main() -> int:
    print("=" * 70)
    print("MfkAgent Historical Thought Pruning 单元测试（Phase G6-B 第二阶段）")
    print("=" * 70)

    run("T1  thinking 字段被移除", _test_t1_thinking_field_removed)
    run("T2  reasoning 字段被移除", _test_t2_reasoning_field_removed)
    run("T3  <thinking> 标签裁剪", _test_t3_thinking_tags_stripped)
    run("T4  最终回答 content 保留", _test_t4_answer_content_preserved)
    run("T5  tool_calls 保留", _test_t5_tool_calls_preserved)
    run("T6  tool_result 保留", _test_t6_tool_result_preserved)
    run("T7  原始 message 对象不变", _test_t7_original_unchanged)
    run("T8  已有 Runtime 测试回归", _test_t8_runtime_regression)
    run("T9  ContextBuilder 集成（DB→payload）", _test_t9_context_builder_integration)
    run("T10 ModelMessage 类型保持 + 裁剪", _test_t10_model_message_preserved)
    run("T11 ORM tool_calls 保留", _test_t11_orm_tool_calls_preserved)
    run("T12 多个 <thinking> 块裁剪", _test_t12_multiple_blocks)
    run("T13 无思考段 → 透传", _test_t13_clean_passthrough)

    report_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (
        BACKEND_DIR / "tests" / "phase_g6b2_thought_pruning_report.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# MfkAgent Historical Thought Pruning 测试报告（Phase G6-B 第二阶段）\n",
        f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        "## 结果总览\n",
        "| # | 用例 | 结果 | 耗时 |",
        "|---|------|------|------|",
    ]
    for i, r in enumerate(results, 1):
        lines.append(
            f"| {i} | {r['name']} | {'✅ PASS' if r['ok'] else '❌ FAIL'} | {r['elapsed_ms']}ms |"
        )
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
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n报告已生成:", report_path)

    print(f"结果: {passed}/{len(results)} 通过")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
