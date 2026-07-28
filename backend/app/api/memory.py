from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.core.database import SessionLocal
from app.models.agent import Memory

router = APIRouter()


class MemoryResponse(BaseModel):
    id: int
    agent_id: str
    user_id: str
    key: str
    value: str
    memory_type: str

    class Config:
        from_attributes = True


class MemoryCreate(BaseModel):
    agent_id: str
    key: str
    value: str
    memory_type: str = "preference"
    user_id: str = "default"


@router.get("/{agent_id}", response_model=List[MemoryResponse])
async def get_memories(agent_id: str, user_id: str = "default"):
    db = SessionLocal()
    try:
        return (
            db.query(Memory)
            .filter(Memory.agent_id == agent_id, Memory.user_id == user_id)
            .all()
        )
    finally:
        db.close()


@router.post("", response_model=MemoryResponse)
async def create_memory(memory: MemoryCreate):
    db = SessionLocal()
    try:
        existing = (
            db.query(Memory)
            .filter(
                Memory.agent_id == memory.agent_id,
                Memory.user_id == memory.user_id,
                Memory.key == memory.key,
            )
            .first()
        )
        if existing:
            existing.value = memory.value
            existing.memory_type = memory.memory_type
            db.commit()
            db.refresh(existing)
            return existing

        db_memory = Memory(
            agent_id=memory.agent_id,
            user_id=memory.user_id,
            key=memory.key,
            value=memory.value,
            memory_type=memory.memory_type,
        )
        db.add(db_memory)
        db.commit()
        db.refresh(db_memory)
        return db_memory
    finally:
        db.close()


@router.delete("/{memory_id}")
async def delete_memory(memory_id: int):
    db = SessionLocal()
    try:
        memory = db.query(Memory).filter(Memory.id == memory_id).first()
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")
        db.delete(memory)
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()
