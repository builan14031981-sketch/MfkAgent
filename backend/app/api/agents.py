from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.core.database import SessionLocal
from app.models.agent import Agent

router = APIRouter()


class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    avatar: str
    system_prompt: str
    identity: str = ""
    capabilities: list[str] = []
    default_model: str = ""

    class Config:
        from_attributes = True


@router.get("", response_model=List[AgentInfo])
async def list_agents():
    db = SessionLocal()
    try:
        agents = db.query(Agent).all()
        return [
            AgentInfo(
                id=a.agent_id,
                name=a.name,
                description=a.description,
                avatar=a.avatar,
                system_prompt=a.identity or a.system_prompt or "",
                identity=a.identity or "",
                capabilities=a.capabilities or [],
                default_model=a.model or "",
            )
            for a in agents
        ]
    finally:
        db.close()


@router.get("/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str):
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return AgentInfo(
            id=agent.agent_id,
            name=agent.name,
            description=agent.description,
            avatar=agent.avatar,
            system_prompt=agent.identity or agent.system_prompt or "",
            identity=agent.identity or "",
            capabilities=agent.capabilities or [],
            default_model=agent.model or "",
        )
    finally:
        db.close()
