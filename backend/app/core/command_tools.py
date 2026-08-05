"""项目沙箱命令执行工具（只读）—— 供 LLM Function Calling 使用。

设计约束（低风险优先）：
- 只允许"查看类"命令：git 状态类、pytest --collect-only / 测试、lint 检查等。
  禁止任何写入/网络/交互命令（rm / git push / pip install / python -i 等）。
- 始终在 project_path 下运行（cwd=项目根），绝对超时，输出截断，GBK 安全解码。
- 与 FILE_TOOLS / GIT_TOOLS / SEARCH_TOOLS 同一模式：project_path + 文本结果。
"""
import os
import re
import subprocess
from typing import Dict, List

from app.core.tools import ToolExecutionError

# 允许执行的安全命令白名单（前缀匹配，每个子参数独立校验）
# 形如: ("命令", [参数前缀...])，参数满足任一前缀即可；空列表 = 只允许裸命令
_ALLOWED_COMMANDS: List[tuple] = [
    # 测试/验证类
    ("pytest", []),
    ("python", ["-m", "pytest"]),
    ("python", ["-m", "unittest"]),
    ("python", ["-m", "py_compile"]),
    ("python", ["-m", "mypy"]),
    ("python", ["-m", "ruff"]),
    ("python", ["-m", "flake8"]),
    ("node", ["--version"]),
    ("node", ["-e", "--check"]),
    ("npm", ["run", "lint"]),
    ("npm", ["run", "test"]),
    ("npm", ["run", "build"]),
    ("npm", ["run", "typecheck"]),
    ("npm", ["test"]),
    ("npm", ["run"]),
    ("git", ["status"]),
    ("git", ["diff"]),
    ("git", ["log"]),
    ("git", ["show"]),
    ("git", ["branch"]),
    # 网络诊断类（只读，用于检查网络状态）
    ("ipconfig", []),
    ("netstat", []),
    ("ping", ["-n"]),  # -n 指定次数，防止无限 ping
    ("nslookup", []),
    ("tracert", []),
    ("systeminfo", []),
    ("hostname", []),
    ("whoami", []),
]

# 危险的 shell 元字符/重定向，一律拒绝（防注入）
_FORBIDDEN_RE = re.compile(r"[;&|`$<>]|\(|\)")

TIMEOUT = 30
MAX_OUTPUT_CHARS = 8000


def _decode_bytes(b: bytes) -> str:
    """先按 UTF-8 解码，失败再按 GBK（Windows 中文输出常见），仍失败则逐字节替换。"""
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return b.decode("gbk")
        except UnicodeDecodeError:
            return b.decode("utf-8", errors="replace")


def _is_allowed(argv: List[str]) -> str:
    """校验命令是否在白名单内。通过返回空串，否则返回拒绝原因。"""
    if not argv:
        return "错误: 命令不能为空"
    cmd = argv[0]
    for allowed_cmd, prefixes in _ALLOWED_COMMANDS:
        if cmd != allowed_cmd:
            continue
        if not prefixes:
            return ""
        if len(argv) >= 2 and argv[1] in prefixes:
            return ""
    return f"错误: 命令 '{cmd}' 不在只读白名单内。只允许: " + ", ".join(sorted(set(c for c, _ in _ALLOWED_COMMANDS)))


def run_command(project_path: str, command: str, timeout: int = TIMEOUT) -> str:
    """在项目内执行只读安全命令（白名单），返回 stdout+stderr 合并输出。
    如果没有 project_path，允许执行系统级命令（如 ipconfig、netstat 等）。
    """
    command = (command or "").strip()
    if not command:
        return "错误: command 不能为空"
    if _FORBIDDEN_RE.search(command):
        return "错误: 命令包含不允许的字符（; & | ` $ < > 等），只读工具拒绝执行"

    # 解析命令行（按空格拆分，保留引号包裹的参数 —— 仅白名单前缀校验场景够用）
    argv = re.split(r"\s+", command.strip())
    reason = _is_allowed(argv)
    if reason:
        return reason

    # 确定工作目录：有 project_path 则用项目目录，否则用当前目录（允许系统级命令）
    if project_path:
        proj_real = os.path.realpath(project_path)
        if not os.path.isdir(proj_real):
            return f"错误: 项目目录不存在: {project_path}"
        cwd = proj_real
    else:
        # 没有绑定项目，允许执行系统级命令（如 ipconfig、netstat）
        cwd = os.getcwd()

    timeout = max(1, min(int(timeout or TIMEOUT), 120))
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=False,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError:
        return f"错误: 找不到命令 '{argv[0]}'（可能未安装或不在 PATH）"
    except subprocess.TimeoutExpired:
        return f"错误: 命令执行超时（>{timeout}s），已终止"
    except Exception as e:
        return f"错误: 命令执行失败: {e}"

    out = _decode_bytes(proc.stdout)
    err = _decode_bytes(proc.stderr)
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
                "执行只读安全命令。支持两类场景：\n"
                "1. 项目内验证代码：pytest / python -m py_compile / npm run lint|test|build / git status|diff|log\n"
                "2. 系统级诊断命令：ipconfig / netstat / ping -n 3 8.8.8.8 / nslookup / tracert / systeminfo / hostname / whoami\n"
                "所有命令必须在白名单内，禁止写入、网络请求或交互式命令。"
                "当用户询问系统信息、网络状态、代理设置等时，应主动调用此工具执行相应命令获取真实数据。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的只读命令，如 'ipconfig'、'netstat -an'、'ping -n 3 8.8.8.8'、'python -m py_compile app.py'",
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
