"""Phase 9 P1: 端口占用检测与自动避让。

在 Windows 桌面环境下，端口极易被占用（Hyper-V、IIS、其他开发工具等）。
本模块提供服务启动前的端口检测、自动递增寻址、端口持久化能力。

用法：
    from app.core.port_manager import find_available_port, write_port_file, read_port_file

    port = find_available_port(8001)
    write_port_file(port)
    # 启动 uvicorn 时使用 port
"""

import socket
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 端口文件统一放在 backend 目录下，供 Electron 主进程读取
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PORT_FILE = BACKEND_DIR / ".mfkagent_port"

# 默认起始端口与最大尝试次数
DEFAULT_PORT = 8001
MAX_PORT_ATTEMPTS = 100
MAX_PORT = 65535


def _is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """检测指定端口是否可用（通过尝试绑定 socket 判断）。

    使用 SO_REUSEADDR 避免 TIME_WAIT 残留干扰。
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
        sock.listen(1)
        return True
    except OSError:
        return False
    finally:
        try:
            sock.close()
        except OSError:
            pass


def find_available_port(
    start_port: int = DEFAULT_PORT,
    host: str = "127.0.0.1",
    max_attempts: int = MAX_PORT_ATTEMPTS,
) -> int:
    """从 start_port 开始向上递增寻找可用端口。

    Args:
        start_port: 起始端口号（默认 8001）
        host: 绑定地址（默认 127.0.0.1）
        max_attempts: 最大尝试次数（默认 100）

    Returns:
        int: 第一个可用端口号

    Raises:
        RuntimeError: 在 max_attempts 次尝试内未找到可用端口
    """
    for offset in range(max_attempts):
        port = start_port + offset
        if port > MAX_PORT:
            raise RuntimeError(
                f"端口寻址已达上限 {MAX_PORT}，无法分配可用端口"
            )
        if _is_port_available(port, host):
            if offset > 0:
                logger.warning(
                    "Phase9 port: 默认端口 %d 被占用，自动切换至 %d（偏移 +%d）",
                    start_port, port, offset,
                )
            else:
                logger.info("Phase9 port: 默认端口 %d 可用", port)
            return port

    raise RuntimeError(
        f"在 {start_port}–{start_port + max_attempts - 1} 范围内未找到可用端口"
    )


def write_port_file(port: int, file_path: Optional[Path] = None) -> None:
    """将最终端口号写入持久化文件，供 Electron 主进程读取。

    Args:
        port: 最终确定的端口号
        file_path: 端口文件路径（默认 backend/.mfkagent_port）
    """
    path = file_path or PORT_FILE
    path.write_text(str(port), encoding="utf-8")
    logger.info("Phase9 port: 端口 %d 已写入 %s", port, path)


def read_port_file(file_path: Optional[Path] = None) -> Optional[int]:
    """从持久化文件读取端口号。

    Returns:
        int | None: 端口号，文件不存在或格式错误时返回 None
    """
    path = file_path or PORT_FILE
    try:
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8").strip()
        return int(content)
    except (ValueError, OSError):
        return None


def clear_port_file(file_path: Optional[Path] = None) -> None:
    """清理端口文件（服务正常关闭时调用）。"""
    path = file_path or PORT_FILE
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass