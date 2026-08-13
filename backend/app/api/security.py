"""安全中心只读接口（专业向安全可视化）。

提供：
  - GET /api/security/policy         审批矩阵（工具 × 三种审批模式 → 执行动作）
  - GET /api/security/status         沙箱/资源/网络 只读状态（派生自现有硬编码配置）
  - GET /api/security/audit          审计日志（分页 + 筛选）
  - GET /api/security/audit/export   审计日志 CSV 导出
  - GET /api/security/logs           应用日志文件列表
  - GET /api/security/logs/current   应用日志内容（筛选 + 分页）
  - GET /api/security/logs/download  应用日志下载
  - GET /api/security/approvals      审批记录（分页 + 状态/工具筛选）
  - POST /api/security/command-risk  命令风险预览（复用现有 CommandRiskEngine，纯计算不改状态）
  - GET /api/security/guardrails     防护清单（禁执行目录 / 只读工具 / 只读命令白名单）

设计约束（遵守项目硬约束）：
  - 不改 AgentRuntime / Tool Runtime / risk_engine / approval_policy / permission / sandbox
  - 本模块纯只读，派生现有策略常量，不修改任何执行链
"""
from __future__ import annotations

import csv
import io
import logging
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from app.core.database import SessionLocal
from app.models.agent import ApprovalRequest, SandboxAuditLog

# 只读引用现有策略常量（单一事实来源，避免两处漂移）
from app.core.tool_runtime.risk_engine import (
    TOOL_RISK_POLICY,
    READ_ONLY_TOOLS,
    RiskDecision,
    ExecutionAction,
    command_risk_engine,
)
from app.core.tool_runtime.approval_policy import ApprovalMode, ApprovalPolicy
from app.core import sandbox as sandbox_mod
from app.core.log_config import LOG_DIR, read_log_file

logger = logging.getLogger(__name__)

router = APIRouter()

MODES = ["safe", "standard", "autonomous"]


def _category(tool: str) -> str:
    """按工具名前缀归类，用于矩阵分组展示。"""
    if tool.startswith("git_"):
        return "Git"
    if tool.startswith("github_"):
        return "GitHub"
    if tool in ("read_file", "write_file", "list_files", "search_files",
                "delete_file", "rename_file"):
        return "文件"
    if tool in ("add_memory", "manage_todos"):
        return "数据"
    return "其他"


def _action_for_tool(tool: str, mode: str) -> str:
    """计算某工具在指定审批模式（build 语境）下的最终动作。

    返回值：allow / approve / block
    """
    if tool in READ_ONLY_TOOLS:
        return "allow"
    if tool in TOOL_RISK_POLICY:
        verdict, risk, reason = TOOL_RISK_POLICY[tool]
        policy = ApprovalPolicy(ApprovalMode(mode))
        ed = policy.decide(RiskDecision(verdict, risk, reason, tool))
        if ed.action == ExecutionAction.EXECUTE:
            return "allow"
        if ed.action == ExecutionAction.REQUIRE_APPROVAL:
            return "approve"
        return "block"
    # 未在策略表声明的工具：build 模式放行（与 risk_engine 一致）
    return "allow"


@router.get("/policy")
async def get_policy():
    """审批矩阵：读取现有 TOOL_RISK_POLICY + READ_ONLY_TOOLS，按模式计算动作。"""
    tools = []
    for tool, (verdict, risk, reason) in TOOL_RISK_POLICY.items():
        actions = {m: _action_for_tool(tool, m) for m in MODES}
        tools.append({
            "name": tool,
            "category": _category(tool),
            "reason": reason,
            "read_only": False,
            "actions": actions,
        })
    # 只读工具单独列出（全部模式自动放行）
    read_only = sorted(READ_ONLY_TOOLS)
    return {
        "modes": MODES,
        "read_only_tools": read_only,
        "write_tools": sorted(tools, key=lambda t: (t["category"], t["name"])),
        "note": "命令执行(run_command/execute_command)由命令风险引擎单独判定：只读白名单自动放行、常规写入需审批、危险命令强制审批。",
    }


