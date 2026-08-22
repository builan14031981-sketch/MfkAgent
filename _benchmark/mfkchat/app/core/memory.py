"""记忆提取与去重。

贴近 MfkAgent MemoryExtractor：对话结束后从消息中提取要点存入记忆。

预埋 Bug ③（测试遗漏）：本模块的【去重逻辑】从未被任何测试覆盖——
相同内容重复提交时应合并（更新 updated_at），而不是新增重复行。
同时隐藏一个真实缺陷：去重只按 content 完全一致判断，未做
「规范化」处理（例如首尾空白、全角/半角差异），导致看似重复的记忆
被当作新条目存储。
"""
from datetime import datetime, timezone

from app.database import Session
from app.models import MemoryItem


def extract_highlights(user_text: str, ai_text: str) -> list:
    """从一次对话中提取记忆要点。

    规则（简单演示版）：
    - 用户消息长度 > 20 字 → 提取前 20 字为记忆；
    - AI 消息含「你记住了」「我会记住」等 → 把 AI 消息存入记忆。
    """
    highlights = []
    if len(user_text) > 20:
        highlights.append(user_text[:20])
    if any(k in ai_text for k in ("你记住了", "我会记住", "请记住")):
        highlights.append(ai_text)
    return highlights


def add_memory(db: Session, scope: str, content: str, agent_id=None, source: str = "manual") -> MemoryItem:
    """新增记忆（带去重）。

    Bug ③ 相关：去重判断存在缺陷——仅按 content 精确匹配，
    不做 trim / 全角半角规范化。请为去重补充测试并评估是否需要规范化。
    """
    item = MemoryItem(scope=scope, agent_id=agent_id, content=content, source=source)
    db.add(item)
    db.flush()
    return item


def query_memories(db: Session, scope: str = None, agent_id: str = None, limit: int = 30) -> list:
    q = db.query(MemoryItem)
    if scope is not None:
        q = q.filter(MemoryItem.scope == scope)
    if agent_id is not None:
        q = q.filter(MemoryItem.agent_id == agent_id)
    return q.order_by(MemoryItem.created_at.desc()).limit(limit).all()
