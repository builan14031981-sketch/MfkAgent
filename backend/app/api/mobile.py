"""移动端（安卓）API — 配对 / 设备管理 / 系统控制 / WOL / 任务推送 WS（MfkAgent 安卓端 M1/M2）。

路由总览（prefix=/api/mobile，main.py 注册）：
  POST /pair/start        PC 端发起配对：生成 6 位配对码 + 可扫码连接信息（仅限本机回环调用）
  POST /pair/confirm      手机提交配对码换取长期 token（一次性消费，防重放；带全局限速）
  GET  /devices           已配对设备列表（PC 设置页 / 手机端均可用）
  POST /devices/{id}/revoke  吊销设备，token 立即失效
  GET  /system/status     PC 工作状态概览（运行中 AgentRun 数、后端 uptime 等）
  POST /system/power      远程关机 / 重启 / 锁屏（必须 confirm=true；写入沙箱审计表）
  POST /system/wol        Wake-on-LAN 魔术包（仅局域网内有效，见规划文档 3.2 物理前提）
  WS   /ws                前台长连接：AgentRun 状态变化推送（M2 推送方案，见规划文档）

鉴权：非回环来源由 main.py 的 mobile_auth 中间件统一拦截（/pair/* 握手除外）。
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.config import BACKEND_DIR
from app.core.database import SessionLocal
from app.core.mobile_auth import (
    consume_pairing_code,
    create_pairing_code,
    issue_device_token,
    revoke_device,
    verify_device_token,
)
from app.core.port_manager import read_port_file
from app.core.sandbox import decode_subprocess_output, run_subprocess
from app.models.agent import AgentRun, SandboxAuditLog
from app.models.mobile import PairedDevice

logger = logging.getLogger(__name__)

router = APIRouter()

_PROCESS_START_MONOTONIC = time.monotonic()

# pair/confirm 全局限速：5 分钟窗口内失败超过阈值即临时锁死（6 位码防爆破底线）
_CONFIRM_FAIL_LIMIT = 20
_confirm_fail_lock = asyncio.Lock()
_confirm_fails: List[float] = []


async def _check_confirm_rate_limit() -> None:
    async with _confirm_fail_lock:
        now = time.monotonic()
        while _confirm_fails and now - _confirm_fails[0] > 300:
            _confirm_fails.pop(0)
        if len(_confirm_fails) >= _CONFIRM_FAIL_LIMIT:
            raise HTTPException(status_code=429, detail="配对码错误次数过多，请 5 分钟后再试")


async def _record_confirm_fail() -> None:
    async with _confirm_fail_lock:
        _confirm_fails.append(time.monotonic())


# ── 工具函数 ──


def _server_port() -> int:
    """当前后端端口：端口文件 > MFK_PORT 环境变量 > 默认 8001。"""
    port = read_port_file()
    if port:
        return port
    env_port = os.environ.get("MFK_PORT")
    if env_port and env_port.isdigit():
        return int(env_port)
    return 8001


def _lan_ips() -> List[str]:
    """枚举本机局域网 IPv4（供二维码 payload 使用）。"""
    ips: List[str] = []
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip.startswith("127.") or ip.startswith("169.254."):
                continue
            ips.append(ip)
    except OSError:
        pass
    # 兜底：直连外网时系统路由表对应的本机地址
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("223.5.5.5", 53))  # 不发包，仅选路由
            ips.append(s.getsockname()[0])
            s.close()
        except OSError:
            pass
    return ips


# ── 配对 ──


class PairConfirmRequest(BaseModel):
    code: str
    device_name: str = ""


@router.post("/pair/start")
async def pair_start(request: Request):
    """PC 端发起配对。仅限本机回环调用（配对码只应展示在 PC 自己的屏幕上）。"""
    client = request.client.host if request.client else ""
    from app.core.mobile_auth import is_loopback_host

    if not is_loopback_host(client):
        raise HTTPException(status_code=403, detail="配对码只能在本机发起")
    code = create_pairing_code()
    port = _server_port()
    bases = [f"http://{ip}:{port}" for ip in _lan_ips()]
    return {
        "code": code,
        "expires_in": 300,
        "port": port,
        "lan_ips": _lan_ips(),
        # 手机扫码后解析该 JSON：遍历 bases 探测 /health 可达项 + code 换 token
        "qr_payload": {"v": 1, "code": code, "bases": bases},
    }


@router.post("/pair/confirm")
async def pair_confirm(req: PairConfirmRequest):
    """手机端用配对码换取长期 token（码一次性消费）。"""
    await _check_confirm_rate_limit()
    if not consume_pairing_code(req.code.strip()):
        await _record_confirm_fail()
        raise HTTPException(status_code=400, detail="配对码无效或已过期")
    token, device_id = issue_device_token(req.device_name)
    return {
        "token": token,
        "device_id": device_id,
        "device_name": (req.device_name or "").strip()[:100] or "未命名设备",
        "api_base_hint": "请使用扫码 payload 中探测成功的 base",
    }


# ── 设备管理 ──


@router.get("/devices")
async def list_devices():
    with SessionLocal() as db:
        rows = db.query(PairedDevice).order_by(PairedDevice.id.desc()).all()
        return [
            {
                "id": d.id,
                "device_name": d.device_name,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
                "revoked": bool(d.revoked),
            }
            for d in rows
        ]


@router.post("/devices/{device_id}/revoke")
async def revoke_device_api(device_id: int):
    if not revoke_device(device_id):
        raise HTTPException(status_code=404, detail="设备不存在或已吊销")
    return {"ok": True}


# ── 系统控制 ──


@router.get("/system/status")
async def system_status():
    with SessionLocal() as db:
        running = db.query(AgentRun).filter(AgentRun.status == "running").count()
    db_path = BACKEND_DIR / "mfkagent.db"
    return {
        "platform": os.name,
        "uptime_seconds": int(time.monotonic() - _PROCESS_START_MONOTONIC),
        "running_runs": running,
        "db_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "server_time": datetime.utcnow().isoformat(),
    }


class PowerRequest(BaseModel):
    action: str  # shutdown | reboot | lock
    confirm: bool


_POWER_COMMANDS = {
    "shutdown": ["shutdown", "/s", "/t", "5", "/c", "MfkAgent 手机端远程关机"],
    "reboot": ["shutdown", "/r", "/t", "5", "/c", "MfkAgent 手机端远程重启"],
    "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
}


@router.post("/system/power")
async def system_power(req: PowerRequest):
    """远程关机/重启/锁屏。confirm 必须为 true（手机端二次确认），并落审计表。"""
    if not req.confirm:
        raise HTTPException(status_code=400, detail="危险操作必须显式 confirm=true")
    argv = _POWER_COMMANDS.get(req.action)
    if argv is None:
        raise HTTPException(status_code=400, detail=f"不支持的操作: {req.action}")

    started = time.monotonic()
    completed = run_subprocess(argv, cwd=str(BACKEND_DIR), timeout=15)
    stdout = decode_subprocess_output(completed.stdout or b"")
    stderr = decode_subprocess_output(completed.stderr or b"")
    duration_ms = int((time.monotonic() - started) * 1000)
    success = completed.returncode == 0

    # 审计落库（写入失败不阻断执行结果返回，与 SandboxAuditLog 设计约定一致）
    try:
        with SessionLocal() as db:
            db.add(
                SandboxAuditLog(
                    tool_name=f"mobile_power_{req.action}",
                    command=" ".join(argv),
                    cwd=str(BACKEND_DIR),
                    duration_ms=duration_ms,
                    exit_code=completed.returncode,
                    output_size=len(stdout) + len(stderr),
                    success=success,
                    error_message=(stderr or None)[:2000],
                )
            )
            db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("mobile power 审计写入失败（不阻断）: %s", e)

    if not success:
        raise HTTPException(status_code=500, detail=f"命令执行失败(exit={completed.returncode}): {stderr[:200]}")
    return {"ok": True, "action": req.action, "duration_ms": duration_ms}


class WolRequest(BaseModel):
    mac: str


@router.post("/system/wol")
async def system_wol(req: WolRequest):
    """发送 Wake-on-LAN 魔术包。注意：广播不出局域网，跨公网唤醒需常开设备代发。"""
    mac_clean = req.mac.replace(":", "").replace("-", "").strip().lower()
    if len(mac_clean) != 12 or any(c not in "0123456789abcdef" for c in mac_clean):
        raise HTTPException(status_code=400, detail="MAC 地址格式无效（应为 AA:BB:CC:DD:EE:FF）")
    mac_bytes = bytes.fromhex(mac_clean)
    magic = b"\xff" * 6 + mac_bytes * 16
    sent = 0
    for port in (9, 7):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.settimeout(2)
                s.sendto(magic, ("255.255.255.255", port))
                sent += 1
        except OSError as e:
            logger.warning("WOL 发送失败(port=%d): %s", port, e)
    if sent == 0:
        raise HTTPException(status_code=500, detail="魔术包发送失败")
    return {"ok": True, "packets": sent}


# ── 前台推送 WebSocket ──


@router.websocket("/ws")
async def mobile_ws(websocket: WebSocket, token: str = ""):
    """前台长连接推送。token 走查询参数（浏览器 WS 无法自定义 header）。

    推送协议：
      服务端 → {"type": "hello", "device_id": int}
      服务端 → {"type": "runs_update", "running": int, "runs": [{id, chat_id, status, state}]}
    客户端可发 "ping"，服务端回 "pong"（保活）。
    """
    device_id = verify_device_token(token)
    if device_id is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    await websocket.send_json({"type": "hello", "device_id": device_id})

    last_snapshot: dict[int, str] = {}
    try:
        while True:
            # 有状态的 AgentRun 快照：变化才推，无变化静默（3s 轮询，SQLite 开销可忽略）
            with SessionLocal() as db:
                rows = (
                    db.query(AgentRun.id, AgentRun.chat_id, AgentRun.status, AgentRun.state)
                    .order_by(AgentRun.id.desc())
                    .limit(20)
                    .all()
                )
            snapshot = {r.id: r.status for r in rows}
            if snapshot != last_snapshot:
                last_snapshot = snapshot
                await websocket.send_json(
                    {
                        "type": "runs_update",
                        "running": sum(1 for s in snapshot.values() if s == "running"),
                        "runs": [
                            {"id": r.id, "chat_id": r.chat_id, "status": r.status, "state": r.state}
                            for r in rows
                        ],
                    }
                )

            # 等待客户端消息或超时（超时即进入下一轮轮询）
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=3.0)
                if msg == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                continue
    except WebSocketDisconnect:
        return
    except Exception as e:  # noqa: BLE001
        logger.warning("mobile ws 异常断开: %s", e)
        return
