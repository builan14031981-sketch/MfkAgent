from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import json


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskTrigger(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT = "event"


class AutoTask:
    def __init__(
        self,
        task_id: str,
        name: str,
        description: str = "",
        trigger: TaskTrigger = TaskTrigger.MANUAL,
        workflow_id: str = None,
        config: Dict[str, Any] = None,
        schedule: str = None,
    ):
        self.task_id = task_id
        self.name = name
        self.description = description
        self.trigger = trigger
        self.workflow_id = workflow_id
        self.config = config or {}
        self.schedule = schedule
        self.status = TaskStatus.PENDING
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "taskId": self.task_id,
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger.value,
            "workflowId": self.workflow_id,
            "config": self.config,
            "schedule": self.schedule,
            "status": self.status.value,
            "lastRun": self.last_run.isoformat() if self.last_run else None,
            "nextRun": self.next_run.isoformat() if self.next_run else None,
            "result": self.result,
        }


class AutoTaskEngine:
    def __init__(self):
        self.tasks: Dict[str, AutoTask] = {}
        self._running = False

    def register_task(self, task: AutoTask):
        self.tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[AutoTask]:
        return self.tasks.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.tasks.values()]

    async def execute_task(self, task_id: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if not task:
            return {"error": f"Task not found: {task_id}"}

        task.status = TaskStatus.RUNNING
        task.last_run = datetime.now()

        try:
            if task.workflow_id:
                from app.services.workflow import workflow_engine
                result = await workflow_engine.execute(task.workflow_id, context or task.config)
            else:
                result = {"status": "no_workflow", "message": "No workflow configured"}

            task.status = TaskStatus.COMPLETED
            task.result = result
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.result = {"error": str(e)}
            return {"error": str(e)}

    def cancel_task(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        task.status = TaskStatus.CANCELLED
        return True

    def delete_task(self, task_id: str) -> bool:
        if task_id in self.tasks:
            del self.tasks[task_id]
            return True
        return False


auto_task_engine = AutoTaskEngine()

sample_task = AutoTask(
    task_id="daily_code_review",
    name="每日代码审查",
    description="自动审查项目代码质量",
    trigger=TaskTrigger.SCHEDULED,
    workflow_id="code_review",
    schedule="0 9 * * *",
)
auto_task_engine.register_task(sample_task)
