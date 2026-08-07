from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.api import models, agents, chat, memory, memories, projects, settings as settings_api, backup, knowledge, fonts, tools, mcp, workflows, autotasks, plugins, trash, greetings, devtools, runs
from app.core.config import settings
from app.core.database import engine, Base
from app.core.errors import APIError, api_error_handler, http_exception_handler, validation_exception_handler

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 预置插件 seed（需在 create_all 之后，表存在才能写入）
from app.services.plugin import plugin_manager as _pm
_pm.seed_default_plugins()


def _ensure_schema():
    """轻量迁移：为旧 SQLite 库补充新增列（create_all 不会改已有表）"""
    from sqlalchemy import inspect
    import sqlalchemy as sa

    inspector = inspect(engine)
    if "memories" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("memories")}
        with engine.begin() as conn:
            if "project_id" not in cols:
                conn.execute(sa.text("ALTER TABLE memories ADD COLUMN project_id INTEGER"))
            if "is_active" not in cols:
                conn.execute(sa.text("ALTER TABLE memories ADD COLUMN is_active BOOLEAN DEFAULT 1"))

    if "chats" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("chats")}
        with engine.begin() as conn:
            if "project_path" not in cols:
                conn.execute(sa.text("ALTER TABLE chats ADD COLUMN project_path VARCHAR(500)"))
            if "context_files" not in cols:
                conn.execute(sa.text("ALTER TABLE chats ADD COLUMN context_files JSON"))
            if "is_deleted" not in cols:
                conn.execute(sa.text("ALTER TABLE chats ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
            if "deleted_at" not in cols:
                conn.execute(sa.text("ALTER TABLE chats ADD COLUMN deleted_at DATETIME"))
            if "thinking_mode" not in cols:
                conn.execute(sa.text("ALTER TABLE chats ADD COLUMN thinking_mode VARCHAR(20) DEFAULT 'none'"))
            if "mode" not in cols:
                conn.execute(sa.text("ALTER TABLE chats ADD COLUMN mode VARCHAR(10) DEFAULT 'build'"))

    if "projects" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("projects")}
        with engine.begin() as conn:
            if "is_deleted" not in cols:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
            if "deleted_at" not in cols:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN deleted_at DATETIME"))
            if "is_pinned" not in cols:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN is_pinned BOOLEAN DEFAULT 0"))

    if "messages" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("messages")}
        with engine.begin() as conn:
            if "tool_calls" not in cols:
                conn.execute(sa.text("ALTER TABLE messages ADD COLUMN tool_calls JSON"))
            if "timeline" not in cols:
                conn.execute(sa.text("ALTER TABLE messages ADD COLUMN timeline JSON"))

    if "agents" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("agents")}
        with engine.begin() as conn:
            if "status" not in cols:
                conn.execute(sa.text("ALTER TABLE agents ADD COLUMN status VARCHAR(20) DEFAULT 'active'"))

    if "memory_items" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("memory_items")}
        with engine.begin() as conn:
            if "agent_id" not in cols:
                conn.execute(sa.text("ALTER TABLE memory_items ADD COLUMN agent_id VARCHAR(100)"))
            if "project_id" not in cols:
                conn.execute(sa.text("ALTER TABLE memory_items ADD COLUMN project_id INTEGER"))

    if "agent_runs" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("agent_runs")}
        with engine.begin() as conn:
            if "state" not in cols:
                conn.execute(sa.text("ALTER TABLE agent_runs ADD COLUMN state VARCHAR(50) DEFAULT 'pending'"))


_ensure_schema()


def _purge_mimo_key():
    """幂等迁移：清除已废弃的 MiMo（token 套餐付费，已不再使用）API Key 残留。"""
    from sqlalchemy import text as _text
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        deleted = db.execute(_text("DELETE FROM settings WHERE key='api_key_mimo'"))
        if deleted.rowcount:
            print(f"[migration] 已清除废弃的 api_key_mimo ({deleted.rowcount} 行)")
        db.commit()
    except Exception as e:  # noqa: BLE001
        print(f"[migration] 清理 api_key_mimo 失败（忽略）: {e}")
        db.rollback()
    finally:
        db.close()


_purge_mimo_key()


def _migrate_legacy_memory():
    """一次性迁移：老 Memory 表 user/preference → MemoryItem(agent)，project → MemoryItem(project)。

    幂等：仅当 memory_items 尚无 agent/project 数据时执行；已存在同 scope+目标+content 则跳过。
    """
    from sqlalchemy import inspect as _inspect
    from app.core.database import SessionLocal
    from app.models.agent import Memory, MemoryItem

    inspector = _inspect(engine)
    if "memories" not in inspector.get_table_names():
        return
    db = SessionLocal()
    try:
        has_new = db.query(MemoryItem).filter(MemoryItem.scope.in_(["agent", "project"])).count() > 0
        if has_new:
            return
        legacy = db.query(Memory).filter(Memory.is_active == True).all()
        added = 0
        for m in legacy:
            if m.memory_type in ("user", "preference") and m.agent_id:
                scope, agent_id, project_id = "agent", m.agent_id, None
            elif m.memory_type == "project" and m.project_id:
                scope, agent_id, project_id = "project", None, m.project_id
            else:
                continue
            exists = db.query(MemoryItem).filter(
                MemoryItem.scope == scope,
                MemoryItem.agent_id == agent_id,
                MemoryItem.project_id == project_id,
                MemoryItem.content == m.value,
            ).first()
            if exists:
                continue
            db.add(MemoryItem(scope=scope, agent_id=agent_id, project_id=project_id, content=m.value))
            added += 1
        if added:
            db.commit()
    finally:
        db.close()


_migrate_legacy_memory()

app = FastAPI(
    title="MfkAgent API",
    description="MfkAgent - AI工作助手后端API",
    version="0.1.0",
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 错误处理
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# 注册路由
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(memories.router, prefix="/api/memories", tags=["memories"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])
app.include_router(backup.router, prefix="/api/backup", tags=["backup"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(fonts.router, prefix="/api/fonts", tags=["fonts"])
app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
app.include_router(mcp.router, prefix="/api/mcp", tags=["mcp"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
app.include_router(autotasks.router, prefix="/api/autotasks", tags=["autotasks"])
app.include_router(plugins.router, prefix="/api/plugins", tags=["plugins"])
app.include_router(trash.router, prefix="/api/trash", tags=["trash"])
app.include_router(greetings.router, prefix="/api/system", tags=["system"])
app.include_router(devtools.router, prefix="/api/devtools", tags=["devtools"])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])

@app.get("/")
async def root():
    return {"message": "MfkAgent API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
