"""审批注册表 — 进程内 pending 审批管理（Phase B-1）

约束（无 DB / 无配置中心）：
- 审批状态仅存内存 asyncio.Future，进程重启即失效（单 worker 场景可接受）。
- 不新增数据库表；审批历史由 chat 消息记录间接保留。
- 超时默认 APPROVAL_TIMEOUT，可通过 register(timeout=...) 覆盖（测试用）。

用法：
    approval_id, info = approval_registry.register(...)
    # 前端点击 → chat.py 审批 API 调用 approval_registry.resolve(approval_id, "approve")
    action = await asyncio.wait_for(info["future"], timeout=info["timeout"])
    approval_registry.remove(approval_id)
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Dict, List, Optional

APPROVAL_TIMEOUT = 300  # 秒；超时未响应视为拒绝


def _resolve_future(future: "asyncio.Future", action: str) -> None:
    if not future.done():
        try:
            future.set_result(action)
        except Exception:
            pass


class ApprovalRegistry:
    """审批注册表（单例）。resolve 线程安全（经 call_soon_threadsafe）。"""

    def __init__(self):
        self._entries: Dict[str, dict] = {}
        self.default_timeout = APPROVAL_TIMEOUT

    def register(
        self,
        tool_call_id: str,
        tool: str,
        command: str,
        risk_level: str,
        risk_reason: str,
        chat_id: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> "tuple[str, dict]":
        """注册一条待审批操作，返回 (approval_id, info)。

        info: {"future","timeout","chat_id","tool_call_id","tool","command","risk_level","risk_reason"}
        """
        approval_id = "aprv_" + uuid.uuid4().hex[:12]
        future = asyncio.get_running_loop().create_future()
        timeout = float(timeout if timeout is not None else self.default_timeout)
        info = {
            "approval_id": approval_id,
            "future": future,
            "timeout": timeout,
            "chat_id": chat_id,
            "tool_call_id": tool_call_id,
            "tool": tool,
            "command": command,
            "risk_level": risk_level,
            "risk_reason": risk_reason,
        }
        self._entries[approval_id] = info
        return approval_id, info

    def resolve(self, approval_id: str, action: str) -> bool:
        """用户批准/拒绝。action: "approve" | "deny"（线程安全，可从任意线程调用）。"""
        info = self._entries.get(approval_id)
        if not info:
            return False
        future = info["future"]
        if future.done():
            return False
        try:
            loop = future.get_loop()
        except Exception:
            loop = None
        if loop is not None:
            loop.call_soon_threadsafe(_resolve_future, future, action)
        else:
            _resolve_future(future, action)
        return True

    def remove(self, approval_id: str) -> bool:
        """审批结束后清理（幂等）。"""
        return self._entries.pop(approval_id, None) is not None

    def get(self, approval_id: str) -> Optional[dict]:
        return self._entries.get(approval_id)

    def pending(self) -> List[str]:
        """当前所有 pending 的 approval_id（测试/观测用）。"""
        return list(self._entries.keys())

    def cancel_by_chat(self, chat_id: int) -> int:
        """流断开清理：将某 chat 所有 pending 审批置为 cancelled 并移除（幂等，防 Future 泄漏）。"""
        n = 0
        for approval_id in list(self._entries.keys()):
            if self._entries[approval_id].get("chat_id") == chat_id:
                self.resolve(approval_id, "cancelled")
                self._entries.pop(approval_id, None)
                n += 1
        return n


approval_registry = ApprovalRegistry()
