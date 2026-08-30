from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import os
# 注意：app.api 的 import 已下移到 _ensure_schema() 之后（见下方）。
# 原因：app.api.models 导入时 model_service 会立即查询 models 表（含新增列），
# 必须先完成轻量迁移，否则旧库会报 "no such column"。
from app.core.config import settings
from app.core.database import engine, Base
from app.core.errors import APIError, api_error_handler, http_exception_handler, validation_exception_handler
from app.core.log_config import init_logging
from app.models.persona import PersonaTemplate, ExpressionKnowledge
# 安卓端：配对设备表必须在 create_all 之前注册到 Base（否则 paired_devices 不会被建表）
from app.models.mobile import PairedDevice  # noqa: F401

logger = logging.getLogger(__name__)

# 日志文件初始化（必须在所有操作之前）
init_logging()

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 自定义端点：seed 内置模板（FreeLLMAPI）+ 加载到 PROVIDERS
from app.core.model_providers import seed_builtin_custom_providers, reload_custom_providers
seed_builtin_custom_providers()
reload_custom_providers()

# 预置插件 seed（需在 create_all 之后，表存在才能写入）
from app.services.plugin import plugin_manager as _pm
_pm.seed_default_plugins()

# MCP 桥接初始化：将插件工具注册到 MCPServer
from app.core.mcp_bridge import register_plugin_tools_to_mcp
register_plugin_tools_to_mcp()

# MCP 外部插件注册：浏览器自动化、系统控制等真实能力
from app.services.mcp_plugins import register_all_external_plugins
register_all_external_plugins()

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
            if "permission_mode" not in cols:
                conn.execute(sa.text("ALTER TABLE chats ADD COLUMN permission_mode VARCHAR(10) DEFAULT 'standard'"))
            if "is_archived" not in cols:
                conn.execute(sa.text("ALTER TABLE chats ADD COLUMN is_archived BOOLEAN DEFAULT 0"))
            if "archived_at" not in cols:
                conn.execute(sa.text("ALTER TABLE chats ADD COLUMN archived_at DATETIME"))
            # 圆桌模式
            if "roundtable_config" not in cols:
                conn.execute(sa.text("ALTER TABLE chats ADD COLUMN roundtable_config JSON DEFAULT '{}'"))
            # T2 压缩止血：压缩边界（视图层裁剪锚点，messages 行永不删除）
            if "compaction_boundary_message_id" not in cols:
                conn.execute(sa.text("ALTER TABLE chats ADD COLUMN compaction_boundary_message_id INTEGER"))

    if "projects" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("projects")}
        with engine.begin() as conn:
            if "is_deleted" not in cols:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
            if "deleted_at" not in cols:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN deleted_at DATETIME"))
            if "is_pinned" not in cols:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN is_pinned BOOLEAN DEFAULT 0"))
            if "is_archived" not in cols:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN is_archived BOOLEAN DEFAULT 0"))
            if "archived_at" not in cols:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN archived_at DATETIME"))

    if "messages" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("messages")}
        with engine.begin() as conn:
            if "tool_calls" not in cols:
                conn.execute(sa.text("ALTER TABLE messages ADD COLUMN tool_calls JSON"))
            if "timeline" not in cols:
                conn.execute(sa.text("ALTER TABLE messages ADD COLUMN timeline JSON"))
            if "task_graph" not in cols:
                conn.execute(sa.text("ALTER TABLE messages ADD COLUMN task_graph JSON"))
            # 圆桌模式：消息发送者
            if "agent_id" not in cols:
                conn.execute(sa.text("ALTER TABLE messages ADD COLUMN agent_id VARCHAR(50)"))

    if "agents" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("agents")}
        with engine.begin() as conn:
            if "status" not in cols:
                conn.execute(sa.text("ALTER TABLE agents ADD COLUMN status VARCHAR(20) DEFAULT 'active'"))
            if "expression_profile" not in cols:
                conn.execute(sa.text("ALTER TABLE agents ADD COLUMN expression_profile VARCHAR(50)"))
            # Phase SubAgent：子代理字段
            if "is_sub_agent" not in cols:
                conn.execute(sa.text("ALTER TABLE agents ADD COLUMN is_sub_agent BOOLEAN DEFAULT 0"))
            if "allowed_tools" not in cols:
                conn.execute(sa.text("ALTER TABLE agents ADD COLUMN allowed_tools JSON"))
            if "parent_agent_id" not in cols:
                conn.execute(sa.text("ALTER TABLE agents ADD COLUMN parent_agent_id VARCHAR(50)"))

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
            if "is_active" not in cols:
                conn.execute(sa.text("ALTER TABLE memory_items ADD COLUMN is_active BOOLEAN DEFAULT 1"))
            if "last_accessed_at" not in cols:
                conn.execute(sa.text("ALTER TABLE memory_items ADD COLUMN last_accessed_at DATETIME"))
            if "access_count" not in cols:
                conn.execute(sa.text("ALTER TABLE memory_items ADD COLUMN access_count INTEGER DEFAULT 0"))

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

    # T6 外部 MCP：plugins 表补充 source 列（builtin / external_mcp）
    if "plugins" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("plugins")}
        with engine.begin() as conn:
            if "source" not in cols:
                conn.execute(sa.text("ALTER TABLE plugins ADD COLUMN source VARCHAR(30) NOT NULL DEFAULT 'builtin'"))

    if "messages" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("messages")}
        with engine.begin() as conn:
            if "attachments" not in cols:
                conn.execute(sa.text("ALTER TABLE messages ADD COLUMN attachments JSON"))


