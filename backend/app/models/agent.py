from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Boolean, Float
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
    agent_runs = relationship("AgentRun", back_populates="chat", cascade="all, delete-orphan")


class AgentRun(Base):
    """Agent 执行运行记录 — 为一次 Agent 执行建立生命周期。

    每次 Chat API → AgentRuntime 执行产生一条 AgentRun。

    status 取值（粗粒度生命周期，与 AgentRuntime 执行生命周期对齐）：
      running    — 执行进行中
      completed  — 正常结束（含工具调用闭环）
      failed     — 异常终止
      cancelled  — 流断开 / 会话清理中止

    state 取值（细粒度阶段，见 agent_runtime/states.py RuntimePhase）：
      pending → building_context / routing / llm_call / tool_execution / verifying
              → completing → completed | failed | cancelled
    每次 state 流转写入 RuntimeState 审计表并发射 state_change 事件。

    位置：chat.py 收到请求创建（started_at）；AgentRuntime 结束 / 异常 / 清理时收尾。
    """
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=True, index=True)
    agent_id = Column(String(50), default="general")
    status = Column(String(20), default="running")
    state = Column(String(50), default="pending")
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    chat = relationship("Chat", back_populates="agent_runs")
    events = relationship("RuntimeEvent", back_populates="run", cascade="all, delete-orphan")
    state_history = relationship("RuntimeState", back_populates="run", cascade="all, delete-orphan")


class RuntimeEvent(Base):
    """运行时事件流水 — AgentRun 生命周期内的顺序事件记录（回放 / 审计 / 前端重建用）。

    event_type 取值（注册表见 agent_runtime/states.py RuntimeEventType）：
      text / thinking / tool_start / tool_result / tool_approval / tool_calls /
      verify_result / verification_failed / state_change / finish / error

    sequence 为 run 内自增序号，保证事件顺序（跨行按 (run_id, sequence) 排序即可回放）。
    """
    __tablename__ = "runtime_events"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, default=dict)
    sequence = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("AgentRun", back_populates="events")


class RuntimeState(Base):
    """Runtime 状态流转审计 — AgentRun.state 每次流转的历史记录。

    每行 = 一次阶段进入（含 from_state / to_state / reason），
    按 id 升序即可还原完整状态机流转路径。
    """
    __tablename__ = "runtime_states"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=False, index=True)
    from_state = Column(String(50), default="pending")
    to_state = Column(String(50), nullable=False)
    reason = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("AgentRun", back_populates="state_history")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    thinking = Column(Text, nullable=True)
    tool_calls  = Column(JSON)
    timeline    = Column(JSON)
    created_at  = Column(DateTime, default=datetime.utcnow)

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
    status = Column(String(20), default="active")  # active / legacy / inactive
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


class CustomModel(Base):
    """自定义模型表：models 表（用户自定义 OpenAI 兼容接入，可覆盖任意 provider 端点）。

    provider 取值：PROVIDERS 任一 id，或 "openai"（通用 OpenAI 兼容端点）。
    与内置模型的关系：自定义模型的 model_id 唯一，model_service 启动时与内置模型合并，
    同名 model_id 时自定义覆盖内置（便于用户替换默认端点）。
    """
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    provider = Column(String(50), default="openai")
    model_name = Column(String(200), nullable=False)
    api_base = Column(String(500), nullable=False)
    api_key = Column(String(500), default="")
    max_tokens = Column(Integer, default=4096)
    temperature = Column(Float, default=0.7)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
