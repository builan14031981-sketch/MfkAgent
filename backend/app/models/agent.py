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
    personality_level = Column(Integer, nullable=True)
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
    # 默认人格推荐值：创建 Chat 时的 personality 快照来源。NULL = 该 Agent 默认无人格（不注入 personality prompt）
    default_personality_level = Column(Integer, nullable=True)
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
    """统一记忆表：供 add_memory 工具 / 前端记忆 UI 使用，三作用域隔离。

    scope 取值：
      global  — 全局记忆（所有 Agent、所有项目共享）
      agent   — 当前 Agent 专属（跨项目，绑定 agent_id）
      project — 当前项目专属（项目内所有 Agent 共享，绑定 project_id）
    """
    __tablename__ = "memory_items"

    id = Column(Integer, primary_key=True, index=True)
    scope = Column(String(20), nullable=False, default="global")
    agent_id = Column(String(100), nullable=True)
    project_id = Column(Integer, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PluginItem(Base):
    """持久化插件表：供插件管理面板 / PluginManager 使用。

    status 取值（与 services/plugin.py PluginStatus 对齐）：
      installed / active / inactive / error
    """
    __tablename__ = "plugins"

    id = Column(Integer, primary_key=True, index=True)
    plugin_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    version = Column(String(50), default="1.0.0")
    description = Column(Text, default="")
    author = Column(String(200), default="")
    status = Column(String(20), default="installed")
    config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(200), unique=True, nullable=False)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
