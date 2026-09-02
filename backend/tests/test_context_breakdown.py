"""上下文分类 token 统计（context_breakdown）单元测试。

验证：
  1. BuiltContext.context_breakdown 字段存在且包含 6 个分类 key
  2. 各分类值为非负整数，总和 > 0
  3. _build_token_usage_event 透出 context_breakdown 到事件 payload
  4. 无 breakdown 时事件中 context_breakdown 为 None（不崩溃）

运行：
  python -m pytest backend/tests/test_context_breakdown.py -v
"""

import asyncio
import io
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

os.environ.setdefault("DATABASE_URL", "sqlite:///./context_breakdown_test.db")

import app.models.agent as _agent_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base, SessionLocal  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from app.models.agent import Agent, Chat, Message, Project  # noqa: E402
from app.core.agent_runtime import get_chat_context_builder, ContextBuildInput  # noqa: E402
from app.core.agent_runtime.agent import AgentRuntime  # noqa: E402


AGENT_ID = "context_breakdown_agent"

_TURN_CONTENT = "帮我读取配置文件并分析代码结构"


def _make_agent(db) -> Agent:
    row = db.query(Agent).filter(Agent.agent_id == AGENT_ID).first()
    if row:
        return row
    row = Agent(
        agent_id=AGENT_ID,
        name="Context Breakdown Test Agent",
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
    row = Project(name="CtxBreakdownProj", path=project_path)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _make_chat(db, project: Project) -> Chat:
    chat = Chat(
        project_id=project.id,
        project_path=project.path,
        agent_id=AGENT_ID,
        title="Context Breakdown Chat",
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


def _build_turn(chat_id: int, content: str):
    """模拟 chat.py 时序：先把本轮 user 消息落库，再构建上下文。"""
    db = SessionLocal()
    try:
        _add_message(db, chat_id, "user", content, 10)
    finally:
        db.close()
    return asyncio.run(get_chat_context_builder().build(
        ContextBuildInput(
            chat_id=chat_id,
            content=content,
            use_tools=True,
            attachments=[],
        )
    ))


# ---------------------------------------------------------------------------
# 1. BuiltContext.context_breakdown 字段与分类 key
# ---------------------------------------------------------------------------

def test_built_context_has_breakdown():
    """BuiltContext 应包含 context_breakdown 字段，且 6 个分类 key 齐全。"""
    tmp_project = tempfile.mkdtemp(prefix="mfk_ctx_breakdown_")
    src_dir = os.path.join(tmp_project, "src")
    os.makedirs(src_dir, exist_ok=True)
    with open(os.path.join(src_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write("def main():\n    pass\n")

    db = SessionLocal()
    try:
        _make_agent(db)
        proj = _make_project(db, tmp_project)
        chat = _make_chat(db, proj)
        chat_id = chat.id
        # 预置历史，规避首轮 greeting 差异
        _add_message(db, chat_id, "user", "先分析一下这个项目", 0)
        _add_message(db, chat_id, "assistant", "好的，我可以帮你分析。", 1)
    finally:
        db.close()

    built = _build_turn(chat_id, _TURN_CONTENT)

    # context_breakdown 字段存在
    assert hasattr(built, "context_breakdown"), "BuiltContext 缺少 context_breakdown 字段"
    assert built.context_breakdown is not None, "context_breakdown 不应为 None（正常场景应统计成功）"

    # 6 个分类 key 齐全
    expected_keys = {"system_prompt", "tools", "memory", "messages", "reminder", "other"}
    actual_keys = set(built.context_breakdown.keys())
    assert expected_keys.issubset(actual_keys), f"缺少分类 key: {expected_keys - actual_keys}"

    # 各值为非负整数
    for key, value in built.context_breakdown.items():
        assert isinstance(value, int), f"{key} 应为 int，实际 {type(value)}"
        assert value >= 0, f"{key} 应为非负数，实际 {value}"

    # system_prompt 和 messages 必然 > 0
    assert built.context_breakdown["system_prompt"] > 0, "system_prompt token 数应 > 0"
    assert built.context_breakdown["messages"] > 0, "messages token 数应 > 0"

    # 总和 > 0
    total = sum(built.context_breakdown.values())
    assert total > 0, "分类 token 总和应 > 0"


# ---------------------------------------------------------------------------
# 2. _build_token_usage_event 透出 context_breakdown
# ---------------------------------------------------------------------------

def test_token_usage_event_includes_context_breakdown():
    """_build_token_usage_event 应将 context_breakdown 透出到事件 payload。"""
    runtime = AgentRuntime()
    breakdown = {
        "system_prompt": 500,
        "tools": 200,
        "memory": 50,
        "messages": 800,
        "reminder": 30,
        "other": 0,
    }
    event = runtime._build_token_usage_event(
        {"prompt_tokens": 100, "completion_tokens": 20},
        "deepseek-chat",
        context_breakdown=breakdown,
    )
    assert event["context_breakdown"] == breakdown, "事件应透出 context_breakdown"
    assert event["cached_tokens"] == 0


def test_token_usage_event_without_breakdown():
    """无 breakdown 时事件中 context_breakdown 为 None，不崩溃。"""
    runtime = AgentRuntime()
    event = runtime._build_token_usage_event(
        {"prompt_tokens": 100, "completion_tokens": 20},
        "deepseek-chat",
    )
    assert event["context_breakdown"] is None


def test_token_usage_event_empty_usage_with_breakdown():
    """空 usage + breakdown 时也应透出。"""
    runtime = AgentRuntime()
    breakdown = {"system_prompt": 10, "tools": 0, "memory": 0, "messages": 0, "reminder": 0, "other": 0}
    event = runtime._build_token_usage_event(None, "deepseek-chat", context_breakdown=breakdown)
    assert event["context_breakdown"] == breakdown
    assert event["prompt_tokens"] == 0


# ---------------------------------------------------------------------------
# 3. BuiltContext.stable_prefix_tokens（稳定前缀 token 数）
# ---------------------------------------------------------------------------

def test_built_context_has_stable_prefix_tokens():
    """BuiltContext 应包含 stable_prefix_tokens 字段，且值 = system_prompt + tools + memory + messages。"""
    tmp_project = tempfile.mkdtemp(prefix="mfk_stable_prefix_")
    src_dir = os.path.join(tmp_project, "src")
    os.makedirs(src_dir, exist_ok=True)
    with open(os.path.join(src_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write("def main():\n    pass\n")

    db = SessionLocal()
    try:
        _make_agent(db)
        proj = _make_project(db, tmp_project)
        chat = _make_chat(db, proj)
        chat_id = chat.id
        # 预置历史
        _add_message(db, chat_id, "user", "先分析一下这个项目", 0)
        _add_message(db, chat_id, "assistant", "好的，我可以帮你分析。", 1)
    finally:
        db.close()

    built = _build_turn(chat_id, _TURN_CONTENT)

    # stable_prefix_tokens 字段存在
    assert hasattr(built, "stable_prefix_tokens"), "BuiltContext 缺少 stable_prefix_tokens 字段"
    assert built.stable_prefix_tokens is not None, "stable_prefix_tokens 不应为 None"
    assert isinstance(built.stable_prefix_tokens, int), "stable_prefix_tokens 应为 int"
    assert built.stable_prefix_tokens > 0, "stable_prefix_tokens 应 > 0（有历史消息时）"

    # stable_prefix_ratio 字段存在且在 0-1 之间
    assert hasattr(built, "stable_prefix_ratio"), "BuiltContext 缺少 stable_prefix_ratio 字段"
    assert built.stable_prefix_ratio is not None, "stable_prefix_ratio 不应为 None"
    assert isinstance(built.stable_prefix_ratio, float), "stable_prefix_ratio 应为 float"
    assert 0.0 <= built.stable_prefix_ratio <= 1.0, "stable_prefix_ratio 应在 0-1 之间"

    # 值应等于 system_prompt + tools + memory + messages（不含 reminder/other）
    if built.context_breakdown:
        expected = (
            built.context_breakdown.get("system_prompt", 0)
            + built.context_breakdown.get("tools", 0)
            + built.context_breakdown.get("memory", 0)
            + built.context_breakdown.get("messages", 0)
        )
        assert built.stable_prefix_tokens == expected, (
            f"stable_prefix_tokens 应等于 system+tools+memory+messages = {expected}, "
            f"实际 {built.stable_prefix_tokens}"
        )
        # ratio 应等于 stable_prefix / total_context
        total_ctx = sum(built.context_breakdown.values())
        if total_ctx > 0:
            expected_ratio = min(1.0, expected / total_ctx)
            assert abs(built.stable_prefix_ratio - expected_ratio) < 0.001, (
                f"stable_prefix_ratio 应等于 {expected_ratio}, 实际 {built.stable_prefix_ratio}"
            )


# ---------------------------------------------------------------------------
# 4. _build_token_usage_event 的 cache_source fallback 逻辑
# ---------------------------------------------------------------------------

def test_token_usage_event_cache_source_api():
    """网关返回真实 cached_tokens > 0 时，cache_source = 'api'，不触发 fallback。"""
    runtime = AgentRuntime()
    event = runtime._build_token_usage_event(
        {"prompt_tokens": 1000, "completion_tokens": 100, "cached_tokens": 800},
        "deepseek-chat",
        stable_prefix_tokens=900,  # 即使有 stable_prefix，也应优先用 API 真实值
    )
    assert event["cached_tokens"] == 800, "应使用 API 返回的真实 cached_tokens"
    assert event["cache_source"] == "api", "cache_source 应为 'api'"


def test_token_usage_event_cache_source_estimated():
    """网关不返回 cached_tokens 但有 stable_prefix_ratio 时，fallback 到比例估算，cache_source = 'estimated'。"""
    runtime = AgentRuntime()
    event = runtime._build_token_usage_event(
        {"prompt_tokens": 1000, "completion_tokens": 100},  # 无 cached_tokens 字段
        "gemini-3.6-flash-high",
        stable_prefix_tokens=850,
        stable_prefix_ratio=0.85,
    )
    assert event["cached_tokens"] == 850, "应按 prompt_tokens × ratio = 1000 × 0.85 = 850 估算"
    assert event["cache_source"] == "estimated", "cache_source 应为 'estimated'"


def test_token_usage_event_cache_source_estimated_ratio_capped():
    """比例估算值不应超过 prompt_tokens（ratio <= 1.0 保证）。"""
    runtime = AgentRuntime()
    event = runtime._build_token_usage_event(
        {"prompt_tokens": 500, "completion_tokens": 100},
        "gemini-3.6-flash-high",
        stable_prefix_ratio=0.9,
    )
    assert event["cached_tokens"] == 450, "500 × 0.9 = 450"
    assert event["cache_source"] == "estimated"


def test_token_usage_event_cache_source_estimated_invalid_ratio():
    """无效 ratio（<=0 或 >1）时不触发 fallback，cache_source = 'none'。"""
    runtime = AgentRuntime()
    event = runtime._build_token_usage_event(
        {"prompt_tokens": 1000, "completion_tokens": 100},
        "some-model",
        stable_prefix_ratio=0.0,
    )
    assert event["cached_tokens"] == 0
    assert event["cache_source"] == "none"


def test_token_usage_event_cache_source_none():
    """网关不返回 cached_tokens 且无 stable_prefix_tokens 时，cache_source = 'none'，cached_tokens = 0。"""
    runtime = AgentRuntime()
    event = runtime._build_token_usage_event(
        {"prompt_tokens": 1000, "completion_tokens": 100},
        "some-model",
        stable_prefix_tokens=None,
    )
    assert event["cached_tokens"] == 0
    assert event["cache_source"] == "none"


def test_token_usage_event_empty_usage_cache_source():
    """空 usage 时 cache_source = 'none'，不崩溃。"""
    runtime = AgentRuntime()
    event = runtime._build_token_usage_event(None, "some-model", stable_prefix_tokens=500)
    assert event["cached_tokens"] == 0
    assert event["cache_source"] == "none"


if __name__ == "__main__":
    test_built_context_has_breakdown()
    test_token_usage_event_includes_context_breakdown()
    test_token_usage_event_without_breakdown()
    test_token_usage_event_empty_usage_with_breakdown()
    test_built_context_has_stable_prefix_tokens()
    test_token_usage_event_cache_source_api()
    test_token_usage_event_cache_source_estimated()
    test_token_usage_event_cache_source_estimated_ratio_capped()
    test_token_usage_event_cache_source_estimated_invalid_ratio()
    test_token_usage_event_cache_source_none()
    test_token_usage_event_empty_usage_cache_source()
    print("test_context_breakdown: all passed")
