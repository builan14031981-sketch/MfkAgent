"""常驻 Playwright 浏览器会话管理器 —— 供前端"浏览器"标签页使用。

与 ui_probe_tools（每次调用即开即关的一次性自检）不同，这里维护一个
常驻的 headless Chromium 实例，按 chat_id 缓存独立页面（page），
支持 navigate / back / forward / reload / screenshot / state / close。

线程模型：
- Playwright sync API 是阻塞式且要求对象在其所属线程内使用，
  因此用一个专用 worker 线程持有 browser + pages，外部通过命令队列
  （submit）派发操作并等待结果。FastAPI 侧用 asyncio.to_thread 调用 submit。

安全：与 ui_probe_tools 一致，仅允许访问本机前端地址（防 SSRF）。
"""
import asyncio
import base64
import logging
import os
import queue
import re
import sys
import threading
from concurrent.futures import Future
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# playwright 可能被安装到项目本地依赖目录（backend/.py_deps），探测并加入 sys.path
_DEPS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".py_deps"
)
if os.path.isdir(_DEPS_DIR) and _DEPS_DIR not in sys.path:
    sys.path.insert(0, _DEPS_DIR)

# 浏览器缓存路径（项目内，绕开用户目录权限限制）
_MS_PLAYWRIGHT_DIR = os.path.join(_DEPS_DIR, "ms-playwright")

# 仅允许本机前端（dev server 端口），拒绝任意外网 URL（SSRF 防护）
_LOCALHOST_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(/.*)?$", re.IGNORECASE)

# 页面导航等待 / 单次操作超时（秒）
_NAV_TIMEOUT_MS = 15000
_OP_TIMEOUT = 30.0


class BrowserStartupError(RuntimeError):
    """浏览器启动失败（未安装 playwright / chromium / 沙箱缺依赖）。"""


def _prepare_playwright_env() -> None:
    """确保 worker 线程能找到项目内浏览器缓存目录。"""
    if os.path.isdir(_MS_PLAYWRIGHT_DIR):
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", _MS_PLAYWRIGHT_DIR)


