from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import os
import time
import asyncio
import uuid
import logging
from app.core.database import SessionLocal
from app.models.agent import Chat, Message, Agent, Project
from app.core.pagination import paginate
from app.core.tokens import count_tokens
from app.core.tool_runtime.approval import approval_registry
from app.core.tool_runtime.choice import choice_registry, CUSTOM_TEXT_MAX
from app.core.tool_runtime.notification import event_bus, NotificationType
from app.core.tool_runtime.executor import _update_approval_status
from app.core.agent_runtime import AgentRuntime, get_chat_context_builder, ContextBuildInput
from app.core.agent_runtime.context_builder import get_default_model as _get_default_model
from app.core.agent_runtime.action_guard import needs_regeneration, find_action_descriptions, REGEN_INSTRUCTION
from app.services.memory_extractor import run_memory_extraction

logger = logging.getLogger(__name__)

router = APIRouter()


async def _call_regen_model(
    model_id: str,
    messages: list,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """输出保护：用同一模型重新生成，去掉动作描写。"""
    from app.services.model import model_service
    result = await model_service.call_once(
        model_id=model_id,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=None,
    )
    return result.content or ""


def _get_memory_settings() -> dict:
    """读取记忆三开关（读闸/写闸/提示）与权限模式。缺省或读取失败按开启处理（fail-open）。"""
    from app.models.agent import Setting
    db = SessionLocal()
    try:
        kv = {}
        for row in db.query(Setting).filter(
            Setting.key.in_(["memory_read_enabled", "memory_write_enabled", "memory_alert", "agent_permission_mode"])
        ).all():
            kv[row.key] = row.value
        def _on(key: str) -> bool:
            v = kv.get(key)
            return v is None or v.lower() != "false"
        return {
            "read": _on("memory_read_enabled"),
            "write": _on("memory_write_enabled"),
            "alert": _on("memory_alert"),
            # autonomous（权限全放开）：不弹卡、不提示，自动保存（与 ask_user_choice 同策略）
            "autonomous": (kv.get("agent_permission_mode") or "standard") == "autonomous",
        }
    finally:
        db.close()

# ── Phase 1.6: Agent 后台任务管理（HTTP 生命周期解耦）──
# Agent 执行由 chat_id 驱动的独立 asyncio.Task 承载，与 SSE 响应对象解耦。
# 前端切页/断连（未显式 cancel）只断开响应流，后台 Task 继续跑完并落库；
# 仅 POST /api/chat/{id}/cancel 显式取消。
_agent_runs: dict[int, "_AgentRun"] = {}


class _AgentRun:
    """一次 Agent 流式执行的后台句柄。

    - task: 后台 asyncio.Task（运行 agent_runtime.run_stream，独立于 HTTP 生命周期）
    - queue: 事件队列（后台 → SSE 消费者）
    - finished: 后台任务是否已结束（含 finish 事件）
    - db_persisted: assistant 消息是否已落库
    """

    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self.task: Optional["asyncio.Task"] = None
        self.finished = False
        self.db_persisted = False
        self.exception: Optional[Exception] = None


def cancel_chat_stream_task(chat_id: int) -> bool:
    """显式取消某会话正在运行的后台 Agent Task（POST /cancel / 测试用）。

    仅此入口会终止后台 LLM/工具循环；HTTP 断连不会触发取消。
    返回是否成功发起取消；Task 不存在或已结束返回 False。
    """
    run = _agent_runs.get(chat_id)
    if run is None or run.task is None or run.task.done():
        return False
    run.task.cancel()
    return True


def _cleanup_agent_run(chat_id: int) -> None:
    _agent_runs.pop(chat_id, None)


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
    attachments: Optional[List[dict]] = None  # Phase 3: 用户消息附件
    timeline: Optional[List[dict]] = None
    task_graph: Optional[dict] = None
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
        query = db.query(Chat).filter(Chat.is_deleted == False, Chat.is_archived == False)
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
            if project.is_archived:
                raise HTTPException(status_code=400, detail="Project is archived")
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
        # 已归档会话进回收站：清除归档标记
        chat.is_archived = False
        chat.archived_at = None
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


class AttachmentItem(BaseModel):
    """附件元数据：前端随 SendRequest 发送，描述一个附件文件。

    kind 取值：
      text   — 文本文件，后端读取内容注入 Prompt（需 path）
      image  — 图片，信息写入 vision_context（需 path）
      binary — 二进制文件，仅注入元数据说明，Agent 自行用工具读取（需 path）
    """
    name: str
    path: Optional[str] = None  # 相对 project_path 的路径（上传文件为 .mfkagent/uploads/xxx）
    mime: str = "application/octet-stream"
    kind: str = "text"  # "text" | "image" | "binary"
    size: int = 0


class SendRequest(BaseModel):
    content: str
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    personality_level: Optional[int] = None
    use_tools: bool = True
    reasoning_effort: Optional[str] = None
    planning_level: Optional[int] = None  # G2-B: Planner 层级控制
    attachments: List[AttachmentItem] = []  # Phase 2: 多模态附件元数据
    # Phase 3 T3/T8: auto_approve / permission_mode 已废弃，权限模式统一从 Settings 读取


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
        if request.attachments:
            user_msg.attachments = [a.model_dump() for a in request.attachments]
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

        # Phase 3 T3/T8: 权限模式统一从 Settings 读取，不再从前端参数透传

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
                attachments=request.attachments,
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

            # ──── V14.1 输出保护：零动作状态出现动作描写 → 重新生成一次 ────
            # 仅非流式路径（流式在 _persist 处处理）。comfort/roleplay/light 不拦截。
            perf_level = (built.persona_context.performance_level
                          if built.persona_context else "none")
            if ai_content and needs_regeneration(perf_level, ai_content):
                logger.info("[action_guard] regen: perf=%s hits=%s", perf_level,
                            find_action_descriptions(ai_content))
                try:
                    regen_msgs = [m.model_dump() if hasattr(m, "model_dump") else dict(m)
                                  for m in built.messages]
                    regen_msgs.append({"role": "user", "content": REGEN_INSTRUCTION})
                    regen_result = await _call_regen_model(
                        model_id=built.context.model_id,
                        messages=regen_msgs,
                        temperature=built.temperature,
                        max_tokens=built.max_tokens,
                    )
                    if regen_result and regen_result.strip():
                        ai_content = regen_result
                except Exception as e:
                    logger.warning("[action_guard] regen failed: %s", e)
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

        # Phase 10: 记忆提取（写闸 = memory_write_enabled，关闭时不提取不落库）
        mem_settings = _get_memory_settings()
        mem_actions = []
        if mem_settings["write"]:
            if mem_settings["alert"] and not mem_settings["autonomous"]:
                # 提示开启且非自治：内联完成提取，把"已保存记忆"通知随本消息落库
                try:
                    mem_actions = await run_memory_extraction(
                        chat_id=chat_id,
                        project_id=chat.project_id,
                        user_message=request.content,
                        ai_content=ai_content,
                        agent_id=chat.agent_id,
                    )
                except Exception:  # noqa: BLE001
                    mem_actions = []
            else:
                # 提示关闭或自治：后台无感提取（非阻塞，独立 Session 落库，Fail-safe）
                try:
                    asyncio.create_task(
                        run_memory_extraction(
                            chat_id=chat_id,
                            project_id=chat.project_id,
                            user_message=request.content,
                            ai_content=ai_content,
                            agent_id=chat.agent_id,
                        )
                    )
                except Exception:  # noqa: BLE001
                    pass
        if mem_actions:
            timeline.append({
                "type": "memory_saved",
                "chat_id": chat_id,
                "count": len(mem_actions),
                "items": [
                    {
                        "memory_type": (a.get("memory_type") or "fact"),
                        "content": (a.get("content") or ""),
                    }
                    for a in mem_actions
                ],
            })
            ai_msg.timeline = timeline
            db.commit()
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
        if request.attachments:
            user_msg.attachments = [a.model_dump() for a in request.attachments]
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

        # Phase 3 T3/T8: 权限模式统一从 Settings 读取，不再从前端参数透传

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
                attachments=request.attachments,
            )
        )

        # 捕获纯数据局部变量：生成器在 db.close() 之后执行，不得引用 ORM 实例
        agent_context = built.context
        model_messages = built.messages
        temperature = built.temperature
        max_tokens = built.max_tokens
        reasoning_effort = built.reasoning_effort
        read_only = built.read_only
        mem_project_id = chat.project_id
        mem_user_content = request.content
        mem_agent_id = chat.agent_id
        # V14.1: 输出保护所需纯数据快照（生成器在 db.close() 后执行）
        mem_perf_level = (built.persona_context.performance_level
                          if built.persona_context else "none")
        mem_model_id = built.context.model_id
        mem_model_messages = [
            m.model_dump() if hasattr(m, "model_dump") else dict(m)
            for m in built.messages
        ]
    finally:
        db.close()

    # ── Phase 1.6: Agent 后台任务与 SSE 生命周期解耦 ──
    # 后台 asyncio.Task 独立运行 AgentRuntime.run_stream，与 SSE HTTP 响应解耦。
    # 前端切页/断连只断开 SSE 消费者，后台 Task 继续跑完并落库；
    # 仅 POST /api/chat/{id}/cancel 显式取消。
    # 若同一 chat 已有运行中的后台任务，先取消旧任务
    if chat_id in _agent_runs:
        cancel_chat_stream_task(chat_id)

    run = _AgentRun(chat_id)
    _agent_runs[chat_id] = run

    async def _background_agent():
        """后台 Agent 执行：独立于 SSE 生命周期，事件写入队列供消费，结果落库。"""
        full_content = ""
        full_thinking = ""
        thinking_chunk_count = 0
        thinking_total_chars = 0
        recorded_tool_calls: List[dict] = []
        timeline_events: List[dict] = []
        # 待落盘的 text 缓冲段：遇到工具事件时先 flush，
        # 使 timeline 保留“文本→工具→文本”的真实交错时序（而非全部文本合并到末尾）
        pending_text = ""
        # 记忆三开关快照（读闸/写闸/提示/自治），生成器内 db 已关闭，必须自行查询
        mem_settings = _get_memory_settings()

        def _put(event):
            """非阻塞写入队列；客户端断连或队列满时跳过（不影响后台执行）。"""
            try:
                run.queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        def _memory_saved_event(actions: list) -> dict:
            """将提取动作列表压缩为前端紧凑通知事件（正文预览不截断，前端 ellipsis 收尾）。"""
            return {
                "type": "memory_saved",
                "chat_id": chat_id,
                "count": len(actions),
                "items": [
                    {
                        "memory_type": (a.get("memory_type") or "fact"),
                        "content": (a.get("content") or ""),
                    }
                    for a in actions
                ],
            }

        def _persist():
            """将 assistant 消息落库（正常完成/取消/异常均调用）。"""
            nonlocal pending_text
            # flush 残余文本段：三条落库路径（正常/取消/异常）统一覆盖
            if pending_text:
                timeline_events.append({"type": "text", "content": pending_text})
                pending_text = ""
            if not full_content and not full_thinking and not recorded_tool_calls:
                return
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

                # 收集数据供 DB 持久化
                if etype == "thinking":
                    content = chunk.get("content", "")
                    full_thinking += content
                    thinking_chunk_count += 1
                    thinking_total_chars += len(content)
                    timeline_events.append({"type": "thinking", "content": content})
                elif etype == "text":
                    piece = chunk.get("content", "")
                    full_content += piece
                    pending_text += piece
                elif etype == "tool_calls":
                    recorded_tool_calls = chunk.get("calls") or recorded_tool_calls
                elif etype in ("tool_start", "tool_result", "tool_approval", "choice_request"):
                    if pending_text:
                        timeline_events.append({"type": "text", "content": pending_text})
                        pending_text = ""
                    timeline_events.append(chunk)

                # 转发事件给 SSE 消费者（非阻塞）
                _put(chunk)

            if thinking_chunk_count > 0:
                logger.info(
                    "Phase12 SSE thinking: chat_id=%s chunks=%d total_chars=%d",
                    chat_id, thinking_chunk_count, thinking_total_chars,
                )

            # V14.1 输出保护：零动作状态出现动作描写 → 重新生成一次（落库前修正）
            if full_content and needs_regeneration(mem_perf_level, full_content):
                logger.info("[action_guard] stream regen: chat=%s perf=%s hits=%s",
                            chat_id, mem_perf_level, find_action_descriptions(full_content))
                try:
                    regen_msgs = list(mem_model_messages)
                    regen_msgs.append({"role": "user", "content": REGEN_INSTRUCTION})
                    new_content = await _call_regen_model(
                        model_id=mem_model_id,
                        messages=regen_msgs,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    if new_content.strip():
                        full_content = new_content
                        pending_text = ""
                except Exception as e:
                    logger.warning("[action_guard] stream regen failed: %s", e)

            # ── Phase 10: 记忆提取（写闸 = memory_write_enabled）──
            # 写闸关闭 → 完全不提取（记忆落库不做）。写闸开启但提示关闭或自治模式 → 后台无感提取。
            # 写闸开启且提示开启且非自治 → 内联完成，通知随消息落库并推入流。
            memory_saved_notice = None
            if mem_settings["write"]:
                if mem_settings["alert"] and not mem_settings["autonomous"]:
                    try:
                        mem_actions = await run_memory_extraction(
                            chat_id=chat_id,
                            project_id=mem_project_id,
                            user_message=mem_user_content,
                            ai_content=full_content,
                            agent_id=mem_agent_id,
                        )
                    except Exception as e:  # noqa: BLE001
                        logger.warning("memory extraction failed: %s", e, exc_info=True)
                        mem_actions = []
                    if mem_actions:
                        memory_saved_notice = _memory_saved_event(mem_actions)
                        timeline_events.append(memory_saved_notice)
                else:
                    try:
                        asyncio.create_task(
                            run_memory_extraction(
                                chat_id=chat_id,
                                project_id=mem_project_id,
                                user_message=mem_user_content,
                                ai_content=full_content,
                                agent_id=mem_agent_id,
                            )
                        )
                    except Exception:  # noqa: BLE001
                        pass

            # DB 持久化（无论客户端是否断连，始终执行）
            _persist()
            run.db_persisted = True

            # 记忆保存通知推入流（在哨兵之前，保证 SSE 客户端可达）
            if memory_saved_notice is not None:
                _put(memory_saved_notice)

            # Phase 3 T3/T8: 发布任务完成通知
            event_bus.task_completed(
                chat_id=chat_id,
                task_description="Agent 任务完成",
                success=True,
                result_summary=full_content[:200] if full_content else "",
            )

        except asyncio.CancelledError:
            logger.info("Agent background task cancelled: chat_id=%s", chat_id)
            # 即使被取消也持久化已有结果
            _persist()
            run.db_persisted = True
            raise
        except Exception as e:
            logger.error("Agent background task error: chat_id=%s error=%s", chat_id, e)
            # run_stream 已在 yield error 事件后 raise，此处不再重复发送
            run.exception = e
            # Phase 3 T3/T8: 发布错误通知
            event_bus.error(
                chat_id=chat_id,
                error_type="agent_error",
                error_message=str(e)[:200],
                recoverable=False,
            )
        finally:
            # 通知 SSE 消费者结束
            _put(None)
            run.finished = True
            # 清理未决审批与未决抉择
            approval_registry.cancel_by_chat(chat_id)
            choice_registry.cancel_by_chat(chat_id)
            # 清理注册表
            _agent_runs.pop(chat_id, None)

    # 启动后台任务
    run.task = asyncio.create_task(_background_agent())

    # SSE 生成器：仅从队列消费事件，格式化后转发给客户端
    async def generate():
        buffer = ""
        last_flush = time.monotonic()
        BATCH_MAX_CHARS = 200
        BATCH_INTERVAL = 0.02

        def _should_flush() -> bool:
            return len(buffer) >= BATCH_MAX_CHARS or (time.monotonic() - last_flush) >= BATCH_INTERVAL

        try:
            while True:
                chunk = await run.queue.get()
                if chunk is None:  # 哨兵：后台任务已结束
                    if buffer:
                        yield f"data: {json.dumps({'type': 'text', 'content': buffer})}\n\n"
                        buffer = ""
                    yield "data: [DONE]\n\n"
                    break

                etype = chunk.get("type")

                # 思考段：立即透传
                if etype == "thinking":
                    yield f"data: {json.dumps(chunk)}\n\n"
                    continue

                # 文本增量：攒批
                if etype == "text":
                    buffer += chunk.get("content", "")
                    if _should_flush():
                        yield f"data: {json.dumps({'type': 'text', 'content': buffer})}\n\n"
                        buffer = ""
                        last_flush = time.monotonic()
                    continue

                # 其他事件：先 flush buffer，再透传
                if buffer:
                    yield f"data: {json.dumps({'type': 'text', 'content': buffer})}\n\n"
                    buffer = ""
                    last_flush = time.monotonic()
                yield f"data: {json.dumps(chunk)}\n\n"

        except asyncio.CancelledError:
            # 客户端断连 — 不取消后台任务，Agent 继续执行并落库
            logger.info("[INFO] SSE consumer disconnected: chat_id=%s (background task continues)", chat_id)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/{chat_id}/cancel")
async def cancel_chat(chat_id: int):
    """Phase 1.6: 显式取消会话正在运行的后台 Agent Task。

    只有此端点会终止后台 LLM/工具执行循环；HTTP 断连不会触发取消。
    """
    if cancel_chat_stream_task(chat_id):
        logger.info("Chat cancelled via /cancel: chat_id=%s", chat_id)
        return {"status": "ok", "chat_id": chat_id, "action": "cancelled"}
    raise HTTPException(status_code=404, detail="No active agent task for this chat")


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


class ApproveRequest(BaseModel):
    # Phase 1.5 新契约（推荐）：按 tool_call_id 决策
    tool_call_id: Optional[str] = None
    decision: Optional[str] = None  # "approved" | "rejected"
    # 兼容旧契约：approval_id + action
    approval_id: Optional[str] = None
    action: Optional[str] = None  # "approve" | "deny"


def _normalize_decision(request: ApproveRequest) -> Optional[str]:
    """将请求归一化为 (approval_id, action)。新契约决策映射：
    decision="approved" → action="approve"；"rejected" → "deny"。"""
    if request.tool_call_id is not None or request.decision is not None:
        if not request.tool_call_id:
            raise HTTPException(status_code=422, detail="tool_call_id 不能为空")
        if request.decision not in ("approved", "rejected"):
            raise HTTPException(status_code=422, detail="decision 必须是 approved 或 rejected")
        info = approval_registry.find_by_tool_call_id(request.tool_call_id)
        if not info:
            raise HTTPException(status_code=404, detail="审批不存在或已处理")
        return info["approval_id"], "approve" if request.decision == "approved" else "deny"

    if not request.approval_id:
        raise HTTPException(status_code=422, detail="tool_call_id 或 approval_id 必须提供")
    if request.action not in ("approve", "deny"):
        raise HTTPException(status_code=422, detail="action 必须是 approve 或 deny")
    return request.approval_id, request.action


@router.post("/{chat_id}/approve")
async def approve_command(chat_id: int, request: ApproveRequest):
    """Phase 1.5: 审批流决策接口（用户同意/拒绝挂起的命令执行）。

    新契约（推荐）：{"tool_call_id": "...", "decision": "approved" | "rejected"}
      按 tool_call_id 反查待审批操作，仅允许已注册的 tool_call_id。
    兼容旧契约：{"approval_id": "...", "action": "approve" | "deny"}。

    返回:
        - 200: {"status": "ok", "approval_id": "...", "action": "approve|deny", "tool": ..., "command": ...}
        - 404: 审批不存在、不属于该会话或已处理
        - 409: 审批已处理或已超时
        - 422: 参数缺失或 decision/action 非法
    """
    approval_id, action = _normalize_decision(request)

    info = approval_registry.get(approval_id)
    if not info:
        raise HTTPException(status_code=404, detail="审批不存在")
    if info.get("chat_id") != chat_id:
        raise HTTPException(status_code=404, detail="审批不属于该会话")

    if not approval_registry.resolve(approval_id, action):
        raise HTTPException(status_code=409, detail="审批已处理或已超时")

    # Phase 3 T3/T8: 同步更新 approval_requests 表状态
    _update_approval_status(approval_id, action)

    # Phase 3 T3/T8: 发布审批完成通知（RuntimeEventBus）
    event_bus.approval_completed(
        chat_id=chat_id,
        approval_id=approval_id,
        tool_call_id=info.get("tool_call_id", ""),
        tool=info.get("tool", ""),
        action=action,
    )

    logger.info(
        "Phase15 approve: chat_id=%s approval_id=%s decision=%s tool=%s command=%s",
        chat_id, approval_id, "approved" if action == "approve" else "rejected",
        info.get("tool", ""), info.get("command", "")[:100],
    )

    return {
        "status": "ok",
        "approval_id": approval_id,
        "action": action,
        "tool": info.get("tool", ""),
        "command": info.get("command", ""),
    }


class ChoiceResolutionRequest(BaseModel):
    choice_id: str
    selected: Optional[int] = None      # 选中预设选项下标（与 custom_text 二选一）
    custom_text: Optional[str] = None   # 用户自定义想法


@router.post("/{chat_id}/choice")
async def resolve_choice(chat_id: int, request: ChoiceResolutionRequest):
    """用户对 ask_user_choice 抉择卡的反馈（对齐 /approve 契约风格）。

    selected 与 custom_text 至少提供一项；抉择不存在、不属于该会话或已处理时返回错误。
    """
    if request.selected is None and not (request.custom_text or "").strip():
        raise HTTPException(status_code=422, detail="selected 或 custom_text 必须提供其一")

    info = choice_registry.get(request.choice_id)
    if not info or info.get("chat_id") != chat_id:
        raise HTTPException(status_code=404, detail="抉择不存在或不属于该会话")

    custom_text = (request.custom_text or "").strip()[:CUSTOM_TEXT_MAX] or None
    if not choice_registry.resolve(request.choice_id, {
        "selected": request.selected,
        "custom_text": custom_text,
    }):
        raise HTTPException(status_code=409, detail="抉择已处理或已超时")

    return {"status": "ok", "choice_id": request.choice_id}


# ──────────────────────────────────────────────────────────────────────────
# Phase 2: 附件上传（严密版加固：始终加唯一前缀防覆盖 + 10MB 硬上限 + 返回原始名）
# ──────────────────────────────────────────────────────────────────────────

# 单文件上传大小硬上限（10MB，超限返回 HTTP 400）
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

# 文本类附件：后端直接读取内容注入 Prompt 的白名单扩展名
_TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".rst", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".json", ".yaml", ".yml", ".xml", ".html", ".htm", ".css", ".scss", ".less",
    ".java", ".kt", ".swift", ".go", ".rs", ".c", ".cpp", ".cc", ".h", ".hpp",
    ".cs", ".rb", ".php", ".sh", ".bash", ".zsh", ".sql", ".ini", ".toml",
    ".cfg", ".conf", ".log", ".csv", ".tsv", ".vue", ".svelte",
}