_ensure_schema()


def _seed_sub_agents():
    """幂等补种子：仅插入缺失的内置子代理（不触碰已有 Agent 数据，不覆盖用户修改）。"""
    from app.core.database import SessionLocal
    from app.models.agent import Agent
    from seed_agents import PRESET_AGENTS

    db = SessionLocal()
    try:
        for agent_data in PRESET_AGENTS:
            if not agent_data.get("is_sub_agent"):
                continue
            existing = db.query(Agent).filter(Agent.agent_id == agent_data["agent_id"]).first()
            if existing:
                continue
            db.add(Agent(**agent_data))
            print(f"[seed] Created sub-agent: {agent_data['name']}")
        db.commit()
    except Exception:
        db.rollback()
        print("[seed] _seed_sub_agents failed (non-fatal)")
    finally:
        db.close()


_seed_sub_agents()

# 2026-08-11：app.api 导入下移至此——迁移完成后才可触碰带新增列的 models 表
from app.api import models, agents, chat, memory, memories, projects, settings as settings_api, backup, knowledge, fonts, tools, plugins, trash, greetings, devtools, runs, todos, skills, mcp, archive, security as security_api, sub_agents, proxy as proxy_api, terminal as terminal_api, browser as browser_api, feishu as feishu_api, workflows, autotasks, defense_ppt  # noqa: E402
from app.api import mobile as mobile_api  # noqa: E402  安卓端：配对/设备/系统控制/WOL/推送WS


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


