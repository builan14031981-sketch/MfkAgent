"""RuntimeEventBus — 统一运行时事件总线（Phase 3 T3/T8）

职责：
  统一所有系统通知来源，不新增第四套体系。
  NotificationManager 作为消费者，桥接事件到 SSE / WebSocket（未来扩展）。

设计原则：
  - 不修改 ToolEventSource（请求级工具事件）
  - 不修改 RuntimeEventRecorder（持久化审计）
  - 本模块作为"通知消费层"，消费 Runtime 事件并广播到外部通道

事件类型（与 RuntimeEventType 对齐）：
  TASK_STARTED / TASK_COMPLETED / TASK_FAILED
  APPROVAL_REQUIRED / APPROVAL_COMPLETED
  ERROR

消费者：
  - SSE 事件桥接（chat.py 中 _put 回调）
  - 桌面通知（notify.ts 前端）
  - WebSocket（未来扩展）
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Callable, Any

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """通知事件类型 — 与 RuntimeEventType 对齐"""
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_COMPLETED = "approval_completed"
    ERROR = "error"


@dataclass
class RuntimeNotification:
    """统一运行时通知事件"""
    type: NotificationType
    chat_id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "chat_id": self.chat_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }

    def to_sse(self) -> dict:
        """转为 SSE 兼容格式（顶层 type 字段 + 扁平化 data）。"""
        result = {"type": self.type.value}
        if self.chat_id is not None:
            result["chat_id"] = self.chat_id
        result.update(self.data)
        return result


class RuntimeEventBus:
    """统一运行时事件总线（单例）。

    所有系统通知通过此总线发布，消费者（NotificationManager、SSE 桥接等）订阅。
    """

    def __init__(self):
        # chat_id → [callback]
        self._subscribers: Dict[int, List[Callable[[RuntimeNotification], None]]] = {}
        # 全局订阅者（不按 chat_id 过滤）
        self._global_subscribers: List[Callable[[RuntimeNotification], None]] = []
        self._history: List[RuntimeNotification] = []
        self._max_history = 1000

    def subscribe(
        self,
        chat_id: int,
        callback: Callable[[RuntimeNotification], None],
    ) -> None:
        """订阅某 chat 的通知事件。"""
        if chat_id not in self._subscribers:
            self._subscribers[chat_id] = []
        self._subscribers[chat_id].append(callback)

    def subscribe_global(self, callback: Callable[[RuntimeNotification], None]) -> None:
        """订阅所有 chat 的通知事件（不按 chat_id 过滤）。"""
        self._global_subscribers.append(callback)

    def unsubscribe(
        self,
        chat_id: int,
        callback: Callable[[RuntimeNotification], None],
    ) -> None:
        """取消订阅某 chat 的通知事件。"""
        if chat_id in self._subscribers:
            try:
                self._subscribers[chat_id].remove(callback)
            except ValueError:
                pass
            if not self._subscribers[chat_id]:
                del self._subscribers[chat_id]

    def publish(self, notification: RuntimeNotification) -> None:
        """发布通知到所有订阅者（同步调用，不阻塞）。"""
        # 记录历史
        self._history.append(notification)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # 广播给 chat 订阅者
        chat_id = notification.chat_id
        if chat_id is not None and chat_id in self._subscribers:
            for callback in self._subscribers[chat_id]:
                try:
                    callback(notification)
                except Exception as e:
                    logger.error(f"EventBus callback error: {e}")

        # 广播给全局订阅者
        for callback in self._global_subscribers:
            try:
                callback(notification)
            except Exception as e:
                logger.error(f"EventBus global callback error: {e}")

    # ──── 便捷发布方法 ────

    def approval_required(
        self,
        chat_id: int,
        approval_id: str,
        tool_call_id: str,
        tool: str,
        command: str,
        risk_level: str,
        risk_reason: str,
    ) -> RuntimeNotification:
        """发布审批请求通知。"""
        notification = RuntimeNotification(
            type=NotificationType.APPROVAL_REQUIRED,
            chat_id=chat_id,
            data={
                "approval_id": approval_id,
                "tool_call_id": tool_call_id,
                "tool": tool,
                "command": command,
                "risk_level": risk_level,
                "risk_reason": risk_reason,
                "title": f"需要审批: {tool}",
                "message": f"Agent 请求执行: {command}",
            },
        )
        self.publish(notification)
        return notification

    def approval_completed(
        self,
        chat_id: int,
        approval_id: str,
        tool_call_id: str,
        tool: str,
        action: str,
    ) -> RuntimeNotification:
        """发布审批完成通知。"""
        notification = RuntimeNotification(
            type=NotificationType.APPROVAL_COMPLETED,
            chat_id=chat_id,
            data={
                "approval_id": approval_id,
                "tool_call_id": tool_call_id,
                "tool": tool,
                "action": action,
                "title": f"审批完成: {tool}",
                "message": f"{'已批准' if action == 'approve' else '已拒绝'}: {tool}",
            },
        )
        self.publish(notification)
        return notification

    def task_completed(
        self,
        chat_id: int,
        task_description: str = "",
        success: bool = True,
        result_summary: str = "",
    ) -> RuntimeNotification:
        """发布任务完成通知。"""
        notification = RuntimeNotification(
            type=NotificationType.TASK_COMPLETED,
            chat_id=chat_id,
            data={
                "task_description": task_description,
                "success": success,
                "result_summary": result_summary,
                "title": "任务完成" if success else "任务失败",
                "message": result_summary,
            },
        )
        self.publish(notification)
        return notification

    def task_started(
        self,
        chat_id: int,
        task_description: str = "",
    ) -> RuntimeNotification:
        """发布任务开始通知。"""
        notification = RuntimeNotification(
            type=NotificationType.TASK_STARTED,
            chat_id=chat_id,
            data={
                "task_description": task_description,
                "title": "任务开始",
                "message": task_description,
            },
        )
        self.publish(notification)
        return notification

    def error(
        self,
        chat_id: int,
        error_type: str = "",
        error_message: str = "",
        recoverable: bool = True,
    ) -> RuntimeNotification:
        """发布错误通知。"""
        notification = RuntimeNotification(
            type=NotificationType.ERROR,
            chat_id=chat_id,
            data={
                "error_type": error_type,
                "error_message": error_message,
                "recoverable": recoverable,
                "title": "执行错误",
                "message": error_message,
            },
        )
        self.publish(notification)
        return notification


# 全局单例
event_bus = RuntimeEventBus()


# ──── 向后兼容：NotificationManager 适配器 ────

class NotificationManager:
    """向后兼容的 NotificationManager，委托给 RuntimeEventBus。

    保留旧接口（emit_approval_required / emit_task_completed / emit_error），
    内部委托给 RuntimeEventBus.publish()。
    """

    def emit_approval_required(
        self,
        chat_id: int,
        tool_call_id: str,
        tool: str,
        command: str,
        risk_level: str,
        risk_reason: str,
    ) -> RuntimeNotification:
        return event_bus.approval_required(
            chat_id=chat_id,
            approval_id="",  # 旧接口无 approval_id
            tool_call_id=tool_call_id,
            tool=tool,
            command=command,
            risk_level=risk_level,
            risk_reason=risk_reason,
        )

    def emit_task_completed(
        self,
        chat_id: int,
        task_description: str,
        success: bool,
        result_summary: str,
    ) -> RuntimeNotification:
        return event_bus.task_completed(
            chat_id=chat_id,
            task_description=task_description,
            success=success,
            result_summary=result_summary,
        )

    def emit_error(
        self,
        chat_id: int,
        error_type: str,
        error_message: str,
        recoverable: bool = True,
    ) -> RuntimeNotification:
        return event_bus.error(
            chat_id=chat_id,
            error_type=error_type,
            error_message=error_message,
            recoverable=recoverable,
        )

    def emit(self, event: Any) -> None:
        """向后兼容：接受旧 NotificationEvent 并转发到 event_bus。"""
        event_type = getattr(event, 'type', None)
        if event_type:
            notification = RuntimeNotification(
                type=NotificationType(event_type.value) if hasattr(event_type, 'value') else NotificationType(event_type),
                chat_id=getattr(event, 'chat_id', None),
                data=getattr(event, 'data', {}),
            )
            event_bus.publish(notification)


notification_manager = NotificationManager()