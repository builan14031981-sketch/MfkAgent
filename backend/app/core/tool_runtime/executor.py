"""工具执行器 — 统一执行所有工具调用，从 model.py 迁移而来。

负责：
- 文件工具执行（read_file / write_file / list_files）
- Git 工具执行
- 搜索工具执行
- 命令工具执行（run_command）
- 通用工具执行（tool_registry）
- Plan 模式只读拦截
- ToolCallCard 格式化
"""

import asyncio
import json
import time
from typing import Callable, Dict, Any, Optional

from app.core.tools import execute_file_tool
from app.core.git_tools import GIT_TOOLS, execute_git_tool
from app.core.search_tools import SEARCH_TOOLS, execute_search_tool
from app.core.command_tools import COMMAND_TOOLS, execute_command_tool
from app.services.tools import tool_registry
from app.core.tool_runtime.events import make_tool_start, make_tool_result, make_tool_approval
from app.core.tool_runtime.risk_engine import command_risk_engine, evaluate_tool, Verdict
from app.core.tool_runtime.approval import approval_registry


async def execute_tool(
    tool_call: Dict,
    project_path: str | None,
    read_only: bool,
    ctx: Dict[str, Any] | None = None,
    emit: Optional[Callable[[Dict], None]] = None,
    auto_approve: bool = False,
) -> Dict:
    """执行单个工具调用

    Args:
        tool_call: {"function": {"name": "...", "arguments": "..."}, "id": "..."}
        project_path: 项目路径（可为 None）
        read_only: 是否为只读模式
        ctx: 上下文（agent_id, project_id 等），供 add_memory 等工具使用
        emit: 可选事件发射器（接收 tool_start / tool_result 事件）。不传则静默（非流式路径零影响）。
        auto_approve: Phase 12 — 自动审批模式。REQUIRE_APPROVAL 级工具自动放行；
                      HIGH_RISK 级工具无视此标志，仍强制人工审批。

    Returns:
        {
            "name": str,
            "tool": str,
            "path": str,
            "success": bool,
            "status": str,
            "arguments": dict,
            "result": str,
            "duration_ms": int,
            "tool_call_id": str,
        }
    """
    ctx = ctx or {}
    func_name = tool_call["function"]["name"]
    tool_call_id = tool_call.get("id", "")

    try:
        func_args = json.loads(tool_call["function"].get("arguments", "{}") or "{}")
    except Exception:
        func_args = {}

    # 工具开始事件：分发前发射
    if emit:
        emit(make_tool_start(tool_call_id=tool_call_id, tool=func_name, input_args=func_args))
    _start_time = time.monotonic()

    result_text = ""

    # 兜底异常保护（Phase C-1）：工具执行异常绝不能打断整个 Agent loop，
    # 统一转换为 tool_result(success=false, error) 回喂模型继续下一轮。
    try:
        mode = "plan" if read_only else "build"

        # 1. 风险判定（唯一执行闸）：命令走命令引擎，文件/git 等走工具策略。
        #    只读工具 → ALLOW 直接执行；写入工具 → build 模式 ASK / plan 模式 DENY。
        if func_name in COMMAND_TOOLS:
            command = str(func_args.get("command", "") or "")
            decision = command_risk_engine.evaluate(command, mode)
        else:
            decision = evaluate_tool(func_name, mode)

        if decision.verdict == Verdict.DENY:
            result_text = decision.reason
        elif decision.verdict == Verdict.HIGH_RISK:
            # Phase 12: 高危操作，无视 auto_approve，强制进入审批流程
            return _make_pending_approval(
                tool_call_id=tool_call_id,
                func_name=func_name,
                func_args=func_args,
                decision=decision,
                ctx=ctx,
                read_only=read_only,
                emit=emit,
            )
        elif decision.verdict == Verdict.REQUIRE_APPROVAL:
            if auto_approve:
                # Phase 12: 自动审批模式 → 直接执行，不等待用户确认
                # tool_start 事件已在上面 emit，此处直接执行工具
                result_text = await _run_tool(func_name, func_args, project_path, ctx)
            else:
                # 需用户确认：登记审批并返回 pending record
                return _make_pending_approval(
                    tool_call_id=tool_call_id,
                    func_name=func_name,
                    func_args=func_args,
                    decision=decision,
                    ctx=ctx,
                    read_only=read_only,
                    emit=emit,
                )
        else:
            result_text = await _run_tool(func_name, func_args, project_path, ctx)
    except Exception as e:  # noqa: BLE001
        result_text = f"错误: 工具执行异常: {e}"

    # ToolCallCard 格式化
    rel_path = str(func_args.get("relative_path", ""))
    success = not result_text.startswith("错误")
    duration_ms = round((time.monotonic() - _start_time) * 1000)

    record = {
        "name": func_name,
        "tool": func_name,
        "path": rel_path,
        "success": success,
        "status": "success" if success else "failed",
        "arguments": func_args,
        "result": result_text,
        "duration_ms": duration_ms,
        "tool_call_id": tool_call_id,
    }

    # 工具结束事件：构造 record 前发射
    if emit:
        emit(make_tool_result(
            tool_call_id=tool_call_id,
            tool=func_name,
            success=success,
            result=result_text,
            duration_ms=duration_ms,
        ))

    return record


