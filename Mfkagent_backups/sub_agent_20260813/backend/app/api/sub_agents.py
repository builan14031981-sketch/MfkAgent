"""子代理（Sub-Agent）管理接口 — Phase SubAgent。

子代理即工具：主 Agent 通过 delegate_sub_agent 工具将子任务委派给专门化子代理。
本 router 提供子代理的 CRUD 管理（创建 / 查询 / 更新 / 删除），供前端管理面板使用。

- 仅操作 is_sub_agent=True 的记录，绝不触碰普通 Agent。
- 内置子代理（seed_agents.PRESET_AGENTS 中的 is_sub_agent 项）允许编辑但禁止删除，
  避免误删后重启又被 seed 逻辑重建造成困惑。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.core.database import SessionLocal
from app.core.capability_profiles import CAPABILITY_TAGS
from app.models.agent import Agent
from app.services.tools import tool_registry

router = APIRouter()

# 内置子代理 agent_id：禁止删除（seed 数据），但允许编辑
BUILTIN_SUB_AGENT_IDS = {"sub_code_reviewer", "sub_researcher", "sub_file_analyst"}


class SubAgentInfo(BaseModel):
    id: str
    name: str
    description: str
    avatar: str
    identity: str = ""
    capabilities: list[str] = []
    status: str = "active"
    allowed_tools: list[str] = []
    parent_agent_id: Optional[str] = None
    is_builtin: bool = False

    class Config:
        from_attributes = True


def _to_info(a: Agent) -> SubAgentInfo:
    return SubAgentInfo(
        id=a.agent_id,
        name=a.name,
        description=a.description or "",
        avatar=a.avatar or "",
        identity=a.identity or "",
        capabilities=a.capabilities or [],
        status=a.status or "active",
        allowed_tools=a.allowed_tools or [],
        parent_agent_id=a.parent_agent_id,
        is_builtin=a.agent_id in BUILTIN_SUB_AGENT_IDS,
    )


def _query_sub_agents(db, agent_id: Optional[str] = None):
    q = db.query(Agent).filter(Agent.is_sub_agent.is_(True))
    if agent_id:
        q = q.filter(Agent.agent_id == agent_id)
    return q.order_by(Agent.id.asc()).all()


@router.get("", response_model=List[SubAgentInfo])
async def list_sub_agents():
    """列出所有子代理。"""
    db = SessionLocal()
    try:
        return [_to_info(a) for a in _query_sub_agents(db)]
    finally:
        db.close()


@router.get("/available-tools")
async def list_available_tools():
    """可用工具名称词表：前端配置子代理工具白名单时展示（只读）。"""
    return {"tools": [t.name for t in tool_registry.get_all()]}


@router.get("/{agent_id}", response_model=SubAgentInfo)
async def get_sub_agent(agent_id: str):
    db = SessionLocal()
    try:
        a = _query_sub_agents(db, agent_id)
        if not a:
            raise HTTPException(status_code=404, detail="Sub-agent not found")
        return _to_info(a[0])
    finally:
        db.close()


class SubAgentCreate(BaseModel):
    agent_id: str
    name: str
    description: str = ""
    avatar: str = ""
    identity: str = ""
    capabilities: List[str] = []
    status: str = "active"
    allowed_tools: List[str] = []
    parent_agent_id: Optional[str] = None


class SubAgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    identity: Optional[str] = None
    capabilities: Optional[List[str]] = None
    status: Optional[str] = None
    allowed_tools: Optional[List[str]] = None
    parent_agent_id: Optional[str] = None


@router.post("", response_model=SubAgentInfo, status_code=201)
async def create_sub_agent(payload: SubAgentCreate):
    """创建子代理。agent_id 必须唯一且不能与内置 Agent 冲突。"""
    agent_id = payload.agent_id.strip()
    if not agent_id:
        raise HTTPException(status_code=422, detail="agent_id 不能为空")
    if agent_id in BUILTIN_SUB_AGENT_IDS:
        raise HTTPException(status_code=422, detail="agent_id 与内置子代理冲突，请换一个")

    db = SessionLocal()
    try:
        if db.query(Agent).filter(Agent.agent_id == agent_id).first():
            raise HTTPException(status_code=409, detail=f"agent_id 已存在: {agent_id}")
        if payload.capabilities:
            unknown = [c for c in payload.capabilities if c not in CAPABILITY_TAGS]
            if unknown:
                raise HTTPException(status_code=422, detail=f"Unknown capability tags: {unknown}")

        agent = Agent(
            agent_id=agent_id,
            name=payload.name,
            description=payload.description,
            avatar=payload.avatar,
            identity=payload.identity,
            capabilities=payload.capabilities,
            status=payload.status or "active",
            is_sub_agent=True,
            allowed_tools=payload.allowed_tools,
            parent_agent_id=payload.parent_agent_id,
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        return _to_info(agent)
    finally:
        db.close()


@router.patch("/{agent_id}", response_model=SubAgentInfo)
async def update_sub_agent(agent_id: str, update: SubAgentUpdate):
    db = SessionLocal()
    try:
        a = _query_sub_agents(db, agent_id)
        if not a:
            raise HTTPException(status_code=404, detail="Sub-agent not found")
        agent = a[0]
        if update.capabilities is not None:
            unknown = [c for c in update.capabilities if c not in CAPABILITY_TAGS]
            if unknown:
                raise HTTPException(status_code=422, detail=f"Unknown capability tags: {unknown}")
            agent.capabilities = update.capabilities
        if update.allowed_tools is not None:
            # 校验工具名是否真实存在（放宽容错：仅过滤，不硬报错）
            known = {t.name for t in tool_registry.get_all()}
            agent.allowed_tools = [t for t in update.allowed_tools if t in known]
        if update.name is not None:
            agent.name = update.name
        if update.description is not None:
            agent.description = update.description
        if update.avatar is not None:
            agent.avatar = update.avatar
        if update.identity is not None:
            agent.identity = update.identity
        if update.status is not None:
            agent.status = update.status
        if update.parent_agent_id is not None:
            agent.parent_agent_id = update.parent_agent_id
        db.commit()
        db.refresh(agent)
        return _to_info(agent)
    finally:
        db.close()


@router.delete("/{agent_id}")
async def delete_sub_agent(agent_id: str):
    """删除子代理。内置子代理禁止删除。"""
    if agent_id in BUILTIN_SUB_AGENT_IDS:
        raise HTTPException(status_code=422, detail="内置子代理不可删除（可编辑）")
    db = SessionLocal()
    try:
        a = _query_sub_agents(db, agent_id)
        if not a:
            raise HTTPException(status_code=404, detail="Sub-agent not found")
        db.delete(a[0])
        db.commit()
        return {"success": True}
    finally:
        db.close()
