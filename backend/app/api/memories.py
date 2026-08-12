from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator, model_validator
from typing import List, Optional
from datetime import datetime
from app.core.database import SessionLocal
from app.models.agent import MemoryItem

router = APIRouter()

SCOPES = {"global", "agent", "project"}


class MemoryItemCreate(BaseModel):
    scope: str = "global"
    content: str
    agent_id: Optional[str] = None
    project_id: Optional[int] = None
    memory_type: str = "preference"
    confidence: float = 0.8
    source_chat_id: Optional[int] = None

    @field_validator("scope")
    @classmethod
    def check_scope(cls, v):
        if v not in SCOPES:
            raise ValueError("scope must be one of global/agent/project")
        return v

    @field_validator("memory_type")
    @classmethod
    def check_memory_type(cls, v):
        if v not in (
            "preference", "fact", "workflow", "project",
            "user_preference", "interaction_pattern", "relationship_note", "current_context",
        ):
            raise ValueError("memory_type 必须是 preference/fact/workflow/project/user_preference/interaction_pattern/relationship_note/current_context 之一")
        return v

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be in [0.0, 1.0]")
        return v

    @model_validator(mode="after")
    def check_context(self):
        if self.scope == "agent" and not self.agent_id:
            raise ValueError("agent scope 需要 agent_id")
        if self.scope == "project" and not self.project_id:
            raise ValueError("project scope 需要 project_id")
        if self.scope == "global":
            self.agent_id = None
            self.project_id = None
        return self


class MemoryItemResponse(BaseModel):
    id: int
    scope: str
    agent_id: Optional[str]
    project_id: Optional[int]
    content: str
    memory_type: str = "preference"
    confidence: float = 0.8
    source_chat_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("", response_model=MemoryItemResponse)
async def create_memory_item(memory: MemoryItemCreate):
    content = (memory.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content 不能为空")
    db = SessionLocal()
    try:
        item = MemoryItem(
            scope=memory.scope,
            agent_id=memory.agent_id,
            project_id=memory.project_id,
            content=content,
            memory_type=memory.memory_type,
            confidence=memory.confidence,
            source_chat_id=memory.source_chat_id,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    finally:
        db.close()


@router.get("", response_model=List[MemoryItemResponse])
async def list_memory_items(
    scope: Optional[str] = None,
    agent_id: Optional[str] = None,
    project_id: Optional[int] = None,
):
    if scope is not None and scope not in SCOPES:
        raise HTTPException(status_code=400, detail="scope must be one of global/agent/project")
    db = SessionLocal()
    try:
        query = db.query(MemoryItem)
        if scope is not None:
            query = query.filter(MemoryItem.scope == scope)
        if agent_id is not None:
            query = query.filter(MemoryItem.agent_id == agent_id)
        if project_id is not None:
            query = query.filter(MemoryItem.project_id == project_id)
        return query.order_by(MemoryItem.created_at.desc(), MemoryItem.id.desc()).all()
    finally:
        db.close()


@router.delete("/{memory_id}")
async def delete_memory_item(memory_id: int):
    db = SessionLocal()
    try:
        item = db.query(MemoryItem).filter(MemoryItem.id == memory_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Memory not found")
        db.delete(item)
        db.commit()
        return {"status": "deleted", "id": memory_id}
    finally:
        db.close()
