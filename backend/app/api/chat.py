from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import os
from app.core.database import SessionLocal
from app.models.agent import Chat, Message, Agent, Memory, Setting, Project
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
    project_path: Optional[str] = None
    context_files: List[str] = []


class ChatResponse(BaseModel):
    id: int
    project_id: Optional[int]
    project_path: Optional[str] = None
    project_name: Optional[str] = None
    agent_id: str
    title: str
    is_pinned: bool = False
    model: Optional[str] = None
    personality_level: int = 50
    context_files: List[str] = []
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


def _chat_to_response(chat) -> ChatResponse:
    """将 Chat ORM 对象转换为响应（填充 project_path/project_name）"""
    return ChatResponse(
        id=chat.id,
        project_id=chat.project_id,
        project_path=chat.project_path or (chat.project.path if chat.project else None),
        project_name=(chat.project.name if chat.project else None),
        agent_id=chat.agent_id,
        title=chat.title,
        is_pinned=chat.is_pinned,
        model=chat.model,
        personality_level=chat.personality_level,
        context_files=chat.context_files or [],
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


@router.get("")
async def list_chats(project_id: Optional[int] = None, page: int = 1, limit: int = 50):
    db = SessionLocal()
    try:
        query = db.query(Chat)
        if project_id is not None:
            query = query.filter(Chat.project_id == project_id)
        query = query.order_by(Chat.is_pinned.desc(), Chat.updated_at.desc())
        result = paginate(query, page, limit)
        result["items"] = [_chat_to_response(c) for c in result["items"]]
        return result
    finally:
        db.close()


@router.post("", response_model=ChatResponse)
async def create_chat(chat: ChatCreate):
    db = SessionLocal()
    try:
        project_path = chat.project_path
        if project_path is None and chat.project_id is not None:
            project = db.query(Project).filter(Project.id == chat.project_id).first()
            if project:
                project_path = project.path

        context_files = [p for p in (chat.context_files or []) if p.strip()]

        db_chat = Chat(
            project_id=chat.project_id,
            project_path=project_path,
            agent_id=chat.agent_id,
            title=chat.title,
            personality_level=chat.personality_level,
            model=chat.model,
            context_files=context_files,
        )
        db.add(db_chat)
        db.commit()
        db.refresh(db_chat)
        return _chat_to_response(db_chat)
    finally:
        db.close()


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(chat_id: int):
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        return _chat_to_response(chat)
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


def _is_within(base_dir: str, file_path: str) -> bool:
    """校验 file_path 是否位于 base_dir 目录内（含自身），防止越权"""
    if not base_dir or not file_path:
        return False
    base_real = os.path.realpath(base_dir)
    file_real = os.path.realpath(file_path)
    return file_real == base_real or file_real.startswith(base_real + os.sep)


class ContextFilesRequest(BaseModel):
    paths: List[str]


@router.get("/{chat_id}/context_files")
async def get_context_files(chat_id: int):
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        return {"context_files": chat.context_files or []}
    finally:
        db.close()


@router.post("/{chat_id}/context_files")
async def add_context_files(chat_id: int, request: ContextFilesRequest):
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        base_dir = chat.project_path or (chat.project.path if chat.project else None)
        if not base_dir:
            raise HTTPException(status_code=400, detail="Chat 未关联项目，无法添加文件上下文")

        accepted: List[str] = []
        rejected: List[str] = []
        for p in request.paths:
            if not p.strip():
                continue
            if not _is_within(base_dir, p):
                rejected.append(p)
                continue
            if not os.path.exists(p):
                rejected.append(p)
                continue
            accepted.append(p)

        if rejected:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "部分路径不在项目目录内或不存在",
                    "accepted": accepted,
                    "rejected": rejected,
                },
            )

        existing = set(chat.context_files or [])
        merged = list(existing)
        for p in accepted:
            if p not in existing:
                merged.append(p)
        chat.context_files = merged
        chat.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(chat)
        return {"context_files": merged, "added": len(merged) - len(existing)}
    finally:
        db.close()


@router.delete("/{chat_id}/context_files")
async def clear_context_files(chat_id: int):
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        chat.context_files = []
        chat.updated_at = datetime.utcnow()
        db.commit()
        return {"context_files": []}
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
    model: Optional[str] = None
    personality_level: Optional[int] = None
    project_id: Optional[int] = None
    unbind_project: Optional[bool] = None


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
        if update.model is not None:
            chat.model = update.model
        if update.personality_level is not None:
            chat.personality_level = update.personality_level
        if update.unbind_project:
            chat.project_id = None
            chat.project_path = None
        elif update.project_id is not None:
            project = db.query(Project).filter(Project.id == update.project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            chat.project_id = project.id
            chat.project_path = project.path
        chat.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(chat)
        return _chat_to_response(chat)
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
    reasoning_effort: Optional[str] = None


class SendResponse(BaseModel):
    user_message: MessageResponse
    ai_message: MessageResponse
    token_usage: dict


def _get_default_model() -> str:
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == "default_model").first()
        if setting and setting.value:
            return setting.value
        return "mimo-v2.5-pro"
    finally:
        db.close()


def _get_agent_prompt(agent_id: str) -> str:
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
        if agent:
            return agent.identity or agent.system_prompt or "你是一个有帮助的AI助手。"
        return "你是一个有帮助的AI助手。"
    finally:
        db.close()





def _get_memory_prompt(agent_id: str, user_id: str = "default", project_id: Optional[int] = None) -> str:
    db = SessionLocal()
    try:
        query = db.query(Memory).filter(
            Memory.agent_id == agent_id,
            Memory.user_id == user_id,
            Memory.is_active == True,
        )
        user_memories = query.filter(Memory.memory_type.in_(["user", "preference"])).all()
        sections = []
        if user_memories:
            lines = ["用户记忆："]
            for m in user_memories:
                lines.append(f"- {m.key}: {m.value}")
            sections.append("\n".join(lines))
        if project_id is not None:
            project_memories = (
                db.query(Memory)
                .filter(
                    Memory.agent_id == agent_id,
                    Memory.user_id == user_id,
                    Memory.memory_type == "project",
                    Memory.project_id == project_id,
                    Memory.is_active == True,
                )
                .all()
            )
            if project_memories:
                lines = ["项目记忆："]
                for m in project_memories:
                    lines.append(f"- {m.key}: {m.value}")
                sections.append("\n".join(lines))
        return "\n\n".join(sections)
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
        memory_prompt = _get_memory_prompt(chat.agent_id, project_id=chat.project_id)
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
                model_id=chat.model or request.model or _get_default_model(),
                messages=model_messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                tools=tools_arg,
                reasoning_effort=request.reasoning_effort,
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
        personality_prompt = get_personality_prompt(chat.personality_level if request.personality_level is None else request.personality_level)
        memory_prompt = _get_memory_prompt(chat.agent_id, project_id=chat.project_id)
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

        effective_model = chat.model or request.model or _get_default_model()
        temperature = request.temperature
        max_tokens = request.max_tokens
        reasoning_effort = request.reasoning_effort

        db.commit()
    finally:
        db.close()

    async def generate():
        full_content = ""
        try:
            async for chunk in model_service.chat_stream(
                model_id=effective_model,
                messages=model_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
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
