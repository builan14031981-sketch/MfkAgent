"""记忆路由。"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List

from app.database import Session, create_session
from app.models import MemoryItem
from app.schemas import MemoryCreate, MemoryOut
from app.core import memory as memory_mod

router = APIRouter(prefix="/memories", tags=["memories"])


def get_db():
    db = create_session()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=MemoryOut)
def add_memory(body: MemoryCreate, db: Session = Depends(get_db)):
    if body.scope not in ("global", "agent", "project"):
        raise HTTPException(400, "scope 必须为 global/agent/project")
    if not body.content.strip():
        raise HTTPException(400, "内容不能为空")
    item = memory_mod.add_memory(db, body.scope, body.content, body.agent_id, body.source)
    db.commit()
    db.refresh(item)
    return item


@router.get("", response_model=List[MemoryOut])
def list_memories(scope: str = None, agent_id: str = None,
                  limit: int = 30, db: Session = Depends(get_db)):
    items = memory_mod.query_memories(db, scope, agent_id, limit)
    return items


@router.delete("/{memory_id}")
def delete_memory(memory_id: int, db: Session = Depends(get_db)):
    item = db.query(MemoryItem).filter(MemoryItem.id == memory_id).first()
    if item is None:
        raise HTTPException(404, "记忆不存在")
    db.delete(item)
    db.commit()
    return {"status": "deleted"}