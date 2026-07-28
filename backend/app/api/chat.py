from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.core.database import SessionLocal
from app.models.agent import Chat, Message

router = APIRouter()


class ChatCreate(BaseModel):
    project_id: Optional[int] = None
    agent_id: str = "warm"
    title: str = "New Chat"


class ChatResponse(BaseModel):
    id: int
    project_id: Optional[int]
    agent_id: str
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    role: str
    content: str


class MessageResponse(BaseModel):
    id: int
    chat_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[ChatResponse])
async def list_chats(project_id: Optional[int] = None):
    db = SessionLocal()
    try:
        query = db.query(Chat)
        if project_id is not None:
            query = query.filter(Chat.project_id == project_id)
        else:
            query = query.filter(Chat.project_id.is_(None))
        return query.order_by(Chat.updated_at.desc()).all()
    finally:
        db.close()


@router.post("", response_model=ChatResponse)
async def create_chat(chat: ChatCreate):
    db = SessionLocal()
    try:
        db_chat = Chat(
            project_id=chat.project_id,
            agent_id=chat.agent_id,
            title=chat.title,
        )
        db.add(db_chat)
        db.commit()
        db.refresh(db_chat)
        return db_chat
    finally:
        db.close()


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(chat_id: int):
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        return chat
    finally:
        db.close()


@router.delete("/{chat_id}")
async def delete_chat(chat_id: int):
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        db.delete(chat)
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()


@router.get("/{chat_id}/messages", response_model=List[MessageResponse])
async def list_messages(chat_id: int):
    db = SessionLocal()
    try:
        return (
            db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
            .all()
        )
    finally:
        db.close()


@router.post("/{chat_id}/messages", response_model=MessageResponse)
async def create_message(chat_id: int, message: MessageCreate):
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        db_message = Message(
            chat_id=chat_id,
            role=message.role,
            content=message.content,
        )
        db.add(db_message)
        chat.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_message)
        return db_message
    finally:
        db.close()
