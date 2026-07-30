from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
from app.core.database import SessionLocal
from app.models.agent import Chat, Message, Agent, Memory
from app.services.model import model_service, Message as ModelMessage
from app.services.tools import tool_registry
from app.core.pagination import paginate
from app.core.tokens import count_tokens
from app.services.knowledge import knowledge_service
from app.services.personality import get_personality_prompt

router = APIRouter()


class ChatCreate(BaseModel):
    project_id: Optional[int] = None
    agent_id: str = "general"
    title: str = "New Chat"
    personality_level: int = 50
    model: Optional[str] = None


class ChatResponse(BaseModel):
    id: int
    project_id: Optional[int]
    agent_id: str
    title: str
    is_pinned: bool = False
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
        query = query.order_by(Chat.is_pinned.desc(), Chat.updated_at.desc())
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
            personality_level=chat.personality_level,
            model=chat.model,
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


@router.get("/{chat_id}/export")
async def export_chat(chat_id: int, format: str = "json"):
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        messages = (
            db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
            .all()
        )

        if format == "markdown":
            lines = [f"# {chat.title}\n"]
            lines.append(f"Agent: {chat.agent_id}\n")
            lines.append(f"Created: {chat.created_at}\n\n")
            lines.append("---\n\n")
            for msg in messages:
                role = "User" if msg.role == "user" else "Assistant"
                lines.append(f"**{role}** ({msg.created_at}):\n")
                lines.append(f"{msg.content}\n\n")
            return {
                "format": "markdown",
                "content": "".join(lines),
                "filename": f"{chat.title}.md",
            }
        else:
            return {
                "format": "json",
                "content": {
                    "chat": {
                        "id": chat.id,
                        "title": chat.title,
                        "agent_id": chat.agent_id,
                        "created_at": str(chat.created_at),
                    },
                    "messages": [
                        {
                            "role": msg.role,
                            "content": msg.content,
                            "created_at": str(msg.created_at),
                        }
                        for msg in messages
                    ],
                },
                "filename": f"{chat.title}.json",
            }
    finally:
        db.close()


class ChatUpdate(BaseModel):
    title: Optional[str] = None
    agent_id: Optional[str] = None
    is_pinned: Optional[bool] = None


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
        if update.is_pinned is not None:
            chat.is_pinned = update.is_pinned
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
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    personality_level: Optional[int] = None
    use_tools: bool = True


class SendResponse(BaseModel):
    user_message: MessageResponse
    ai_message: MessageResponse
    token_usage: dict


def _get_agent_prompt(agent_id: str) -> str:
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
        if agent:
            return agent.identity or agent.system_prompt or "你是一个有帮助的AI助手。"
        return "你是一个有帮助的AI助手。"
    finally:
        db.close()





def _get_memory_prompt(agent_id: str, user_id: str = "default") -> str:
    db = SessionLocal()
    try:
        memories = (
            db.query(Memory)
            .filter(Memory.agent_id == agent_id, Memory.user_id == user_id)
            .all()
        )
        if not memories:
            return ""
        lines = ["用户偏好和记忆："]
        for m in memories:
            lines.append(f"- {m.key}: {m.value}")
        return "\n".join(lines)
    finally:
        db.close()


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
        personality_prompt = get_personality_prompt(chat.personality_level if request.personality_level is None else request.personality_level)
        memory_prompt = _get_memory_prompt(chat.agent_id)
        knowledge_context = ""
        if chat.project_id:
            knowledge_context = knowledge_service.get_context(chat.project_id, request.content)
        full_prompt = system_prompt
        if personality_prompt:
            full_prompt += "\n\n" + personality_prompt
        if memory_prompt:
            full_prompt += "\n\n" + memory_prompt
        if knowledge_context:
            full_prompt += "\n\n" + knowledge_context
        model_messages = [ModelMessage(role="system", content=full_prompt)]
        for msg in history:
            model_messages.append(ModelMessage(role=msg.role, content=msg.content))

        agent_for_caps = db.query(Agent).filter(Agent.agent_id == chat.agent_id).first()
        allowed_tools = set(agent_for_caps.capabilities) if agent_for_caps else None
        try:
            tools_arg = None
            if request.use_tools and allowed_tools is not None:
                if allowed_tools:
                    tools_arg = [t for t in tool_registry.get_definitions() if t["function"]["name"] in allowed_tools]
                else:
                    tools_arg = []
            ai_response = await model_service.chat(
                model_id=chat.model or request.model or "mimo-v2.5-pro",
                messages=model_messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                tools=tools_arg,
            )
            ai_content = ai_response.content
            api_usage = ai_response.usage if hasattr(ai_response, 'usage') else None
        except Exception as e:
            ai_content = f"[AI回复失败: {str(e)}]"
            api_usage = None

        ai_msg = Message(chat_id=chat_id, role="assistant", content=ai_content)
        db.add(ai_msg)
        chat.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user_msg)
        db.refresh(ai_msg)

        if api_usage and isinstance(api_usage, dict) and api_usage.get("total_tokens", 0) > 0:
            token_usage = api_usage
        else:
            prompt_tokens = count_tokens(full_prompt) + count_tokens(request.content)
            completion_tokens = count_tokens(ai_content)
            token_usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }

        return SendResponse(
            user_message=MessageResponse.model_validate(user_msg),
            ai_message=MessageResponse.model_validate(ai_msg),
            token_usage=token_usage,
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
        personality_prompt = get_personality_prompt(request.personality_level)
        memory_prompt = _get_memory_prompt(chat.agent_id)
        knowledge_context = ""
        if chat.project_id:
            knowledge_context = knowledge_service.get_context(chat.project_id, request.content)
        full_prompt = system_prompt
        if personality_prompt:
            full_prompt += "\n\n" + personality_prompt
        if memory_prompt:
            full_prompt += "\n\n" + memory_prompt
        if knowledge_context:
            full_prompt += "\n\n" + knowledge_context
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
                model_id=chat.model or request.model or "mimo-v2.5-pro",
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
