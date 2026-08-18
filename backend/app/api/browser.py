"""可交互浏览器 API —— 前端"浏览器"标签页（Phase UI-Browser）。

为前端右侧面板的"浏览器"标签提供后端能力：
  - 常驻 Playwright 会话（按 chat_id 维护独立 page）
  - 导航：navigate / back / forward / reload
  - 画面：screenshot（JPEG base64，前端轮询）
  - 状态：state（当前 url / title / hasPage）

安全：仅允许访问本机前端地址（防 SSRF），与 ui_probe_tools 一致。
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.browser_session import browser_manager, validate_local_url

logger = logging.getLogger(__name__)

router = APIRouter()


class NavigateRequest(BaseModel):
    chat_id: int
    url: str
    wait_for: str = ""


class ChatIdRequest(BaseModel):
    chat_id: int


class ScreenshotQuery(BaseModel):
    chat_id: int
    max_width: int = 1280


@router.get("/browser/health")
async def browser_health():
    """浏览器服务可用性（playwright 是否就绪）。"""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return {"ok": True}
    except ImportError:
        return {"ok": False, "error": "playwright 未安装"}


@router.post("/browser/navigate")
async def browser_navigate(req: NavigateRequest):
    """导航到本机前端 URL，返回页面状态。"""
    err = validate_local_url(req.url)
    if err:
        return {"ok": False, "error": err}
    return await browser_manager.run("navigate", req.chat_id, url=req.url, wait_for=req.wait_for)


@router.post("/browser/back")
async def browser_back(req: ChatIdRequest):
    return await browser_manager.run("back", req.chat_id)


@router.post("/browser/forward")
async def browser_forward(req: ChatIdRequest):
    return await browser_manager.run("forward", req.chat_id)


@router.post("/browser/reload")
async def browser_reload(req: ChatIdRequest):
    return await browser_manager.run("reload", req.chat_id)


@router.get("/browser/state")
async def browser_state(chat_id: int):
    return await browser_manager.run("state", chat_id)


@router.get("/browser/screenshot")
async def browser_screenshot(chat_id: int, max_width: int = 1280):
    """返回当前页面 JPEG 截图（base64 data URI 直接可 <img> 展示）。"""
    return await browser_manager.run("screenshot", chat_id, max_width=max_width)


@router.post("/browser/close")
async def browser_close(req: ChatIdRequest):
    """关闭该 chat 的浏览器页面（释放资源）。"""
    return await browser_manager.run("close", req.chat_id)
