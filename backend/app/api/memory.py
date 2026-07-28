from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()


class MemoryItem(BaseModel):
    id: int
    agent_id: int
    user_id: str
    key: str
    value: str
    memory_type: str


class MemoryCreate(BaseModel):
    agent_id: int
    key: str
    value: str
    memory_type: str = "preference"


@router.get("/{agent_id}", response_model=List[MemoryItem])
async def get_memories(agent_id: int, user_id: str = "default"):
    return []


@router.post("", response_model=MemoryItem)
async def create_memory(memory: MemoryCreate):
    raise HTTPException(status_code=501, detail="Memory system not implemented yet")


@router.delete("/{memory_id}")
async def delete_memory(memory_id: int):
    raise HTTPException(status_code=501, detail="Memory system not implemented yet")
