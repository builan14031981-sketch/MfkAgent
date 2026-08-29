"""T1 缓存前缀契约 — 前缀稳定性回归测试。

LLM prompt cache 为严格前缀匹配：请求从头到某位置逐字节相同才命中。
本测试验证 prompt_stability_enabled（默认开）下：

  1. system prompt 3 轮对话逐字节一致（逐轮变化的 ⑦⑧⑨⑩ 迁出 system，
     ⑥ 层之后插入 STATIC_SYSTEM_PROMPT_END 边界）
  2. ⑦ intent_hint / ⑧ task_context / ⑨ tool_guidance / ⑩ attachments
     以 <system-reminder> 出现在 BuiltContext.turn_reminder
  3. "system prompt + tools 数组 + 历史 N-1 条消息" 序列化 JSON 的 sha256
     逐轮不变（前缀只允许追加、不允许任何既有字节变化）
  4. DB 历史消息零改动（reminder 只存在于发往 LLM 的消息副本）
  5. 回滚开关：prompt_stability=False 时恢复旧装配路径（⑨ 回到 system）
  6. AgentRuntime._apply_turn_reminder：copy-on-write 包裹最后一条 user 副本
  7. extract_cached_tokens：OpenAI 系 / DeepSeek 两种 usage 字段归一化

场景：项目绑定 + 3 轮任务对话（含工具调用、文本附件、任务图步进）。
所有 3 条消息均含"分析"（_SERIOUS_KEYWORDS），保证 work_mode_text 逐轮一致；
预置 2 条历史消息（interaction_count ≥ 2），规避 V17 首轮 greeting 差异。

运行：
  python -m pytest backend/tests/test_prefix_stability.py -v
"""

import asyncio
import hashlib
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

if "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///./prefix_stability_test.db")

import app.models.agent as _agent_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base, SessionLocal  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from app.models.agent import Agent, Chat, Message, Project  # noqa: E402
from app.core.agent_runtime import get_chat_context_builder, ContextBuildInput  # noqa: E402
from app.core.agent_runtime.agent import AgentRuntime, _apply_turn_reminder  # noqa: E402
from app.core.agent_runtime.context_builder import (  # noqa: E402
    STATIC_SYSTEM_PROMPT_END,
    is_prompt_stability_enabled,
)
from app.services.model import extract_cached_tokens  # noqa: E402


AGENT_ID = "prefix_stability_agent"

_TURN_CONTENTS = [
    "帮我读取配置文件并分析代码结构",
    "继续分析，这里读取补充说明文件作参考",
    "根据分析结果修改配置文件并整理报告",
]

_ATTACHMENT_NOTE = "补充说明：main.py 的入口函数在文件末尾，先看 main() 再看辅助函数。"


# ---------------------------------------------------------------------------
# DB seeding
# ---------------------------------------------------------------------------