@router.get("/status")
async def get_status():
    """沙箱/资源/网络 只读状态（派生自现有硬编码配置）。"""
    quota = sandbox_mod.DISK_QUOTA_BYTES
    return {
        "sandbox_path_guard": True,          # resolve_sandbox_path 路径越权拦截
        "forbidden_dirs_enabled": True,      # is_forbidden_cwd 禁执行目录黑名单
        "disk_quota_gb": {
            k: round(v / (1024 ** 3), 1) for k, v in quota.items()
        },
        "run_command_timeout_sec": 30,       # run_command TIMEOUT
        "execute_command_timeout_sec": 60,   # execute_command EXECUTE_TIMEOUT（上限 300）
        "execute_command_output_chars": 10000,
        "plan_readonly": True,               # plan 模式一律只读
    }


@router.get("/audit")
async def list_audit(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tool_name: Optional[str] = Query(None),
    success: Optional[bool] = Query(None),
):
    """审计日志：分页 + 按工具名 / 结果筛选。"""
    db = SessionLocal()
    try:
        q = db.query(SandboxAuditLog)
        if tool_name:
            q = q.filter(SandboxAuditLog.tool_name == tool_name)
        if success is not None:
            q = q.filter(SandboxAuditLog.success == success)
        total = q.count()
        rows = q.order_by(SandboxAuditLog.created_at.desc(), SandboxAuditLog.id.desc()) \
                .offset(offset).limit(limit).all()
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "items": [
                {
                    "id": r.id,
                    "chat_id": r.chat_id,
                    "agent_run_id": r.agent_run_id,
                    "tool_name": r.tool_name,
                    "command": r.command,
                    "cwd": r.cwd,
                    "duration_ms": r.duration_ms,
                    "exit_code": r.exit_code,
                    "output_size": r.output_size,
                    "success": r.success,
                    "error_message": r.error_message,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
        }
    finally:
        db.close()


@router.get("/audit/export")
async def export_audit(
    tool_name: Optional[str] = Query(None),
    success: Optional[bool] = Query(None),
):
    """审计日志 CSV 导出（全部匹配行，不分页）。"""
    db = SessionLocal()
    try:
        q = db.query(SandboxAuditLog)
        if tool_name:
            q = q.filter(SandboxAuditLog.tool_name == tool_name)
        if success is not None:
            q = q.filter(SandboxAuditLog.success == success)
        rows = q.order_by(SandboxAuditLog.created_at.desc(), SandboxAuditLog.id.desc()).all()

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "tool_name", "command", "cwd", "duration_ms",
                         "exit_code", "output_size", "success", "error_message",
                         "created_at", "chat_id", "agent_run_id"])
        for r in rows:
            writer.writerow([
                r.id, r.tool_name, r.command, r.cwd, r.duration_ms,
                r.exit_code, r.output_size, "1" if r.success else "0",
                r.error_message or "",
                r.created_at.isoformat() if r.created_at else "",
                r.chat_id or "", r.agent_run_id or "",
            ])
        buf.seek(0)
        filename = f"mfk_audit_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    finally:
        db.close()


# ───────────────────── 应用日志（文件读取） ─────────────────────


@router.get("/logs")
async def list_log_files():
    """列出可用日志文件（按修改时间倒序）。"""
    log_dir = LOG_DIR
    if not os.path.isdir(log_dir):
        return {"files": []}
    files = []
    for fname in sorted(os.listdir(log_dir), reverse=True):
        fpath = os.path.join(log_dir, fname)
        if os.path.isfile(fpath) and fname.endswith(".log"):
            size = os.path.getsize(fpath)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat()
            files.append({
                "name": fname,
                "size": size,
                "modified": mtime,
            })
    return {"files": files}


