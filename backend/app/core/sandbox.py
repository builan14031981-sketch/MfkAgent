"""统一路径沙箱与子进程执行封装（Phase 8 P0 + Phase 9 P1 长路径兼容）。

职责：
  1. resolve_sandbox_path() — 唯一路径越权校验入口
     - Phase 9: 使用 safe_resolve() 替代 Path.resolve()，避免穿透 Junction
     - is_relative_to() 做 Windows 大小写安全的包含判定
     - 越权统一抛 SandboxViolation(PermissionError)
  2. decode_subprocess_output() — Windows 兼容的 subprocess 阶梯解码
     - UTF-8 → GBK/CP936 → UTF-8(errors=replace)，绝不抛 UnicodeDecodeError
  3. run_subprocess() — 统一子进程执行封装
     - 注入 PYTHONIOENCODING=utf-8 引导 Python 子进程以 UTF-8 输出
     - CREATE_NO_WINDOW 防黑窗，绝对超时，捕获 stdout+stderr

所有本地文件读写 / 目录列举 / 命令执行工具都必须经由本模块，禁止自行拼路径。
"""
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union

# Phase 9 P1: 长路径与 Junction 过滤
from app.core.path_utils import safe_resolve as _safe_resolve, ensure_long_path, IS_WINDOWS


class SandboxViolation(PermissionError):
    """路径越权异常：既是 PermissionError（明确的越权语义），也便于上层精确捕获。"""


def resolve_sandbox_path(target_path: str, project_root: str) -> Path:
    """解析并校验路径，防止 Path Traversal 路径穿越。

    Phase 9: 使用 safe_resolve() 替代 Path.resolve()，避免穿透 Windows Junction
    导致路径解析到项目目录之外。

    Args:
        target_path: 目标路径（支持相对路径或绝对路径，如 src/app.py / C:\\proj\\x）
        project_root: 项目根目录绝对路径（沙箱边界）。相对路径会被转为绝对路径。

    Returns:
        Path: 规范化后的真实路径

    Raises:
        SandboxViolation(PermissionError): 真实路径越出 project_root 之外
    """
    # project_root 统一归一为绝对路径（兼容相对路径调用方，如测试中的 "."）
    root = _safe_resolve(os.path.abspath(project_root))
    if Path(target_path).is_absolute():
        target = _safe_resolve(target_path)
    else:
        target = _safe_resolve(root / target_path)

    if not (target == root or target.is_relative_to(root)):
        raise SandboxViolation(
            f"【安全拦截】路径越权，禁止访问项目目录之外: {target_path}"
        )
    return target


def decode_subprocess_output(output_bytes: bytes) -> str:
    """Windows 兼容的 subprocess 阶梯解码策略。

    优先 UTF-8，其次 Windows 中文默认编码 GBK/CP936，
    终极兜底 UTF-8 强制解码并替换非法字符，绝不抛 Exception。
    """
    if not output_bytes:
        return ""
    for encoding in ("utf-8", "gbk", "cp936"):
        try:
            return output_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return output_bytes.decode("utf-8", errors="replace")


def run_subprocess(
    argv: List[str],
    cwd: Optional[str] = None,
    timeout: int = 30,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    """统一子进程执行封装。

    - 注入 PYTHONIOENCODING=utf-8，从源头引导 Python 子进程以 UTF-8 输出
    - text=False 保留原始字节，由 decode_subprocess_output 阶梯解码
    - CREATE_NO_WINDOW 防止 Windows 弹出黑框
    """
    run_env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    if env:
        run_env.update(env)
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=False,
        timeout=timeout,
        env=run_env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