async def _run_tool(
    func_name: str,
    func_args: Dict[str, Any],
    project_path: str | None,
    ctx: Dict[str, Any],
) -> str:
    """执行通过风险判定后的工具调用（不重复判定）。

    统一承载文件 / Git / 搜索 / 命令 / 通用工具的实体内核。
    """
    if func_name in ("write_file", "read_file", "list_files"):
        if not project_path:
            return "错误: 文件操作需要绑定项目"
        return execute_file_tool(func_name, project_path=project_path, **func_args)

    if func_name in GIT_TOOLS:
        if not project_path:
            return "错误: Git 操作需要绑定项目"
        return execute_git_tool(func_name, project_path=project_path, **func_args)

    if func_name in SEARCH_TOOLS:
        if not project_path:
            return "错误: 搜索操作需要绑定项目"
        return execute_search_tool(func_name, project_path=project_path, **func_args)

    if func_name in COMMAND_TOOLS:
        return execute_command_tool(func_name, project_path=project_path or "", **func_args)

    r = await tool_registry.execute(func_name, **{**ctx, **func_args})
    return r.output if r.success else f"Error: {r.error}"


def _describe_tool_command(func_name: str, func_args: Dict[str, Any]) -> str:
    """生成审批卡片的可读描述文本。"""
    if func_name == "run_command":
        return str(func_args.get("command", "") or "")
    if func_name == "write_file":
        return f"写入文件: {func_args.get('relative_path', '')}"
    if func_name in GIT_TOOLS:
        return f"{func_name}({', '.join(f'{k}={v}' for k, v in func_args.items())})"
    return func_name


def _make_pending_approval(
    tool_call_id: str,
    func_name: str,
    func_args: Dict,
    decision,
    ctx: Dict[str, Any],
    read_only: bool = False,
    emit: Optional[Callable[[Dict], None]] = None,
) -> Dict:
    """登记待审批工具调用，发射 tool_approval 事件，返回 status=awaiting_approval 的 pending record。

    不发射 tool_result；由 model.py 在用户作出决定后调用 complete_approval 完成闭环。
    """
    command = _describe_tool_command(func_name, func_args)
    chat_id = ctx.get("chat_id")
    approval_id, info = approval_registry.register(
        tool_call_id=tool_call_id,
        tool=func_name,
        command=command,
        risk_level=decision.risk_level.value,
        risk_reason=decision.reason,
        chat_id=chat_id,
    )

    if emit:
        emit(make_tool_approval(
            approval_id=approval_id,
            tool_call_id=tool_call_id,
            tool=func_name,
            command=command,
            risk_level=decision.risk_level.value,
            risk_reason=decision.reason,
            chat_id=chat_id,
        ))

    return {
        "name": func_name,
        "tool": func_name,
        "path": str(func_args.get("relative_path", "")),
        "success": False,
        "status": "awaiting_approval",
        "arguments": func_args,
        "result": "",
        "duration_ms": 0,
        "tool_call_id": tool_call_id,
        "approval_id": approval_id,
        "approval_future": info["future"],
        "approval_timeout": info["timeout"],
        "risk_level": decision.risk_level.value,
        "risk_reason": decision.reason,
        "verdict": decision.verdict.value,  # Phase 12: 供 auto_approve 逻辑判断
        "read_only": read_only,
    }


async def complete_approval(
    record: Dict,
    project_path: Optional[str] = None,
    emit: Optional[Callable[[Dict], None]] = None,
) -> Dict:
    """等待审批结果并完成工具闭环（Phase B-1）。

    - approve → 执行命令，构造成功/失败 record，发射 tool_result
    - deny / timeout / cancelled → 注入拒绝结果（success=False），发射 tool_result

    调用方约定：在 tool_approval 事件已 yield 给前端后调用本函数。
    """
    try:
        action = await asyncio.wait_for(record["approval_future"], timeout=record["approval_timeout"])
    except asyncio.TimeoutError:
        action = "timeout"
    approval_registry.remove(record["approval_id"])

    start = time.monotonic()
    if action == "approve":
        result_text = await _run_tool(record["tool"], record["arguments"], project_path, {})
        success = not result_text.startswith("错误")
        status = "success" if success else "failed"
    else:
        text = {
            "deny": "用户拒绝了该操作，未执行。",
            "timeout": f"审批超时（>{record['approval_timeout']:.0f}s），已自动拒绝。",
            "cancelled": "操作已取消（会话流已结束）。",
        }.get(action, "操作已取消。")
        result_text = f"已取消: {text}"
        success = False
        status = "denied"

    duration_ms = round((time.monotonic() - start) * 1000) if action == "approve" else 0

    final = dict(record)
    final.pop("approval_future", None)
    final.pop("approval_timeout", None)
    final.update({
        "success": success,
        "status": status,
        "result": result_text,
        "duration_ms": duration_ms,
    })

    if emit:
        emit(make_tool_result(
            tool_call_id=final["tool_call_id"],
            tool=final["tool"],
            success=success,
            result=result_text,
            duration_ms=duration_ms,
        ))

    return final