def _self_heal_agent_json_fields():
    """启动自检：遍历所有 Agent，修复损坏的 JSON 字段（skills/capabilities/allowed_tools）。

    背景：Agent 表的 JSON 列若因手动编辑数据库等原因写入了无效 JSON（如 `[" comfyui-local\\]`），
    SQLAlchemy 读取时会抛 JSONDecodeError，导致所有使用该 Agent 的聊天返回 500。
    此函数在启动时自动检测并修复为 `[]`，打 ERROR 日志便于审计。

    幂等：仅修复无效 JSON，有效数据不动。
    """
    import json as _json
    from sqlalchemy import text as _text
    from app.core.database import SessionLocal

    JSON_FIELDS = ("skills", "capabilities", "allowed_tools")
    db = SessionLocal()
    try:
        rows = db.execute(_text("SELECT id, agent_id, name, skills, capabilities, allowed_tools FROM agents")).fetchall()
        repaired = 0
        for row in rows:
            aid, agent_id, name = row[0], row[1], row[2]
            fixes = {}
            for i, field in enumerate(JSON_FIELDS, start=3):
                raw = row[i]
                if raw is None or raw == "":
                    continue
                try:
                    _json.loads(raw)
                except (ValueError, TypeError):
                    fixes[field] = raw
            if fixes:
                for field, bad_val in fixes.items():
                    db.execute(
                        _text(f"UPDATE agents SET {field} = '[]' WHERE id = :id"),
                        {"id": aid},
                    )
                    logger.error(
                        "Self-heal: Agent '%s' (id=%s) field '%s' had invalid JSON, reset to []. Bad value: %s",
                        agent_id, aid, field, repr(bad_val[:100]),
                    )
                repaired += 1
        if repaired:
            db.commit()
            logger.info("_self_heal_agent_json_fields: repaired %d agent(s)", repaired)
        else:
            logger.info("_self_heal_agent_json_fields: all agent JSON fields valid, no repair needed")
    except Exception:
        db.rollback()
        logger.exception("_self_heal_agent_json_fields failed (non-fatal)")
    finally:
        db.close()


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

# 启动自检：修复 Agent 表中损坏的 JSON 字段（防止单条坏数据导致聊天 500）
_self_heal_agent_json_fields()

app = FastAPI(
    title="MfkAgent API",
    description="MfkAgent - AI工作助手后端API",
    version="0.1.0",
)

# CORS配置
# 安卓端 M1：追加 Capacitor WebView scheme（capacitor://localhost / https://localhost），
# 桌面版 Electron（file:// 无 Origin 头）不受影响。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS + ["capacitor://localhost", "https://localhost", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 安卓端 M1：非回环来源的 API 鉴权中间件 ──
# 本机回环（Electron/桌面浏览器）直接放行，行为零变化；
# 手机等非本机来源访问 /api/* 必须携带配对 token（/api/mobile/pair/* 握手除外）。
from fastapi.responses import JSONResponse  # noqa: E402
from app.core.mobile_auth import is_loopback_host, verify_device_token  # noqa: E402


@app.middleware("http")
async def mobile_remote_auth_middleware(request, call_next):
    path = request.url.path
    if path.startswith("/api/") and os.environ.get("TESTING") != "1":
        client = request.client.host if request.client else ""
        if not is_loopback_host(client) and not path.startswith("/api/mobile/pair/"):
            auth = request.headers.get("authorization", "")
            token = auth[7:] if auth.lower().startswith("bearer ") else ""
            if verify_device_token(token) is None:
                return JSONResponse({"detail": "未配对设备或凭证无效"}, status_code=401)
    return await call_next(request)

