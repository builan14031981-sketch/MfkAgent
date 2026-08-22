"""飞书反向通道：WebSocket 长连接事件订阅。

用户在飞书群里 @ 机器人，MfkAgent 收到 im.message.receive_v1 事件，
解析消息文本并回发到群（当前为通道验证的 echo 回复，后续可替换为 Agent 生成）。

长连接模式依据：飞书开放平台「长连接接收事件」仅支持企业自建应用，
无需公网地址；事件需在 3 秒内确认，超时平台会重推（本实现确认即返回，处理放后台）。

注意：lark_oapi.ws.client 在模块导入时用 asyncio.get_event_loop() 绑定全局 loop，
因此全部 lark_oapi 导入必须放在设置了专用 loop 的线程内完成，否则会绑定到
uvicorn 主事件循环导致 run_until_complete 报 "This event loop is already running"。
"""
import asyncio
import json
import logging
import re
import threading
from typing import Any, Dict, Optional

from app.core.config import settings
from app.services.feishu import get_feishu_service

logger = logging.getLogger("feishu_ws")

_client: Optional[Any] = None
_loop: Optional[asyncio.AbstractEventLoop] = None
_queue: Optional[asyncio.Queue] = None


def _strip_mention_keys(text: str) -> str:
    return re.sub(r"@_user_\d+", "", text).strip()


def _parse_receive(payload: Dict[str, Any]) -> Optional[Dict[str, str]]:
    event = payload.get("event") or {}
    message = event.get("message") or {}
    chat_id = message.get("chat_id") or ""
    chat_type = message.get("chat_type") or ""
    message_type = message.get("message_type") or ""
    if not chat_id or message_type != "text":
        return None
    if chat_type == "group" and not message.get("mention"):
        return None
    try:
        content = json.loads(message.get("content") or "{}")
    except (json.JSONDecodeError, TypeError):
        return None
    text = _strip_mention_keys(content.get("text") or "")
    if not text:
        return None
    sender = event.get("sender") or {}
    return {
        "chat_id": chat_id,
        "chat_type": chat_type,
        "message_id": message.get("message_id") or "",
        "text": text,
        "open_id": (sender.get("sender_id") or {}).get("open_id") or "",
        "sender_type": sender.get("sender_type") or "",
    }


async def _reply(info: Dict[str, str]) -> None:
    svc = get_feishu_service()
    reply = f"[回声] {info['text']}"
    await svc.send_text(info["chat_id"], reply)
    logger.info("feishu echo replied chat_id=%s text=%r", info["chat_id"], reply)


async def _consume() -> None:
    while True:
        info = await _queue.get()
        try:
            await _reply(info)
        except Exception:
            logger.exception("feishu reply failed info=%s", info)


def _on_message(data: Any) -> None:
    try:
        from lark_oapi.core.json import JSON

        payload = JSON.marshal(data)
    except Exception:
        logger.exception("feishu ws marshal event failed")
        return
    info = _parse_receive(payload)
    if not info:
        return
    logger.info("feishu ws received chat_type=%s chat_id=%s open_id=%s text=%r",
                info["chat_type"], info["chat_id"], info["open_id"], info["text"])
    if _loop is not None and _queue is not None and not _loop.is_closed():
        _loop.call_soon_threadsafe(_queue.put_nowait, info)


def _ws_worker() -> None:
    global _client
    ws_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(ws_loop)
    import lark_oapi as lark
    from lark_oapi.core.enum import LogLevel

    handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(_on_message)
        .build()
    )
    _client = lark.ws.Client(
        settings.FEISHU_APP_ID,
        settings.FEISHU_APP_SECRET,
        event_handler=handler,
        log_level=LogLevel.INFO,
    )
    try:
        _client.start()
    except Exception:
        logger.exception("feishu ws client exited")


def _loop_worker() -> None:
    global _loop, _queue
    asyncio.set_event_loop(_loop)
    _queue = asyncio.Queue()
    _loop.create_task(_consume())
    _loop.run_forever()


def start() -> None:
    global _loop
    if _client is not None:
        return
    if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
        logger.warning("feishu ws skipped: missing FEISHU_APP_ID/FEISHU_APP_SECRET")
        return
    _loop = asyncio.new_event_loop()
    threading.Thread(target=_loop_worker, daemon=True, name="feishu-ws-loop").start()
    threading.Thread(target=_ws_worker, daemon=True, name="feishu-ws").start()
    logger.info("feishu ws long-connection started app_id=%s", settings.FEISHU_APP_ID)