# 图片类附件 MIME 前缀
_IMAGE_MIME_PREFIX = "image/"

# 图片类附件扩展名兜底白名单（部分上传链路 MIME 丢失/退化成 octet-stream，需按扩展名兜底识别为 image）
_IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif",
    ".svg", ".ico", ".heic", ".heif", ".avif",
}


def _detect_attachment_kind(filename: str, mime: str) -> str:
    """根据文件名扩展名与 MIME 推断附件 kind：text / image / binary。

    分类优先级：
    1. MIME 以 image/ 开头 → image（标准情况）
    2. 文件扩展名命中 _IMAGE_EXTS → image（MIME 丢失/退化为 octet-stream 时的兜底）
    3. 文件扩展名命中 _TEXT_EXTS → text
    4. 其余 → binary

    text/binary 分类逻辑保持不变；仅新增图片扩展名兜底。
    """
    if mime and mime.startswith(_IMAGE_MIME_PREFIX):
        return "image"
    _, ext = os.path.splitext(filename.lower())
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _TEXT_EXTS:
        return "text"
    return "binary"


def _build_unique_disk_name(original_name: str) -> str:
    """生成防覆盖磁盘文件名：<timestamp>_<uuid8>_<original_name>。

    - 始终加唯一前缀，彻底杜绝同名覆盖历史文件
    - original_name 经 os.path.basename 防路径穿越
    - 返回的磁盘文件名（含前缀），供落盘使用；返回给前端的 name 仍为原始名
    """
    safe_base = os.path.basename(original_name or "unnamed") or "unnamed"
    ts = int(time.time())
    uid = uuid.uuid4().hex[:8]
    return f"{ts}_{uid}_{safe_base}"


