"""工具执行器 — 统一执行所有工具调用，从 model.py 迁移而来。

负责：
- 文件工具执行（read_file / write_file / list_files / find_files / edit_file / apply_patch）
- Git 工具执行
- 搜索工具执行
- 命令工具执行（run_command）
- 通用工具执行（tool_registry）
- Plan 模式只读拦截
- ToolCallCard 格式化
- Phase 3 T3/T8: 统一 ExecutionDecision 决策链
- Phase H: 工具结果 >8000 字符统一截断（head 6000 + tail 2000），防大输出撑爆上下文
"""

import asyncio
import json
import os
import time
from typing import Callable, Dict, Any, Optional

from app.core.tools import execute_file_tool
from app.core.git_tools import GIT_TOOLS, execute_git_tool
from app.core.search_tools import SEARCH_TOOLS, execute_search_tool
from app.core.command_tools import COMMAND_TOOLS, execute_command_tool
from app.core.ui_probe_tools import UI_PROBE_TOOLS, execute_ui_probe_tool
from app.core.image_gen_tools import IMAGE_GEN_TOOLS, execute_image_gen_tool
from app.core.spec_check_tools import SPEC_CHECK_TOOLS, execute_spec_check_tool
from app.services.tools import tool_registry
from app.core.tool_runtime.events import make_tool_start, make_tool_result, make_tool_approval, make_choice_request
from app.core.tool_runtime.risk_engine import (
    command_risk_engine, evaluate_tool, Verdict,
    ExecutionDecision, ExecutionAction,
)
from app.core.tool_runtime.approval import approval_registry
from app.core.tool_runtime.choice import choice_registry, CUSTOM_TEXT_MAX
from app.core.tool_runtime.approval_policy import get_approval_policy, ApprovalMode
from app.core.tool_runtime.notification import event_bus

# Phase H: 工具结果截断（head + tail 拼接），防止单条工具结果撑爆上下文
TOOL_RESULT_MAX_CHARS = 8000
TOOL_RESULT_HEAD = 5900
TOOL_RESULT_TAIL = 1900


def _truncate_result(text: str, func_name: str = "") -> str:
    """统一截断工具结果文本；截断时保留头尾并给出提示（read_file 提示分段读取）。"""
    if len(text) <= TOOL_RESULT_MAX_CHARS:
        return text
    head = text[:TOOL_RESULT_HEAD]
    tail = text[-TOOL_RESULT_TAIL:]
    mid = len(text) - TOOL_RESULT_HEAD - TOOL_RESULT_TAIL
    if func_name == "read_file":
        hint = "\n[已截断] 输出过长，请用 read_file(offset=..., limit=...) 分段读取该文件。"
    else:
        hint = f"\n[已截断] 结果共 {len(text)} 字符，仅保留首尾各一部分（中间 {mid} 字符省略）。"
    return head + hint + "\n" + tail


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
        auto_approve: 已废弃（Phase 3 T3/T8），保留只为向后兼容。
                      权限模式统一从 ApprovalPolicy 读取。

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
        if func_name in COMMAND_TOOLS:
            command = str(func_args.get("command", "") or "")
            if func_name == "run_outside_command":
                decision = command_risk_engine.evaluate_outside(command, mode)
            elif func_name == "execute_command":
                decision = command_risk_engine.evaluate_execute(command, mode)
            else:
                decision = command_risk_engine.evaluate(command, mode)
        else:
            decision = evaluate_tool(func_name, mode)

        # 2. Phase 3 T3/T8: 统一决策链 — ApprovalPolicy 将 RiskDecision 转为 ExecutionDecision
        policy = get_approval_policy()
        exec_decision = policy.decide(decision)

        # 3. AgentRuntime 只消费 ExecutionDecision
        if exec_decision.action == ExecutionAction.BLOCK:
            result_text = exec_decision.reason
        elif exec_decision.action == ExecutionAction.REQUIRE_APPROVAL:
            # 需要用户审批：登记审批并返回 pending record
            return _make_pending_approval(
                tool_call_id=tool_call_id,
                func_name=func_name,
                func_args=func_args,
                decision=decision,
                exec_decision=exec_decision,
                ctx=ctx,
                read_only=read_only,
                emit=emit,
            )
        else:
            # EXECUTE: 直接执行
            if func_name == "ask_user_choice":
                # 抉择工具拦截：自主模式直接采纳推荐项；其他模式登记 pending 等待用户抉择
                return await _dispatch_user_choice(
                    tool_call_id=tool_call_id,
                    func_args=func_args,
                    ctx=ctx,
                    emit=emit,
                    start_time=_start_time,
                )
            result_text = await _run_tool(func_name, func_args, project_path, ctx, emit=emit)
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
    # 文件类工具：计算绝对路径供前端直接用于打开/定位
    _file_path = None
    if func_name in ("write_file", "read_file") and project_path and success:
        _rel = str(func_args.get("relative_path", ""))
        if _rel:
            _file_path = os.path.join(project_path, _rel.replace("/", os.sep))

    if emit:
        emit(make_tool_result(
            tool_call_id=tool_call_id,
            tool=func_name,
            success=success,
            result=result_text,
            duration_ms=duration_ms,
            file_path=_file_path,
        ))

    return record


