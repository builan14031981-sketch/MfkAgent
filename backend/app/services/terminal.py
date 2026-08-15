"""内置终端会话服务（2026-08-14）。

架构：FastAPI WebSocket + 真实 PTY（pywinpty/winpty 即 Windows ConPTY）驱动。

安全模型（与 Agent 命令风险引擎解耦，专为人类交互终端设计）：
  - 人类终端不做逐条命令分级（risk_engine._FORBIDDEN_RE 会封死 | > $ 等 shell 必需符）。
  - 仅拦截破坏性命令（复用 risk_engine._DESTRUCTIVE_PATTERNS，单一事实来源）：
      输入逐字符转发（shell 自然回显），在回车换行处 hold；命中破坏性模式 → 挂起该换行，
      向前端发 approval 事件；批准后补发换行让命令执行，拒绝后发 Ctrl-C 取消当前行。
  - 尽力而为：一旦输入中出现 ESC/控制字符（方向键/历史回显等），本行置为不可追踪，
    回车直接放行（fail-open），不影响交互式程序（vim/top）。
  - cwd 创建时锚定（禁执行目录黑名单校验），之后允许自由 cd。

线程模型：
  - pywinpty read() 为阻塞读 → 后台读线程循环 read()，经 loop.call_soon_threadsafe
    推入 asyncio.Queue，WS 发送任务消费；会话进程退出后线程结束并投递 exit 事件。
  - 输入处理在 WS 接收循环（async 上下文）内同步执行，写入 PTY 为快速非阻塞操作。
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
import time
import uuid
from typing import Dict, Optional

from app.core.sandbox import is_forbidden_cwd

# 破坏性命令模式：复用风险引擎的单一事实来源（避免两处漂移）
from app.core.tool_runtime.risk_engine import _DESTRUCTIVE_PATTERNS

logger = logging.getLogger(__name__)

DEFAULT_SHELL = "powershell.exe"

# 终端专用补充破坏性模式（rd /s 递归删除目录树等）
_TERMINAL_DESTRUCTIVE_EXTRA = [
    re.compile(r"(^|\s)(rd|rmdir)\s+/s(\s|$)", re.I),
    re.compile(r"(^|\s)del\s+/[fqs]([^a-z]|$)", re.I),
]


class TerminalSession:
    """单个 PTY 终端会话。线程安全：读线程产出，WS 任务消费。"""

    def __init__(self, session_id: str, shell: str, cwd: str, cols: int, rows: int) -> None:
        self.session_id = session_id
        self.shell = shell
        self.cwd = cwd
        self.cols = cols
        self.rows = rows
        import winpty  # 延迟导入：仅在真正需要时加载

        self._factory = winpty.PtyProcess.spawn
        self.pty = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.out_q: Optional[asyncio.Queue] = None
        self._lock = threading.Lock()
        self._reader_thread: Optional[threading.Thread] = None
        self._terminated = False
        self.connected = False  # 当前是否有 WS 占用
        self.last_connected_at = time.time()
        # 行级拦截状态
        self.line_buf = ""
        self.line_trackable = True
        self.pending_approval: Optional[dict] = None  # {id, command}

    # ── 生命周期 ──

    def spawn(self) -> None:
        if self.pty is not None:
            return
        kwargs = {}
        if self.cwd and os.path.isdir(self.cwd):
            kwargs["cwd"] = self.cwd
        kwargs["dimensions"] = (max(self.rows, 2), max(self.cols, 2))
        self.pty = self._factory(self.shell, **kwargs)

    def start_reader(self, loop: asyncio.AbstractEventLoop, q: asyncio.Queue) -> None:
        """在 WS/会话创建时绑定事件循环与输出队列，并启动阻塞读线程。"""
        self._loop = loop
        self.out_q = q
        if self._reader_thread is None and self.pty is not None:
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()

    def _read_loop(self) -> None:
        try:
            while not self._terminated:
                try:
                    chunk = self.pty.read()
                except Exception as exc:  # noqa: BLE001 - EOF/终止均属正常退出
                    self._emit("exit", {"code": self._exit_status()})
                    return
                if chunk is None:
                    # pywinpty 在无数据时返回 None（非阻塞）
                    time.sleep(0.02)
                    continue
                if chunk == "":
                    if not self.pty.isalive():
                        self._emit("exit", {"code": self._exit_status()})
                        return
                    time.sleep(0.02)
                    continue
                self._emit("output", {"data": chunk})
        except Exception:  # noqa: BLE001
            logger.exception("terminal reader ended with error")

    def _exit_status(self) -> Optional[int]:
        try:
            return int(self.pty.exitstatus)
        except Exception:  # noqa: BLE001
            return None

    def _emit(self, kind: str, payload: dict) -> None:
        if self._loop is None or self.out_q is None:
            return
        self._loop.call_soon_threadsafe(self.out_q.put_nowait, {"type": kind, **payload})

    def kill(self) -> None:
        with self._lock:
            self._terminated = True
            if self.pty is not None:
                try:
                    self.pty.terminate(force=True)
                except Exception:  # noqa: BLE001
                    pass
            self.connected = False

    # ── 输入处理（WS 接收循环内同步调用）──

    def on_input(self, data: str) -> list:
        """处理客户端输入。返回需要额外投递的事件（审批请求）。"""
        events: list = []
        if not data:
            return events
        buf = []
        for ch in data:
            if self.pending_approval is not None:
                # 已有审批挂起：忽略后续输入，避免污染当前行
                continue
            if ch in ("\r", "\n"):
                if self.line_trackable and self._is_destructive(self.line_buf):
                    pid = uuid.uuid4().hex[:8]
                    cmd = self.line_buf.strip()
                    self.pending_approval = {"id": pid, "command": cmd}
                    events.append({"type": "approval", "id": pid, "command": cmd})
                    # hold 该换行：不写入 PTY
                    self.line_buf = ""
                    self.line_trackable = True
                    continue
                buf.append(ch)
                self.line_buf = ""
                self.line_trackable = True
            elif ch in ("\x08", "\x7f"):
                # 退格：更正行缓冲
                if self.line_trackable and self.line_buf:
                    self.line_buf = self.line_buf[:-1]
                buf.append(ch)
            elif ch == "\x1b":
                # ESC 序列（方向键等）：行内容不可追踪 → fail-open
                self.line_trackable = False
                buf.append(ch)
            elif ord(ch) < 0x20:
                # 其他控制字符（Ctrl-C 等）：不可追踪，放行
                self.line_trackable = False
                buf.append(ch)
            else:
                if self.line_trackable and len(self.line_buf) < 4096:
                    self.line_buf += ch
                buf.append(ch)
        if buf:
            self._write("".join(buf))
        return events

    def on_approve(self) -> None:
        if self.pending_approval is None:
            return
        self.pending_approval = None
        self._write("\r")

    def on_reject(self) -> None:
        if self.pending_approval is None:
            return
        self.pending_approval = None
        # Ctrl-C 取消当前行（cmd 与 PowerShell 均清除输入行）
        self._write("\x03")

    def on_resize(self, cols: int, rows: int) -> None:
        self.cols, self.rows = max(cols, 1), max(rows, 1)
        if self.pty is not None:
            try:
                self.pty.setwinsize(self.rows, self.cols)
            except Exception:  # noqa: BLE001
                pass

    def _write(self, data: str) -> None:
        if self.pty is not None:
            try:
                self.pty.write(data)
            except Exception:  # noqa: BLE001
                logger.exception("terminal write failed")

    # ── 破坏性判定 ──

    def _is_destructive(self, line: str) -> bool:
        line = line.strip()
        if not line:
            return False
        for pat in _DESTRUCTIVE_PATTERNS:
            if pat.search(line):
                return True
        for pat in _TERMINAL_DESTRUCTIVE_EXTRA:
            if pat.search(line):
                return True
        return False


class TerminalManager:
    """终端会话注册表：创建 / 取回 / 回收，附带闲置 TTL 清理。"""

    def __init__(self) -> None:
        self._sessions: Dict[str, TerminalSession] = {}
        self._ttl_seconds = 30 * 60
        self._janitor_task: Optional[asyncio.Task] = None

    def create(self, shell: str, cwd: str, cols: int, rows: int) -> TerminalSession:
        sid = uuid.uuid4().hex[:16]
        session = TerminalSession(sid, shell, cwd, cols, rows)
        self._sessions[sid] = session
        self._ensure_janitor()
        return session

    def get(self, session_id: str) -> Optional[TerminalSession]:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            session.kill()

    def _ensure_janitor(self) -> None:
        if self._janitor_task is not None and not self._janitor_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._janitor_task = loop.create_task(self._janitor())

    async def _janitor(self) -> None:
        while True:
            await asyncio.sleep(60)
            now = time.time()
            expired = [
                sid
                for sid, s in self._sessions.items()
                if not s.connected and (now - s.last_connected_at) > self._ttl_seconds
            ]
            for sid in expired:
                logger.info("terminal janitor: remove idle session %s", sid)
                self.remove(sid)

    def shutdown_all(self) -> None:
        for sid in list(self._sessions.keys()):
            self.remove(sid)
        self._sessions.clear()


_terminal_manager = TerminalManager()


def get_terminal_manager() -> TerminalManager:
    return _terminal_manager