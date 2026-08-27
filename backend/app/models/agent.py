from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship, validates
from datetime import datetime
from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    path = Column(String(500), nullable=False)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    is_archived = Column(Boolean, default=False)
    archived_at = Column(DateTime)
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
    summary = Column(String(500), nullable=True)  # 会话语义摘要（Agent 自动生成，Sidebar 展示）
    is_pinned = Column(Boolean, default=False)
    personality_level = Column(Integer, nullable=True)
    model = Column(String(50))
    thinking_mode = Column(String(20), default="none")
    mode = Column(String(20), default="build")
    permission_mode = Column(String(10), default="standard", nullable=False)
    context_files = Column(JSON, default=list)
    # ──── 圆桌模式（Roundtable）────
    # mode="roundtable" 时启用：多 Agent 同会话讨论
    roundtable_config = Column(JSON, default=dict)  # {agent_ids, max_rounds, need_summary, moderator_id, strategy}
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime)
    is_archived = Column(Boolean, default=False)
    archived_at = Column(DateTime)
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
    # Phase H: checkpoint 血缘 — 本次执行从哪个 run 继续（重跑/断点续跑时设置）
    parent_run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=True, index=True)
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
    agent_id = Column(String(50), nullable=True)  # 圆桌模式：标记消息发送者
    content = Column(Text, nullable=False)
    thinking = Column(Text, nullable=True)
    tool_calls  = Column(JSON)
    attachments = Column(JSON)       # Phase 3: 用户消息附件（image/text/binary 元数据）
    timeline    = Column(JSON)
    task_graph  = Column(JSON)  # Phase 1.6: TaskGraph 进度摘要（前端切页后重放用）
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
    # Expression Profile V1：表达风格配置（companion / warm / professional / coder / creative）
    expression_profile = Column(String(50), nullable=True)
    # ──── 子代理标记（Phase SubAgent）────
    # 是否为子代理：主 Agent 可通过 delegate_sub_agent 工具委派任务给它
    is_sub_agent = Column(Boolean, default=False)
    # 子代理允许的工具白名单（JSON 字符串数组）；NULL/空 = 不限制
    allowed_tools = Column(JSON, default=list)
    # 所属主代理 agent_id（可空，仅子代理有意义）
    parent_agent_id = Column(String(50), nullable=True)
    # ──── 美学创作技能绑定（Phase CreativeAgent）────
    # Agent 默认携带的技能 id 列表（JSON 数组，如 ["gc-minimal-zine-poster", "surreal-pop-collage"]）；
    # 运行时由 context_builder 读取并注入 system prompt（②b 层），独立于前端会话级注入。
    # NULL/空列表 = 不绑定任何技能（与旧行为完全兼容）。
    skills = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ──── 防御：JSON 字段写入校验 ────
    # 确保通过 ORM 写入的 skills/capabilities/allowed_tools 始终是列表类型，
    # 防止传入字符串/None 等非列表值导致后续 JSON 序列化异常或读取失败。
    # 注意：此校验仅覆盖 ORM 写入路径，手动编辑数据库或直接 SQL 写入不在此列（由启动自检兜底）。
    @validates("skills", "capabilities", "allowed_tools")
    def _validate_json_list_fields(self, key, value):
        if value is None:
            return []
        if isinstance(value, str):
            # 兼容旧代码可能传入 JSON 字符串的情况，尝试解析
            try:
                import json as _json
                parsed = _json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except (ValueError, TypeError):
                return []
        if not isinstance(value, list):
            return []
        return value


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


