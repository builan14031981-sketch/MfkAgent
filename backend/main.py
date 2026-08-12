from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
# 注意：app.api 的 import 已下移到 _ensure_schema() 之后（见下方）。
# 原因：app.api.models 导入时 model_service 会立即查询 models 表（含新增列），
# 必须先完成轻量迁移，否则旧库会报 "no such column"。
from app.core.config import settings
from app.core.database import engine, Base
from app.core.errors import APIError, api_error_handler, http_exception_handler, validation_exception_handler
from app.models.persona import PersonaTemplate, ExpressionKnowledge

logger = logging.getLogger(__name__)

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 预置插件 seed（需在 create_all 之后，表存在才能写入）
from app.services.plugin import plugin_manager as _pm
_pm.seed_default_plugins()

# Persona System V1 seed（ExpressionKnowledge + PersonaTemplate）
from seed_persona import seed_all as _seed_persona
_seed_persona()


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
            if "task_graph" not in cols:
                conn.execute(sa.text("ALTER TABLE messages ADD COLUMN task_graph JSON"))

    if "agents" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("agents")}
        with engine.begin() as conn:
            if "status" not in cols:
                conn.execute(sa.text("ALTER TABLE agents ADD COLUMN status VARCHAR(20) DEFAULT 'active'"))
            if "expression_profile" not in cols:
                conn.execute(sa.text("ALTER TABLE agents ADD COLUMN expression_profile VARCHAR(50)"))

    if "memory_items" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("memory_items")}
        with engine.begin() as conn:
            if "agent_id" not in cols:
                conn.execute(sa.text("ALTER TABLE memory_items ADD COLUMN agent_id VARCHAR(100)"))
            if "project_id" not in cols:
                conn.execute(sa.text("ALTER TABLE memory_items ADD COLUMN project_id INTEGER"))
            if "memory_type" not in cols:
                conn.execute(sa.text("ALTER TABLE memory_items ADD COLUMN memory_type VARCHAR(50) DEFAULT 'preference'"))
            if "confidence" not in cols:
                conn.execute(sa.text("ALTER TABLE memory_items ADD COLUMN confidence FLOAT DEFAULT 0.8"))
            if "source_chat_id" not in cols:
                conn.execute(sa.text("ALTER TABLE memory_items ADD COLUMN source_chat_id INTEGER"))

    if "agent_runs" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("agent_runs")}
        with engine.begin() as conn:
            if "state" not in cols:
                conn.execute(sa.text("ALTER TABLE agent_runs ADD COLUMN state VARCHAR(50) DEFAULT 'pending'"))

    if "models" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("models")}
        with engine.begin() as conn:
            if "supports_vision" not in cols:
                conn.execute(sa.text("ALTER TABLE models ADD COLUMN supports_vision BOOLEAN DEFAULT 0"))
            if "source" not in cols:
                conn.execute(sa.text("ALTER TABLE models ADD COLUMN source VARCHAR(10) NOT NULL DEFAULT 'manual'"))

    if "messages" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("messages")}
        with engine.begin() as conn:
            if "attachments" not in cols:
                conn.execute(sa.text("ALTER TABLE messages ADD COLUMN attachments JSON"))


_ensure_schema()

# 2026-08-11：app.api 导入下移至此——迁移完成后才可触碰带新增列的 models 表
from app.api import models, agents, chat, memory, memories, projects, settings as settings_api, backup, knowledge, fonts, tools, plugins, trash, greetings, devtools, runs, todos, voice, skills, mcp  # noqa: E402


def _backfill_custom_model_source():
    """一次性回填：models 表 source 字段（sync/manual）。

    2026-08-11 自定义模型治理：历史存量记录无法区分来源，按启发式回填：
      - (provider, model_id) 在当前 enabled_models 候选池内 → sync；
      - 不在池内且 enabled=0 → sync 残留幽灵，直接清理（字段均可从 provider 重新派生，零数据损失）；
      - 不在池内且 enabled=1 → 判为 manual（用户手动创建）。
    幂等：仅处理 source 为空/默认值且需要改判的行；每行判定均打日志便于审计。
    """
    import json as _json
    from app.core.database import SessionLocal
    from app.models.agent import CustomModel, Setting

    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == "enabled_models").first()
        pool = set()
        if row and row.value:
            try:
                m = _json.loads(row.value)
                if isinstance(m, dict):
                    for pid, ids in m.items():
                        if isinstance(ids, list):
                            pool.update((pid, i) for i in ids if isinstance(i, str))
            except (ValueError, TypeError):
                pass
        changed = 0
        for cm in db.query(CustomModel).all():
            in_pool = (cm.provider, cm.model_id) in pool
            if in_pool:
                if cm.source != "sync":
                    cm.source = "sync"
                    changed += 1
                logger.info("source backfill: %s@%s -> sync (in pool)", cm.model_id, cm.provider)
            elif not cm.enabled:
                logger.info("source backfill: %s@%s -> ghost, deleting", cm.model_id, cm.provider)
                db.delete(cm)
                changed += 1
            else:
                logger.info("source backfill: %s@%s -> manual (kept)", cm.model_id, cm.provider)
        if changed:
            db.commit()
            logger.info("_backfill_custom_model_source: %d rows changed", changed)
    except Exception:
        db.rollback()
        logger.exception("_backfill_custom_model_source failed")
    finally:
        db.close()


_backfill_custom_model_source()


def _purge_mimo_key():
    """已禁用：MiMo 已重新启用，不再清除 api_key_mimo。"""
    pass


# _purge_mimo_key()  # 已禁用：MiMo 已重新启用


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


def _migrate_legacy_todos():
    """一次性迁移：旧 SQLite todos 表 → 本地 JSON 文件（幂等，见 todo_store）。"""
    from app.core import todo_store

    migrated = todo_store.migrate_from_db_once()
    if migrated:
        print("[migration] 待办已从 SQLite todos 表迁移到 data/todos.json")


_migrate_legacy_todos()

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
app.include_router(plugins.router, prefix="/api/plugins", tags=["plugins"])
app.include_router(trash.router, prefix="/api/trash", tags=["trash"])
app.include_router(greetings.router, prefix="/api/system", tags=["system"])
app.include_router(devtools.router, prefix="/api/devtools", tags=["devtools"])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
app.include_router(todos.router, prefix="/api/todos", tags=["todos"])
app.include_router(voice.router, prefix="/api/voice", tags=["voice"])
app.include_router(skills.router, prefix="/api/skills", tags=["skills"])
app.include_router(mcp.router, prefix="/api/mcp", tags=["mcp"])

@app.get("/")
async def root():
    return {"message": "MfkAgent API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ── Phase 9 P1: 端口自动检测与避让 ──
if __name__ == "__main__":
    import uvicorn
    import os
    from app.core.port_manager import find_available_port, write_port_file, clear_port_file

    # Phase 8: 优先使用 Electron 主进程传入的端口（MFK_PORT），否则自动探测
    mfk_port = os.environ.get("MFK_PORT")
    if mfk_port:
        port = int(mfk_port)
        logger.info("Phase8 port: 使用 Electron 传入端口 MFK_PORT=%d", port)
    else:
        port = find_available_port(start_port=8001)
    write_port_file(port)

    try:
        uvicorn.run("main:app", host="127.0.0.1", port=port, reload=False)
    finally:
        clear_port_file()
