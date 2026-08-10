"""待办事项 RESTful API — /api/todos（JSON 文件持久化）

支持：
- GET    /api/todos?status=pending&project_id=xxx  （默认仅返回 pending）
- POST   /api/todos                                 （新增待办）
- PATCH  /api/todos/{id}                            （更新状态/标题）
- DELETE /api/todos/{id}                            （删除）

存储：本地 JSON 文件（app.core.todo_store），非数据库。REST 契约与旧实现一致。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core import todo_store

router = APIRouter()

_VALID_STATUS = {"pending", "completed"}


class TodoCreate(BaseModel):
    title: str
    project_id: Optional[int] = None
    status: str = "pending"


class TodoUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


class TodoResponse(BaseModel):
    id: str
    project_id: Optional[int]
    title: str
    status: str
    created_at: str
    updated_at: str


def _to_response(t: dict) -> dict:
    return {
        "id": t["id"],
        "project_id": t.get("project_id"),
        "title": t["title"],
        "status": t["status"],
        "created_at": t.get("created_at", ""),
        "updated_at": t.get("updated_at", ""),
    }


@router.get("")
async def list_todos(status: str = "pending", project_id: Optional[int] = None):
    """列出待办事项。默认仅返回 pending 状态。

    - status=pending（默认）：仅未完成
    - status=completed：仅已完成
    - status=all：全部
    - project_id：按项目过滤（可选）
    """
    if status != "all" and status not in _VALID_STATUS:
        raise HTTPException(status_code=422, detail=f"status 必须是 {sorted(_VALID_STATUS)} 或 all")
    todos = todo_store.list_todos(status=status, project_id=project_id)
    return [_to_response(t) for t in todos]


@router.post("")
async def create_todo(todo: TodoCreate):
    """新增待办事项。"""
    if todo.status not in _VALID_STATUS:
        raise HTTPException(status_code=422, detail=f"status 必须是 {sorted(_VALID_STATUS)}")
    if not todo.title or not todo.title.strip():
        raise HTTPException(status_code=422, detail="title 不能为空")

    new_todo = todo_store.create_todo(
        title=todo.title,
        project_id=todo.project_id,
        status=todo.status,
    )
    return _to_response(new_todo)


@router.patch("/{todo_id}")
async def update_todo(todo_id: str, update: TodoUpdate):
    """更新待办事项（状态/标题）。"""
    if update.status is not None and update.status not in _VALID_STATUS:
        raise HTTPException(status_code=422, detail=f"status 必须是 {sorted(_VALID_STATUS)}")
    if update.title is not None and not update.title.strip():
        raise HTTPException(status_code=422, detail="title 不能为空")

    updated = todo_store.update_todo(
        todo_id=todo_id,
        status=update.status,
        title=update.title,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="待办不存在")
    return _to_response(updated)


@router.delete("/{todo_id}")
async def delete_todo(todo_id: str):
    """删除待办事项。"""
    ok = todo_store.delete_todo(todo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="待办不存在")
    return {"status": "ok", "id": todo_id}
