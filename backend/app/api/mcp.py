from fastapi import APIRouter, Request
from app.services.mcp import mcp_server

router = APIRouter()


@router.post("")
async def handle_mcp(request: Request):
    body = await request.json()
    response = mcp_server.handle_request(body)
    return response


@router.get("/capabilities")
async def get_capabilities():
    return mcp_server.get_capabilities()


@router.get("/tools")
async def list_tools():
    return {"tools": [t.to_dict() for t in mcp_server.tools.values()]}


@router.get("/resources")
async def list_resources():
    return {"resources": [r.to_dict() for r in mcp_server.resources.values()]}


@router.get("/prompts")
async def list_prompts():
    return {"prompts": [p.to_dict() for p in mcp_server.prompts.values()]}
