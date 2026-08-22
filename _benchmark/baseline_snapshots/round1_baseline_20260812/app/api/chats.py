"""会话路由：创建会话、发消息、查消息。"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List

from app.database import Session, create_session
from app.models import Chat, Message
from app.schemas import ChatCreate, ChatOut, SendRequest, MessageOut
from app.services import chat_service

router = APIRouter(prefix="/chats", tags=["chats"])


def get_db():
    db = create_session()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=ChatOut)
def create_chat(body: ChatCreate, db: Session = Depends(get_db)):
    try:
        chat = chat_service.create_chat(
            db, body.agent_id, body.title, body.model,
            body.mode, body.project_path, body.personality_level,
        )
        db.commit()
        db.refresh(chat)
        return chat
    except chat_service.ChatError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.get("", response_model=List[ChatOut])
def list_chats(agent_id: str = None, db: Session = Depends(get_db)):
    q = db.query(Chat)
    if agent_id is not None:
        q = q.filter(Chat.agent_id == agent_id)
    return q.order_by(Chat.id.desc()).all()


@router.get("/{chat_id}/messages", response_model=List[MessageOut])
def list_messages(chat_id: int, db: Session = Depends(get_db)):
    if db.query(Chat).filter(Chat.id == chat_id).first() is None:
        raise HTTPException(404, "会话不存在")
    return (
        db.query(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.id)
        .all()
    )


@router.post("/{chat_id}/send")
def send_message(chat_id: int, body: SendRequest, db: Session = Depends(get_db)):
    try:
        user_msg, ai_msg, meta = chat_service.send_message(db, chat_id, body.content)
        db.commit()
        return {
            "user_message": {"id": user_msg.id, "content": user_msg.content},
            "ai_message": {"id": ai_msg.id, "content": ai_msg.content},
            "meta": meta,
        }
    except chat_service.ChatError as e:
        db.rollback()
        raise HTTPException(400, str(e))