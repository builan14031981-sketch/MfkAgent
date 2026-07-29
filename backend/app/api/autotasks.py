from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from app.services.autotask import auto_task_engine, AutoTask, TaskTrigger

router = APIRouter()


class TaskCreate(BaseModel):
    name: str
    description: str = ""
    trigger: str = "manual"
    workflow_id: str = None
    config: Dict[str, Any] = {}
    schedule: str = None


class TaskExecute(BaseModel):
    context: Dict[str, Any] = {}


@router.get("")
async def list_tasks():
    return {"tasks": auto_task_engine.list_tasks()}


@router.get("/{task_id}")
async def get_task(task_id: str):
    task = auto_task_engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


@router.post("")
async def create_task(request: TaskCreate):
    task_id = request.name.lower().replace(" ", "_")
    task = AutoTask(
        task_id=task_id,
        name=request.name,
        description=request.description,
        trigger=TaskTrigger(request.trigger),
        workflow_id=request.workflow_id,
        config=request.config,
        schedule=request.schedule,
    )
    auto_task_engine.register_task(task)
    return task.to_dict()


@router.post("/{task_id}/execute")
async def execute_task(task_id: str, request: TaskExecute):
    result = await auto_task_engine.execute_task(task_id, request.context)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    success = auto_task_engine.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "cancelled"}


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    success = auto_task_engine.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted"}