async def _run_tool(
    func_name: str,
    func_args: Dict[str, Any],
    project_path: str | None,
    ctx: Dict[str, Any],
    emit: Optional[Callable[[Dict], None]] = None,
) -> str:
    """执行通过风险判定后的工具调用（不重复判定）。

    统一承载文件 / Git / 搜索 / 命令 / 通用工具的实体内核。
    Phase H: 统一出口截断，防止单条工具结果撑爆上下文。
    """
    if func_name in ("write_file", "read_file", "list_files", "find_files", "edit_file", "apply_patch"):
        if not project_path:
            return "错误: 文件操作需要绑定项目"
        return _truncate_result(
            execute_file_tool(func_name, project_path=project_path, **func_args), func_name
        )

    if func_name in GIT_TOOLS:
        if not project_path:
            return "错误: Git 操作需要绑定项目"
        return _truncate_result(execute_git_tool(func_name, project_path=project_path, **func_args), func_name)

    if func_name in SEARCH_TOOLS:
        if not project_path:
            return "错误: 搜索操作需要绑定项目"
        return _truncate_result(execute_search_tool(func_name, project_path=project_path, **func_args), func_name)

    if func_name in SPEC_CHECK_TOOLS:
        if not project_path:
            return "错误: 规格校验需要绑定项目"
        return _truncate_result(execute_spec_check_tool(func_name, project_path=project_path, **func_args), func_name)

    if func_name in UI_PROBE_TOOLS:
        if not project_path:
            return "错误: UI 自检需要绑定项目"
        # playwright 为同步阻塞 API，放线程池避免卡住事件循环
        return _truncate_result(
            await asyncio.to_thread(
                execute_ui_probe_tool, func_name, project_path=project_path, **func_args
            ),
            func_name,
        )

    if func_name in IMAGE_GEN_TOOLS:
        # 文生图含同步轮询/下载，放线程池避免卡住事件循环；
        # chat_id 用于生成图片的可访问代理 URL（前端渲染）
        return _truncate_result(
            await asyncio.to_thread(
                execute_image_gen_tool, func_name, project_path=project_path or "",
                chat_id=ctx.get("chat_id"), **func_args
            ),
            func_name,
        )

    if func_name in COMMAND_TOOLS:
        return _truncate_result(
            execute_command_tool(func_name, project_path=project_path or "", **func_args), func_name
        )

    # emit 以 _emit 键透传给 registry 工具（编排工具发射 sub_agent 事件用），
    # 普通工具 execute(**kwargs) 会忽略未知键，零影响。
    r = await tool_registry.execute(func_name, **{**ctx, **func_args, "_emit": emit})
    return _truncate_result(r.output if r.success else f"Error: {r.error}", func_name)


# ──── ask_user_choice：抉择工具（pending record 模式，对齐 approval）────

_CHOICE_TOOL = "ask_user_choice"


def _normalize_choice_options(raw) -> list:
    """整理 options 参数：2-4 项，每项 {label, description}；不足 2 项时补齐占位项。"""
    opts = []
    if isinstance(raw, list):
        for item in raw[:4]:
            if isinstance(item, dict):
                label = str(item.get("label", "") or "").strip()
                if not label:
                    continue
                opts.append({
                    "label": label[:120],
                    "description": str(item.get("description", "") or "").strip()[:300],
                })
            elif isinstance(item, str) and item.strip():
                opts.append({"label": item.strip()[:120], "description": ""})
    while len(opts) < 2:
        opts.append({"label": f"方案 {len(opts) + 1}", "description": ""})
    return opts[:4]


def _choice_recommended_text(options: list, recommended) -> str:
    idx = recommended if isinstance(recommended, int) and 0 <= recommended < len(options) else 0
    return options[idx]["label"]


def _format_choice_result(options: list, recommended, selected, custom_text, note: str = "") -> str:
    """拼装回喂模型的抉择结果文本。"""
    parts = []
    if isinstance(selected, int) and 0 <= selected < len(options):
        parts.append(f"用户选择了：{options[selected]['label']}")
    if custom_text:
        parts.append(f"用户想法：{custom_text}")
    if not parts:
        parts.append(f"用户未明确选择，采纳推荐项：{_choice_recommended_text(options, recommended)}")
    if note:
        parts.append(note)
    return "\n".join(parts)


