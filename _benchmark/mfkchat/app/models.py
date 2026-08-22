"""ORM 模型。"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(64), nullable=False)
    identity = Column(Text, default="")
    capabilities = Column(Text, default="[]")   # JSON 数组
    personality_level = Column(Integer, default=0)
    status = Column(String(16), default="active")

    chats = relationship("Chat", back_populates="agent")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(64), ForeignKey("agents.agent_id"), index=True)
    title = Column(String(255), default="New Chat")
    model = Column(String(64), default="")
    mode = Column(String(16), default="chat")    # chat / build
    project_path = Column(String(512), default="")
    personality_level = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_now)

    agent = relationship("Agent", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False, index=True)
    role = Column(String(16), nullable=False)   # system/user/assistant
    content = Column(Text, default="")
    tokens = Column(Integer, default=0)
    timeline = Column(Text, default="")         # JSON 数组（工具调用记录）
    created_at = Column(DateTime, default=_now)

    chat = relationship("Chat", back_populates="messages")


class MemoryItem(Base):
    __tablename__ = "memory_items"

    id = Column(Integer, primary_key=True, index=True)
    scope = Column(String(16), default="global")  # global / agent / project
    agent_id = Column(String(64), nullable=True)
    content = Column(Text, nullable=False)
    source = Column(String(32), default="manual")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now)