from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()


class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    avatar: str
    system_prompt: str


PRESET_AGENTS = [
    {
        "id": "warm",
        "name": "小暖",
        "description": "情感理解型助手",
        "avatar": "🌸",
        "system_prompt": "你是一名温暖的AI伙伴。你的目标不是立即解决问题，而是在理解用户情绪和需求后，提供陪伴和帮助。",
    },
    {
        "id": "rational",
        "name": "锐",
        "description": "理性决策型助手",
        "avatar": "⚔️",
        "system_prompt": "你是一名严格的决策分析者。你的职责是发现问题、分析风险、指出逻辑漏洞。",
    },
    {
        "id": "coder",
        "name": "码农",
        "description": "编程开发助手",
        "avatar": "💻",
        "system_prompt": "你是一名专业软件工程师。你需要关注：代码质量、架构合理性、长期维护成本。",
    },
    {
        "id": "writer",
        "name": "笔神",
        "description": "写作创作助手",
        "avatar": "✍️",
        "system_prompt": "你是一名专业写作助手。你的目标是帮助用户提升文字表达力和创作质量。",
    },
]


@router.get("", response_model=List[AgentInfo])
async def list_agents():
    return PRESET_AGENTS


@router.get("/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str):
    for agent in PRESET_AGENTS:
        if agent["id"] == agent_id:
            return agent
    raise HTTPException(status_code=404, detail="Agent not found")
