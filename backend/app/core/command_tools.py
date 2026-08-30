"""项目沙箱命令执行工具 —— 供 LLM Function Calling 使用。

设计说明（Phase B-1 / Phase 8 P0 / Phase 4 T1）：
- 命令是否可执行由 Command Risk Engine（risk_engine.py）在 executor 层判定，
  本模块只负责"执行"：解析 argv → subprocess 运行 → 输出解码/截断。
- 保留 shell 元字符防御（_FORBIDDEN_RE）作为纵深防御。
- 始终在 project_path 下运行（cwd=沙箱锚定项目根），绝对超时，输出截断。
- subprocess 统一走 sandbox.run_subprocess（PYTHONIOENCODING=utf-8 +
  CREATE_NO_WINDOW），输出用阶梯解码（UTF-8 → GBK → CP936 → 替换兜底），
  杜绝 Windows 下 GBK 乱码与解码崩溃。

execute_command（Secure Execution Runtime V1 + Phase 4 T1 增强）：
- 专为项目命令设计（pytest / npm test / npm run build 等）
- 返回结构化结果：stdout / stderr / exit_code / execution_time
- 风险策略：安全命令 ALLOW，未知命令 REQUIRE_APPROVAL，危险命令 HIGH_RISK
- Phase 4 T1: 执行前 cwd 禁执行目录黑名单检查（黑名单命中直接拒绝）
- Phase 4 T1: 执行后写审计日志到 sandbox_audit_logs（写入失败不影响执行）
- Phase 4 T1: 高风险磁盘操作（git clone / npm install / pip install）执行前检查磁盘配额
"""
import json
import logging
import os
import re
import subprocess
import time
from typing import Dict, List, Optional

from app.core.tools import ToolExecutionError
from app.core.sandbox import (
    SandboxViolation,
    check_disk_quota,
    decode_subprocess_output,
    detect_high_risk_disk_op,
    is_forbidden_cwd,
    resolve_sandbox_path,
    run_subprocess,
    DISK_QUOTA_BYTES,
)

logger = logging.getLogger(__name__)

# 危险的 shell 元字符/重定向，一律拒绝（防注入，纵深防御）
_FORBIDDEN_RE = re.compile(r"[;&|`$<>]|\(|\)")

def _has_forbidden_chars(command: str) -> bool:
    cmd_lower = (command or "").lower().strip()
    if cmd_lower.startswith("powershell") or cmd_lower.startswith("pwsh"):
        # 对 powershell 命令，允许语法符号 ($ ; () 等)，仅拦截重定向、反引号与管道
        return bool(re.search(r"[`&|<>]", command))
    return bool(_FORBIDDEN_RE.search(command))

# 显式 cd 到外部目录（绝对路径 / UNC / .. 逃逸）：工作目录已锚定，直接拦截
_CD_ESCAPE_RE = re.compile(r"\bcd\s+([A-Za-z]:[\\/]|\\\\|\.\.)", re.I)

TIMEOUT = 30
MAX_OUTPUT_CHARS = 8000

# 审计日志 command/cwd 截断（避免超长 LLM 输出撑爆数据库 TEXT 字段）
_AUDIT_TEXT_MAX = 8192


def _split_command(command: str) -> List[str]:
    """按空白拆分命令，支持双引号包裹的含空格参数（保留反斜杠原样）。

    修复：reg query "HKCU\\...\\Internet Settings" 这类路径含空格，
    原 re.split(r"\\s+") 会把路径拆碎且残留引号，导致命令无效。
    """
    args = []
    buf = []
    in_quote = False
    for ch in command:
        if ch == '"':
            in_quote = not in_quote
        elif ch in (" ", "\t") and not in_quote:
            if buf:
                args.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        args.append("".join(buf))
    return args


