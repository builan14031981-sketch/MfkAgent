"""工具目录只读接口（E7-1：移除直接执行旁路）。

仅保留只读的工具列表 / 定义查询。任何工具执行都必须经过 AgentRuntime
（Executor → Permission → Risk → Approval → Verification → Event）闭环，
api 层禁止直接调用 tool_registry.execute。

开发调试用的裸工具执行已移至 devtools router（/api/devtools/tools/call，
仅 DEBUG 模式可用）。
"""
from fastapi import APIRouter
from app.services.tools import tool_registry

router = APIRouter()


@router.get("")
async def list_tools():
    tools = tool_registry.get_all()
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in tools
        ]
    }


@router.get("/definitions")
async def get_tool_definitions():
    return {"definitions": tool_registry.get_definitions()}
