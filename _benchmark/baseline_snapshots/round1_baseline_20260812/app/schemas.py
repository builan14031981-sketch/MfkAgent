"""Pydantic 请求/响应模型。"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ── Agent ──
class AgentCreate(BaseModel):
    agent_id: str = Field(min_length=1, max_length=64)
    name: str
    identity: str = ""
    capabilities: List[str] = []
    personality_level: int = 0


class AgentOut(BaseModel):
    id: int
    agent_id: str
    name: str
    identity: str
    capabilities: List[str]
    personality_level: int
    status: str


# ── Chat / Message ──
class ChatCreate(BaseModel):
    agent_id: str
    title: str = "New Chat"
    model: str = ""
    mode: str = "chat"
    project_path: str = ""
    personality_level: Optional[int] = None


class ChatOut(BaseModel):
    id: int
    agent_id: str
    title: str
    model: str
    mode: str
    personality_level: Optional[int]


class SendRequest(BaseModel):
    content: str = Field(min_length=1)


class MessageOut(BaseModel):
    id: int
    chat_id: int
    role: str
    content: str
    tokens: int
    timeline: str = ""


# ── Memory ──
class MemoryCreate(BaseModel):
    scope: str = "global"
    agent_id: Optional[str] = None
    content: str
    source: str = "manual"


class MemoryOut(BaseModel):
    id: int
    scope: str
    agent_id: Optional[str]
    content: str
    source: str