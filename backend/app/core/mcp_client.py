"""外部 MCP server stdio 客户端（T6 MVP）— 通过 JSON-RPC 2.0 接入真实 MCP server。

架构：
  StdioMCPConnection   单个 server 的子进程连接：spawn → initialize 握手 → tools/list
                       枚举 → tools/call 调用。每请求带超时；进程崩溃自动重启（指数退避）。
  ExternalMCPManager   多 server 管理器：从 plugins 表（source="external_mcp"）读配置，
                       维护连接、枚举工具、注册进 tool_registry / risk_engine / permission，
                       并提供「会话冻结清单」。

会话冻结（配合 prompt 缓存前缀稳定性）：
  - 每个会话（chat_id）首次解析工具目录时对当时的外部工具集做快照，会话期内冻结；
  - MCP server 启停 / 工具变更不影响已冻结会话，下个会话生效；
  - 检测到漂移时打 warning 日志（提示用户新开会话），并暴露 get_session_drift() 供 UI 使用。

风险判定（fail-closed，不得绕过 L0/L1/L2）：
  - 枚举到外部工具后按 annotations.readOnlyHint 分级（缺省 = 写入类，保守处理）：
      只读类 → 并入 risk_engine.READ_ONLY_TOOLS（build/plan 均自动放行）
      写入类 → 注入 risk_engine.TOOL_RISK_POLICY = HIGH_RISK/WRITE
               （任何权限模式都强制人工审批；plan 一律 deny，与沙箱外命令同哲学）
  - 全部外部调用走 executor 统一执行闸（evaluate_tool → ApprovalPolicy → 审批链），
    并写入 SandboxAuditLog 审计。

配置（复用 plugins 表，复用现有插件启停）：
    PluginItem(
        plugin_id="filesystem",            # server 名（工具命名 mcp__<server>__<tool>）
        name="Filesystem MCP", source="external_mcp", status="active",
        config={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/path"],
            "env": {...},                   # 可选，合并进子进程环境
            "cwd": "...",                   # 可选，子进程工作目录
        },
    )

本期不做：SSE/HTTP transport、OAuth、resources 订阅、sampling。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ──── 协议与超时常量 ────
MCP_PROTOCOL_VERSION = "2024-11-05"
INIT_TIMEOUT_S = 90.0        # initialize 握手总超时（npx 冷启动含包下载）
LIST_TIMEOUT_S = 30.0        # tools/list 超时
CALL_TIMEOUT_S = 120.0       # tools/call 默认超时
RESTART_BACKOFF_BASE_S = 1.0
RESTART_BACKOFF_MAX_S = 60.0

# 审计文本截断（与 command_tools._truncate_audit_text 同规格）
_AUDIT_TRUNCATE = 8 * 1024


def _truncate_audit_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    text = str(text)
    return text[:_AUDIT_TRUNCATE] if len(text) > _AUDIT_TRUNCATE else text


def external_tool_name(server_id: str, tool_name: str) -> str:
    """外部工具统一命名 mcp__<server>__<tool>（防与内置/其他 server 撞名）。"""
    return f"mcp__{server_id}__{tool_name}"


def merge_external_definitions(def_map: Dict[str, Dict], tool_names: List[str]) -> None:
    """把外部 MCP 工具定义合并进 ToolSelector._def_map（幂等；selector.select 每次调用）。

    定义来源 = tool_registry 中已注册的 MCPExternalTool（get_definition() 输出
    OpenAI Function Calling 格式）。仅处理 mcp__ 前缀且 def_map 尚无定义的名称。
    """
    try:
        from app.services.tools import tool_registry
        for name in tool_names:
            if name in def_map or not str(name).startswith("mcp__"):
                continue
            tool = tool_registry.get(name)
            if tool is not None:
                def_map[name] = tool.get_definition()
    except Exception as e:  # noqa: BLE001
        logger.debug("[mcp_client] 外部工具定义合并失败（忽略）: %s", e)


class StdioMCPConnection:
    """单个外部 MCP server 的 stdio JSON-RPC 2.0 连接。

    生命周期：start() spawn 子进程 → ensure_ready() 握手+枚举 → call_tool() 调用。
    子进程异常退出时自动重启（指数退避，成功后计数归零）；stop() 显式停用不再重启。
    """

    def __init__(
        self,
        server_id: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        call_timeout_s: float = CALL_TIMEOUT_S,
    ):
        self.server_id = server_id
        self.command = command
        self.args = list(args)
        self.env = env or {}
        self.cwd = cwd
        self.call_timeout_s = call_timeout_s

        self._proc: Optional[asyncio.subprocess.Process] = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._next_id = 1
        self._reader_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._restart_task: Optional[asyncio.Task] = None
        self._restart_attempts = 0
        self._init_lock = asyncio.Lock()
        self._initialized = asyncio.Event()
        self._stopping = False
        # EOF 驱动的退出标志：Windows 上 returncode 回收有延迟，不能只看 returncode
        self._exited = False
        self.tools: List[Dict[str, Any]] = []  # 最近一次 tools/list 原始结果

    # ──── 状态 ────

    @property
    def is_running(self) -> bool:
        return (
            self._proc is not None
            and self._proc.returncode is None
            and not self._exited
        )

    @property
    def is_ready(self) -> bool:
        return self._initialized.is_set()

    # ──── 启动 / 握手 ────

    async def start(self) -> None:
        """spawn 子进程并启动读循环（幂等；不阻塞：握手交给 ensure_ready）。"""
        self._stopping = False
        if self.is_running:
            return
        await self._spawn()

    async def _spawn(self) -> None:
        # Windows 下 npx/npm 是 .cmd shim，create_subprocess_exec 不走 shell 解析，
        # 必须 shutil.which 解析出完整可执行路径。
        resolved = shutil.which(self.command) or self.command
        env = dict(os.environ)
        env.update(self.env)
        self._proc = await asyncio.create_subprocess_exec(
            resolved, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=self.cwd,
        )
        self._reader_task = asyncio.create_task(self._read_loop(), name=f"mcp-{self.server_id}-reader")
        self._stderr_task = asyncio.create_task(self._stderr_loop(), name=f"mcp-{self.server_id}-stderr")
        self._exited = False
        logger.info("[mcp_client] 已启动 server=%s pid=%s cmd=%s %s",
                    self.server_id, self._proc.pid, self.command, " ".join(self.args))

    async def ensure_ready(self, timeout: float = INIT_TIMEOUT_S) -> None:
        """initialize 握手 + tools/list 枚举（幂等；并发调用共享一次握手）。"""
        if self._initialized.is_set():
            return
        async with self._init_lock:
            if self._initialized.is_set():
                return
            try:
                await self._handshake()
                await self._enumerate_tools()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # 握手失败：清空半成品 pending，交由上层决定重试/重启
                self._fail_pending(ConnectionError(f"initialize 失败: {e}"))
                raise
            self._initialized.set()
            self._restart_attempts = 0
            logger.info("[mcp_client] server=%s 握手完成，枚举到 %d 个工具",
                        self.server_id, len(self.tools))

    async def _handshake(self) -> None:
        await self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mfkagent", "version": "1.0.0"},
            },
            timeout=INIT_TIMEOUT_S,
        )
        # initialized 通知（无 id，无响应）
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    async def _enumerate_tools(self) -> None:
        tools: List[Dict[str, Any]] = []
        cursor = None
        while True:
            params: Dict[str, Any] = {"cursor": cursor} if cursor else {}
            result = await self._request("tools/list", params, timeout=LIST_TIMEOUT_S)
            tools.extend(result.get("tools") or [])
            cursor = result.get("nextCursor")
            if not cursor:
                break
        self.tools = tools

    # ──── 调用 ────

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any],
                        timeout: Optional[float] = None) -> Dict[str, Any]:
        """tools/call；超时/未连接抛异常。可取消（wait_for 级联取消 future）。"""
        if not self.is_running:
            raise ConnectionError(f"MCP server {self.server_id} 未运行")
        return await self._request(
            "tools/call",
            {"name": tool_name, "arguments": arguments or {}},
            timeout=timeout or self.call_timeout_s,
        )

    async def _request(self, method: str, params: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        if not self.is_running:
            raise ConnectionError(f"MCP server {self.server_id} 未运行")
        loop = asyncio.get_running_loop()
        req_id = self._next_id
        self._next_id += 1
        fut: asyncio.Future = loop.create_future()
        self._pending[req_id] = fut
        if not self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}):
            self._pending.pop(req_id, None)
            raise ConnectionError(f"MCP server {self.server_id} stdin 已关闭")
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)  # 迟到响应由 reader 丢弃
            raise
        except asyncio.CancelledError:
            self._pending.pop(req_id, None)
            raise

    def _send(self, payload: Dict[str, Any]) -> bool:
        """写入一行 JSON-RPC；进程已死/stdin 关闭返回 False。"""
        if self._exited or self._proc is None or self._proc.stdin is None or self._proc.returncode is not None:
            return False
        try:
            data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
            self._proc.stdin.write(data)
        except (ConnectionResetError, BrokenPipeError, RuntimeError, OSError):
            return False
        return True

    # ──── 读循环 / 崩溃重启 ────

    async def _read_loop(self) -> None:
        proc = self._proc
        assert proc and proc.stdout
        while True:
            line = await proc.stdout.readline()
            if not line:
                break  # EOF → _on_exit
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                # MCP stdio 契约 stdout 仅 JSON-RPC；容忍个别 server 违规打印
                logger.debug("[mcp_client] server=%s stdout 非 JSON 行: %.200s", self.server_id, text)
                continue
            self._dispatch_message(msg)
        await self._on_exit()

    def _dispatch_message(self, msg: Dict[str, Any]) -> None:
        req_id = msg.get("id")
        if req_id is None:
            return  # server 主动通知（本期不处理 resources/sampling）
        fut = self._pending.pop(req_id, None)
        if fut is None or fut.done():
            return  # 超时/取消后的迟到响应
        if "error" in msg and msg["error"] is not None:
            err = msg["error"]
            fut.set_exception(RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}"))
        else:
            fut.set_result(msg.get("result") or {})

    async def _stderr_loop(self) -> None:
        proc = self._proc
        assert proc and proc.stderr
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                logger.debug("[mcp_client] server=%s stderr: %s", self.server_id, text)

    async def _on_exit(self) -> None:
        """子进程退出：清 pending → 自动重启（指数退避）或停用。"""
        self._exited = True
        self._fail_pending(ConnectionError(f"MCP server {self.server_id} 子进程已退出"))
        self._initialized.clear()
        if self._stopping:
            return
        code = self._proc.returncode if self._proc else None
        logger.warning("[mcp_client] server=%s 子进程退出（code=%s），%.1fs 后自动重启",
                       self.server_id, code, self._current_backoff())
        self._restart_task = asyncio.create_task(self._restart_loop(), name=f"mcp-{self.server_id}-restart")

    def _current_backoff(self) -> float:
        return min(RESTART_BACKOFF_BASE_S * (2 ** self._restart_attempts), RESTART_BACKOFF_MAX_S)

    async def _restart_loop(self) -> None:
        while not self._stopping:
            await asyncio.sleep(self._current_backoff())
            if self._stopping:
                return
            try:
                self._fail_pending(ConnectionError(f"MCP server {self.server_id} 正在重启"))
                await self._spawn()
                await self.ensure_ready(timeout=INIT_TIMEOUT_S)
                logger.info("[mcp_client] server=%s 重启成功（第 %d 次尝试），工具数 %d",
                            self.server_id, self._restart_attempts + 1, len(self.tools))
                external_mcp_manager.on_connection_ready(self)
                return
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._restart_attempts += 1
                logger.warning("[mcp_client] server=%s 重启失败（第 %d 次）: %s，下轮退避 %.1fs",
                               self.server_id, self._restart_attempts, e, self._current_backoff())

    def _fail_pending(self, exc: Exception) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()

    # ──── 停止 ────

    async def stop(self) -> None:
        """显式停用：不再自动重启，杀进程树，清 pending。"""
        self._stopping = True
        if self._restart_task and not self._restart_task.done():
            self._restart_task.cancel()
        self._fail_pending(ConnectionError(f"MCP server {self.server_id} 已停用"))
        if self.is_running:
            self._kill_tree()
        # 读/stderr 循环会随进程 EOF 自然退出；短暂等待收尾，避免任务悬挂
        for task in (self._reader_task, self._stderr_task):
            if task and not task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=3)
                except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                    pass
        self._proc = None

    def _kill_tree(self) -> None:
        proc = self._proc
        if proc is None or proc.returncode is not None:
            return
        try:
            if sys.platform == "win32":
                # npx → cmd shim → node 子进程；逐进程 kill 会留孤儿，整树强杀
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True, timeout=5,
                )
            else:
                proc.kill()
        except Exception as e:  # noqa: BLE001
            logger.warning("[mcp_client] server=%s 杀进程树失败: %s", self.server_id, e)


class MCPExternalTool:
    """外部 MCP 工具的 tool_registry 适配器（鸭子类型兼容 services.tools.Tool）。

    executor._run_tool 对未知工具兜底走 tool_registry.execute(name, **kwargs)，
    注册本类即获得分发能力；定义由 get_definition() 输出 OpenAI Function Calling 格式。
    """

    def __init__(self, name: str, description: str, parameters: Dict[str, Any],
                 server_id: str, tool_name: str):
        self.name = name
        self.description = description
        self.parameters = parameters
        self._server_id = server_id
        self._tool_name = tool_name

    def get_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, **kwargs) -> Any:
        from app.services.tools import ToolResult

        # executor 以 {**ctx, **func_args, "_emit": emit} 合并传参；
        # 剥离运行时上下文键，剩余即 MCP 工具实参。
        chat_id = kwargs.pop("chat_id", None)
        kwargs.pop("agent_run_id", None)
        kwargs.pop("agent_id", None)
        kwargs.pop("project_id", None)
        kwargs.pop("_emit", None)

        t0 = time.monotonic()
        manager = external_mcp_manager
        text, ok, err = await manager.call_external(self._server_id, self._tool_name, kwargs)
        duration_ms = round((time.monotonic() - t0) * 1000)
        manager.write_audit(
            server_id=self._server_id, tool_name=self._tool_name,
            arguments=kwargs, duration_ms=duration_ms,
            success=ok, error_message=err, chat_id=chat_id,
        )
        if ok:
            return ToolResult(success=True, output=text)
        return ToolResult(success=False, output="", error=text)


class ExternalMCPManager:
    """外部 MCP server 管理器（模块级单例 external_mcp_manager）。

    所有公开方法均不阻塞事件循环：DB 读取为同步快查（与现有 permission/plugin_tools
    同模式），子进程 IO 全异步且带超时。
    """

    def __init__(self):
        self._conns: Dict[str, StdioMCPConnection] = {}
        self._server_tools: Dict[str, List[Dict[str, Any]]] = {}
        self._ready = asyncio.Event()
        self._started = False
        self._initial_task: Optional[asyncio.Task] = None
        # 会话冻结清单：session_key → {"servers": [...], "tools": {tool_name: meta}}
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._drift_warned: Dict[str, float] = {}

    # ──── 启动 ────

    def startup(self) -> None:
        """应用启动时调用（幂等）：后台任务枚举全部 server，绝不阻塞启动。"""
        if self._started:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 无事件循环（导入期/同步测试环境）→ 留待首次 refresh 懒启动
            return
        self._started = True
        self._initial_task = loop.create_task(self._initial_enumerate(), name="mcp-manager-initial")

    async def _initial_enumerate(self) -> None:
        try:
            await self.refresh()
        except Exception as e:  # noqa: BLE001
            logger.warning("[mcp_client] 初始枚举异常（不阻断启动）: %s", e)
        finally:
            self._ready.set()

    def initial_ready(self) -> bool:
        """首轮枚举是否已完成（无论有无可用 server）。"""
        return self._ready.is_set()

    async def wait_ready(self, timeout: float = 30.0) -> bool:
        """等待首轮枚举完成（测试/懒启动用）。"""
        if not self._started:
            await self.refresh()
            self._ready.set()
            return True
        try:
            await asyncio.wait_for(self._ready.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    # ──── 配置装载 ────

    def _load_configs(self) -> List[Dict[str, Any]]:
        """读 plugins 表 source="external_mcp" 且 status="active" 的记录。

        任何异常回退空列表（fail-closed：读不到配置就不提供外部工具）。
        """
        try:
            from app.core.database import SessionLocal
            from app.models.agent import PluginItem
        except Exception as e:  # noqa: BLE001
            logger.warning("[mcp_client] 装载外部 MCP 配置失败（模型不可用）: %s", e)
            return []
        db = SessionLocal()
        try:
            rows = (
                db.query(PluginItem)
                .filter(PluginItem.source == "external_mcp", PluginItem.status == "active")
                .all()
            )
            configs = []
            for row in rows:
                cfg = row.config or {}
                command = str(cfg.get("command") or "").strip()
                if not command:
                    logger.warning("[mcp_client] 外部 MCP 插件 %s 缺少 config.command，跳过", row.plugin_id)
                    continue
                configs.append({
                    "server_id": row.plugin_id,
                    "command": command,
                    "args": [str(a) for a in (cfg.get("args") or [])],
                    "env": {str(k): str(v) for k, v in (cfg.get("env") or {}).items()},
                    "cwd": cfg.get("cwd") or None,
                    "call_timeout_s": float(cfg.get("call_timeout_s") or CALL_TIMEOUT_S),
                })
            return configs
        except Exception as e:  # noqa: BLE001
            logger.warning("[mcp_client] 读取外部 MCP 配置异常（回退空集）: %s", e)
            return []
        finally:
            try:
                db.close()
            except Exception:  # noqa: BLE001
                pass

    # ──── 枚举 / 注册 ────

    async def refresh(self) -> None:
        """按当前配置同步连接与工具清单（幂等；停用的 server 会被杀掉）。

        完成一次枚举后置位 ready（懒启动路径：首次 refresh 后冻结清单才可用）。
        """
        configs = {c["server_id"]: c for c in self._load_configs()}

        # 停掉已不在配置中的连接
        for sid in list(self._conns):
            if sid not in configs:
                logger.info("[mcp_client] server=%s 已停用，停止连接", sid)
                await self._conns.pop(sid).stop()
                self._server_tools.pop(sid, None)

        for sid, cfg in configs.items():
            conn = self._conns.get(sid)
            if conn is None:
                conn = StdioMCPConnection(
                    server_id=sid, command=cfg["command"], args=cfg["args"],
                    env=cfg["env"], cwd=cfg["cwd"], call_timeout_s=cfg["call_timeout_s"],
                )
                self._conns[sid] = conn
            try:
                await conn.start()
                await conn.ensure_ready()
                self._server_tools[sid] = conn.tools
            except Exception as e:  # noqa: BLE001
                # spawn 失败（命令不存在）或握手失败 → 杀掉残留进程，转入后台重启循环
                logger.warning("[mcp_client] server=%s 初始化失败: %s（转入后台自动重启）", sid, e)
                self._server_tools.pop(sid, None)
                if self._conns.get(sid) is conn and not conn._stopping:
                    if conn.is_running:
                        conn._kill_tree()
                    if conn._restart_task is None or conn._restart_task.done():
                        conn._restart_task = asyncio.create_task(
                            conn._restart_loop(), name=f"mcp-{sid}-restart")

        self._register_all()
        self._ready.set()

    def on_connection_ready(self, conn: StdioMCPConnection) -> None:
        """连接重启成功后的回调：刷新工具缓存 + 幂等重注册。"""
        self._server_tools[conn.server_id] = conn.tools
        self._register_all()

    def _register_all(self) -> None:
        """把当前已枚举的外部工具注册到 tool_registry / risk_engine / permission。

        幂等：重复注册覆盖同名项；风险策略只增不减（不放宽既有判定）。
        """
        try:
            from app.services.tools import tool_registry
            from app.core.tool_runtime import risk_engine
            from app.core.tool_runtime.risk_engine import RiskLevel, Verdict
        except Exception as e:  # noqa: BLE001
            logger.warning("[mcp_client] 外部工具注册失败（运行时尚未就绪）: %s", e)
            return

        registered = 0
        for sid, tools in self._server_tools.items():
            for t in tools:
                tool_name = str(t.get("name") or "").strip()
                if not tool_name:
                    continue
                name = external_tool_name(sid, tool_name)
                schema = t.get("inputSchema") or {"type": "object", "properties": {}}
                description = str(t.get("description") or f"外部 MCP 工具 {tool_name}（server: {sid}）")
                tool_registry.register(MCPExternalTool(
                    name=name, description=description, parameters=schema,
                    server_id=sid, tool_name=tool_name,
                ))

                # 风险分级（fail-closed：无 annotations 时按写入类处理）。
                # 写入类注入 HIGH_RISK：经 ApprovalPolicy 在任何权限模式（SAFE/STANDARD/
                # AUTONOMOUS）下都强制人工审批——外部 server 风险未知，与沙箱外命令同哲学，
                # 不得被 STANDARD 模式的"普通写入自动批准"放行。
                annotations = t.get("annotations") or {}
                read_only = bool(annotations.get("readOnlyHint"))
                if read_only:
                    if name not in risk_engine.READ_ONLY_TOOLS:
                        risk_engine.READ_ONLY_TOOLS = risk_engine.READ_ONLY_TOOLS | {name}
                else:
                    risk_engine.TOOL_RISK_POLICY.setdefault(
                        name,
                        (Verdict.HIGH_RISK, RiskLevel.WRITE,
                         f"外部 MCP 工具（{sid}/{tool_name}）未声明只读，需你确认后执行"),
                    )
                    # 保持派生集合同步（permission 侧同时动态读取，双保险）
                    risk_engine.PLAN_FORBIDDEN_TOOLS = (
                        frozenset(risk_engine.PLAN_FORBIDDEN_TOOLS) | {name}
                    )
                    self._sync_permission_compat(name)
                self._register_no_path(name)
                registered += 1
        if registered:
            logger.info("[mcp_client] 外部工具注册完成，共 %d 个", registered)

    def _sync_permission_compat(self, name: str) -> None:
        """写入类外部工具同步进 PermissionFilter._plan_write_tools 兼容镜像（原地 mutation）。"""
        try:
            from app.core.tool_runtime import permission
            mirror = getattr(permission.PermissionFilter, "_plan_write_tools", None)
            if mirror is not None and hasattr(mirror, "add") and name not in mirror:
                mirror.add(name)
        except Exception as e:  # noqa: BLE001
            logger.debug("[mcp_client] _plan_write_tools 镜像同步失败: %s", e)

    def _register_no_path(self, name: str) -> None:
        """外部工具加入无项目路径白名单（原地 mutation，保持 context_builder 持有的引用有效）。

        MCP server 的可访问范围由其自身启动参数约束（如 filesystem 的 allowed dirs），
        与会话是否绑定 project_path 无关。
        """
        try:
            from app.core.tool_runtime import permission
            no_path = getattr(permission, "NO_PATH_TOOLS", None)
            if no_path is not None and hasattr(no_path, "add") and name not in no_path:
                no_path.add(name)
        except Exception as e:  # noqa: BLE001
            logger.debug("[mcp_client] NO_PATH_TOOLS 更新失败: %s", e)

    # ──── 工具调用 ────

    async def call_external(self, server_id: str, tool_name: str,
                            arguments: Dict[str, Any]) -> tuple:
        """执行外部工具调用。返回 (text, ok, err)；异常一律转错误文本不抛出。"""
        conn = self._conns.get(server_id)
        if conn is None:
            return (f"错误: 外部 MCP server {server_id} 未连接（可能已停用，新开会话后生效）",
                    False, "server not connected")
        if not conn.is_running:
            return (f"错误: 外部 MCP server {server_id} 正在重启，请稍后重试",
                    False, "server restarting")
        try:
            result = await conn.call_tool(tool_name, arguments)
        except asyncio.TimeoutError:
            msg = f"错误: 外部 MCP 工具调用超时（{conn.call_timeout_s}s）"
            return (msg, False, "timeout")
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            msg = f"错误: 外部 MCP 工具调用失败: {e}"
            return (msg, False, str(e))

        text = _content_to_text(result)
        if result.get("isError"):
            return (f"错误: 外部 MCP 工具返回错误: {text}", False, text)
        return (text, True, None)

    def write_audit(self, server_id: str, tool_name: str, arguments: Dict[str, Any],
                    duration_ms: int, success: bool, error_message: Optional[str],
                    chat_id: Optional[int] = None, agent_run_id: Optional[int] = None) -> None:
        """外部调用审计 → SandboxAuditLog（写入失败绝不阻断主链路）。"""
        try:
            from app.core.database import SessionLocal
            from app.models.agent import SandboxAuditLog

            summary = f"mcp://{server_id}/{tool_name} args={json.dumps(arguments, ensure_ascii=False, default=str)}"
            db = SessionLocal()
            try:
                db.add(SandboxAuditLog(
                    chat_id=chat_id,
                    agent_run_id=agent_run_id,
                    tool_name=external_tool_name(server_id, tool_name),
                    command=_truncate_audit_text(summary),
                    cwd=None,
                    duration_ms=int(duration_ms),
                    exit_code=0 if success else 1,
                    output_size=0,
                    success=bool(success),
                    error_message=_truncate_audit_text(error_message),
                ))
                db.commit()
            except Exception as e:  # noqa: BLE001
                db.rollback()
                logger.warning("[sandbox_audit] 外部 MCP 审计写入失败: %s", e)
            finally:
                try:
                    db.close()
                except Exception:  # noqa: BLE001
                    pass
        except Exception as e:  # noqa: BLE001
            logger.warning("[sandbox_audit] 外部 MCP 审计写入异常: %s", e)

    # ──── 会话冻结清单 ────

    @staticmethod
    def _session_key(chat: Any) -> str:
        cid = getattr(chat, "id", None)
        return f"chat:{cid}"

    def _build_live_snapshot(self) -> Dict[str, Any]:
        tools: Dict[str, Dict[str, Any]] = {}
        for sid, raw_tools in sorted(self._server_tools.items()):
            for t in raw_tools:
                tool_name = str(t.get("name") or "").strip()
                if not tool_name:
                    continue
                name = external_tool_name(sid, tool_name)
                tools[name] = {
                    "server": sid,
                    "read_only": bool((t.get("annotations") or {}).get("readOnlyHint")),
                    "description": str(t.get("description") or ""),
                }
        return {"servers": sorted(self._server_tools.keys()), "tools": tools}

    def frozen_external_tool_names(self, chat: Any) -> List[str]:
        """会话冻结的外部工具名列表（供 PermissionFilter.resolve 调用，同步非阻塞）。

        - 管理器首轮枚举未完成 → 返回空（fail-closed），且不创建快照；
        - 首次调用创建快照并冻结，会话期内不变；
        - 检测到与实时状态漂移时打 warning（限频），提示新开会话。
        """
        if not self._ready.is_set():
            return []
        key = self._session_key(chat)
        snap = self._snapshots.get(key)
        if snap is None:
            snap = self._build_live_snapshot()
            self._snapshots[key] = snap
            if snap["tools"]:
                logger.info("[mcp_client] 会话 %s 冻结外部工具清单：%d 个（%s）",
                            key, len(snap["tools"]), ", ".join(snap["servers"]))
        self._warn_drift(key, snap)
        return list(snap["tools"].keys())

    def _warn_drift(self, key: str, snap: Dict[str, Any]) -> None:
        live = self._build_live_snapshot()
        if live["tools"].keys() == snap["tools"].keys():
            return
        now = time.monotonic()
        if now - self._drift_warned.get(key, 0.0) < 60.0:
            return
        self._drift_warned[key] = now
        added = sorted(set(live["tools"]) - set(snap["tools"]))
        removed = sorted(set(snap["tools"]) - set(live["tools"]))
        logger.warning(
            "[mcp_client] 会话 %s 的外部 MCP 工具已变更（+%s -%s）；"
            "当前会话继续使用冻结清单，新开会话后生效",
            key, added or "无", removed or "无",
        )

    def get_session_drift(self, chat: Any) -> Dict[str, Any]:
        """查询某会话冻结清单与实时状态的差异（供 UI/运维展示「请新开会话」提示）。"""
        key = self._session_key(chat)
        snap = self._snapshots.get(key) or {"servers": [], "tools": {}}
        live = self._build_live_snapshot()
        return {
            "session_key": key,
            "frozen": snap["servers"],
            "live": live["servers"],
            "added_tools": sorted(set(live["tools"]) - set(snap["tools"])),
            "removed_tools": sorted(set(snap["tools"]) - set(live["tools"])),
            "stale": live["tools"].keys() != snap["tools"].keys(),
        }

    def drop_session(self, chat: Any) -> None:
        """会话结束时释放冻结清单（防长期运行内存增长）。"""
        self._snapshots.pop(self._session_key(chat), None)
        self._drift_warned.pop(self._session_key(chat), None)

    # ──── 调试 / 测试辅助 ────

    def get_connection(self, server_id: str) -> Optional[StdioMCPConnection]:
        return self._conns.get(server_id)

    def get_server_tools(self, server_id: str) -> List[Dict[str, Any]]:
        return list(self._server_tools.get(server_id, []))

    async def shutdown(self) -> None:
        """应用关闭/测试清理：停全部连接。"""
        for conn in list(self._conns.values()):
            await conn.stop()
        self._conns.clear()
        self._server_tools.clear()
        self._ready.clear()
        self._started = False


def _content_to_text(result: Dict[str, Any]) -> str:
    """MCP tools/call 结果 → 文本（content[].text 拼接；兜底 structuredContent/原始 JSON）。"""
    content = result.get("content")
    parts: List[str] = []
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and item.get("text") is not None:
                parts.append(str(item["text"]))
            else:
                parts.append(json.dumps(item, ensure_ascii=False, default=str))
    if parts:
        return "\n".join(parts)
    structured = result.get("structuredContent")
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False, default=str)
    return json.dumps(result, ensure_ascii=False, default=str)


# 模块级单例
external_mcp_manager = ExternalMCPManager()