class BrowserSessionManager:
    """单例：一个常驻 Chromium + 每 chat 一个 page。

    用法：
        from app.core.browser_session import browser_manager
        result = await browser_manager.run("navigate", chat_id=1, url="...")
    """

    def __init__(self) -> None:
        self._queue: "queue.Queue[Optional[tuple]]" = queue.Queue()
        self._ready = threading.Event()
        self._error: Optional[Exception] = None
        self._browser = None  # type: ignore
        self._pages: Dict[int, Any] = {}
        self._thread: Optional[threading.Thread] = None

    # ── 启动 worker ──
    def _ensure_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._worker, name="browser-session", daemon=True)
        self._thread.start()

    def _worker(self) -> None:
        _prepare_playwright_env()
        try:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True, args=["--no-sandbox"])
        except Exception as e:  # noqa: BLE001
            self._error = BrowserStartupError(f"浏览器启动失败: {type(e).__name__}: {e}")
            self._ready.set()
            return
        self._ready.set()
        while True:
            item = self._queue.get()
            if item is None:
                break
            fn, future = item
            try:
                future.set_result(fn(self))
            except Exception as e:  # noqa: BLE001
                future.set_exception(e)

    def submit(self, fn: Callable[["BrowserSessionManager"], Any], timeout: float = _OP_TIMEOUT) -> Any:
        """向 worker 派发一个操作并同步等待结果（FastAPI 侧用 to_thread 调用）。"""
        self._ensure_thread()
        if not self._ready.wait(10):
            raise BrowserStartupError("浏览器 worker 未在 10s 内就绪")
        if self._error is not None:
            raise self._error
        future: "Future[Any]" = Future()
        self._queue.put((fn, future))
        return future.result(timeout)

    # ── 供 worker 线程内部使用的操作 ──
    def _get_page(self, chat_id: int) -> Any:
        page = self._pages.get(chat_id)
        if page is None:
            page = self._browser.new_page(viewport={"width": 1440, "height": 900})
            self._pages[chat_id] = page
        return page

    def _navigate(self, chat_id: int, url: str, wait_for: str = "") -> Dict[str, Any]:
        page = self._get_page(chat_id)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        except Exception as e:  # noqa: BLE001
            logger.warning("browser navigate %s -> %s 异常: %s", chat_id, url, e)
        if wait_for:
            try:
                page.wait_for_selector(wait_for, timeout=8000)
            except Exception as e:  # noqa: BLE001
                logger.warning("browser wait_for %s 超时: %s", wait_for, e)
        return self._state(chat_id)

    def _back(self, chat_id: int) -> Dict[str, Any]:
        page = self._pages.get(chat_id)
        if page is None:
            return {"ok": False, "error": "尚未打开任何页面"}
        try:
            page.go_back(wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        except Exception as e:  # noqa: BLE001
            logger.warning("browser go_back 异常: %s", e)
        return self._state(chat_id)

    def _forward(self, chat_id: int) -> Dict[str, Any]:
        page = self._pages.get(chat_id)
        if page is None:
            return {"ok": False, "error": "尚未打开任何页面"}
        try:
            page.go_forward(wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        except Exception as e:  # noqa: BLE001
            logger.warning("browser go_forward 异常: %s", e)
        return self._state(chat_id)

    def _reload(self, chat_id: int) -> Dict[str, Any]:
        page = self._pages.get(chat_id)
        if page is None:
            return {"ok": False, "error": "尚未打开任何页面"}
        try:
            page.reload(wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        except Exception as e:  # noqa: BLE001
            logger.warning("browser reload 异常: %s", e)
        return self._state(chat_id)

    def _state(self, chat_id: int) -> Dict[str, Any]:
        page = self._pages.get(chat_id)
        if page is None:
            return {"ok": True, "url": "", "title": "", "hasPage": False}
        try:
            url = page.url
            title = page.title()
        except Exception:  # noqa: BLE001
            url, title = "", ""
        return {"ok": True, "url": url, "title": title, "hasPage": True}

    def _screenshot(self, chat_id: int, max_width: int = 1280, full_page: bool = False, timeout: int = 15000) -> Dict[str, Any]:
        page = self._pages.get(chat_id)
        if page is None:
            return {"ok": False, "error": "尚未打开任何页面"}
        try:
            data = page.screenshot(
                type="jpeg", quality=70,
                full_page=full_page,
                timeout=timeout,
            )
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"截图失败: {type(e).__name__}: {e}"}
        b64 = base64.b64encode(data).decode("ascii")
        return {
            "ok": True,
            "mime": "image/jpeg",
            "image_base64": b64,
            "size_bytes": len(data),
            **self._state(chat_id),
        }

    def _close(self, chat_id: int) -> Dict[str, Any]:
        page = self._pages.pop(chat_id, None)
        if page is not None:
            try:
                page.close()
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True}

    # ── 对外异步入口（FastAPI async 端点直接 await）──
    async def run(self, op: str, chat_id: int, **kwargs) -> Any:
        """在 worker 线程执行操作，返回结果（不抛异常，错误以 dict 返回）。"""
        fn_map: Dict[str, Callable[[Any], Any]] = {
            "navigate": lambda m: self._navigate(chat_id, kwargs["url"], kwargs.get("wait_for", "")),
            "back": lambda m: self._back(chat_id),
            "forward": lambda m: self._forward(chat_id),
            "reload": lambda m: self._reload(chat_id),
            "state": lambda m: self._state(chat_id),
            "screenshot": lambda m: self._screenshot(
                chat_id,
                max_width=int(kwargs.get("max_width", 1280)),
                full_page=bool(kwargs.get("full_page", False)),
                timeout=int(kwargs.get("timeout", 15000)),
            ),
            "close": lambda m: self._close(chat_id),
        }
        fn = fn_map.get(op)
        if fn is None:
            return {"ok": False, "error": f"未知浏览器操作: {op}"}
        try:
            return await asyncio.to_thread(self.submit, fn)
        except BrowserStartupError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:  # noqa: BLE001
            logger.exception("browser op %s failed", op)
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def shutdown(self) -> None:
        """关闭浏览器并结束 worker（应用退出时调用）。"""
        try:
            if self._thread is not None and self._thread.is_alive():
                self._queue.put(None)
                self._thread.join(timeout=5)
        except Exception:  # noqa: BLE001
            pass


def validate_local_url(url: str) -> Optional[str]:
    """校验 URL 必须为本机前端地址；不合法返回错误文案，合法返回 None。"""
    url = (url or "").strip()
    if not _LOCALHOST_RE.match(url):
        return f"仅允许访问本机前端地址（http://localhost:端口），拒绝: {url}"
    return None


browser_manager = BrowserSessionManager()
