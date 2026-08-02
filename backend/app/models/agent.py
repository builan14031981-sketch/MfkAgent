from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    path = Column(String(500), nullable=False)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    is_pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chats = relationship("Chat", back_populates="project", cascade="all, delete-orphan")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    project_path = Column(String(500))
    agent_id = Column(String(50), default="general")
    title = Column(String(200), default="New Chat")
    is_pinned = Column(Boolean, default=False)
    personality_level = Column(Integer, default=50)
    model = Column(String(50))
    thinking_mode = Column(String(20), default="none")
    mode = Column(String(10), default="build")
    context_files = Column(JSON, default=list)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    tool_calls = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    chat = relationship("Chat", back_populates="messages")


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    avatar = Column(String(500))
    system_prompt = Column(Text)
    identity = Column(Text)
    capabilities = Column(JSON, default=list)
    model = Column(String(50), default="mimo-v2.5-pro")
    temperature = Column(Integer, default=70)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(50), nullable=False)
    user_id = Column(String(100), default="default")
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    key = Column(String(200), nullable=False)
    value = Column(Text, nullable=False)
    memory_type = Column(String(50), default="preference")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MemoryItem(Base):
    """极简记忆表：供 add_memory 工具 / 前端极简记忆 UI 使用。

    scope 取值：global（全局记忆）| project（项目相关记忆）
    """
    __tablename__ = "memory_items"

    id = Column(Integer, primary_key=True, index=True)
    scope = Column(String(20), nullable=False, default="global")
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(200), unique=True, nullable=False)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