async def _dispatch_user_choice(
    tool_call_id: str,
    func_args: Dict[str, Any],
    ctx: Dict[str, Any],
    emit: Optional[Callable[[Dict], None]],
    start_time: float,
) -> Dict:
    """抉择工具分发：AUTONOMOUS 直接采纳推荐项；其他模式登记 pending + 发 choice_request 事件。"""
    question = str(func_args.get("question", "") or "").strip() or "这个任务你希望怎么处理？"
    options = _normalize_choice_options(func_args.get("options"))
    raw_rec = func_args.get("recommended")
    recommended = raw_rec if isinstance(raw_rec, int) and 0 <= raw_rec < len(options) else None
    allow_custom = bool(func_args.get("allow_custom", True))
    chat_id = ctx.get("chat_id")

    # 自主模式：不挂起不弹卡，直接采纳推荐项
    if get_approval_policy().mode == ApprovalMode.AUTONOMOUS:
        result_text = _format_choice_result(
            options, recommended, None, None,
            note="（自主模式：由 Agent 自行决定，已采纳推荐项）",
        )
        duration_ms = round((time.monotonic() - start_time) * 1000)
        if emit:
            emit(make_tool_result(
                tool_call_id=tool_call_id, tool=_CHOICE_TOOL,
                success=True, result=result_text, duration_ms=duration_ms,
            ))
        return {
            "name": _CHOICE_TOOL, "tool": _CHOICE_TOOL, "path": "",
            "success": True, "status": "success",
            "arguments": func_args, "result": result_text,
            "duration_ms": duration_ms, "tool_call_id": tool_call_id,
        }

    # 其他模式：登记 pending 抉择，发射 choice_request 事件（前端渲染抉择卡）
    choice_id, info = choice_registry.register(
        tool_call_id=tool_call_id, chat_id=chat_id,
        question=question, options=options, recommended=recommended,
    )
    if emit:
        emit(make_choice_request(
            choice_id=choice_id, tool_call_id=tool_call_id, question=question,
            options=options, recommended=recommended,
            allow_custom=allow_custom, chat_id=chat_id,
        ))
    return {
        "name": _CHOICE_TOOL, "tool": _CHOICE_TOOL, "path": "",
        "success": False, "status": "awaiting_choice",
        "arguments": func_args, "result": "",
        "duration_ms": 0, "tool_call_id": tool_call_id,
        "choice_id": choice_id,
        "choice_future": info["future"],
        "choice_timeout": info["timeout"],
        "choice_options": options,
        "choice_recommended": recommended,
        "chat_id": chat_id,
    }


async def complete_choice(record: Dict, emit: Optional[Callable[[Dict], None]] = None) -> Dict:
    """完成 pending 抉择闭环：等待用户选择（超时→采纳推荐项），发射 tool_result 并返回最终 record。

    调用方约定：与 complete_approval 一致，在 choice_request 事件已 yield 给前端后调用。
    """
    options = record.get("choice_options") or []
    recommended = record.get("choice_recommended")
    try:
        action = await asyncio.wait_for(record["choice_future"], timeout=record["choice_timeout"])
    except asyncio.TimeoutError:
        action = {"selected": None, "custom_text": None, "timeout": True}
    choice_registry.remove(record.get("choice_id", ""))

    if action.get("cancelled"):
        success, status = False, "cancelled"
        result_text = "抉择已取消（会话流已结束），请基于已有信息自行决定并继续。"
    elif action.get("timeout"):
        success, status = True, "success"
        result_text = _format_choice_result(
            options, recommended, None, None,
            note=f"（抉择超时 >{record['choice_timeout']:.0f}s，已自动采纳推荐项）",
        )
    else:
        success, status = True, "success"
        custom_text = (action.get("custom_text") or "")[:CUSTOM_TEXT_MAX] or None
        result_text = _format_choice_result(
            options, recommended, action.get("selected"), custom_text,
            note=str(action.get("note", "") or ""),
        )

    if emit:
        emit(make_tool_result(
            tool_call_id=record.get("tool_call_id", ""),
            tool=_CHOICE_TOOL, success=success, result=result_text,
            duration_ms=round(record.get("duration_ms", 0)),
        ))

    final = dict(record)
    final.pop("choice_future", None)
    final.pop("choice_timeout", None)
    final.pop("choice_options", None)
    final.pop("choice_recommended", None)
    final.update({"success": success, "status": status, "result": result_text})
    return final