@router.post("/{chat_id}/upload", response_model=AttachmentItem)
async def upload_attachment(chat_id: int, file: UploadFile = File(...)):
    """上传附件文件，保存至 {project_path}/.mfkagent/uploads/，返回 AttachmentItem。

    严密版加固：
    - 🚨 校验 chat.project_path，未关联项目直接 HTTP 400
    - 🛡️ 始终加 `<timestamp>_<uuid8>_<original>` 前缀落盘，彻底防覆盖
    - 🛡️ 返回的 AttachmentItem.name 保持原始文件名（不含前缀）
    - 🛡️ 单文件最大 10MB，写入超限立即终止并删除残留文件，返回 HTTP 400
    - 返回 path 为相对 project_path 的路径（如 .mfkagent/uploads/123_abc_x.png）
    """
    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        project_path = chat.project_path or (chat.project.path if chat.project else None)

        # 上传目录：有项目时存到 {project_path}/.mfkagent/uploads/，无项目时存到全局 data/uploads/{chat_id}/
        if project_path:
            upload_dir = os.path.join(project_path, ".mfkagent", "uploads")
        else:
            # 无项目关联：使用后端全局上传目录
            global_upload_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "uploads", str(chat_id))
            upload_dir = global_upload_root
        os.makedirs(upload_dir, exist_ok=True)

        # 始终加唯一前缀落盘（防覆盖）；返回 name 仍为原始文件名
        original_name = file.filename or "unnamed"
        disk_name = _build_unique_disk_name(original_name)
        dest = os.path.join(upload_dir, disk_name)

        # 流式写入 + 大小硬上限校验（超限立即终止，删除残留文件）
        size = 0
        oversized = False
        try:
            with open(dest, "wb") as f:
                while True:
                    chunk = await file.read(64 * 1024)  # 64KB chunks
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_UPLOAD_SIZE:
                        oversized = True
                        break
                    f.write(chunk)
        except OSError:
            # 写入异常：清理残留文件，避免脏数据
            try:
                if os.path.exists(dest):
                    os.remove(dest)
            except OSError:
                pass
            raise HTTPException(status_code=500, detail="附件写入磁盘失败")

        if oversized:
            # 超限：删除已写部分，返回 400
            try:
                os.remove(dest)
            except OSError:
                pass
            raise HTTPException(
                status_code=400,
                detail=f"附件过大（单文件上限 10MB，已接收 {size} 字节）",
            )

        # 路径：有项目时返回相对路径（正斜杠跨平台一致），无项目时返回绝对路径
        if project_path:
            rel_path = os.path.relpath(dest, project_path).replace(os.sep, "/")
        else:
            rel_path = dest.replace(os.sep, "/")
        mime = file.content_type or "application/octet-stream"
        # kind 推断基于原始文件名（扩展名未被前缀影响）
        kind = _detect_attachment_kind(original_name, mime)

        return AttachmentItem(
            name=original_name,  # 返回原始文件名（不含 timestamp_uuid 前缀）
            path=rel_path,
            mime=mime,
            kind=kind,
            size=size,
        )
    finally:
        db.close()