def run_command(project_path: str, command: str, timeout: int = TIMEOUT) -> str:
    """执行命令并返回 stdout+stderr 合并输出（策略判定已在 executor 层完成）。
    如果没有 project_path，允许执行系统级命令（如 ipconfig、netstat 等）。
    """
    command = (command or "").strip()
    if not command:
        return "错误: command 不能为空"
    if _has_forbidden_chars(command):
        # T11: 可安全拆分的链式/wrapper 命令放行（逐段风险判定已在 CommandRiskEngine.evaluate
        # 完成，与执行门共用同一 fail-closed 解析器）；其余维持元字符拒绝。
        # 局部导入避免与 tool_runtime 包 __init__（模块级 ToolRuntime 实例化）循环导入。
        from app.core.tool_runtime.risk_engine import chain_gate_allows
        if not chain_gate_allows(command):
            return "错误: 命令包含不允许的字符（& | ` < > 等），拒绝执行。"
    if _CD_ESCAPE_RE.search(command):
        return "错误: 不支持 cd 切换到项目外目录（工作目录已锚定在项目内），请直接使用项目内相对命令"

    # 解析命令行（支持双引号含空格参数）
    argv = _split_command(command)

    # 确定工作目录：有 project_path 则用沙箱解析后的项目根；否则用当前目录（允许系统级命令）
    if project_path:
        try:
            cwd = str(resolve_sandbox_path(".", project_path))
        except SandboxViolation as e:
            return f"错误: {e}"
        if not os.path.isdir(cwd):
            return f"错误: 项目目录不存在: {project_path}"
    else:
        # 没有绑定项目，允许执行系统级命令（如 ipconfig、netstat）
        cwd = os.getcwd()

    timeout = max(1, min(int(timeout or TIMEOUT), 120))
    try:
        proc = run_subprocess(argv, cwd=cwd, timeout=timeout)
    except FileNotFoundError:
        return f"错误: 找不到命令 '{argv[0]}'（可能未安装或不在 PATH）"
    except subprocess.TimeoutExpired:
        return f"错误: 命令执行超时（>{timeout}s），已终止"
    except Exception as e:
        return f"错误: 命令执行失败: {e}"

    out = decode_subprocess_output(proc.stdout)
    err = decode_subprocess_output(proc.stderr)
    combined = (out + ("\n" + err if err else "")).strip()
    if not combined:
        combined = "(无输出)"

    prefix = f"$ {' '.join(argv)}\n[exit code {proc.returncode}]\n"
    if len(combined) > MAX_OUTPUT_CHARS:
        combined = combined[:MAX_OUTPUT_CHARS] + f"\n...(输出已截断，共 {len(combined)} 字符)"
    return prefix + combined


# ──── execute_command（Secure Execution Runtime V1 + Phase 4 T1）────

EXECUTE_TIMEOUT = 60
EXECUTE_MAX_OUTPUT = 10000


def _truncate_audit_text(text: str, max_len: int = _AUDIT_TEXT_MAX) -> str:
    """审计日志文本截断（避免 LLM 长输出撑爆数据库）。"""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"...(truncated, total {len(text)} chars)"


