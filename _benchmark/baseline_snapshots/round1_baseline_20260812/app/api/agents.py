"""Agent 路由。"""
import json

from fastapi import APIRouter, HTTPException, Depends
from typing import List

from app.database import Session, create_session
from app.models import Agent
from app.schemas import AgentCreate, AgentOut

router = APIRouter(prefix="/agents", tags=["agents"])


def _serialize(agent) -> dict:
    try:
        caps = json.loads(agent.capabilities or "[]")
    except ValueError:
        caps = []
    return {
        "id": agent.id,
        "agent_id": agent.agent_id,
        "name": agent.name,
        "identity": agent.identity,
        "capabilities": caps,
        "personality_level": agent.personality_level,
        "status": agent.status,
    }


def get_db():
    db = create_session()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=List[AgentOut])
def list_agents(status: str = None, db: Session = Depends(get_db)):
    q = db.query(Agent)
    if status is not None:
        q = q.filter(Agent.status == status)
    rows = q.order_by(Agent.id).all()
    return [_serialize(a) for a in rows]


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if agent is None:
        raise HTTPException(404, "Agent 不存在")
    return _serialize(agent)


@router.post("", response_model=AgentOut)
def create_agent(body: AgentCreate, db: Session = Depends(get_db)):
    if db.query(Agent).filter(Agent.agent_id == body.agent_id).first() is not None:
        raise HTTPException(400, "agent_id 已存在")
    agent = Agent(
        agent_id=body.agent_id,
        name=body.name,
        identity=body.identity,
        capabilities=json.dumps(body.capabilities, ensure_ascii=False),
        personality_level=body.personality_level,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _serialize(agent)