@router.get("/{chat_id}/file")
async def serve_attachment_file(chat_id: int, path: str):
    """提供附件文件（图片等）供前端渲染。
    
    Query params:
        path: 附件相对路径（如 .mfkagent/uploads/xxx.png）
    
    安全：仅允许访问项目路径下的 .mfkagent/uploads/ 目录。
    """
    from fastapi.responses import FileResponse
    import mimetypes

    db = SessionLocal()
    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        project_path = chat.project_path
        if not project_path:
            raise HTTPException(status_code=400, detail="Chat 未绑定项目路径")
        
        # 安全检查：仅允许 .mfkagent/uploads/ 下的文件
        normalized = os.path.normpath(path).replace("\\", "/")
        if not normalized.startswith(".mfkagent/uploads/"):
            raise HTTPException(status_code=403, detail="仅允许访问上传目录下的文件")
        
        abs_path = os.path.join(project_path, normalized)
        abs_path = os.path.normpath(abs_path)
        if not abs_path.startswith(os.path.normpath(project_path)):
            raise HTTPException(status_code=403, detail="路径越界")
        
        if not os.path.isfile(abs_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        mime, _ = mimetypes.guess_type(abs_path)
        return FileResponse(abs_path, media_type=mime or "application/octet-stream")
    finally:
        db.close()
