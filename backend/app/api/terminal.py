"""内置终端 API（2026-08-14）。

端点：
  - POST /api/terminal                创建会话（返回 session_id）
  - GET  /api/terminal/{sid}          查询会话状态
  - POST /api/terminal/{sid}/kill     强制终止会话
  - WS   /api/terminal/ws?sid=xxx     连接会话（disconnect 保留会话，发送 close 消息则终止）

WS 消息协议（JSON 文本帧）：
  客户端 → 服务端：
    {type:"input", data:"..."}          原始输入（xterm onData 逐键转发）
    {type:"resize", cols:120, rows:30}  尺寸变化（FitAddon → 后端 PTY）
    {type:"approve", id:"..."}          批准挂起的危险命令
    {type:"reject",  id:"..."}          拒绝挂起的危险命令
    {type:"close"}                      终止会话并断开
  服务端 → 客户端：
    {type:"output", data:"..."}         终端输出
    {type:"approval", id, command}      危险命令待审批
    {type:"exit", code}                 PTY 进程退出
    {type:"error", message}             错误
    {type:"ready", sid, cwd, cols, rows}连接成功

安全：cwd 创建时锚定（is_forbidden_cwd 校验）；危险命令行级拦截（见 services.terminal）。
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.sandbox import is_forbidden_cwd
from app.services.terminal import DEFAULT_SHELL, get_terminal_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class TerminalCreateRequest(BaseModel):
    shell: str = DEFAULT_SHELL
    cwd: Optional[str] = None
    cols: int = 120
    rows: int = 30


class TerminalCreateResponse(BaseModel):
    session_id: str
    cwd: str
    shell: str


@router.post("/terminal", response_model=TerminalCreateResponse)
async def create_terminal(req: TerminalCreateRequest):
    """创建终端会话。cwd 缺省回退当前用户主目录；命中禁执行目录则拒绝。"""
    cwd = req.cwd or ""
    import os

    if not cwd:
        cwd = os.path.expanduser("~")
    cwd = os.path.abspath(cwd)
    if not os.path.isdir(cwd):
        raise HTTPException(status_code=400, detail=f"cwd 不存在: {cwd}")
    forbidden, reason = is_forbidden_cwd(cwd)
    if forbidden:
        raise HTTPException(status_code=400, detail=f"cwd 命中禁执行目录: {reason}")

    manager = get_terminal_manager()
    session = manager.create(req.shell, cwd, req.cols, req.rows)
    session.spawn()
    logger.info("terminal created: %s cwd=%s", session.session_id, cwd)
    return TerminalCreateResponse(session_id=session.session_id, cwd=cwd, shell=req.shell)


@router.get("/terminal/{sid}")
async def get_terminal(sid: str):
    session = get_terminal_manager().get(sid)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "session_id": session.session_id,
        "cwd": session.cwd,
        "shell": session.shell,
        "connected": session.connected,
    }


@router.post("/terminal/{sid}/kill")
async def kill_terminal(sid: str):
    manager = get_terminal_manager()
    session = manager.get(sid)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    manager.remove(sid)
    return {"ok": True}


@router.websocket("/terminal/ws")
async def terminal_ws(ws: WebSocket):
    """WebSocket 终端连接。?sid= 缺省时自动创建新会话。"""
    await ws.accept()
    import os as _os

    manager = get_terminal_manager()
    sid = ws.query_params.get("sid") or ""

    if sid and manager.get(sid) is None:
        await ws.send_json({"type": "error", "message": "会话不存在或已过期"})
        await ws.close()
        return

    if sid:
        session = manager.get(sid)
    else:
        # 自动创建：cwd 回退主目录
        cwd = _os.path.expanduser("~")
        session = manager.create(DEFAULT_SHELL, cwd, 120, 30)
        session.spawn()
        sid = session.session_id
        logger.info("terminal ws auto-created: %s", sid)

    if session.connected:
        await ws.send_json({"type": "error", "message": "会话已被其他窗口占用"})
        await ws.close()
        return

    import asyncio as _asyncio

    loop = _asyncio.get_running_loop()
    q: _asyncio.Queue = _asyncio.Queue()
    session.connected = True
    session.last_connected_at = _asyncio.get_event_loop().time()
    import time as _time

    session.last_connected_at = _time.time()
    session.start_reader(loop, q)

    try:
        await ws.send_json({
            "type": "ready",
            "sid": session.session_id,
            "cwd": session.cwd,
            "shell": session.shell,
            "cols": session.cols,
            "rows": session.rows,
        })
    except Exception:  # noqa: BLE001
        pass

    async def send_loop():
        try:
            while True:
                event = await q.get()
                try:
                    await ws.send_json(event)
                except Exception:  # noqa: BLE001
                    return
        finally:
            pass

    send_task = loop.create_task(send_loop())

    try:
        while True:
            raw = await ws.receive_text()
            try:
                import json as _json

                msg = _json.loads(raw)
            except Exception:  # noqa: BLE001
                continue
            mtype = msg.get("type")
            if mtype == "input":
                for event in session.on_input(msg.get("data") or ""):
                    await ws.send_json(event)
            elif mtype == "resize":
                session.on_resize(int(msg.get("cols") or 120), int(msg.get("rows") or 30))
            elif mtype == "approve":
                session.on_approve()
            elif mtype == "reject":
                session.on_reject()
            elif mtype == "close":
                manager.remove(session.session_id)
                break
            elif mtype == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        # 断线：保留会话（PTY 继续跑），等待重连或 TTL 回收
        logger.info("terminal ws disconnected: %s", sid)
    finally:
        send_task.cancel()
        session.connected = False
        session.last_connected_at = _time.time()