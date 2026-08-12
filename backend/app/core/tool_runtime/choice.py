"""抉择注册表 — 进程内 pending 抉择管理（ask_user_choice 工具）

架构对齐 approval.py 的 pending record 模式：
- 抉择状态仅存内存 asyncio.Future，进程重启即失效（单 worker 场景可接受）。
- 不新增数据库表；抉择历史由 chat 消息记录间接保留。
- 超时默认 CHOICE_TIMEOUT；超时后由 executor 自动采纳推荐项。

用法：
    choice_id, info = choice_registry.register(...)
    # 前端点击 → chat.py /choice API 调用 choice_registry.resolve(choice_id, {...})
    action = await asyncio.wait_for(info["future"], timeout=info["timeout"])
    choice_registry.remove(choice_id)
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional

CHOICE_TIMEOUT = 300  # 秒；超时未响应自动采纳推荐项
CUSTOM_TEXT_MAX = 4000  # 用户自定义输入的后端截断上限


def _resolve_future(future: "asyncio.Future", action: Any) -> None:
    if not future.done():
        try:
            future.set_result(action)
        except Exception:
            pass


class ChoiceRegistry:
    """抉择注册表（单例）。resolve 线程安全（经 call_soon_threadsafe）。"""

    def __init__(self):
        self._entries: Dict[str, dict] = {}
        self.default_timeout = CHOICE_TIMEOUT

    def register(
        self,
        tool_call_id: str,
        chat_id: Optional[int] = None,
        question: str = "",
        options: Optional[List[dict]] = None,
        recommended: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> "tuple[str, dict]":
        """注册一条待抉择请求，返回 (choice_id, info)。

        info: {"future","timeout","chat_id","tool_call_id","question","options","recommended"}
        """
        choice_id = "chc_" + uuid.uuid4().hex[:12]
        future = asyncio.get_running_loop().create_future()
        timeout = float(timeout if timeout is not None else self.default_timeout)
        info = {
            "choice_id": choice_id,
            "future": future,
            "timeout": timeout,
            "chat_id": chat_id,
            "tool_call_id": tool_call_id,
            "question": question,
            "options": options or [],
            "recommended": recommended,
        }
        self._entries[choice_id] = info
        return choice_id, info

    def resolve(self, choice_id: str, action: dict) -> bool:
        """用户作出抉择。action: {"selected": int|None, "custom_text": str|None}（线程安全）。"""
        info = self._entries.get(choice_id)
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

    def remove(self, choice_id: str) -> bool:
        """抉择结束后清理（幂等）。"""
        return self._entries.pop(choice_id, None) is not None

    def get(self, choice_id: str) -> Optional[dict]:
        return self._entries.get(choice_id)

    def pending(self) -> List[str]:
        """当前所有 pending 的 choice_id（测试/观测用）。"""
        return list(self._entries.keys())

    def cancel_by_chat(self, chat_id: int) -> int:
        """流断开清理：将某 chat 所有 pending 抉择置为 cancelled 并移除（幂等，防 Future 泄漏）。"""
        n = 0
        for choice_id in list(self._entries.keys()):
            if self._entries[choice_id].get("chat_id") == chat_id:
                self.resolve(choice_id, {"selected": None, "custom_text": None, "cancelled": True})
                self._entries.pop(choice_id, None)
                n += 1
        return n


choice_registry = ChoiceRegistry()