@router.get("/logs/current")
async def read_current_log(
    level: Optional[str] = Query(None, description="筛选级别：ERROR / WARNING / INFO / DEBUG"),
    search: Optional[str] = Query(None, description="关键词搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(100, ge=10, le=500, description="每页条数"),
):
    """读取今日日志，支持按级别/关键词筛选 + 分页。"""
    log_file = LOG_DIR / "app.log"
    return read_log_file(str(log_file), level=level, search=search, page=page, page_size=page_size)


@router.get("/logs/download")
async def download_logs():
    """下载完整应用日志文件。"""
    log_file = LOG_DIR / "app.log"
    if not os.path.isfile(log_file):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="日志文件不存在")
    return FileResponse(
        path=str(log_file),
        filename="app.log",
        media_type="text/plain; charset=utf-8",
    )


# ───────────────────── 审批记录 ─────────────────────


@router.get("/approvals")
async def list_approvals(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="筛选状态：pending / approve / deny / timeout / cancelled"),
    tool_name: Optional[str] = Query(None, description="工具名筛选"),
):
    """审批记录：分页 + 按状态/工具名筛选。"""
    db = SessionLocal()
    try:
        q = db.query(ApprovalRequest)
        if status:
            q = q.filter(ApprovalRequest.status == status)
        if tool_name:
            q = q.filter(ApprovalRequest.tool_name == tool_name)
        total = q.count()
        rows = q.order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc()) \
                .offset(offset).limit(limit).all()
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "items": [
                {
                    "id": r.id,
                    "approval_id": r.approval_id,
                    "tool_name": r.tool_name,
                    "command": r.command,
                    "risk_level": r.risk_level,
                    "risk_reason": r.risk_reason,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
                }
                for r in rows
            ],
        }
    finally:
        db.close()


# ───────────────────── 命令风险预览 ─────────────────────


class CommandRiskRequest(BaseModel):
    command: str
    mode: str = "build"  # build / plan
    engine: str = "run_command"  # run_command / execute_command


@router.post("/command-risk")
async def preview_command_risk(req: CommandRiskRequest):
    """命令风险预览：复用现有 CommandRiskEngine，纯计算不修改状态。

    返回 RiskDecision 的核心字段，不依赖审批模式，展示命令本身的风险特征。
    """
    if req.engine == "execute_command":
        decision = command_risk_engine.evaluate_execute(req.command, req.mode)
    else:
        decision = command_risk_engine.evaluate(req.command, req.mode)
    return {
        "verdict": decision.verdict.value,
        "risk_level": decision.risk_level.value,
        "reason": decision.reason,
        "command": decision.command,
    }


# ───────────────────── 防护清单 ─────────────────────


@router.get("/guardrails")
async def get_guardrails():
    """防护清单：禁执行目录 / 只读命令白名单 / 只读工具 / 写入工具规则。"""
    # 禁执行目录（从 sandbox 模块读取，纯只读展示）
    forbidden_dirs = sorted(sandbox_mod._FORBIDDEN_DIRS)

    # 只读命令白名单（从 risk_engine 模块读取）
    from app.core.tool_runtime.risk_engine import _ALLOWED_COMMANDS, _ALLOWED_PY_MODULES

    allowed_commands = []
    for cmd, prefixes in _ALLOWED_COMMANDS:
        allowed_commands.append({
            "command": cmd,
            "allowed_args": list(prefixes) if prefixes else None,
        })
    allowed_commands.append({
        "command": "python",
        "allowed_args": ["--version", "-V", f"-m {'/'.join(sorted(_ALLOWED_PY_MODULES))}"],
    })

    # 写入工具规则
    write_tools = []
    for tool, (verdict, risk, reason) in TOOL_RISK_POLICY.items():
        write_tools.append({
            "name": tool,
            "verdict": verdict.value,
            "risk_level": risk.value,
            "reason": reason,
        })

    return {
        "forbidden_dirs": forbidden_dirs,
        "allowed_commands": allowed_commands,
        "read_only_tools": sorted(READ_ONLY_TOOLS),
        "write_tools": sorted(write_tools, key=lambda t: t["name"]),
        "disk_quota_gb": {
            k: round(v / (1024 ** 3), 1) for k, v in sandbox_mod.DISK_QUOTA_BYTES.items()
        },
    }
