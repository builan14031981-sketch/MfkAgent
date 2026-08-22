"""OrchestrationRunner — 编排执行：并行 spawn 子代理 + 结果收集 + 汇总。

流程：
  1. 接收 OrchestrationPlan（来自 OrchestrationPlanner）
  2. 对每个子任务并行 spawn 子代理（复用 run_sub_agent + 角色模板身份）
  3. 收集 SubTaskResult[]（结构化）
  4. 可选 emit SSE 事件（sub_agent）供前端展示各子代理进度
  5. 生成 OrchestrationReport（含综合结论）

角色模板来源：get_orchestration_role（DB 内置模板优先，内存定义兜底）。
每次 spawn 均为全新隔离实例，执行完即弃、不保留状态。

并行控制：
  - MAX_CONCURRENCY = 4（防止 token/资源爆炸）
  - 单子代理 max_tokens 来自角色定义（默认 4096）
  - 任一子代理失败不影响其他（收集错误进 SubTaskResult.error）

emit 事件格式（type=sub_agent）：
  {
    "type": "sub_agent",
    "id": f"sub_{role}_{seq}",
    "role": role_id,
    "title": "角色名",
    "content": "摘要/错误",
    "status": "running" | "completed" | "failed",
  }
"""

import asyncio
import time
from typing import Awaitable, Callable, List, Optional

from app.core.orchestrator.models import (
    OrchestrationPlan,
    OrchestrationReport,
    SubTaskResult,
)
from app.core.orchestrator.roles import get_orchestration_role

# 最大并行子代理数（防止 token / 并发资源爆炸）
MAX_CONCURRENCY = 4

# emit 事件回调签名：Callable[[dict], None]（同步）或 Awaitable。二者皆可。
EmitFn = Optional[Callable[[dict], None]]


def _emit_sync(emit: EmitFn, event: dict) -> None:
    """发射事件（emit 为同步回调时直接调用；async 回调由调用方负责）。"""
    if emit:
        emit(event)


async def _run_subtask(
    role: str,
    task: str,
    output_format: str,
    *,
    chat_id: Optional[int],
    project_path: Optional[str],
    model_id: Optional[str],
    max_tokens: int,
    seq: int,
    emit: EmitFn,
) -> SubTaskResult:
    """执行单个子任务（返回结构化结果，不抛异常）。"""
    role_def = get_orchestration_role(role)
    display_name = role_def.name if role_def else role
    result = SubTaskResult(role=role, status="failed")

    _emit_sync(emit, {
        "type": "sub_agent",
        "id": f"sub_{role}_{seq}",
        "role": role,
        "title": display_name,
        "content": f"开始执行: {task[:120]}",
        "status": "running",
    })

    try:
        # 延迟导入：sub_agent → agent_runtime → context_builder → tools → orchestrator_tool，
        # 顶层导入会造成循环依赖。
        from app.services.sub_agent import SubAgentError, run_sub_agent

        summary = await run_sub_agent(
            sub_agent_id=f"orchestration_{role}",
            task=(
                f"【子任务背景】\n{task}\n"
                f"【期望输出】\n{output_format or '结构化结论'}\n"
                f"【协作提示】你是整体任务中的一名子代理，完成后只输出你的结论，"
                f"不要重复整个任务背景。"
            ),
            chat_id=chat_id,
            project_path=project_path,
            model_id=model_id,
            max_tokens=max_tokens or 4096,
            identity_override=role_def.identity_template if role_def else None,
            allowed_tools_override=role_def.suggested_tools if role_def else None,
            max_tool_rounds=5,
        )
        result.status = "completed"
        result.summary = summary
        _emit_sync(emit, {
            "type": "sub_agent",
            "id": f"sub_{role}_{seq}",
            "role": role,
            "title": display_name,
            "content": f"完成: {summary[:120]}",
            "status": "completed",
        })
    except (SubAgentError, Exception) as e:  # noqa: BLE001
        result.error = f"{type(e).__name__}: {str(e)}"[:500]
        _emit_sync(emit, {
            "type": "sub_agent",
            "id": f"sub_{role}_{seq}",
            "role": role,
            "title": display_name,
            "content": f"失败: {str(e)[:120]}",
            "status": "failed",
        })
    return result


def _synthesize(results: List[SubTaskResult]) -> str:
    """汇总综合结论（轻量合成：标题 + 各角色要点 + 建议下一步）。"""
    done = [r for r in results if r.status == "completed"]
    failed = [r for r in results if r.status == "failed"]
    if not results:
        return "未产生子代理结果。"
    lines = [
        f"共 {len(results)} 个子代理协作，其中 {len(done)} 成功、{len(failed)} 失败。",
    ]
    if done:
        lines.append("各角色结论要点：")
        for r in done:
            head = r.summary.strip().splitlines()[:2]
            excerpt = " ".join(head)[:180] if head else "(无内容)"
            lines.append(f"- [{r.role}] {excerpt}")
    if failed:
        lines.append("失败角色及原因：")
        for r in failed:
            lines.append(f"- [{r.role}] {r.error[:180]}")
    lines.append("建议下一步：由主 Agent 综合以上结论，对失败项可直接重试或改用其他策略。")
    return "\n".join(lines)


async def run_orchestration(
    plan: OrchestrationPlan,
    *,
    chat_id: Optional[int] = None,
    project_path: Optional[str] = None,
    model_id: Optional[str] = None,
    emit: EmitFn = None,
) -> OrchestrationReport:
    """执行编排计划。

    Args:
        plan: OrchestrationPlanner 的输出
        chat_id / project_path / model_id: 透传给子代理（继承主会话环境）
        emit: 事件发射器（可选；不传则静默，非流式路径零影响）

    Returns:
        OrchestrationReport：含子代理结果与综合结论（to_tool_output 渲染为工具输出）
    """
    report = OrchestrationReport(plan=plan)
    start = time.perf_counter()

    if not plan.need_orchestration or not plan.subtasks:
        report.synthesis = "无需编排，主 Agent 直接执行。"
        report.duration_ms = 0
        return report

    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    seq_counter = 0

    async def _limited(task: dict, seq: int) -> SubTaskResult:
        async with sem:
            return await _run_subtask(
                role=task.role,
                task=task.task,
                output_format=task.output_format,
                chat_id=chat_id,
                project_path=project_path,
                model_id=model_id,
                max_tokens=task.max_tokens,
                seq=seq,
                emit=emit,
            )

    # 顺序编号（并发下也保证每个角色 id 唯一）
    async def _wrapped(task: dict) -> SubTaskResult:
        nonlocal seq_counter
        seq_counter += 1
        return await _limited(task, seq_counter)

    results = await asyncio.gather(*[_wrapped(t) for t in plan.subtasks])
    report.results = list(results)
    report.synthesis = _synthesize(report.results)
    report.duration_ms = int((time.perf_counter() - start) * 1000)
    return report


__all__ = ["run_orchestration", "OrchestrationReport", "MAX_CONCURRENCY"]