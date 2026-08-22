"""SpawnOrchestrationTool — 子代理编排工具

主 Agent 在执行循环中调用本工具，将复杂任务拆分为多个专业子代理并行协作，
收集结果并汇总为编排报告返回给主 Agent。

工具名：spawn_orchestration
参数：
  - task: 用户任务 / 待编排的复杂任务描述（自包含）
  - roles: 可选，指定角色列表（如 ["architecture", "backend"]）；缺省时由
    OrchestrationPlanner 依据任务内容自动拆分。

行为：
  1. OrchestrationPlanner 分析复杂度并拆分（roles 缺省时）
  2. 简单任务 → 返回"无需编排"提示，主 Agent 直接执行
  3. 复杂任务 → 并行 spawn 子代理（动态角色身份，上下文隔离）
  4. 返回 OrchestrationReport.to_tool_output()（各角色结论 + 综合建议）

事件：编排过程发射 type=sub_agent 事件（经 executor 的 _emit 透传），
前端渲染编排进度。
"""

from app.core.orchestrator.roles import (
    get_orchestration_role,
    role_ids,
)
from app.services.tools import Tool, ToolResult


class SpawnOrchestrationTool(Tool):
    def __init__(self):
        super().__init__(
            name="spawn_orchestration",
            description=(
                "将复杂任务拆解为多个专业子代理并行协作（编排），收集各子代理结论并汇总成报告。"
                "适用于：大型系统设计、跨领域实现（前端+后端+测试+安全）、多模块重构等复杂任务。"
                "简单任务会直接返回无需编排，你继续主导执行即可。"
                "可用的角色（自动选择或指定 roles 参数）：" + "、".join(role_ids()) + "。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "待编排的任务描述：背景 + 目标 + 期望产出（自包含）",
                    },
                    "roles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选，指定参与角色列表（从可用角色中选择）；缺省时自动拆分",
                    },
                },
                "required": ["task"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        from app.services.sub_agent import SubAgentError

        task = str(kwargs.get("task", "") or "").strip()
        chat_id = kwargs.get("chat_id")
        project_path = kwargs.get("project_path")
        model_id = kwargs.get("model_id")
        emit = kwargs.get("_emit")

        if not task:
            return ToolResult(success=False, output="", error="参数 task 不能为空")

        try:
            # 延迟导入避免循环依赖（planner→context_builder→tools→本模块）
            from app.core.orchestrator.planner import orchestration_plan
            from app.core.orchestrator.runner import run_orchestration

            # 1. 规划：roles 缺省时由 LLM 拆分；指定时直接构造子任务
            if kwargs.get("roles"):
                plan = await self._plan_from_roles(task, kwargs.get("roles"))
            else:
                plan = await orchestration_plan(task, model_id=model_id)

            if not plan.need_orchestration:
                return ToolResult(
                    success=True,
                    output=(
                        f"任务被判定为 {plan.complexity.value}，无需子代理编排。"
                        f"判定依据：{plan.reason or '—'}。请直接执行该任务。"
                    ),
                )

            # 2. 执行编排（并行 spawn + 汇总），emit 透传 sub_agent 事件
            report = await run_orchestration(
                plan,
                chat_id=chat_id if isinstance(chat_id, int) else None,
                project_path=project_path or None,
                model_id=model_id or None,
                emit=emit,
            )

            # 3. 返回编排报告（工具输出文本）
            return ToolResult(success=True, output=report.to_tool_output())
        except SubAgentError as e:
            return ToolResult(success=False, output="", error=str(e))
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, output="", error=f"编排失败: {e}")

    async def _plan_from_roles(self, task: str, roles) -> "OrchestrationPlan":
        """按用户指定角色构造编排计划（跳过 LLM 拆分）。"""
        from app.core.orchestrator.models import (
            OrchestrationPlan,
            SubTaskSpec,
            TaskComplexity,
        )

        subtasks = []
        seen = set()
        for rid in (roles or []):
            rid = str(rid).strip()
            if not rid or rid in seen:
                continue
            seen.add(rid)
            role_def = get_orchestration_role(rid)
            if not role_def:
                continue
            subtasks.append(SubTaskSpec(
                role=rid,
                task=task,
                output_format=f"按 {role_def.name} 视角输出结论",
                max_tokens=role_def.max_tokens,
            ))
        return OrchestrationPlan(
            complexity=TaskComplexity.COMPLEX if subtasks else TaskComplexity.SIMPLE,
            need_orchestration=len(subtasks) >= 2,
            subtasks=subtasks,
            reason="用户指定角色编排",
            planner_source="user_roles",
        )


__all__ = ["SpawnOrchestrationTool"]