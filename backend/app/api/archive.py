from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
import re
import json
import logging

from app.core.database import SessionLocal
from app.models.agent import Project, Chat, Message, Setting

logger = logging.getLogger(__name__)
from app.core.config import BACKEND_DIR

router = APIRouter()


# ── 归档目录解析 ──
def _resolve_archive_dir() -> str:
    """解析归档文件夹：settings.archive_dir（用户配置）优先，空则用默认 backend/Archive/"""
    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == "archive_dir").first()
        raw = (row.value or "").strip() if row else ""
    finally:
        db.close()
    base = raw if raw else os.path.join(str(BACKEND_DIR), "Archive")
    os.makedirs(base, exist_ok=True)
    return base


def _safe_name(name: str) -> str:
    """文件系统安全文件名：剔除非法字符"""
    safe = re.sub(r'[\\/:*?"<>|]', "_", name or "untitled")
    return safe.strip() or "untitled"


def _chat_to_markdown(chat, messages) -> str:
    lines = [f"# {chat.title}\n"]
    lines.append(f"Agent: {chat.agent_id}\n")
    if chat.project_id:
        lines.append(f"Project: {chat.project.name if chat.project else chat.project_id}\n")
    lines.append(f"Created: {chat.created_at}\n\n")
    lines.append("---\n\n")
    for msg in messages:
        role = "User" if msg.role == "user" else "Assistant"
        lines.append(f"**{role}** ({msg.created_at}):\n")
        lines.append(f"{msg.content}\n\n")
    return "".join(lines)


def _chat_to_json(chat, messages) -> dict:
    return {
        "chat": {
            "id": chat.id,
            "title": chat.title,
            "agent_id": chat.agent_id,
            "project_id": chat.project_id,
            "created_at": str(chat.created_at),
            "archived_at": str(datetime.utcnow()),
        },
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": str(msg.created_at),
            }
            for msg in messages
        ],
    }


def _write_export_files(archive_dir: str, kind: str, name: str, obj_id: int, md: str, js: dict) -> str:
    """写归档文件到归档目录，返回相对路径（用于展示）。目录结构：{archive_dir}/{kind}s/{safe_name}_{id}/"""
    folder = os.path.join(archive_dir, f"{kind}s", f"{_safe_name(name)}_{obj_id}")
    os.makedirs(folder, exist_ok=True)
    md_path = os.path.join(folder, f"{_safe_name(name)}.md")
    js_path = os.path.join(folder, f"{_safe_name(name)}.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(js_path, "w", encoding="utf-8") as f:
        json.dump(js, f, ensure_ascii=False, indent=2)
    return folder


# ── 响应模型 ──
class ArchiveItem(BaseModel):
    type: str  # "project" | "chat"
    id: int
    name: str
    project_id: Optional[int] = None
    archived_at: Optional[datetime] = None
    archive_path: Optional[str] = None

    class Config:
        from_attributes = True


class ArchiveListResponse(BaseModel):
    items: List[ArchiveItem]
    archive_dir: str


# ── 列表 ──
@router.get("", response_model=ArchiveListResponse)
async def list_archives():
    """列出全部归档项（项目 + 会话，按归档时间倒序）"""
    db = SessionLocal()
    try:
        archive_dir = _resolve_archive_dir()
        projects = (
            db.query(Project)
            .filter(Project.is_archived == True)
            .order_by(Project.archived_at.desc())
            .all()
        )
        chats = (
            db.query(Chat)
            .filter(Chat.is_archived == True)
            .order_by(Chat.archived_at.desc())
            .all()
        )
        items: List[ArchiveItem] = []
        for p in projects:
            items.append(ArchiveItem(
                type="project",
                id=p.id,
                name=p.name,
                archived_at=p.archived_at,
                archive_path=os.path.join(archive_dir, "projects", f"{_safe_name(p.name)}_{p.id}"),
            ))
        for c in chats:
            items.append(ArchiveItem(
                type="chat",
                id=c.id,
                name=c.title,
                project_id=c.project_id,
                archived_at=c.archived_at,
                archive_path=os.path.join(archive_dir, "chats", f"{_safe_name(c.title)}_{c.id}"),
            ))
        return ArchiveListResponse(items=items, archive_dir=archive_dir)
    finally:
        db.close()


# ── 归档 ──
@router.post("/projects/{project_id}")
async def archive_project(project_id: int):
    """归档项目：导出文件 + 级联归档其下会话。不触碰项目本地目录。"""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if project.is_deleted:
            raise HTTPException(status_code=400, detail="Project is in trash")
        if project.is_archived:
            raise HTTPException(status_code=400, detail="Project already archived")

        now = datetime.utcnow()
        archive_dir = _resolve_archive_dir()

        # 先写文件（项目元数据 + 其下会话记录），全部成功后才标记库
        chats = (
            db.query(Chat)
            .filter(Chat.project_id == project_id, Chat.is_deleted == False, Chat.is_archived == False)
            .all()
        )
        try:
            project_md = [
                f"# {project.name}\n",
                f"Path: {project.path}\n",
                f"Created: {project.created_at}\n",
                f"Archived: {now}\n\n",
            ]
            project_folder = _write_export_files(archive_dir, "project", project.name, project.id, "".join(project_md), {
                "project": {
                    "id": project.id,
                    "name": project.name,
                    "path": project.path,
                    "created_at": str(project.created_at),
                    "archived_at": str(now),
                },
                "chats": [
                    {"id": c.id, "title": c.title, "agent_id": c.agent_id}
                    for c in chats
                ],
            })
            for chat in chats:
                msgs = (
                    db.query(Message)
                    .filter(Message.chat_id == chat.id)
                    .order_by(Message.created_at.asc())
                    .all()
                )
                _write_export_files(archive_dir, "chat", chat.title, chat.id, _chat_to_markdown(chat, msgs), _chat_to_json(chat, msgs))
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"归档写入失败: {e}")

        # 写文件成功后标记
        project.is_archived = True
        project.archived_at = now
        project.updated_at = now
        for chat in chats:
            chat.is_archived = True
            chat.archived_at = now
            chat.updated_at = now
        db.commit()
        return {"status": "archived", "id": project_id, "archive_path": project_folder}
    finally:
        db.close()


