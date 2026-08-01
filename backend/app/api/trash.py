from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.core.database import SessionLocal
from app.models.agent import Project, Chat

router = APIRouter()


class TrashProjectItem(BaseModel):
    id: int
    type: str = "project"
    name: str
    path: str
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrashChatItem(BaseModel):
    id: int
    type: str = "chat"
    title: str
    project_id: Optional[int] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrashResponse(BaseModel):
    projects: List[TrashProjectItem]
    chats: List[TrashChatItem]


@router.get("", response_model=TrashResponse)
async def list_trash():
    """回收站：已软删除的项目与会话"""
    db = SessionLocal()
    try:
        projects = (
            db.query(Project)
            .filter(Project.is_deleted == True)
            .order_by(Project.deleted_at.desc())
            .all()
        )
        chats = (
            db.query(Chat)
            .filter(Chat.is_deleted == True)
            .order_by(Chat.deleted_at.desc())
            .all()
        )
        return TrashResponse(
            projects=[
                TrashProjectItem(
                    id=p.id,
                    name=p.name,
                    path=p.path,
                    deleted_at=p.deleted_at,
                )
                for p in projects
            ],
            chats=[
                TrashChatItem(
                    id=c.id,
                    title=c.title,
                    project_id=c.project_id,
                    deleted_at=c.deleted_at,
                )
                for c in chats
            ],
        )
    finally:
        db.close()


@router.post("/projects/{project_id}/restore")
async def restore_project(project_id: int):
    """恢复已删除项目（其下会话一并恢复）"""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if not project.is_deleted:
            raise HTTPException(status_code=400, detail="Project is not in trash")
        project.is_deleted = False
        project.deleted_at = None
        project.updated_at = datetime.utcnow()
        db.query(Chat).filter(Chat.project_id == project_id, Chat.is_deleted == True).update(
            {"is_deleted": False, "deleted_at": None}
        )
        db.commit()
        return {"status": "restored", "id": project_id}
    finally:
        db.close()


@router.post("/chats/{chat_id}/restore")
async def restore_chat(chat_id: int):
    """恢复已删除会话（若其所属项目仍处于删除状态则一并恢复）"""
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        if not chat.is_deleted:
            raise HTTPException(status_code=400, detail="Chat is not in trash")
        chat.is_deleted = False
        chat.deleted_at = None
        chat.updated_at = datetime.utcnow()
        if chat.project_id:
            project = db.query(Project).filter(Project.id == chat.project_id).first()
            if project and project.is_deleted:
                project.is_deleted = False
                project.deleted_at = None
        db.commit()
        return {"status": "restored", "id": chat_id}
    finally:
        db.close()


@router.delete("/projects/{project_id}/forever")
async def purge_project(project_id: int):
    """彻底物理删除项目及其消息历史"""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        db.delete(project)
        db.commit()
        return {"status": "purged", "id": project_id}
    finally:
        db.close()


@router.delete("/chats/{chat_id}/forever")
async def purge_chat(chat_id: int):
    """彻底物理删除会话及其消息历史"""
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        db.delete(chat)
        db.commit()
        return {"status": "purged", "id": chat_id}
    finally:
        db.close()
