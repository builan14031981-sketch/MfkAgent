from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
from app.core.database import SessionLocal
from app.models.agent import Chat, Message, Agent
from app.services.model import model_service, Message as ModelMessage
from app.core.pagination import paginate

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


@router.get("")
async def list_chats(project_id: Optional[int] = None, page: int = 1, limit: int = 20):
    db = SessionLocal()
    try:
        query = db.query(Chat)
        if project_id is not None:
            query = query.filter(Chat.project_id == project_id)
        else:
            query = query.filter(Chat.project_id.is_(None))
        query = query.order_by(Chat.updated_at.desc())
        result = paginate(query, page, limit)
        result["items"] = [ChatResponse.model_validate(c) for c in result["items"]]
        return result
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


class ChatUpdate(BaseModel):
    title: Optional[str] = None
    agent_id: Optional[str] = None


@router.patch("/{chat_id}", response_model=ChatResponse)
async def update_chat(chat_id: int, update: ChatUpdate):
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        if update.title is not None:
            chat.title = update.title
        if update.agent_id is not None:
            chat.agent_id = update.agent_id
        chat.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(chat)
        return chat
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
    personality_level: int = 50


class SendResponse(BaseModel):
    user_message: MessageResponse
    ai_message: MessageResponse


def _get_agent_prompt(agent_id: str) -> str:
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
        if agent:
            return agent.system_prompt
        return "你是一个有帮助的AI助手。"
    finally:
        db.close()


PERSONALITY_PROMPTS = {
    0: "你是一名高度共情的助手。回答时优先关注用户感受。不要直接否定用户。即使发现问题，也应该温和表达。你的目标是让用户感受到理解和支持。",
    25: "你是一名温和的助手。在理解用户感受的基础上，适度提供建议和分析。保持友好和支持的语气。",
    50: "",
    75: "你是一名理性的分析者。回答时优先检查事实、逻辑和风险。如果用户观点存在问题，应该明确指出。",
    100: "你是一名极度理性的决策分析者。你的首要任务不是让用户舒服，而是帮助用户接近真实答案。你必须主动发现漏洞、质疑未经验证的观点、指出错误假设、直接说明风险。如果用户的想法明显错误，不要迎合。",
}


def _get_personality_prompt(level: int) -> str:
    level = max(0, min(100, level))
    closest = min(PERSONALITY_PROMPTS.keys(), key=lambda k: abs(k - level))
    return PERSONALITY_PROMPTS[closest]


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

        if chat.title == "New Chat":
            chat.title = request.content[:50].strip()
            if len(request.content) > 50:
                chat.title += "..."

        history = (
            db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
            .all()
        )

        system_prompt = _get_agent_prompt(chat.agent_id)
        personality_prompt = _get_personality_prompt(request.personality_level)
        full_prompt = system_prompt
        if personality_prompt:
            full_prompt += "\n\n" + personality_prompt
        model_messages = [ModelMessage(role="system", content=full_prompt)]
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

        if chat.title == "New Chat":
            chat.title = request.content[:50].strip()
            if len(request.content) > 50:
                chat.title += "..."

        history = (
            db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
            .all()
        )

        system_prompt = _get_agent_prompt(chat.agent_id)
        personality_prompt = _get_personality_prompt(request.personality_level)
        full_prompt = system_prompt
        if personality_prompt:
            full_prompt += "\n\n" + personality_prompt
        model_messages = [ModelMessage(role="system", content=full_prompt)]
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
