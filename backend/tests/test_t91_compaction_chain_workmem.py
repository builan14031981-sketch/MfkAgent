"""T91 压缩增强回归测试：摘要链（previousSummary）+ 压缩后工作记忆恢复。

覆盖（工单 T91，feat/f-t91-compress）：
  1. 摘要链自动检测：messages 头部已有【历史记忆摘要】节点 → 作为旧摘要输入合并
     （缓存友好路径：合并指令追加在摘要指令之后，前缀不变命中缓存）。
  2. 摘要链显式传入：previous_summary 参数（手动 /compress 传 chats.summary 用）。
  3. 工作记忆恢复：从 assistant tool_calls 的 function.arguments.path 提取文件路径，
     以【工作记忆】块注入记忆节点（压缩后追问"刚才改了哪些文件"可答）。
  4. 工作记忆恢复：从 timeline 事件（tool_start/tool_result）的 input.path 提取。
  5. 工作记忆上限：超过 5 个路径时仅保留最近 5 个（去重保序）。
  6. 回滚路径（cache_aware=false）：旧路径下 previous_summary 同样作为输入合并。

运行：pytest backend/tests/test_t91_compaction_chain_workmem.py
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.core.agent_runtime.agent import AgentRuntime, is_cache_aware_compaction_enabled
from app.services.model import model_service

AGENT_MODULE = "app.core.agent_runtime.agent"


def _result(content):
    return SimpleNamespace(content=content)


def _sys(content="系统设定"):
    return {"role": "system", "content": content}


def _mem_node(summary="旧摘要：此前修改过 a.py 与 b.py，后端采用 FastAPI。"):
    return {"role": "user", "content": f"【历史记忆摘要】\n{summary}"}


def _plain(content):
    return {"role": "user", "content": content}


def _tool_call_assistant(tool, path):
    """构造带 tool_calls 的 assistant 消息（模拟自动压缩内存路径的写入/读取调用）。"""
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "call_x",
            "type": "function",
            "function": {"name": tool, "arguments": f'{{"path": "{path}"}}'},
        }],
    }


def _timeline_assistant(paths, tool="write_file"):
    """构造带 timeline 的 assistant 消息（模拟手动 /compress 的 DB 行 timeline）。"""
    return {
        "role": "assistant",
        "content": "执行工具",
        "timeline": [
            {"type": "tool_start", "tool_call_id": "t1", "tool": tool, "input": {"path": p}}
            for p in paths
        ],
    }


def _memory_node_of(out):
    """返回压缩结果中首个非 system 消息（记忆节点）的 content。"""
    for m in out:
        role = m["role"] if isinstance(m, dict) else m.role
        if role == "system":
            continue
        content = m["content"] if isinstance(m, dict) else m.content
        return content
    return None


# ═════════════════════════════════════════════════════════════════════════
# 1. 摘要链：自动检测既有记忆节点 → 合并指令追加（缓存友好路径）
# ═════════════════════════════════════════════════════════════════════════

def test_summary_chain_auto_detects_memory_node():
    messages = [
        _sys(),
        _mem_node("旧摘要：此前修改过 a.py 与 b.py，后端采用 FastAPI。"),
        _plain("新增中间消息-1：又改了 c.py"),
        _plain("新增中间消息-2：决定改用 PostgreSQL"),
        _plain("新增中间消息-3：补充了测试"),
        _plain("新增中间消息-4：修复了一个 bug"),
        _plain("近期消息-1"),
        _plain("近期消息-2"),
        _plain("近期消息-3"),
        _plain("近期消息-4"),
    ]
    mock_call = AsyncMock(side_effect=[_result("合并后的新摘要"), _result("OK")])
    with patch.object(model_service, "call_once", mock_call), \
         patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=True):
        out = asyncio.run(AgentRuntime().compress_history(messages, keep_recent=4))

    first = mock_call.await_args_list[0].args[1]
    instruction = first[-1]["content"]
    # 摘要链：合并指令追加在摘要指令之后（前缀不变）
    assert "除最后4条消息之外" in instruction, "摘要指令应保留（前缀缓存契约）"
    assert "旧摘要" in instruction, "合并指令应引用旧摘要"
    assert "a.py 与 b.py" in instruction, "旧摘要正文应作为输入合并"
    # 前缀 = 完整对话原样（含记忆节点），逐字节命中主循环缓存
    assert len(first) == len(messages) + 1
    # 输出形状不变：system + 记忆节点 + keep_recent
    assert len(out) == 1 + 1 + 4
    mem = _memory_node_of(out)
    assert mem.startswith("【历史记忆摘要】")
    assert "合并后的新摘要" in mem


# ═════════════════════════════════════════════════════════════════════════
# 2. 摘要链：显式 previous_summary 参数（手动 /compress 传 chats.summary 用）
# ═════════════════════════════════════════════════════════════════════════

def test_summary_chain_explicit_previous_summary():
    messages = [_sys()] + [_plain(f"中间消息-{i}：改了 f.py") for i in range(4)] + [
        _plain("近期消息-1"), _plain("近期消息-2"), _plain("近期消息-3"), _plain("近期消息-4"),
    ]
    mock_call = AsyncMock(side_effect=[_result("新摘要"), _result("OK")])
    with patch.object(model_service, "call_once", mock_call), \
         patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=True):
        out = asyncio.run(AgentRuntime().compress_history(
            messages, keep_recent=4, previous_summary="chats.summary 里的旧摘要"
        ))

    first = mock_call.await_args_list[0].args[1]
    instruction = first[-1]["content"]
    assert "chats.summary 里的旧摘要" in instruction, "显式 previous_summary 应作为输入合并"
    assert len(out) == 1 + 1 + 4


# ═════════════════════════════════════════════════════════════════════════
# 3. 工作记忆：从 tool_calls 提取文件路径注入记忆节点
# ═════════════════════════════════════════════════════════════════════════

def test_working_memory_from_tool_calls():
    messages = [
        _sys(),
        _tool_call_assistant("write_file", "a.py"),
        _plain("中间消息：继续开发"),
        _tool_call_assistant("read_file", "b.py"),
        _plain("中间消息：阅读后修改"),
        _tool_call_assistant("replace_in_file", "c.py"),
        _plain("近期消息-1"),
        _plain("近期消息-2"),
        _plain("近期消息-3"),
        _plain("近期消息-4"),
    ]
    mock_call = AsyncMock(side_effect=[_result("摘要"), _result("OK")])
    with patch.object(model_service, "call_once", mock_call), \
         patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=True):
        out = asyncio.run(AgentRuntime().compress_history(messages, keep_recent=4))

    mem = _memory_node_of(out)
    assert mem.startswith("【历史记忆摘要】")
    assert "【工作记忆】" in mem, "记忆节点应注入工作记忆块"
    assert "a.py" in mem and "b.py" in mem and "c.py" in mem, "最近被读/写文件路径应注入"


# ═════════════════════════════════════════════════════════════════════════
# 4. 工作记忆：从 timeline 事件提取（手动 /compress 的 DB 行 timeline）
# ═════════════════════════════════════════════════════════════════════════

def test_working_memory_from_timeline():
    messages = [
        _sys(),
        _timeline_assistant(["d.py", "e.py"]),
        _plain("中间消息-1：timeline 已记录"),
        _plain("中间消息-2：继续开发"),
        _plain("中间消息-3：验证结果"),
        _plain("中间消息-4：收尾"),
        _plain("近期消息-1"),
        _plain("近期消息-2"),
        _plain("近期消息-3"),
        _plain("近期消息-4"),
    ]
    mock_call = AsyncMock(side_effect=[_result("摘要"), _result("OK")])
    with patch.object(model_service, "call_once", mock_call), \
         patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=True):
        out = asyncio.run(AgentRuntime().compress_history(messages, keep_recent=4))

    mem = _memory_node_of(out)
    assert "d.py" in mem and "e.py" in mem, "timeline 事件里的文件路径应注入"


# ═════════════════════════════════════════════════════════════════════════
# 5. 工作记忆上限：超过 5 个仅保留最近 5 个（去重保序）
# ═════════════════════════════════════════════════════════════════════════

def test_working_memory_limit_five():
    messages = [_sys()]
    for i in range(7):
        messages.append(_tool_call_assistant("write_file", f"f{i}.py"))
    messages += [
        _plain("近期消息-1"), _plain("近期消息-2"), _plain("近期消息-3"), _plain("近期消息-4"),
    ]
    mock_call = AsyncMock(side_effect=[_result("摘要"), _result("OK")])
    with patch.object(model_service, "call_once", mock_call), \
         patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=True):
        out = asyncio.run(AgentRuntime().compress_history(messages, keep_recent=4))

    mem = _memory_node_of(out)
    # 仅保留最近 5 个（f2..f6），最早 f0/f1 被丢弃
    assert "f2.py" in mem and "f6.py" in mem
    assert "f0.py" not in mem and "f1.py" not in mem
    for i in range(2, 7):
        assert f"f{i}.py" in mem


# ═════════════════════════════════════════════════════════════════════════
# 6. 回滚路径（cache_aware=false）：previous_summary 同样作为输入合并（旧路径）
# ═════════════════════════════════════════════════════════════════════════

def test_legacy_path_merges_previous_summary():
    messages = [_sys()] + [_plain(f"中间消息-{i}") for i in range(4)] + [
        _plain("近期消息-1"), _plain("近期消息-2"), _plain("近期消息-3"), _plain("近期消息-4"),
    ]
    mock_call = AsyncMock(return_value=_result("旧路径摘要"))
    with patch.object(model_service, "call_once", mock_call), \
         patch(f"{AGENT_MODULE}.is_cache_aware_compaction_enabled", return_value=False):
        out = asyncio.run(AgentRuntime().compress_history(
            messages, keep_recent=4, previous_summary="旧路径旧摘要"
        ))

    assert mock_call.await_count == 1, "旧路径无自批评"
    legacy = mock_call.await_args_list[0].args[1]
    assert len(legacy) == 2
    assert "旧路径旧摘要" in legacy[1]["content"], "旧路径下 previous_summary 应合并进 user prompt"
    mem = _memory_node_of(out)
    assert "旧路径摘要" in mem


# ═════════════════════════════════════════════════════════════════════════
# 7. 开关语义：默认开，仅显式 false/0/off/no 回滚
# ═════════════════════════════════════════════════════════════════════════

def test_switch_default_on_opt_out_semantics():
    from app.core import database as database_module
    from unittest.mock import MagicMock

    cases = [
        (None, True),                              # 无行 → 默认开
        (SimpleNamespace(value=None), True),
        (SimpleNamespace(value="false"), False),   # 显式关 → 回滚旧路径
        (SimpleNamespace(value="0"), False),
        (SimpleNamespace(value="off"), False),
        (SimpleNamespace(value="no"), False),
        (SimpleNamespace(value="garbage"), True),  # 非法值按默认开
        (SimpleNamespace(value="true"), True),
        (SimpleNamespace(value="1"), True),
        (SimpleNamespace(value="on"), True),
        (SimpleNamespace(value="yes"), True),
    ]
    for row, expected in cases:
        fake_db = MagicMock()
        fake_db.query.return_value.filter.return_value.first.return_value = row
        with patch.object(database_module, "SessionLocal", return_value=fake_db):
            got = is_cache_aware_compaction_enabled()
        assert got is expected, f"row={row!r} 期望 {expected}，实际 {got}"


def test_switch_default_on_when_db_unavailable():
    from app.core import database as database_module
    with patch.object(database_module, "SessionLocal", side_effect=RuntimeError("db down")):
        assert is_cache_aware_compaction_enabled() is True, "DB 不可用按默认开"