class Todo(Base):
    """待办事项表 — 供 Agent manage_todos 工具与前端 /api/todos 使用。

    status 取值：pending（未完成）/ completed（已完成）
    project_id 可选，关联 Project 表，支持项目作用域隔离。
    """
    __tablename__ = "todos"

    id = Column(String(36), primary_key=True, index=True)  # UUID
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    title = Column(String(500), nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending / completed
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
    memory_type = Column(String(50), default="preference")  # preference / fact / workflow / project
    confidence = Column(Float, default=0.8)                 # 提取置信度 0.0 ~ 1.0
    source_chat_id = Column(Integer, nullable=True)         # 记忆来源 Chat ID（自动提取时回填）
    is_active = Column(Boolean, default=True)               # 软删标记（P0-2 衰减剪枝）
    last_accessed_at = Column(DateTime, nullable=True)      # 最近访问时间（P0-2 访问衰减）
    access_count = Column(Integer, default=0)               # 访问次数（P0-2 访问衰减）
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


class ApprovalRequest(Base):
    """Phase 3 T3/T8: 审批请求持久化表 — 记录工具审批请求的生命周期。

    用于：
      - 重启后识别哪些任务在等待审批（V1 不恢复 Future，仅展示状态）
      - UI 展示历史审批记录
      - 审批审计追踪

    status 取值：
      pending   — 等待用户审批
      approve   — 用户批准
      deny      — 用户拒绝
      timeout   — 超时自动拒绝
      cancelled — 会话断开取消
    """
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    approval_id = Column(String(50), unique=True, nullable=False, index=True)
    tool_call_id = Column(String(100), nullable=True, index=True)
    agent_run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=True, index=True)
    tool_name = Column(String(100), nullable=False)
    command = Column(Text, nullable=True)
    risk_level = Column(String(20), nullable=False)
    risk_reason = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class SandboxAuditLog(Base):
    """Phase 4 T1: 本地代码沙箱执行审计表 — 记录每次 execute_command / git clone 等高风险命令的元信息。

    设计原则：
      - 独立新表，不修改任何已有核心表（Chat/Message/ToolCall/Task/AgentRun/RuntimeState/RuntimeEvent）
      - 写入失败 try/except 兜底，绝不阻断主执行链
      - 仅记录元信息（命令、cwd、耗时、退出码、输出大小），不记录 stdout/stderr 内容
        （避免 LLM 输出敏感信息被持久化到审计表）
      - command / cwd 截断存储（TEXT 字段，无长度限制但 LLM 传超长字符串时按 8K 截断）
    """
    __tablename__ = "sandbox_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=True, index=True)
    agent_run_id = Column(Integer, ForeignKey("agent_runs.id"), nullable=True, index=True)
    tool_name = Column(String(100), nullable=False, index=True)
    command = Column(Text, nullable=False)
    cwd = Column(Text, nullable=True)
    duration_ms = Column(Integer, default=0, nullable=False)
    exit_code = Column(Integer, nullable=True)
    output_size = Column(Integer, default=0, nullable=False)
    success = Column(Boolean, default=True, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class SkillDefinition(Base):
    """Phase 4 T3: Skill Prompt Fragment 定义表 — 静态 prompt 片段，仅用于增强模型行为。

    设计原则：
      - Skill 只是数据（name + system_prompt_fragment），不包含 Tool / Code / API / Executor
      - 由 skill_store 加载 enabled 记录，context_builder 拼接到 system prompt
      - 不修改 ToolRegistry / Executor / RiskEngine
    """
    __tablename__ = "skill_definitions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, default="", nullable=False)
    category = Column(String(50), default="general", nullable=False, index=True)
    system_prompt_fragment = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


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
    context_window = Column(Integer, default=256000)  # 上下文窗口大小（token），默认从200K提高至256K兜底
    enabled = Column(Boolean, default=True)
    supports_vision = Column(Boolean, default=False)  # 模型是否支持多模态图片识别
    # 2026-08-11 新增：记录来源，区分"候选池自动同步"与"用户手动创建"。
    # sync：_sync_custom_models 从 enabled_models 自动创建/维护，生命周期由候选池接管；
    # manual：用户在"自定义模型"表单手动创建，sync 逻辑绝不触碰。
    source = Column(String(10), default="manual", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomProvider(Base):
    """自定义端点表：用户动态添加的 OpenAI 兼容供应商，运行时转为 ProviderDef 合并进 PROVIDERS。

    只存元数据（名称 + 默认端点），api_key / api_base 覆盖 / enabled_models / provider_disabled
    全部复用 settings 表现有机制（key 前缀为 custom_<id>），与官方供应商 100% 同构。
    """
    __tablename__ = "custom_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    default_api_base = Column(String(500), nullable=False)
    description = Column(String(500), default="")
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
