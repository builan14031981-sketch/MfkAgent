from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import os
import time
from app.core.database import SessionLocal
from app.models.agent import Chat, Message, Agent, Project
from app.core.pagination import paginate
from app.core.tokens import count_tokens
from app.core.tool_runtime.approval import approval_registry
from app.core.agent_runtime import AgentRuntime, get_chat_context_builder, ContextBuildInput
from app.core.agent_runtime.context_builder import get_default_model as _get_default_model

router = APIRouter()


class ChatCreate(BaseModel):
    project_id: Optional[int] = None
    agent_id: Optional[str] = None
    title: str = "New Chat"
    personality_level: Optional[int] = None
    model: Optional[str] = None
    thinking_mode: Optional[str] = None
    mode: Optional[str] = None
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
    personality_level: Optional[int] = None
    thinking_mode: str = "none"
    mode: str = "build"
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
    thinking: Optional[str] = None
    tool_calls: Optional[List[dict]] = None
    timeline: Optional[List[dict]] = None
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
        thinking_mode=chat.thinking_mode or "none",
        mode=chat.mode or "build",
        context_files=chat.context_files or [],
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


@router.get("")
async def list_chats(project_id: Optional[int] = None, page: int = 1, limit: int = 50):
    db = SessionLocal()
    try:
        query = db.query(Chat).filter(Chat.is_deleted == False)
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
        agent_id = chat.agent_id or "general"
        project_path = None
        project_id = chat.project_id

        # 项目继承校验：project_id 存在时，校验 Project 存在并精确绑定 project_path
        if project_id is not None:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            project_path = project.path

        if project_path is None and chat.project_path:
            project_path = chat.project_path

        context_files = [p for p in (chat.context_files or []) if p.strip()]
        thinking_mode = chat.thinking_mode or "none"
        mode = chat.mode or "build"

        # 人格快照：request 未显式提供 personality_level 时，从 Agent.default_personality_level 快照。
        # Agent 默认 NULL（无人格）→ Chat.personality_level=NULL → 不注入 personality prompt。
        personality_level = chat.personality_level
        if personality_level is None and agent_id:
            agent_ctx = db.query(Agent).filter(Agent.agent_id == agent_id).first()
            if agent_ctx:
                personality_level = agent_ctx.default_personality_level

        db_chat = Chat(
            project_id=project_id,
            project_path=project_path,
            agent_id=agent_id,
            title=chat.title,
            personality_level=personality_level,
            model=chat.model,
            thinking_mode=thinking_mode,
            mode=mode,
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
    """软删除：移入回收站"""
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        chat.is_deleted = True
        chat.deleted_at = datetime.utcnow()
        chat.updated_at = datetime.utcnow()
        db.commit()
        return {"status": "trashed"}
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
    thinking_mode: Optional[str] = None
    mode: Optional[str] = None
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
        if update.thinking_mode is not None:
            chat.thinking_mode = update.thinking_mode
        if update.mode is not None:
            chat.mode = update.mode
        if update.unbind_project:
            chat.project_id = None
            chat.project_path = None
        elif update.project_id is not None:
            project = db.query(Project).filter(Project.id == update.project_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            chat.project_id = project.id
            chat.project_path = project.path
        # 置顶/取消置顶不刷新 updated_at：取消置顶后应回到按更新时间排序的原位置，
        # 而非因时间被刷新而跳到列表最顶部。仅内容性变更才更新排序时间。
        has_content_change = (
            update.title is not None
            or update.agent_id is not None
            or update.model is not None
            or update.personality_level is not None
            or update.thinking_mode is not None
            or update.mode is not None
            or update.unbind_project
            or update.project_id is not None
        )
        if has_content_change:
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


@router.delete("/{chat_id}/messages/{message_id}")
async def delete_message_from(chat_id: int, message_id: int):
    """删除指定消息及其之后的所有消息（用于重生成 / 编辑时清空后续历史）"""
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        target = (
            db.query(Message)
            .filter(Message.id == message_id, Message.chat_id == chat_id)
            .first()
        )
        if not target:
            raise HTTPException(status_code=404, detail="Message not found")

        # 按主键自增顺序，删除该消息及其之后的所有消息
        to_delete = (
            db.query(Message)
            .filter(Message.chat_id == chat_id, Message.id >= message_id)
            .order_by(Message.id.asc())
            .all()
        )
        for m in to_delete:
            db.delete(m)
        chat.updated_at = datetime.utcnow()
        db.commit()
        return {"deleted": len(to_delete)}
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
    planning_level: Optional[int] = None  # G2-B: Planner 层级控制


class SendResponse(BaseModel):
    user_message: MessageResponse
    ai_message: MessageResponse
    token_usage: dict


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

        # 释放写事务：模型工具（如 add_memory）在独立 Session 中写库，
        # 若此处仍持有未提交的写锁，SQLite 会报 database is locked。
        # 同时确保 ChatContextBuilder 在新 Session 中能读到刚写入的 user_msg。
        db.commit()

        # Phase E3: ChatContextBuilder 统一组装（AgentContext + system prompt + messages + 参数）
        built = await get_chat_context_builder().build(
            ContextBuildInput(
                chat_id=chat_id,
                content=request.content,
                model=request.model,
                personality_level=request.personality_level,
                use_tools=request.use_tools,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                reasoning_effort=request.reasoning_effort,
                planning_level=request.planning_level,
            )
        )

        full_prompt = built.system_prompt
        memory_text = built.memory_text

        try:
            agent_runtime = AgentRuntime()
            agent_result = await agent_runtime.run(
                context=built.context,
                messages=built.messages,
                temperature=built.temperature,
                max_tokens=built.max_tokens,
                reasoning_effort=built.reasoning_effort,
                read_only=built.read_only,
            )

            ai_content = agent_result.content
            api_usage = agent_result.usage
        except Exception as e:
            ai_content = f"[AI回复失败: {str(e)}]"
            api_usage = None

        ai_msg = Message(chat_id=chat_id, role="assistant", content=ai_content)
        # 非流式路径：从 AgentResult 构造 timeline（仅有 tool_start/tool_result/text）
        timeline = []
        try:
            _result = agent_result
        except NameError:
            _result = None
        if _result and _result.tool_calls:
            for tc in _result.tool_calls:
                tc_id = tc.get("tool_call_id", "")
                tc_name = tc.get("tool", tc.get("name", ""))
                tc_input = tc.get("input", getattr(tc, "input", {}))
                timeline.append({
                    "type": "tool_start",
                    "tool_call_id": tc_id,
                    "tool": tc_name,
                    "input": tc_input,
                })
                timeline.append({
                    "type": "tool_result",
                    "tool_call_id": tc_id,
                    "tool": tc_name,
                    "success": tc.get("success", False),
                    "result": tc.get("result", ""),
                    "duration_ms": tc.get("duration_ms", 0),
                })
        if ai_content:
            timeline.append({"type": "text", "content": ai_content})
        if timeline:
            ai_msg.timeline = timeline
        db.add(ai_msg)
        chat.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user_msg)
        db.refresh(ai_msg)

        if api_usage and isinstance(api_usage, dict) and api_usage.get("total_tokens", 0) > 0:
            token_usage = api_usage
        else:
            prompt_tokens = count_tokens(full_prompt) + count_tokens(memory_text or "") + count_tokens(request.content)
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

        # 释放写事务：模型工具（如 add_memory）在独立 Session 中写库，
        # 若此处仍持有未提交的写锁，SQLite 会报 database is locked。
        # 同时确保 ChatContextBuilder 在新 Session 中能读到刚写入的 user_msg。
        db.commit()

        # Phase E3: ChatContextBuilder 统一组装（AgentContext + system prompt + messages + 参数）
        built = await get_chat_context_builder().build(
            ContextBuildInput(
                chat_id=chat_id,
                content=request.content,
                model=request.model,
                personality_level=request.personality_level,
                use_tools=request.use_tools,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                reasoning_effort=request.reasoning_effort,
                planning_level=request.planning_level,
            )
        )

        # 捕获纯数据局部变量：生成器在 db.close() 之后执行，不得引用 ORM 实例
        agent_context = built.context
        model_messages = built.messages
        temperature = built.temperature
        max_tokens = built.max_tokens
        reasoning_effort = built.reasoning_effort
        read_only = built.read_only
    finally:
        db.close()

    async def generate():
        full_content = ""
        full_thinking = ""
        recorded_tool_calls: List[dict] = []
        timeline_events: List[dict] = []
        buffer = ""
        last_flush = time.monotonic()
        BATCH_MAX_CHARS = 200
        BATCH_INTERVAL = 0.02  # 20ms 微型时间窗口

        def _should_flush() -> bool:
            return len(buffer) >= BATCH_MAX_CHARS or (time.monotonic() - last_flush) >= BATCH_INTERVAL

        try:
            agent_runtime = AgentRuntime()
            async for chunk in agent_runtime.run_stream(
                context=agent_context,
                messages=model_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                read_only=read_only,
            ):
                etype = chunk.get("type")

                # 思考段增量：立即透传（不攒批），前端第一时间显示"思考中/灰色思考块"
                if etype == "thinking":
                    content = chunk.get("content", "")
                    full_thinking += content
                    timeline_events.append({"type": "thinking", "content": content})
                    yield f"data: {json.dumps({'type': 'thinking', 'content': content})}\n\n"
                    continue

                # 文本增量：攒批打包为一个 SSE 事件，减轻前端高频 DOM 渲染压力
                if etype == "text":
                    content = chunk.get("content", "")
                    full_content += content
                    buffer += content
                    if _should_flush():
                        yield f"data: {json.dumps({'type': 'text', 'content': buffer})}\n\n"
                        buffer = ""
                        last_flush = time.monotonic()
                    continue

                # 工具调用汇总：仅记录，不直接透传（前端用 tool_start/tool_result 实时渲染）
                if etype == "tool_calls":
                    recorded_tool_calls = chunk.get("calls") or recorded_tool_calls
                    continue

                # 其余事件（tool_start/tool_result/finish/error）：先 flush 残留 buffer，再原样透传
                if buffer:
                    yield f"data: {json.dumps({'type': 'text', 'content': buffer})}\n\n"
                    buffer = ""
                    last_flush = time.monotonic()
                # 轨迹事件写入 timeline（过滤 SSE 控制信号 finish/error）
                if etype in ("tool_start", "tool_result", "tool_approval"):
                    timeline_events.append(chunk)
                yield f"data: {json.dumps(chunk)}\n\n"

            # 流结束：flush 剩余 buffer
            if buffer:
                yield f"data: {json.dumps({'type': 'text', 'content': buffer})}\n\n"
                buffer = ""

            # 记录最终 text 轨迹事件（完整内容，非增量片段）
            if full_content:
                timeline_events.append({"type": "text", "content": full_content})

            db2 = SessionLocal()
            try:
                chat2 = db2.query(Chat).filter(Chat.id == chat_id).first()
                ai_msg = Message(
                    chat_id=chat_id,
                    role="assistant",
                    content=full_content,
                    thinking=full_thinking or None,
                    tool_calls=recorded_tool_calls if recorded_tool_calls else None,
                    timeline=timeline_events if timeline_events else None,
                )
                db2.add(ai_msg)
                if chat2:
                    chat2.updated_at = datetime.utcnow()
                db2.commit()
            finally:
                db2.close()

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            # 断连/结束清理：将本会话未决审批置为 cancelled，防止 Future 泄漏
            approval_registry.cancel_by_chat(chat_id)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


class CompressRequest(BaseModel):
    keep_recent: int = 4


class CompressResponse(BaseModel):
    messages: List[MessageResponse]
    compressed: bool
    original_count: int
    compressed_count: int


@router.post("/{chat_id}/compress", response_model=CompressResponse)
async def compress_chat(chat_id: int, request: CompressRequest = CompressRequest()):
    """G6-B: 会话压缩 — 将冗长历史消息提炼为摘要，减少上下文占用。

    流程：
    1. 加载当前会话全部消息
    2. 调用 AgentRuntime.compress_history 进行三段式压缩
    3. 删除旧消息，写入压缩后的新消息列表
    4. 返回压缩结果（含是否实际压缩、消息数变化）
    """
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        old_messages = (
            db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
            .all()
        )

        if not old_messages:
            return CompressResponse(
                messages=[],
                compressed=False,
                original_count=0,
                compressed_count=0,
            )

        original_count = len(old_messages)

        # 转换为 compress_history 所需格式
        msg_dicts = [{"role": m.role, "content": m.content} for m in old_messages]

        # 调用压缩引擎
        agent_runtime = AgentRuntime()
        compressed = await agent_runtime.compress_history(
            msg_dicts,
            keep_recent=request.keep_recent,
        )

        compressed_count = len(compressed)

        # 未触发压缩（中间消息不足 min_middle）→ 原样返回
        if compressed_count == original_count:
            return CompressResponse(
                messages=[MessageResponse.model_validate(m) for m in old_messages],
                compressed=False,
                original_count=original_count,
                compressed_count=compressed_count,
            )

        # 压缩成功：删除旧消息，写入新消息
        for m in old_messages:
            db.delete(m)

        new_messages = []
        for msg_dict in compressed:
            new_msg = Message(
                chat_id=chat_id,
                role=msg_dict.get("role", "user"),
                content=msg_dict.get("content", ""),
            )
            db.add(new_msg)
            db.flush()
            new_messages.append(new_msg)

        chat.updated_at = datetime.utcnow()
        db.commit()

        # refresh 后返回
        return CompressResponse(
            messages=[MessageResponse.model_validate(m) for m in new_messages],
            compressed=True,
            original_count=original_count,
            compressed_count=compressed_count,
        )
    finally:
        db.close()


class ToolApprovalRequest(BaseModel):
    approval_id: str
    action: str  # "approve" | "deny"


@router.post("/{chat_id}/tool-approval")
async def tool_approval(chat_id: int, request: ToolApprovalRequest):
    """用户对挂起命令审批的反馈（Phase B-1）。

    仅允许 approve/deny；审批不存在、不属于该会话或已处理时返回错误。
    """
    if request.action not in ("approve", "deny"):
        raise HTTPException(status_code=422, detail="action 必须是 approve 或 deny")

    info = approval_registry.get(request.approval_id)
    if not info or info.get("chat_id") != chat_id:
        raise HTTPException(status_code=404, detail="审批不存在或不属于该会话")

    if not approval_registry.resolve(request.approval_id, request.action):
        raise HTTPException(status_code=409, detail="审批已处理或已超时")

    return {"status": "ok", "approval_id": request.approval_id, "action": request.action}