def _write_sandbox_audit(
    tool_name: str,
    command: str,
    cwd: str,
    duration_ms: int,
    exit_code: Optional[int],
    output_size: int,
    success: bool,
    error_message: Optional[str] = None,
    chat_id: Optional[int] = None,
    agent_run_id: Optional[int] = None,
) -> None:
    """Phase 4 T1: 写审计日志到 sandbox_audit_logs 表。

    旁路设计：所有异常 try/except 兜底，绝不抛回主流程，绝不阻断命令执行。
    仅记录元信息（命令、cwd、耗时、退出码、输出大小、success），不记录 stdout/stderr 内容。
    """
    try:
        from app.core.database import SessionLocal
        from app.models.agent import SandboxAuditLog

        db = SessionLocal()
        try:
            log = SandboxAuditLog(
                chat_id=chat_id,
                agent_run_id=agent_run_id,
                tool_name=tool_name,
                command=_truncate_audit_text(command),
                cwd=_truncate_audit_text(cwd) if cwd else None,
                duration_ms=duration_ms,
                exit_code=exit_code,
                output_size=output_size,
                success=success,
                error_message=_truncate_audit_text(error_message) if error_message else None,
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.warning("[sandbox_audit] 写入审计日志失败: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception as e:
        # 数据库 SessionLocal 创建失败时（极端情况），静默吞掉
        logger.warning("[sandbox_audit] 初始化审计会话失败: %s", e)


def _check_disk_quota_for_command(command: str, work_dir: str) -> Optional[str]:
    """检查命令对应的高风险磁盘操作的磁盘配额。

    Returns:
        None: 通过
        str: 拒绝原因（人类可读）
    """
    op = detect_high_risk_disk_op(command)
    if not op:
        return None
    required = DISK_QUOTA_BYTES.get(op, 0)
    if required <= 0:
        return None
    ok, message = check_disk_quota(work_dir, required)
    if not ok:
        return message
    return None


def execute_command(
    project_path: str,
    command: str,
    cwd: str = "",
    timeout: int = EXECUTE_TIMEOUT,
    chat_id: Optional[int] = None,
    agent_run_id: Optional[int] = None,
) -> str:
    """安全执行项目命令，返回结构化 JSON 结果。

    安全约束：
      - 必须绑定 project_path（沙箱锚定）
      - 禁止 shell 元字符
      - 禁止 cd 逃逸到项目外
      - Phase 4 T1: 禁止 cwd 落入禁执行目录黑名单（Windows 系统目录/Program Files/用户根目录等）
      - Phase 4 T1: 高风险磁盘操作（git clone/npm install/pip install）执行前检查磁盘配额
      - Phase 4 T1: 执行后写审计日志（写入失败不影响执行）
      - 超时自动终止
      - 输出截断保护

    Returns:
        JSON 字符串: {"stdout": "...", "stderr": "...", "exit_code": 0, "execution_time": 0.123}
    """
    command = (command or "").strip()
    if not command:
        return json.dumps({"stdout": "", "stderr": "command 不能为空", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)

    if not project_path:
        return json.dumps({"stdout": "", "stderr": "execute_command 需要绑定项目（project_path 不能为空）", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)

    if _has_forbidden_chars(command):
        return json.dumps({"stdout": "", "stderr": "命令包含不允许的字符（& | ` < > 等），拒绝执行。", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)

    if _CD_ESCAPE_RE.search(command):
        return json.dumps({"stdout": "", "stderr": "不支持 cd 切换到项目外目录", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)

    # 沙箱校验：工作目录必须在 project_path 内
    try:
        if cwd and cwd.strip():
            work_dir = str(resolve_sandbox_path(cwd.strip(), project_path))
        else:
            work_dir = str(resolve_sandbox_path(".", project_path))
    except SandboxViolation as e:
        return json.dumps({"stdout": "", "stderr": f"路径越权: {e}", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)

    if not os.path.isdir(work_dir):
        return json.dumps({"stdout": "", "stderr": f"工作目录不存在: {work_dir}", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)

    # Phase 4 T1: 禁执行目录黑名单兜底（即使 work_dir 已被沙箱校验过，再做一次系统级黑名单检查）
    forbidden, forbid_reason = is_forbidden_cwd(work_dir)
    if forbidden:
        return json.dumps({"stdout": "", "stderr": f"【安全拦截】{forbid_reason}", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)

    # Phase 4 T1: 高风险磁盘操作配额检查
    quota_err = _check_disk_quota_for_command(command, work_dir)
    if quota_err:
        return json.dumps({"stdout": "", "stderr": f"【安全拦截】{quota_err}", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)

    timeout = max(1, min(int(timeout or EXECUTE_TIMEOUT), 300))
    argv = _split_command(command)

    start = time.monotonic()
    try:
        from app.core.proxy import resolve_proxy_env

        proc = run_subprocess(
            argv, cwd=work_dir, timeout=timeout, env=resolve_proxy_env()
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = decode_subprocess_output(proc.stdout) or ""
        stderr = decode_subprocess_output(proc.stderr) or ""
        exit_code = proc.returncode
        success = (exit_code == 0)

        # 输出截断
        if len(stdout) > EXECUTE_MAX_OUTPUT:
            stdout = stdout[:EXECUTE_MAX_OUTPUT] + f"\n...(stdout 已截断，共 {len(stdout)} 字符)"
        if len(stderr) > EXECUTE_MAX_OUTPUT:
            stderr = stderr[:EXECUTE_MAX_OUTPUT] + f"\n...(stderr 已截断，共 {len(stderr)} 字符)"

        # Phase 4 T1: 写审计日志（双重 try/except 兜底，失败不影响主流程）
        try:
            _write_sandbox_audit(
                tool_name="execute_command",
                command=command,
                cwd=work_dir,
                duration_ms=elapsed_ms,
                exit_code=exit_code,
                output_size=len(stdout) + len(stderr),
                success=success,
                chat_id=chat_id,
                agent_run_id=agent_run_id,
            )
        except Exception as audit_err:
            logger.warning("[execute_command] 审计日志写入异常（已吞掉）: %s", audit_err)

        return json.dumps({
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "execution_time": round(elapsed_ms / 1000, 3),
        }, ensure_ascii=False)

    except FileNotFoundError:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        try:
            _write_sandbox_audit(
                tool_name="execute_command",
                command=command,
                cwd=work_dir,
                duration_ms=elapsed_ms,
                exit_code=-1,
                output_size=0,
                success=False,
                error_message=f"找不到命令 '{argv[0] if argv else ''}'（可能未安装或不在 PATH）",
                chat_id=chat_id,
                agent_run_id=agent_run_id,
            )
        except Exception as audit_err:
            logger.warning("[execute_command] 审计日志写入异常（已吞掉）: %s", audit_err)
        return json.dumps({"stdout": "", "stderr": f"找不到命令 '{argv[0]}'（可能未安装或不在 PATH）", "exit_code": -1, "execution_time": round(elapsed_ms / 1000, 3)}, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        try:
            _write_sandbox_audit(
                tool_name="execute_command",
                command=command,
                cwd=work_dir,
                duration_ms=elapsed_ms,
                exit_code=-1,
                output_size=0,
                success=False,
                error_message=f"命令执行超时（>{timeout}s）",
                chat_id=chat_id,
                agent_run_id=agent_run_id,
            )
        except Exception as audit_err:
            logger.warning("[execute_command] 审计日志写入异常（已吞掉）: %s", audit_err)
        return json.dumps({"stdout": "", "stderr": f"命令执行超时（>{timeout}s），已终止", "exit_code": -1, "execution_time": round(elapsed_ms / 1000, 3)}, ensure_ascii=False)
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        try:
            _write_sandbox_audit(
                tool_name="execute_command",
                command=command,
                cwd=work_dir,
                duration_ms=elapsed_ms,
                exit_code=-1,
                output_size=0,
                success=False,
                error_message=f"命令执行异常: {e}",
                chat_id=chat_id,
                agent_run_id=agent_run_id,
            )
        except Exception as audit_err:
            logger.warning("[execute_command] 审计日志写入异常（已吞掉）: %s", audit_err)
        return json.dumps({"stdout": "", "stderr": f"命令执行异常: {e}", "exit_code": -1, "execution_time": round(elapsed_ms / 1000, 3)}, ensure_ascii=False)


# ──── run_outside_command（沙箱外命令 · 强制人工审批）────

OUTSIDE_TIMEOUT = 60
OUTSIDE_MAX_OUTPUT = 10000


def run_command_outside(
    project_path: str,
    command: str,
    cwd: str,
    timeout: int = OUTSIDE_TIMEOUT,
    chat_id: Optional[int] = None,
    agent_run_id: Optional[int] = None,
) -> str:
    """在项目沙箱外执行命令（任意 cwd），返回结构化 JSON 结果。

    与 execute_command 的核心差异：**不做 resolve_sandbox_path 沙箱锚定**，
    工作目录可以是项目外的任意目录（沙箱外的意义所在）。

    安全约束：
      - 必须绑定 project_path（会话前置条件，与 execute_command 一致）
      - cwd 必填且必须为绝对路径（拒绝相对路径，避免落到后端进程不可预期的当前目录）
      - cwd 必须存在
      - 允许自由 cd 到任意非禁执行目录（不做 _CD_ESCAPE_RE 拦截）
      - 保留 shell 元字符拦截（_FORBIDDEN_RE，纵深防御）
      - Phase 4 T1: cwd 落入禁执行目录黑名单（Windows 系统目录/Program Files/盘根）→ 拒绝
      - Phase 4 T1: 高风险磁盘操作（git clone/npm install/pip install）执行前检查磁盘配额
      - Phase 4 T1: 执行后写审计日志（写入失败不影响执行）
      - 超时自动终止 + 输出截断

    风险判定在 executor 层由 evaluate_outside 完成（恒定 HIGH_RISK → 强制人工审批），
    本模块只负责"执行"。所有拦截返回统一以"错误:" 开头（供完成验证的拦截豁免识别）。
    """
    command = (command or "").strip()
    cwd = (cwd or "").strip()
    if not command:
        return json.dumps({"stdout": "", "stderr": "command 不能为空", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)
    if not project_path:
        return json.dumps({"stdout": "", "stderr": "run_outside_command 需要绑定项目（project_path 不能为空）", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)
    if not cwd:
        return json.dumps({"stdout": "", "stderr": "cwd 不能为空，必须显式指定沙箱外目标目录（绝对路径）", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)
    if not os.path.isabs(cwd):
        return json.dumps({"stdout": "", "stderr": f"cwd 必须为绝对路径: {cwd}", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)
    if _has_forbidden_chars(command):
        return json.dumps({"stdout": "", "stderr": "命令包含不允许的字符（& | ` < > 等），拒绝执行。如需连续执行多个命令，请分多次调用 run_command_outside", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)

    work_dir = os.path.normpath(cwd)
    if not os.path.isdir(work_dir):
        return json.dumps({"stdout": "", "stderr": f"错误: 工作目录不存在: {work_dir}", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)

    # Phase 4 T1: 禁执行目录黑名单（系统目录/Program Files/盘根 → 拒绝）
    forbidden, forbid_reason = is_forbidden_cwd(work_dir)
    if forbidden:
        return json.dumps({"stdout": "", "stderr": f"错误: 【安全拦截】{forbid_reason}", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)

    # Phase 4 T1: 高风险磁盘操作配额检查
    quota_err = _check_disk_quota_for_command(command, work_dir)
    if quota_err:
        return json.dumps({"stdout": "", "stderr": f"错误: 【安全拦截】{quota_err}", "exit_code": -1, "execution_time": 0}, ensure_ascii=False)

    timeout = max(1, min(int(timeout or OUTSIDE_TIMEOUT), 300))
    argv = _split_command(command)

    start = time.monotonic()
    try:
        from app.core.proxy import resolve_proxy_env

        proc = run_subprocess(argv, cwd=work_dir, timeout=timeout, env=resolve_proxy_env())
        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = decode_subprocess_output(proc.stdout) or ""
        stderr = decode_subprocess_output(proc.stderr) or ""
        exit_code = proc.returncode
        success = (exit_code == 0)

        # 输出截断
        if len(stdout) > OUTSIDE_MAX_OUTPUT:
            stdout = stdout[:OUTSIDE_MAX_OUTPUT] + f"\n...(stdout 已截断，共 {len(stdout)} 字符)"
        if len(stderr) > OUTSIDE_MAX_OUTPUT:
            stderr = stderr[:OUTSIDE_MAX_OUTPUT] + f"\n...(stderr 已截断，共 {len(stderr)} 字符)"

        # Phase 4 T1: 写审计日志（双重 try/except 兜底，失败不影响主流程）
        try:
            _write_sandbox_audit(
                tool_name="run_outside_command",
                command=command,
                cwd=work_dir,
                duration_ms=elapsed_ms,
                exit_code=exit_code,
                output_size=len(stdout) + len(stderr),
                success=success,
                chat_id=chat_id,
                agent_run_id=agent_run_id,
            )
        except Exception as audit_err:
            logger.warning("[run_outside_command] 审计日志写入异常（已吞掉）: %s", audit_err)

        return json.dumps({
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "execution_time": round(elapsed_ms / 1000, 3),
        }, ensure_ascii=False)

    except FileNotFoundError:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        try:
            _write_sandbox_audit(
                tool_name="run_outside_command",
                command=command,
                cwd=work_dir,
                duration_ms=elapsed_ms,
                exit_code=-1,
                output_size=0,
                success=False,
                error_message=f"找不到命令 '{argv[0] if argv else ''}'（可能未安装或不在 PATH）",
                chat_id=chat_id,
                agent_run_id=agent_run_id,
            )
        except Exception as audit_err:
            logger.warning("[run_outside_command] 审计日志写入异常（已吞掉）: %s", audit_err)
        return json.dumps({"stdout": "", "stderr": f"找不到命令 '{argv[0]}'（可能未安装或不在 PATH）", "exit_code": -1, "execution_time": round(elapsed_ms / 1000, 3)}, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        try:
            _write_sandbox_audit(
                tool_name="run_outside_command",
                command=command,
                cwd=work_dir,
                duration_ms=elapsed_ms,
                exit_code=-1,
                output_size=0,
                success=False,
                error_message=f"命令执行超时（>{timeout}s）",
                chat_id=chat_id,
                agent_run_id=agent_run_id,
            )
        except Exception as audit_err:
            logger.warning("[run_outside_command] 审计日志写入异常（已吞掉）: %s", audit_err)
        return json.dumps({"stdout": "", "stderr": f"命令执行超时（>{timeout}s），已终止", "exit_code": -1, "execution_time": round(elapsed_ms / 1000, 3)}, ensure_ascii=False)
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        try:
            _write_sandbox_audit(
                tool_name="run_outside_command",
                command=command,
                cwd=work_dir,
                duration_ms=elapsed_ms,
                exit_code=-1,
                output_size=0,
                success=False,
                error_message=f"命令执行异常: {e}",
                chat_id=chat_id,
                agent_run_id=agent_run_id,
            )
        except Exception as audit_err:
            logger.warning("[run_outside_command] 审计日志写入异常（已吞掉）: %s", audit_err)
        return json.dumps({"stdout": "", "stderr": f"命令执行异常: {e}", "exit_code": -1, "execution_time": round(elapsed_ms / 1000, 3)}, ensure_ascii=False)


# ──── Schema & 注册 ────

COMMAND_TOOLS_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "执行系统命令。支持两类场景：\n"
                "1. 项目内验证代码：pytest / python -m py_compile / npm run lint|test|build / git status|diff|log\n"
                "2. 系统级诊断命令：ipconfig / netstat / ping -n 3 8.8.8.8 / nslookup / tracert / systeminfo / "
                "netsh winhttp show proxy / reg query / tasklist / getmac / route print / arp -a / dir / ver 等\n"
                "只读命令自动执行；危险或修改性操作（写文件、安装、删除等）会先请求用户确认，批准后才会执行。\n"
                "当用户询问系统信息、网络状态、代理设置等时，应主动调用此工具获取真实数据。\n"
                "### Windows 代理查询（重要）\n"
                "Windows 存在两套独立代理配置：WinINET（系统/浏览器实际使用）与 WinHTTP（部分命令行程序使用）。\n"
                "用户询问「系统代理 / 电脑代理 / 浏览器代理」时，优先使用 WinINET 注册表查询：\n"
                "reg query \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings\" /v ProxyEnable\n"
                "reg query \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings\" /v ProxyServer\n"
                "注意：netsh winhttp show proxy 只能代表 WinHTTP 层，不代表用户系统代理状态，不得仅凭它判断用户代理配置。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的命令，如 'ipconfig'、'netstat -an'、'ping -n 3 8.8.8.8'、'python -m py_compile app.py'",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时秒数（默认 30，上限 120）",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "安全执行项目命令（Secure Execution Runtime V1）。\n"
                "专为项目内命令设计：pytest / npm test / npm run build / python app.py 等。\n"
                "返回结构化 JSON：stdout / stderr / exit_code / execution_time。\n"
                "安全命令（pytest/npm test）自动放行；未知命令需审批；危险命令（rm/del/format）强制拦截。\n"
                "当用户说「运行测试」「启动项目」「编译」「执行命令」时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的命令，如 'pytest'、'npm test'、'npm run build'、'python app.py'",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "工作目录（相对于 project_path，可选，默认项目根目录）",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时秒数（默认 60，上限 300）",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_outside_command",
            "description": (
                "在项目沙箱外执行命令（任意工作目录），返回结构化 JSON：stdout / stderr / exit_code / execution_time。\n"
                "与 execute_command 不同：工作目录不受项目根限制，可用于操作项目外的其他目录。\n"
                "安全约束：cwd 必须为绝对路径且存在；Windows 系统目录/Program Files/盘符根目录被拒绝；禁止 shell 元字符。\n"
                "【重要】每一步沙箱外命令都会弹出人工审批，用户批准后才执行，任何权限模式都不会自动放行。"
                "仅在用户明确要求操作项目外目录时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的命令，如 'ver'、'dir'、'python app.py'、'git log'",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "沙箱外目标工作目录（必须为绝对路径，如 'E:/data'、'D:/repo'）",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时秒数（默认 60，上限 300）",
                    },
                },
                "required": ["command", "cwd"],
            },
        },
    },
]

COMMAND_TOOLS = {
    "run_command": run_command,
    "execute_command": execute_command,
    "run_outside_command": run_command_outside,
}


def execute_command_tool(name: str, project_path: str, **kwargs) -> str:
    """执行命令工具并返回文本结果（失败返回错误说明）。"""
    fn = COMMAND_TOOLS.get(name)
    if fn is None:
        return f"错误: 未知工具 {name}"
    try:
        return fn(project_path=project_path, **kwargs)
    except ToolExecutionError as e:
        return f"错误: {e}"
    except Exception as e:
        return f"错误: {e}"