def _describe_tool_command(func_name: str, func_args: Dict[str, Any]) -> str:
    """生成审批卡片的可读描述文本。"""
    if func_name == "run_command":
        return str(func_args.get("command", "") or "")
    if func_name == "execute_command":
        return str(func_args.get("command", "") or "")
    if func_name == "run_outside_command":
        cwd = str(func_args.get("cwd", "") or "")
        return f"[cwd: {cwd}] {func_args.get('command', '')}"
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
    exec_decision: Optional[ExecutionDecision] = None,
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

    # Phase 3 T3/T8: 发布 RuntimeEventBus 审批通知
    if chat_id is not None:
        event_bus.approval_required(
            chat_id=chat_id,
            approval_id=approval_id,
            tool_call_id=tool_call_id,
            tool=func_name,
            command=command,
            risk_level=decision.risk_level.value,
            risk_reason=decision.reason,
        )

    record = {
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
        "verdict": decision.verdict.value,
        "read_only": read_only,
        "chat_id": chat_id,  # Phase 3 T3/T8: 供通知链路使用
    }

    # Phase 3 T3/T8: 持久化审批请求到 approval_requests 表
    if exec_decision:
        record["exec_decision"] = exec_decision.to_dict()
    _persist_approval_request(
        approval_id=approval_id,
        tool_call_id=tool_call_id,
        tool_name=func_name,
        command=command,
        risk_level=decision.risk_level.value,
        risk_reason=decision.reason,
        chat_id=chat_id,
    )

    return record


def _persist_approval_request(
    approval_id: str,
    tool_call_id: str,
    tool_name: str,
    command: str,
    risk_level: str,
    risk_reason: str,
    chat_id: Optional[int] = None,
) -> None:
    """Phase 3 T3/T8: 持久化审批请求到数据库（旁路，不阻断执行）。"""
    try:
        from app.core.database import SessionLocal
        from app.models.agent import ApprovalRequest

        db = SessionLocal()
        try:
            ar = ApprovalRequest(
                approval_id=approval_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                command=command,
                risk_level=risk_level,
                risk_reason=risk_reason,
                chat_id=chat_id,
                status="pending",
            )
            db.add(ar)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
    except Exception:
        pass  # 旁路：持久化失败不影响主流程


async def complete_approval(
    record: Dict,
    project_path: Optional[str] = None,
    emit: Optional[Callable[[Dict], None]] = None,
) -> Dict:
    """等待审批结果并完成工具闭环（Phase B-1 + Phase 3 T3/T8 DB 持久化）。

    - approve → 执行命令，构造成功/失败 record，发射 tool_result
    - deny / timeout / cancelled → 注入拒绝结果（success=False），发射 tool_result
    - Phase 3 T3/T8: 审批结果持久化到 approval_requests 表

    调用方约定：在 tool_approval 事件已 yield 给前端后调用本函数。
    """
    try:
        action = await asyncio.wait_for(record["approval_future"], timeout=record["approval_timeout"])
    except asyncio.TimeoutError:
        action = "timeout"
    approval_registry.remove(record["approval_id"])

    # Phase 3 T3/T8: 发布审批完成通知
    event_bus.approval_completed(
        chat_id=record.get("chat_id"),
        approval_id=record.get("approval_id", ""),
        tool_call_id=record.get("tool_call_id", ""),
        tool=record.get("tool", ""),
        action=action,
    )

    # Phase 3 T3/T8: 更新审批请求 DB 状态
    _update_approval_status(record.get("approval_id", ""), action)

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
        # 文件类工具审批完成后：计算绝对路径供前端
        _fp = None
        if final["tool"] in ("write_file", "read_file") and project_path and success:
            _rel = str(final.get("arguments", {}).get("relative_path", ""))
            if _rel:
                _fp = os.path.join(project_path, _rel.replace("/", os.sep))
        emit(make_tool_result(
            tool_call_id=final["tool_call_id"],
            tool=final["tool"],
            success=success,
            result=result_text,
            duration_ms=duration_ms,
            file_path=_fp,
        ))

    return final


def _update_approval_status(approval_id: str, action: str) -> None:
    """Phase 3 T3/T8: 更新审批请求 DB 状态（旁路，不阻断执行）。"""
    if not approval_id:
        return
    try:
        from app.core.database import SessionLocal
        from app.models.agent import ApprovalRequest
        from datetime import datetime

        db = SessionLocal()
        try:
            ar = db.query(ApprovalRequest).filter(ApprovalRequest.approval_id == approval_id).first()
            if ar:
                ar.status = action
                ar.resolved_at = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
    except Exception:
        pass  # 旁路