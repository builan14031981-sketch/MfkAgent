from typing import Dict, Any, List, Optional
from enum import Enum
import json


class StepType(str, Enum):
    TOOL = "tool"
    PROMPT = "prompt"
    CONDITION = "condition"
    LOOP = "loop"


class WorkflowStep:
    def __init__(
        self,
        step_id: str,
        step_type: StepType,
        config: Dict[str, Any],
        next_step: str = None,
    ):
        self.step_id = step_id
        self.step_type = step_type
        self.config = config
        self.next_step = next_step

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stepId": self.step_id,
            "type": self.step_type.value,
            "config": self.config,
            "nextStep": self.next_step,
        }


class Workflow:
    def __init__(
        self,
        workflow_id: str,
        name: str,
        description: str = "",
        steps: List[WorkflowStep] = None,
    ):
        self.workflow_id = workflow_id
        self.name = name
        self.description = description
        self.steps = steps or []

    def add_step(self, step: WorkflowStep):
        self.steps.append(step)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflowId": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
        }


class WorkflowEngine:
    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}

    def register_workflow(self, workflow: Workflow):
        self.workflows[workflow.workflow_id] = workflow

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        return self.workflows.get(workflow_id)

    def list_workflows(self) -> List[Dict[str, Any]]:
        return [w.to_dict() for w in self.workflows.values()]

    async def execute(self, workflow_id: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return {"error": f"Workflow not found: {workflow_id}"}

        context = context or {}
        results = []
        current_step = None

        for step in workflow.steps:
            if current_step and step.step_id != current_step:
                continue

            result = await self._execute_step(step, context)
            results.append({"stepId": step.step_id, "result": result})

            if step.next_step:
                current_step = step.next_step
            else:
                break

        return {
            "workflowId": workflow_id,
            "results": results,
            "context": context,
        }

    async def _execute_step(self, step: WorkflowStep, context: Dict[str, Any]) -> Dict[str, Any]:
        if step.step_type == StepType.TOOL:
            return await self._execute_tool_step(step, context)
        elif step.step_type == StepType.PROMPT:
            return await self._execute_prompt_step(step, context)
        elif step.step_type == StepType.CONDITION:
            return await self._execute_condition_step(step, context)
        else:
            return {"status": "skipped", "reason": f"Unknown step type: {step.step_type}"}

    async def _execute_tool_step(self, step: WorkflowStep, context: Dict[str, Any]) -> Dict[str, Any]:
        from app.services.tools import tool_registry

        tool_name = step.config.get("tool")
        args = step.config.get("args", {})

        for key, value in args.items():
            if isinstance(value, str) and value.startswith("$"):
                var_name = value[1:]
                if var_name in context:
                    args[key] = context[var_name]

        result = await tool_registry.execute(tool_name, **args)
        return result.to_dict()

    async def _execute_prompt_step(self, step: WorkflowStep, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = step.config.get("prompt", "")
        for key, value in context.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
        return {"prompt": prompt}

    async def _execute_condition_step(self, step: WorkflowStep, context: Dict[str, Any]) -> Dict[str, Any]:
        condition = step.config.get("condition", "")
        var_name = step.config.get("variable", "")

        if var_name in context:
            value = context[var_name]
            if condition == "empty":
                return {"met": not value}
            elif condition == "not_empty":
                return {"met": bool(value)}

        return {"met": False}


workflow_engine = WorkflowEngine()

sample_workflow = Workflow(
    workflow_id="code_review",
    name="代码审查",
    description="自动审查代码质量",
)
sample_workflow.add_step(
    WorkflowStep(
        step_id="read_file",
        step_type=StepType.TOOL,
        config={"tool": "read_file", "args": {"path": "$file_path"}},
        next_step="analyze",
    )
)
sample_workflow.add_step(
    WorkflowStep(
        step_id="analyze",
        step_type=StepType.PROMPT,
        config={"prompt": "请分析以下代码的质量和潜在问题:\n{file_content}"},
    )
)

workflow_engine.register_workflow(sample_workflow)
