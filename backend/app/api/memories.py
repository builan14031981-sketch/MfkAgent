from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime
from app.core.database import SessionLocal
from app.models.agent import MemoryItem

router = APIRouter()

SCOPES = {"global", "project"}


class MemoryItemCreate(BaseModel):
    scope: str = "global"
    content: str

    @field_validator("scope")
    @classmethod
    def check_scope(cls, v):
        if v not in SCOPES:
            raise ValueError("scope must be global or project")
        return v


class MemoryItemResponse(BaseModel):
    id: int
    scope: str
    content: str
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
        item = MemoryItem(scope=memory.scope, content=content)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    finally:
        db.close()


@router.get("", response_model=List[MemoryItemResponse])
async def list_memory_items(scope: Optional[str] = None):
    if scope is not None and scope not in SCOPES:
        raise HTTPException(status_code=400, detail="scope must be global or project")
    db = SessionLocal()
    try:
        query = db.query(MemoryItem)
        if scope is not None:
            query = query.filter(MemoryItem.scope == scope)
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
