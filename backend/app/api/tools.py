from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from app.services.tools import tool_registry

router = APIRouter()


class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}


class ToolCallResponse(BaseModel):
    success: bool
    output: str
    error: str


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


@router.post("/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    result = await tool_registry.execute(request.tool_name, **request.arguments)
    return ToolCallResponse(
        success=result.success,
        output=result.output,
        error=result.error,
    )


@router.get("/definitions")
async def get_tool_definitions():
    return {"definitions": tool_registry.get_definitions()}
