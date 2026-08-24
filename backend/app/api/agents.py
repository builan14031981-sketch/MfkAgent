from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import case
from app.core.database import SessionLocal
from app.core.capability_profiles import CAPABILITY_TAGS
from app.models.agent import Agent

router = APIRouter()

# Agent 展示优先级：核心研发 Agent 置顶，其余辅助 Agent 按定义顺序排列（唯一权威排序源）
AGENT_ORDER = {
    "general": 0,
    "g": 1,
    "coder": 2,
    "frontend_ui": 3,
    "product": 4,
    "writer": 5,
    "writer_narrative": 6,
    "writer_jiangnan": 7,
    "personal": 8,
    "spark": 9,
    "pianai": 10,
    "research": 11,
    "defense_ppt_expert": 12,
}

# Agent 用途分组：core=核心研发 / assist=辅助智能 / sub=子代理（前端分组展示依据）
AGENT_GROUP = {
    "general": "core",
    "g": "core",
    "coder": "core",
    "frontend_ui": "core",
    "product": "core",
    "research": "assist",
    "personal": "assist",
    "spark": "assist",
    "pianai": "assist",
    "writer": "assist",
    "writer_narrative": "assist",
    "writer_jiangnan": "assist",
    "defense_ppt_expert": "assist",
    "sub_code_reviewer": "sub",
    "sub_researcher": "sub",
    "sub_file_analyst": "sub",
}


class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    avatar: str
    icon: str = ""
    system_prompt: str
    identity: str = ""
    capabilities: list[str] = []
    status: str = "active"
    default_personality_level: Optional[int] = None
    expression_profile: Optional[str] = None
    group: str = "assist"

    class Config:
        from_attributes = True


def _to_info(a: Agent) -> AgentInfo:
    return AgentInfo(
        id=a.agent_id,
        name=a.name,
        description=a.description,
        avatar=a.avatar,
        icon=a.avatar,
        system_prompt=a.identity or a.system_prompt or "",
        identity=a.identity or "",
        capabilities=a.capabilities or [],
        status=a.status or "active",
        default_personality_level=a.default_personality_level,
        expression_profile=a.expression_profile,
        group=AGENT_GROUP.get(a.agent_id, "assist"),
    )


@router.get("", response_model=List[AgentInfo])
async def list_agents():
    db = SessionLocal()
    try:
        order_expr = case(
            *[(Agent.agent_id == key, idx) for key, idx in AGENT_ORDER.items()],
            else_=99,
        )
        agents = db.query(Agent).order_by(order_expr, Agent.id.asc()).all()
        return [_to_info(a) for a in agents]
    finally:
        db.close()


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    identity: Optional[str] = None
    capabilities: Optional[List[str]] = None
    default_personality_level: Optional[int] = None
    expression_profile: Optional[str] = None


@router.get("/capability-tags")
async def list_capability_tags():
    """领域能力标签词表：前端 Agent 详情编辑时使用（与工具权限无关）"""
    return {"tags": CAPABILITY_TAGS}


@router.patch("/{agent_id}", response_model=AgentInfo)
async def update_agent(agent_id: str, update: AgentUpdate):
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        if update.capabilities is not None:
            unknown = [c for c in update.capabilities if c not in CAPABILITY_TAGS]
            if unknown:
                raise HTTPException(status_code=422, detail=f"Unknown capability tags: {unknown}")
            agent.capabilities = update.capabilities
        if update.name is not None:
            agent.name = update.name
        if update.description is not None:
            agent.description = update.description
        if update.avatar is not None:
            agent.avatar = update.avatar
        if update.identity is not None:
            agent.identity = update.identity
        if update.default_personality_level is not None:
            agent.default_personality_level = update.default_personality_level
        if update.expression_profile is not None:
            agent.expression_profile = update.expression_profile
        db.commit()
        db.refresh(agent)
        return _to_info(agent)
    finally:
        db.close()


@router.get("/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str):
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return _to_info(agent)
    finally:
        db.close()
