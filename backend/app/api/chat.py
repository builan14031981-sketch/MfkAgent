from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
from app.core.database import SessionLocal
from app.models.agent import Chat, Message
from app.services.model import model_service, Message as ModelMessage
from app.api.agents import PRESET_AGENTS

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


class SendRequest(BaseModel):
    content: str
    model: str = "mimo-v2.5-pro"
    temperature: float = 0.7
    max_tokens: int = 4096


class SendResponse(BaseModel):
    user_message: MessageResponse
    ai_message: MessageResponse


def _get_agent_prompt(agent_id: str) -> str:
    for agent in PRESET_AGENTS:
        if agent["id"] == agent_id:
            return agent["system_prompt"]
    return "你是一个有帮助的AI助手。"


@router.post("/{chat_id}/send", response_model=SendResponse)
async def send_message(chat_id: int, request: SendRequest):
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        user_msg = Message(chat_id=chat_id, role="user", content=request.content)
        db.add(user_msg)
        db.flush()

        history = (
            db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
            .all()
        )

        system_prompt = _get_agent_prompt(chat.agent_id)
        model_messages = [ModelMessage(role="system", content=system_prompt)]
        for msg in history:
            model_messages.append(ModelMessage(role=msg.role, content=msg.content))

        try:
            ai_response = await model_service.chat(
                model_id=request.model,
                messages=model_messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            ai_content = ai_response.content
        except Exception as e:
            ai_content = f"[AI回复失败: {str(e)}]"

        ai_msg = Message(chat_id=chat_id, role="assistant", content=ai_content)
        db.add(ai_msg)
        chat.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user_msg)
        db.refresh(ai_msg)

        return SendResponse(
            user_message=MessageResponse.model_validate(user_msg),
            ai_message=MessageResponse.model_validate(ai_msg),
        )
    finally:
        db.close()


@router.post("/{chat_id}/send/stream")
async def send_message_stream(chat_id: int, request: SendRequest):
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        user_msg = Message(chat_id=chat_id, role="user", content=request.content)
        db.add(user_msg)
        db.flush()

        history = (
            db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
            .all()
        )

        system_prompt = _get_agent_prompt(chat.agent_id)
        model_messages = [ModelMessage(role="system", content=system_prompt)]
        for msg in history:
            model_messages.append(ModelMessage(role=msg.role, content=msg.content))

        db.commit()
    finally:
        db.close()

    async def generate():
        full_content = ""
        try:
            async for chunk in model_service.chat_stream(
                model_id=request.model,
                messages=model_messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                if "content" in chunk:
                    full_content += chunk["content"]
                yield f"data: {json.dumps(chunk)}\n\n"

            db2 = SessionLocal()
            try:
                chat2 = db2.query(Chat).filter(Chat.id == chat_id).first()
                ai_msg = Message(
                    chat_id=chat_id, role="assistant", content=full_content
                )
                db2.add(ai_msg)
                if chat2:
                    chat2.updated_at = datetime.utcnow()
                db2.commit()
            finally:
                db2.close()

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
