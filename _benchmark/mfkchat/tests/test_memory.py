"""记忆模块测试。

注意：本文件刻意【未覆盖去重逻辑】——
预埋 Bug ③（测试遗漏）：core/memory.py 的 add_memory 声称"带去重"，
但实际只做精确 content 匹配，且周围没有针对去重/规范化的用例。
请评估该函数是否存在缺陷，并补充（或修正）相应测试。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core import memory as memory_mod
from app.models import MemoryItem


def test_add_and_query(db):
    memory_mod.add_memory(db, "global", "用户偏好简洁回答", source="manual")
    items = memory_mod.query_memories(db, scope="global")
    assert len(items) == 1
    assert items[0].content == "用户偏好简洁回答"


def test_add_agent_scoped(db):
    memory_mod.add_memory(db, "agent", "该 agent 专用记忆", agent_id="coder")
    items = memory_mod.query_memories(db, scope="agent", agent_id="coder")
    assert len(items) == 1


def test_query_scope_filter(db):
    memory_mod.add_memory(db, "global", "全局记忆")
    memory_mod.add_memory(db, "agent", "agent 记忆", agent_id="coder")
    globals_ = memory_mod.query_memories(db, scope="global")
    assert len(globals_) == 1
    assert globals_[0].content == "全局记忆"


def test_extract_highlights_long_user(db):
    user = "今天聊了很多关于项目架构的事情，我们决定采用微服务" * 2
    hs = memory_mod.extract_highlights(user, "好")
    assert len(hs) >= 1
    assert len(hs[0]) <= 20


def test_extract_highlights_memorize_phrase(db):
    hs = memory_mod.extract_highlights("短消息", "好的我会记住这件事")
    assert "我会记住" in hs[0]


def test_delete_memory(db):
    item = memory_mod.add_memory(db, "global", "待删除")
    db.delete(item)
    db.flush()
    items = memory_mod.query_memories(db, scope="global")
    assert len(items) == 0