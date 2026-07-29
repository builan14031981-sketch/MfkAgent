from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from app.services.workflow import workflow_engine, Workflow, WorkflowStep, StepType

router = APIRouter()


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    steps: List[Dict[str, Any]] = []


class WorkflowExecute(BaseModel):
    context: Dict[str, Any] = {}


@router.get("")
async def list_workflows():
    return {"workflows": workflow_engine.list_workflows()}


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    workflow = workflow_engine.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow.to_dict()


@router.post("")
async def create_workflow(request: WorkflowCreate):
    workflow_id = request.name.lower().replace(" ", "_")
    workflow = Workflow(
        workflow_id=workflow_id,
        name=request.name,
        description=request.description,
    )
    for step_data in request.steps:
        step = WorkflowStep(
            step_id=step_data.get("stepId", ""),
            step_type=StepType(step_data.get("type", "tool")),
            config=step_data.get("config", {}),
            next_step=step_data.get("nextStep"),
        )
        workflow.add_step(step)
    workflow_engine.register_workflow(workflow)
    return workflow.to_dict()


@router.post("/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, request: WorkflowExecute):
    result = await workflow_engine.execute(workflow_id, request.context)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
