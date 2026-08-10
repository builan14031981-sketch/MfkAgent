"""项目沙箱命令执行工具 —— 供 LLM Function Calling 使用。

设计说明（Phase B-1 / Phase 8 P0）：
- 命令是否可执行由 Command Risk Engine（risk_engine.py）在 executor 层判定，
  本模块只负责"执行"：解析 argv → subprocess 运行 → 输出解码/截断。
- 保留 shell 元字符防御（_FORBIDDEN_RE）作为纵深防御。
- 始终在 project_path 下运行（cwd=沙箱锚定项目根），绝对超时，输出截断。
- subprocess 统一走 sandbox.run_subprocess（PYTHONIOENCODING=utf-8 +
  CREATE_NO_WINDOW），输出用阶梯解码（UTF-8 → GBK → CP936 → 替换兜底），
  杜绝 Windows 下 GBK 乱码与解码崩溃。
"""
import os
import re
import subprocess
from typing import Dict, List

from app.core.tools import ToolExecutionError
from app.core.sandbox import (
    SandboxViolation,
    decode_subprocess_output,
    resolve_sandbox_path,
    run_subprocess,
)

# 危险的 shell 元字符/重定向，一律拒绝（防注入，纵深防御）
_FORBIDDEN_RE = re.compile(r"[;&|`$<>]|\(|\)")

# 显式 cd 到外部目录（绝对路径 / UNC / .. 逃逸）：工作目录已锚定，直接拦截
_CD_ESCAPE_RE = re.compile(r"\bcd\s+([A-Za-z]:[\\/]|\\\\|\.\.)", re.I)

TIMEOUT = 30
MAX_OUTPUT_CHARS = 8000


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
    if _FORBIDDEN_RE.search(command):
        return "错误: 命令包含不允许的字符（; & | ` $ < > 等），拒绝执行"
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
]

COMMAND_TOOLS = {
    "run_command": run_command,
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
