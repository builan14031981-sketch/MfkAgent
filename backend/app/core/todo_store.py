"""待办事项 JSON 文件存储层 — 替代 SQLite todos 表（P0 技术债）。

本地文件持久化，用户可直接查看/迁移。文件默认位于 backend/data/todos.json，
通过绝对路径定位（基于本模块位置推导，不依赖 CWD），可用环境变量
MFKAGENT_TODOS_FILE 覆盖（测试隔离用）。

存储格式：顶层 dict {"todos": [...]}，每项为
  {"id", "project_id", "title", "status", "created_at", "updated_at"}
created_at / updated_at 为 ISO8601 字符串。

并发安全：所有写操作以文件锁串行化；写入采用临时文件 + os.replace 原子替换。
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

# 默认绝对路径：<backend>/data/todos.json（本模块位于 backend/app/core/ 下，上溯三级）
_DEFAULT_TODO_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "todos.json"

_ENV_FILE = "MFKAGENT_TODOS_FILE"

_VALID_STATUS = {"pending", "completed"}

_lock = threading.RLock()

# 迁移开关：曾从 SQLite 迁移到 JSON（避免每次冷启动重复读库）
_migrated_marker = False


def get_todo_file() -> Path:
    """返回当前使用的待办 JSON 文件路径（支持环境变量覆盖）。"""
    override = os.environ.get(_ENV_FILE)
    if override:
        return Path(override)
    return _DEFAULT_TODO_FILE


def _load() -> list:
    """读取当前 todos 列表。文件不存在或损坏时返回空列表。"""
    path = get_todo_file()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        todos = data.get("todos", []) if isinstance(data, dict) else []
        return todos if isinstance(todos, list) else []
    except (OSError, ValueError):
        return []


def _save(todos: list) -> None:
    """原子写入 todos 列表（临时文件 + os.replace）。"""
    path = get_todo_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    payload = {"todos": todos}
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _now_iso() -> str:
    return datetime.now().isoformat()


def _default_sort(todos: list) -> list:
    """按 created_at 倒序（新→旧），兼容 REST 与工具契约。"""
    return sorted(todos, key=lambda t: t.get("created_at", "") or "", reverse=True)


def _migrate_from_db_once() -> None:
    """一次性迁移：旧 SQLite todos 表数据 → JSON 文件（幂等）。

    仅当 JSON 文件尚不存在且旧表存在时执行；迁移成功后写文件，
    标记 _migrated_marker 防止重复扫描。SQLite 表保留（向后兼容读取）。
    """
    global _migrated_marker
    if _migrated_marker:
        return
    if get_todo_file().exists():
        _migrated_marker = True
        return

    try:
        from app.core.database import SessionLocal
        from app.models.agent import Todo
        from sqlalchemy import inspect
        from app.core.database import engine

        inspector = inspect(engine)
        if "todos" not in inspector.get_table_names():
            _migrated_marker = True
            return

        db = SessionLocal()
        try:
            rows = db.query(Todo).order_by(Todo.created_at.asc()).all()
        finally:
            db.close()
        if not rows:
            _migrated_marker = True
            return

        todos = [
            {
                "id": t.id,
                "project_id": t.project_id,
                "title": t.title,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else _now_iso(),
                "updated_at": t.updated_at.isoformat() if t.updated_at else _now_iso(),
            }
            for t in rows
        ]
        _save(todos)
    except Exception:
        # 迁移失败不阻断启动：JSON 缺失时 list 返回空，写操作会重建文件
        pass
    finally:
        _migrated_marker = True


# ---- 对外 CRUD（REST 路由与 manage_todos 工具共用）----


def list_todos(status: str = "pending", project_id: int | None = None) -> list:
    """列出待办。

    status: 'pending'（默认，仅未完成）/ 'completed' / 'all'。
    project_id 非空时按项目过滤。
    """
    with _lock:
        _migrate_from_db_once()
        todos = _load()
    if status != "all":
        todos = [t for t in todos if t.get("status") == status]
    if project_id is not None:
        todos = [t for t in todos if t.get("project_id") == project_id]
    return _default_sort(todos)


def create_todo(title: str, project_id: int | None = None, status: str = "pending") -> dict:
    """新增待办并返回新对象（写入 JSON）。"""
    if status not in _VALID_STATUS:
        raise ValueError(f"status 必须是 {sorted(_VALID_STATUS)}")
    now = _now_iso()
    new_todo = {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "title": title.strip(),
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    with _lock:
        _migrate_from_db_once()
        todos = _load()
        todos.append(new_todo)
        _save(todos)
    return new_todo


def update_todo(todo_id: str, status: str | None = None, title: str | None = None) -> dict | None:
    """更新待办（status/title 均可选），返回更新后对象；不存在返回 None。"""
    with _lock:
        todos = _load()
        for t in todos:
            if t.get("id") == todo_id:
                if title is not None:
                    t["title"] = title.strip()
                if status is not None:
                    if status not in _VALID_STATUS:
                        raise ValueError(f"status 必须是 {sorted(_VALID_STATUS)}")
                    t["status"] = status
                t["updated_at"] = _now_iso()
                _save(todos)
                return t
    return None


def delete_todo(todo_id: str) -> bool:
    """删除待办，返回是否删除成功。"""
    with _lock:
        todos = _load()
        remaining = [t for t in todos if t.get("id") != todo_id]
        if len(remaining) == len(todos):
            return False
        _save(remaining)
        return True


def get_todo(todo_id: str) -> dict | None:
    """按 id 取单个待办（不存在返回 None）。"""
    with _lock:
        _migrate_from_db_once()
        todos = _load()
    for t in todos:
        if t.get("id") == todo_id:
            return t
    return None


def migrate_from_db_once() -> bool:
    """公共迁移入口：旧 SQLite todos 表 → JSON 文件（幂等，启动时调用）。

    Returns:
        True 表示本次执行了迁移，False 表示无需迁移（JSON 已存在/表不存在/已迁移过）。
    """
    global _migrated_marker
    with _lock:
        before = _migrated_marker
        _migrate_from_db_once()
        return not before and get_todo_file().exists()

