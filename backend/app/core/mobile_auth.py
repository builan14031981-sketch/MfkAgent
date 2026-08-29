"""移动端配对鉴权核心 — 扫码配对 / token 签发校验 / 回环判定（MfkAgent 安卓端）。

鉴权模型（与 docs/安卓端产品规划.md 4.3 对齐）：
  - 本机回环（127.0.0.1 / ::1）= 可信来源，桌面版 Electron 全部走这里，零影响
  - 非回环来源（手机 / 局域网其他设备）访问 /api/* 必须携带
    Authorization: Bearer <token>（配对握手端点 /api/mobile/pair/* 除外）
  - token 一次签发长期有效（sha256 落库），吊销立即失效
"""
from __future__ import annotations

import hashlib
import secrets
import threading
from datetime import datetime, timedelta
from typing import Optional, Tuple

from app.core.database import SessionLocal
from app.models.mobile import PairedDevice

# ── 配对码（内存态即可：只活 5 分钟，进程重启即失效，无持久化价值） ──

_PAIRING_TTL_SECONDS = 300
_pairing_lock = threading.Lock()
_pairing_codes: dict[str, datetime] = {}  # code -> 过期时间


def create_pairing_code() -> str:
    """生成 6 位数字配对码，有效期 _PAIRING_TTL_SECONDS。同时清理过期码。"""
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.utcnow()
    with _pairing_lock:
        expired = [c for c, exp in _pairing_codes.items() if exp <= now]
        for c in expired:
            _pairing_codes.pop(c, None)
        _pairing_codes[code] = now + timedelta(seconds=_PAIRING_TTL_SECONDS)
    return code


def consume_pairing_code(code: str) -> bool:
    """校验并一次性消费配对码（防重放）。"""
    now = datetime.utcnow()
    with _pairing_lock:
        exp = _pairing_codes.get(code)
        if exp is None or exp <= now:
            _pairing_codes.pop(code, None)
            return False
        _pairing_codes.pop(code, None)
        return True


# ── 设备 token ──


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_device_token(device_name: str) -> Tuple[str, int]:
    """签发新设备 token：明文只在本次响应返回，库里只存哈希。"""
    token = secrets.token_hex(32)
    now = datetime.utcnow()
    with SessionLocal() as db:
        device = PairedDevice(
            device_name=(device_name or "").strip()[:100] or "未命名设备",
            token_hash=hash_token(token),
            created_at=now,
            last_seen_at=now,
            revoked=0,
        )
        db.add(device)
        db.commit()
        db.refresh(device)
        return token, device.id


def verify_device_token(token: str) -> Optional[int]:
    """校验 Bearer token；命中则刷新 last_seen 并返回设备 id（未命中返回 None）。

    返回 id 而非 ORM 对象：会话关闭后 DetachedInstance 不可再访问，调用方只需 id。
    """
    if not token or len(token) < 32:
        return None
    with SessionLocal() as db:
        device = (
            db.query(PairedDevice)
            .filter(PairedDevice.token_hash == hash_token(token), PairedDevice.revoked == 0)
            .first()
        )
        if device is None:
            return None
        device_id = device.id
        device.last_seen_at = datetime.utcnow()
        db.commit()
        return device_id


def revoke_device(device_id: int) -> bool:
    """吊销设备：token 立即失效。返回是否找到未吊销的设备。"""
    with SessionLocal() as db:
        device = db.query(PairedDevice).filter(PairedDevice.id == device_id).first()
        if device is None or device.revoked:
            return False
        device.revoked = 1
        db.commit()
        return True


# ── 来源判定 ──


def is_loopback_host(host: str) -> bool:
    """本机回环判定。桌面版 Electron 的请求全部来自 127.0.0.1，直接放行。"""
    if not host:
        return False
    return host in ("127.0.0.1", "::1", "localhost") or host.startswith("127.")