# 错误处理
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# 注册路由
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(sub_agents.router, prefix="/api/sub-agents", tags=["sub-agents"])
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
app.include_router(archive.router, prefix="/api/archive", tags=["archive"])
app.include_router(security_api.router, prefix="/api/security", tags=["security"])
app.include_router(greetings.router, prefix="/api/system", tags=["system"])
app.include_router(devtools.router, prefix="/api/devtools", tags=["devtools"])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
app.include_router(todos.router, prefix="/api/todos", tags=["todos"])
app.include_router(skills.router, prefix="/api/skills", tags=["skills"])
app.include_router(mcp.router, prefix="/api/mcp", tags=["mcp"])
app.include_router(proxy_api.router, prefix="/api/proxy", tags=["proxy"])
app.include_router(terminal_api.router, prefix="/api", tags=["terminal"])
app.include_router(browser_api.router, prefix="/api", tags=["browser"])
app.include_router(feishu_api.router, prefix="/api/feishu", tags=["feishu"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
app.include_router(autotasks.router, prefix="/api/autotasks", tags=["autotasks"])
app.include_router(defense_ppt.router, prefix="/api/defense-ppt", tags=["defense-ppt"])
app.include_router(mobile_api.router, prefix="/api/mobile", tags=["mobile"])

# 静态文件：ComfyUI 生成的图片输出目录，前端用 /generated_images/xxx.png 访问
_gen_img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "generated_images")
os.makedirs(_gen_img_dir, exist_ok=True)
app.mount("/generated_images", StaticFiles(directory=_gen_img_dir), name="generated_images")

# 关闭时清理所有终端 PTY 会话
@app.on_event("shutdown")
async def _shutdown_terminal():
    from app.services.terminal import get_terminal_manager
    get_terminal_manager().shutdown_all()

@app.on_event("shutdown")
async def _shutdown_browser():
    from app.core.browser_session import browser_manager
    browser_manager.shutdown()

# 证据化收尾：启动时回收进程重启前遗留的 status=running 陈旧 run（1281/1229/1234 类僵尸），
# 置为 failed 并补写 error 证据事件，避免"进行中"永远挂着。
@app.on_event("startup")
async def _recover_stale_runs_on_startup():
    import asyncio
    try:
        from app.core.agent_runtime.recorder import runtime_event_recorder
        recovered = await asyncio.to_thread(runtime_event_recorder.recover_stale_runs)
        if recovered:
            logger.warning("启动回收陈旧 AgentRun %d 个（interrupted by restart）", recovered)
    except Exception as e:
        logger.warning("启动回收陈旧 AgentRun 异常（已忽略不阻断启动）: %s", e)

@app.on_event("startup")
async def _start_feishu_ws():
    try:
        from app.services.feishu_ws import start as start_feishu_ws
        if getattr(settings, "FEISHU_WS_ENABLED", True):
            start_feishu_ws()
    except Exception as e:
        logger.warning("飞书 WebSocket 启动异常（已忽略不阻断启动）: %s", e)

# T6 外部 MCP：后台枚举 stdio MCP server 工具（异步不阻塞启动，失败仅告警）
@app.on_event("startup")
async def _start_external_mcp():
    try:
        from app.core.mcp_client import external_mcp_manager
        external_mcp_manager.startup()
    except Exception as e:
        logger.warning("外部 MCP 启动异常（已忽略不阻断启动）: %s", e)

@app.on_event("shutdown")
async def _shutdown_external_mcp():
    try:
        from app.core.mcp_client import external_mcp_manager
        await external_mcp_manager.shutdown()
    except Exception as e:
        logger.warning("外部 MCP 关闭异常（已忽略）: %s", e)

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
    import sys
    import urllib.request
    from app.core.port_manager import find_available_port, write_port_file, clear_port_file

    # 单实例检测：防止多个后端进程并存导致端口漂移和前端访问错乱
    def _is_mfkagent_running(port: int) -> bool:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                body = r.read().decode("utf-8", errors="ignore")
                return '"status"' in body and "healthy" in body
        except Exception:
            return False

    for _check_port in (8001, 8002, 8003, 8004, 8005):
        if _is_mfkagent_running(_check_port):
            print(f"[main] MfkAgent 后端已在端口 {_check_port} 运行，跳过启动（避免多实例并存）。")
            print(f"[main] 如需重启，请先关闭现有进程或访问 http://127.0.0.1:{_check_port}")
            sys.exit(0)

    # Phase 8: 优先使用 Electron 主进程传入的端口（MFK_PORT），否则自动探测
    mfk_port = os.environ.get("MFK_PORT")
    if mfk_port:
        port = int(mfk_port)
        logger.info("Phase8 port: 使用 Electron 传入端口 MFK_PORT=%d", port)
    else:
        port = find_available_port(start_port=8001)
    write_port_file(port)

    # 安卓端：MFK_HOST=0.0.0.0 时监听全部网卡，供手机局域网访问（默认 127.0.0.1 桌面行为不变）
    mfk_host = os.environ.get("MFK_HOST", "127.0.0.1")

    try:
        if mfk_host != "127.0.0.1":
            logger.warning("MfkAgent 后端以 MFK_HOST=%s 启动：局域网可访问，请确保已配对设备管理（/api/mobile）", mfk_host)
        uvicorn.run(app, host=mfk_host, port=port, reload=False)
    finally:
        clear_port_file()
