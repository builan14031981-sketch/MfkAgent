from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.knowledge import knowledge_service

router = APIRouter()


class IndexRequest(BaseModel):
    project_id: int
    force: bool = False


class SearchRequest(BaseModel):
    project_id: int
    query: str
    limit: int = 5


@router.post("/index")
async def index_project(request: IndexRequest):
    result = knowledge_service.index_project(request.project_id, request.force)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/search")
async def search_knowledge(request: SearchRequest):
    results = knowledge_service.search(request.project_id, request.query, request.limit)
    return {"results": results}


@router.get("/context/{project_id}")
async def get_context(project_id: int, query: str, max_tokens: int = 2000):
    context = knowledge_service.get_context(project_id, query, max_tokens)
    return {"context": context}


@router.get("/stats")
async def get_stats():
    return knowledge_service.get_stats()
