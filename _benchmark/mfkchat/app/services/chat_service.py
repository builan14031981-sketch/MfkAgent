"""对话服务：创建会话、发送消息（组装上下文 + 意图 + 简版回复 + 记忆提取）。"""
import json
from typing import Optional

from app.models import Agent, Chat, Message
from app.database import Session
from app.core import intent as intent_mod, tokens, context as context_mod, memory as memory_mod


class ChatError(Exception):
    pass


def create_chat(db: Session, agent_id: str, title: str, model: str,
                mode: str, project_path: str, personality_level: Optional[int]) -> Chat:
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if agent is None:
        raise ChatError(f"Agent 不存在: {agent_id}")
    chat = Chat(
        agent_id=agent_id, title=title, model=model, mode=mode,
        project_path=project_path,
        personality_level=personality_level if personality_level is not None else agent.personality_level,
    )
    db.add(chat)
    db.flush()
    return chat


def _tally_messages(db: Session, chat_id: int) -> list:
    return (
        db.query(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.id)
        .all()
    )


def _load_agent(db: Session, agent_id: str) -> Optional[Agent]:
    return db.query(Agent).filter(Agent.agent_id == agent_id).first()


def _load_memories(db: Session, agent_id: str, limit: int = 10) -> list:
    return memory_mod.query_memories(db, scope="agent", agent_id=agent_id, limit=limit)


def _build_context_system(db: Session, chat: Chat) -> list:
    agent = _load_agent(db, chat.agent_id)
    identity = agent.identity if agent else ""
    caps = _json_caps(agent.capabilities) if agent else []
    memories = _load_memories(db, chat.agent_id)
    mem_items = [{"scope": "agent", "content": m.content} for m in memories]
    mem_text = context_mod.build_memory_text(mem_items)
    persona_text = context_mod.assemble_personality_text(chat.personality_level or 0)
    system = context_mod.build_system_prompt(
        identity=identity, capabilities=caps,
        memory_text=mem_text, personality_text=persona_text,
    )
    return [{"role": "system", "content": system}]


def send_message(db: Session, chat_id: int, content: str) -> tuple:
    """处理一条用户消息，返回 (user_msg, ai_msg, meta)。"""
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if chat is None:
        raise ChatError("会话不存在")

    user_msg = Message(chat_id=chat_id, role="user", content=content,
                       tokens=tokens.count_tokens(content))
    db.add(user_msg)
    db.flush()

    analyzer = intent_mod.IntentAnalyzer()
    intent_result = analyzer.analyze(content)
    history = _tally_messages(db, chat_id)
    sys_messages = _build_context_system(db, chat)

    max_tokens = 8000
    history_dicts = [{"role": m.role, "content": m.content} for m in history]
    sys_est = tokens.estimate_messages_tokens(sys_messages)
    full = sys_messages + history_dicts
    total_est = tokens.estimate_messages_tokens(full)

    truncated = False
    context_messages = history_dicts
    if total_est > max_tokens:
        budget = max_tokens - sys_est
        context_messages = context_mod.truncate_history(history_dicts, budget)
        truncated = True

    reply = _template_reply(content, intent_result["intent"])
    ai_msg = Message(chat_id=chat_id, role="assistant", content=reply,
                     tokens=tokens.count_tokens(reply))
    db.add(ai_msg)
    db.flush()

    memory_added = 0
    try:
        highlights = memory_mod.extract_highlights(content, reply)
        for h in highlights:
            memory_mod.add_memory(db, "agent", h, agent_id=chat.agent_id, source="auto")
            memory_added += 1
    except Exception:  # noqa: BLE001 — 记忆失败不应阻断对话
        pass

    db.flush()
    meta = {
        "intent": intent_result["intent"],
        "tokens_per_context": tokens.estimate_messages_tokens(full),
        "context_messages": len(context_messages),
        "truncated": truncated,
        "memory_added": memory_added,
    }
    return user_msg, ai_msg, meta


def _template_reply(content: str, intent: str) -> str:
    if intent in ("file_operation", "project_debug", "memory_operation"):
        return f"[任务建议] 检测到 {intent} 意图，需要工具配合完成。消息: {content[:50]}"
    return f"收到: {content[:80]}"


def _json_caps(raw: str) -> list:
    try:
        return json.loads(raw or "[]")
    except ValueError:
        return []