def _make_agent(db) -> Agent:
    row = db.query(Agent).filter(Agent.agent_id == AGENT_ID).first()
    if row:
        return row
    row = Agent(
        agent_id=AGENT_ID,
        name="Prefix Stability Test Agent",
        identity="你是负责代码分析任务的测试助手。",
        capabilities=["software_development"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _make_project(db, project_path: str) -> Project:
    row = db.query(Project).filter(Project.path == project_path).first()
    if row:
        return row
    row = Project(name="PrefixStabilityProj", path=project_path)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _make_chat(db, project: Project) -> Chat:
    chat = Chat(
        project_id=project.id,
        project_path=project.path,
        agent_id=AGENT_ID,
        title="Prefix Stability Chat",
        mode="build",
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def _add_message(db, chat_id: int, role: str, content: str, offset_min: int) -> Message:
    msg = Message(
        chat_id=chat_id,
        role=role,
        content=content,
        created_at=datetime.utcnow() + timedelta(minutes=offset_min),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


_CLOCK_OFFSET = {"minute": 10}  # 逐轮递增，保证 created_at 严格单调（历史排序确定性）


def _build_turn(chat_id: int, content: str, attachments=None):
    """模拟 chat.py 时序：先把本轮 user 消息落库，再构建上下文。"""
    db = SessionLocal()
    try:
        _CLOCK_OFFSET["minute"] += 1
        _add_message(db, chat_id, "user", content, _CLOCK_OFFSET["minute"])
    finally:
        db.close()
    return asyncio.run(get_chat_context_builder().build(
        ContextBuildInput(
            chat_id=chat_id,
            content=content,
            use_tools=True,
            attachments=attachments or [],
        )
    ))


# ---------------------------------------------------------------------------
# 请求模拟：model.py 记忆注入 + agent.py reminder 包裹后的最终 LLM payload
# ---------------------------------------------------------------------------

def _simulate_llm_request(built) -> dict:
    """按 model.py / agent.py 的发送前行为模拟最终 payload：

    - 记忆注入：每轮一致追加到 system 消息尾部（纯拷贝）
    - turn_reminder：包裹到本轮最后一条 user 消息副本末尾
    """
    msgs = [{"role": m.role, "content": m.content} for m in built.messages]
    assert msgs and msgs[0]["role"] == "system"
    if built.memory_text:
        msgs[0]["content"] = msgs[0]["content"] + "\n\n" + built.memory_text
    if built.turn_reminder:
        msgs = _apply_turn_reminder(msgs, built.turn_reminder)
    return {
        "system_prompt": msgs[0]["content"],
        "tools": built.context.tools or [],
        "messages": msgs,
    }


def _canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _prefix_digest(req: dict, history_count: int) -> str:
    """sha256(system prompt + tools 数组 + 历史前 history_count 条消息)。

    history_count 取"历史 N-1 条"（N=请求消息总数，含 system 与本轮新增的
    带 reminder 的 user 消息；历史条目即排除这两者后的部分），跨轮比较同一
    长度前缀，验证既有字节零变化（append-only 契约）。
    """
    payload = {
        "system_prompt": req["system_prompt"],
        "tools": req["tools"],
        "history": req["messages"][1:1 + history_count],
    }
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 1-4. 3 轮对话前缀稳定性（核心验收）
# ---------------------------------------------------------------------------

def test_three_turn_prefix_stability():
    """3 轮对话（工具/附件/任务步进）：system+tools+历史N-1 的 sha256 逐轮不变。"""
    tmp_project = tempfile.mkdtemp(prefix="mfk_prefix_stability_")
    src_dir = os.path.join(tmp_project, "src")
    os.makedirs(src_dir, exist_ok=True)
    with open(os.path.join(src_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write("def main():\n    pass\n")
    with open(os.path.join(tmp_project, "notes.txt"), "w", encoding="utf-8") as f:
        f.write(_ATTACHMENT_NOTE)

    db = SessionLocal()
    try:
        _make_agent(db)
        proj = _make_project(db, tmp_project)
        chat = _make_chat(db, proj)
        chat_id = chat.id
        # 预置历史：规避首轮 greeting（first_message=interaction_count==1）
        _add_message(db, chat_id, "user", "先分析一下这个项目的代码风格", 0)
        _add_message(db, chat_id, "assistant", "好的，我可以帮你分析代码结构与风格。", 1)
        seeded = [
            (m.role, m.content)
            for m in db.query(Message).filter(Message.chat_id == chat_id).all()
        ]
    finally:
        db.close()

    # ── 3 轮 build：t2 带文本附件（⑩），t3 任务步进（⑧ goal 变化）──
    built1 = _build_turn(chat_id, _TURN_CONTENTS[0])
    built2 = _build_turn(chat_id, _TURN_CONTENTS[1], attachments=[
        {"kind": "text", "name": "notes.txt", "path": "notes.txt",
         "size": len(_ATTACHMENT_NOTE.encode("utf-8")), "mime": "text/plain"},
    ])
    built3 = _build_turn(chat_id, _TURN_CONTENTS[2])

    req1 = _simulate_llm_request(built1)
    req2 = _simulate_llm_request(built2)
    req3 = _simulate_llm_request(built3)

    # ── 断言 1：system prompt 3 轮逐字节一致 ──
    assert req1["system_prompt"] == req2["system_prompt"] == req3["system_prompt"], (
        "system prompt 逐轮变化，破坏前缀缓存契约"
    )
    # 稳定区边界存在，且位于 prompt 末尾段
    assert STATIC_SYSTEM_PROMPT_END in req1["system_prompt"]
    # 动态层不再出现在 system
    assert "<system-reminder>" not in req1["system_prompt"]
    assert "工具使用指导" not in req1["system_prompt"]
    assert _ATTACHMENT_NOTE not in req1["system_prompt"]

    # ── 断言 2：⑦⑧⑨⑩ 进入 turn_reminder ──
    assert built1.turn_reminder and "<system-reminder>" in built1.turn_reminder
    assert built1.turn_reminder.rstrip().endswith("</system-reminder>")
    assert "工具使用指导" in built1.turn_reminder, "⑨ tool_guidance 应迁入 reminder"
    assert "notes.txt" in built2.turn_reminder and _ATTACHMENT_NOTE in built2.turn_reminder, (
        "⑩ attachments 应迁入 reminder"
    )
    # ⑧ 任务图步进：3 轮 plan 均产出（file_operation ∈ TASK_INTENTS），goal 随消息步进
    assert built1.context.task_context and built2.context.task_context \
        and built3.context.task_context, "任务图应逐轮产出 task_context"
    goals = {
        built1.context.task_context["goal"],
        built2.context.task_context["goal"],
        built3.context.task_context["goal"],
    }
    assert len(goals) == 3, "3 轮 goal 应随消息步进而不同（逐轮变化内容）"

    # ── 断言 3：system+tools+历史N-1 的 sha256 逐轮不变（append-only 前缀）──
    assert _canonical(req1["tools"]) == _canonical(req2["tools"]) == _canonical(req3["tools"]), (
        "tools 数组逐轮变化，前缀在 tools 处断裂"
    )
    n1 = len(req1["messages"]) - 2  # N=消息总数（含 system 与本轮 user），历史 N-1 条
    n2 = len(req2["messages"]) - 2
    d1 = _prefix_digest(req1, n1)
    d2_prefix = _prefix_digest(req2, n1)
    d2 = _prefix_digest(req2, n2)
    d3_prefix = _prefix_digest(req3, n2)
    assert d1 == d2_prefix, "第 2 轮请求的前缀段相对第 1 轮发生了字节变化"
    assert d2 == d3_prefix, "第 3 轮请求的前缀段相对第 2 轮发生了字节变化"
    # 前缀单调增长（逐轮确有追加，而非恒空）
    assert n2 > n1

    # ── 断言 4：DB 历史消息零改动（新增行仅为按 chat.py 时序落库的轮次 user 消息）──
    db = SessionLocal()
    try:
        after = [
            (m.role, m.content)
            for m in db.query(Message).filter(Message.chat_id == chat_id).all()
        ]
    finally:
        db.close()
    assert after[:len(seeded)] == seeded, "已入库的历史消息被改动"
    appended = after[len(seeded):]
    assert sorted(c for _, c in appended) == sorted(_TURN_CONTENTS), (
        "新增行应仅为 3 轮 user 消息原文"
    )
    for _, content in after:
        assert "<system-reminder>" not in content, "reminder 泄漏进 DB 消息"


# ---------------------------------------------------------------------------
# 5. 回滚开关：prompt_stability=False 恢复旧装配路径
# ---------------------------------------------------------------------------

def test_rollback_flag_restores_legacy_assembly():
    """prompt_stability=False：⑨ 回到 system、无边界标记、不产出 reminder。"""
    from types import SimpleNamespace

    builder = get_chat_context_builder()
    chat_view = SimpleNamespace(mode="build", project_path="e:/proj", agent_id="t", project_id=1)

    legacy = builder._assemble_prompt(
        system_prompt="你是测试助手。",
        capabilities=["general_assistance"],
        personality_prompt="",
        effective_chat=chat_view,
        workspace_context="",
        tool_context=None,
        tool_guidance="## 工具使用指导\n- 使用 read_file",
        prompt_stability=False,
    )
    assert "工具使用指导" in legacy, "旧路径下 ⑨ 应拼入 system"
    assert STATIC_SYSTEM_PROMPT_END not in legacy, "旧路径不应插入稳定区边界"

    stable = builder._assemble_prompt(
        system_prompt="你是测试助手。",
        capabilities=["general_assistance"],
        personality_prompt="",
        effective_chat=chat_view,
        workspace_context="",
        tool_context=None,
        tool_guidance="## 工具使用指导\n- 使用 read_file",
        prompt_stability=True,
    )
    assert "工具使用指导" not in stable
    assert STATIC_SYSTEM_PROMPT_END in stable

    reminder = builder._build_turn_reminder(
        effective_chat=chat_view,
        tool_context=None,
        task_context=None,
        attachments=None,
        tool_guidance="## 工具使用指导\n- 使用 read_file",
    )
    assert reminder.startswith("<system-reminder>") and reminder.endswith("</system-reminder>")
    assert builder._build_turn_reminder(chat_view, None, None, None, None) == ""

    # 默认值：settings 无该 key 时默认开启
    assert is_prompt_stability_enabled() is True


# ---------------------------------------------------------------------------
# 6. _apply_turn_reminder：copy-on-write，只动最后一条 user 副本
# ---------------------------------------------------------------------------

def test_apply_turn_reminder_copies_last_user_message():
    original_user = {"role": "user", "content": "原始问题"}
    history_user = {"role": "user", "content": "更早的问题"}
    messages = [
        {"role": "system", "content": "SYS"},
        history_user,
        {"role": "assistant", "content": "答"},
        original_user,
    ]

    out = _apply_turn_reminder(messages, "<system-reminder>R</system-reminder>")

    # 列表就地替换（返回即发送 payload），但原 user dict 对象零改动（copy-on-write）
    assert out is messages
    assert out[-1] is not original_user
    assert original_user["content"] == "原始问题", "原 user dict 被原地改动"
    assert out[-1]["content"] == "原始问题\n\n<system-reminder>R</system-reminder>"
    # 历史 user 消息不受影响
    assert out[1] is history_user
    assert history_user["content"] == "更早的问题"
    assert out[0]["content"] == "SYS"
    # 空 reminder 原样返回
    assert _apply_turn_reminder(messages, "") is messages
    assert _apply_turn_reminder(messages, None) is messages


# ---------------------------------------------------------------------------
# 7. extract_cached_tokens：OpenAI 系 / DeepSeek 字段归一化
# ---------------------------------------------------------------------------

def test_extract_cached_tokens_both_providers():
    assert extract_cached_tokens(None) == 0
    assert extract_cached_tokens({}) == 0
    # OpenAI 系
    assert extract_cached_tokens({
        "prompt_tokens": 100,
        "prompt_tokens_details": {"cached_tokens": 64},
    }) == 64
    # DeepSeek
    assert extract_cached_tokens({"prompt_tokens": 100, "prompt_cache_hit_tokens": 80}) == 80
    # 双字段并存 → 任一非零即取
    assert extract_cached_tokens({
        "prompt_cache_hit_tokens": 80,
        "prompt_tokens_details": {"cached_tokens": 64},
    }) == 80
    # 无缓存字段 / 非法值
    assert extract_cached_tokens({"prompt_tokens": 100}) == 0
    assert extract_cached_tokens({"prompt_cache_hit_tokens": "abc"}) == 0


# ---------------------------------------------------------------------------
# token_usage 事件透出 cached_tokens
# ---------------------------------------------------------------------------

def test_token_usage_event_includes_cached_tokens():
    runtime = AgentRuntime()
    event = runtime._build_token_usage_event(
        {"prompt_tokens": 100, "completion_tokens": 20,
         "prompt_tokens_details": {"cached_tokens": 64}},
        "deepseek-chat",
    )
    assert event["cached_tokens"] == 64
    event2 = runtime._build_token_usage_event(
        {"prompt_tokens": 100, "completion_tokens": 20, "prompt_cache_hit_tokens": 80},
        "deepseek-chat",
    )
    assert event2["cached_tokens"] == 80
    empty = runtime._build_token_usage_event(None, "deepseek-chat")
    assert empty["cached_tokens"] == 0


if __name__ == "__main__":
    test_three_turn_prefix_stability()
    test_rollback_flag_restores_legacy_assembly()
    test_apply_turn_reminder_copies_last_user_message()
    test_extract_cached_tokens_both_providers()
    test_token_usage_event_includes_cached_tokens()
    print("test_prefix_stability: all passed")