@router.post("/chats/{chat_id}")
async def archive_chat(chat_id: int):
    """归档会话：导出文件 + 标记"""
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        if chat.is_deleted:
            raise HTTPException(status_code=400, detail="Chat is in trash")
        if chat.is_archived:
            raise HTTPException(status_code=400, detail="Chat already archived")
        # 所属项目已归档时，会话处于归档态，不能再单独操作
        if chat.project_id:
            project = db.query(Project).filter(Project.id == chat.project_id).first()
            if project and project.is_archived:
                raise HTTPException(status_code=400, detail="所属项目已归档")

        now = datetime.utcnow()
        archive_dir = _resolve_archive_dir()
        msgs = (
            db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
            .all()
        )
        try:
            folder = _write_export_files(archive_dir, "chat", chat.title, chat.id, _chat_to_markdown(chat, msgs), _chat_to_json(chat, msgs))
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"归档写入失败: {e}")

        chat.is_archived = True
        chat.archived_at = now
        chat.updated_at = now
        db.commit()
        return {"status": "archived", "id": chat_id, "archive_path": folder}
    finally:
        db.close()


# ── 恢复 ──
@router.post("/{item_type}/{item_id}/restore")
async def restore_archive(item_type: str, item_id: int):
    """恢复归档项：清除 is_archived 标记。项目恢复时其下归档会话一并恢复。"""
    if item_type not in ("project", "chat"):
        raise HTTPException(status_code=400, detail="item_type must be 'project' or 'chat'")
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        if item_type == "project":
            project = db.query(Project).filter(Project.id == item_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            if not project.is_archived:
                raise HTTPException(status_code=400, detail="Project is not archived")
            project.is_archived = False
            project.archived_at = None
            project.updated_at = now
            # 其下归档会话一并恢复
            db.query(Chat).filter(Chat.project_id == item_id, Chat.is_archived == True).update(
                {"is_archived": False, "archived_at": None, "updated_at": now}
            )
        else:
            chat = db.query(Chat).filter(Chat.id == item_id).first()
            if not chat:
                raise HTTPException(status_code=404, detail="Chat not found")
            if not chat.is_archived:
                raise HTTPException(status_code=400, detail="Chat is not archived")
            chat.is_archived = False
            chat.archived_at = None
            chat.updated_at = now
        db.commit()
        return {"status": "restored", "id": item_id}
    finally:
        db.close()


# ── 彻底删除 ──
@router.delete("/{item_type}/{item_id}")
async def purge_archive(item_type: str, item_id: int):
    """彻底删除归档项：删除磁盘归档文件 + 物理删除数据库记录。不触碰项目本地目录。"""
    if item_type not in ("project", "chat"):
        raise HTTPException(status_code=400, detail="item_type must be 'project' or 'chat'")
    db = SessionLocal()
    try:
        archive_dir = _resolve_archive_dir()
        if item_type == "project":
            project = db.query(Project).filter(Project.id == item_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            if not project.is_archived:
                raise HTTPException(status_code=400, detail="Project is not archived")
            folder = os.path.join(archive_dir, "projects", f"{_safe_name(project.name)}_{project.id}")
            db.delete(project)  # 级联删除其下 chats/messages（relationship cascade）
        else:
            chat = db.query(Chat).filter(Chat.id == item_id).first()
            if not chat:
                raise HTTPException(status_code=404, detail="Chat not found")
            if not chat.is_archived:
                raise HTTPException(status_code=400, detail="Chat is not archived")
            folder = os.path.join(archive_dir, "chats", f"{_safe_name(chat.title)}_{chat.id}")
            db.delete(chat)
        db.commit()
        # 物理删除磁盘归档文件（失败仅告警，不阻断）
        try:
            if os.path.isdir(folder):
                import shutil
                shutil.rmtree(folder, ignore_errors=True)
        except Exception as e:
            logger.warning("Failed to remove archive folder: %s — %s", folder, e)
        return {"status": "purged", "id": item_id}
    finally:
        db.close()
