from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import List, Optional
from app.core.database import SessionLocal
from app.models.agent import Memory

router = APIRouter()

# user/project 为正式类型；preference 为旧版默认值，兼容保留，注入时按用户记忆处理
MEMORY_TYPES = {"user", "project", "preference"}


class MemoryResponse(BaseModel):
    id: int
    agent_id: str
    user_id: str
    project_id: Optional[int]
    key: str
    value: str
    memory_type: str
    is_active: bool = True

    class Config:
        from_attributes = True


class MemoryCreate(BaseModel):
    agent_id: str
    key: str
    value: str
    memory_type: str = "user"
    user_id: str = "default"
    project_id: Optional[int] = None
    is_active: bool = True

    @field_validator("memory_type")
    @classmethod
    def check_memory_type(cls, v):
        if v not in MEMORY_TYPES:
            raise ValueError(f"memory_type must be one of {sorted(MEMORY_TYPES)}")
        return v


class MemoryUpdate(BaseModel):
    key: Optional[str] = None
    value: Optional[str] = None
    memory_type: Optional[str] = None
    project_id: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("memory_type")
    @classmethod
    def check_memory_type(cls, v):
        if v is not None and v not in MEMORY_TYPES:
            raise ValueError(f"memory_type must be one of {sorted(MEMORY_TYPES)}")
        return v


@router.get("", response_model=List[MemoryResponse])
async def list_memories(
    agent_id: Optional[str] = None,
    user_id: str = "default",
    memory_type: Optional[str] = None,
    project_id: Optional[int] = None,
):
    db = SessionLocal()
    try:
        query = db.query(Memory)
        if agent_id is not None:
            query = query.filter(Memory.agent_id == agent_id)
        query = query.filter(Memory.user_id == user_id)
        if memory_type is not None:
            if memory_type not in MEMORY_TYPES:
                raise HTTPException(status_code=400, detail="memory_type must be user or project")
            query = query.filter(Memory.memory_type == memory_type)
        if project_id is not None:
            query = query.filter(Memory.project_id == project_id)
        return query.order_by(Memory.updated_at.desc()).all()
    finally:
        db.close()


@router.get("/{agent_id}", response_model=List[MemoryResponse])
async def get_memories(agent_id: str, user_id: str = "default", memory_type: Optional[str] = None):
    db = SessionLocal()
    try:
        query = db.query(Memory).filter(Memory.agent_id == agent_id, Memory.user_id == user_id)
        if memory_type is not None:
            if memory_type not in MEMORY_TYPES:
                raise HTTPException(status_code=400, detail="memory_type must be user or project")
            query = query.filter(Memory.memory_type == memory_type)
        return query.all()
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
                Memory.memory_type == memory.memory_type,
                Memory.project_id == memory.project_id,
            )
            .first()
        )
        if existing:
            existing.value = memory.value
            existing.is_active = memory.is_active
            db.commit()
            db.refresh(existing)
            return existing

        db_memory = Memory(
            agent_id=memory.agent_id,
            user_id=memory.user_id,
            project_id=memory.project_id,
            key=memory.key,
            value=memory.value,
            memory_type=memory.memory_type,
            is_active=memory.is_active,
        )
        db.add(db_memory)
        db.commit()
        db.refresh(db_memory)
        return db_memory
    finally:
        db.close()


@router.get("/detail/{memory_id}", response_model=MemoryResponse)
async def get_memory(memory_id: int):
    db = SessionLocal()
    try:
        memory = db.query(Memory).filter(Memory.id == memory_id).first()
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")
        return memory
    finally:
        db.close()


async def _apply_update(memory_id: int, update: MemoryUpdate) -> Memory:
    db = SessionLocal()
    try:
        memory = db.query(Memory).filter(Memory.id == memory_id).first()
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")
        if update.key is not None:
            memory.key = update.key
        if update.value is not None:
            memory.value = update.value
        if update.memory_type is not None:
            memory.memory_type = update.memory_type
        if update.project_id is not None:
            memory.project_id = update.project_id
        if update.is_active is not None:
            memory.is_active = update.is_active
        db.commit()
        db.refresh(memory)
        return memory
    finally:
        db.close()


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(memory_id: int, update: MemoryUpdate):
    return await _apply_update(memory_id, update)


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def patch_memory(memory_id: int, update: MemoryUpdate):
    return await _apply_update(memory_id, update)


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
