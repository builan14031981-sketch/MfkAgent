"""日志统一配置：按天轮转文件 + 终端输出，所有模块 logger 自动写入。"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler

from app.core.config import DATA_DIR

LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"

# 日志格式：时间 | 级别 | 文件:行号 | 消息
_FORMAT = "%(asctime)s | %(levelname)s | %(pathname)s:%(lineno)d | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def init_logging() -> None:
    """初始化日志系统。在 main.py 最早期调用，幂等。"""
    if _is_initialized():
        return

    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FMT)

    # 文件处理器：每天午夜轮转，保留 30 天
    file_handler = TimedRotatingFileHandler(
        LOG_FILE, when="midnight", interval=1, backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # 终端处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # 配置根 logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    logging.getLogger(__name__).info("Logging initialized: %s", LOG_FILE)


def _is_initialized() -> bool:
    """检查是否已初始化（避免重复添加 handler）。"""
    root = logging.getLogger()
    return any(
        isinstance(h, TimedRotatingFileHandler) and h.baseFilename == str(LOG_FILE)
        for h in root.handlers
    )


def read_log_file(
    file_path: str,
    level: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    """读取日志文件，支持按级别/关键词筛选 + 分页。"""
    if not os.path.isfile(file_path):
        return {"total": 0, "page": page, "page_size": page_size, "lines": []}

    level_upper = level.upper() if level else None
    all_lines: list[dict] = []

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n\r")
            if not line:
                continue

            # 解析日志行：跳过格式不匹配的行
            if " | " not in line:
                continue

            parts = line.split(" | ", 2)
            if len(parts) < 3:
                continue

            timestamp = parts[0]
            log_level = parts[1]
            message = parts[2] if len(parts) > 2 else ""

            # 级别筛选
            if level_upper and log_level != level_upper:
                continue

            # 关键词筛选
            if search and search.lower() not in line.lower():
                continue

            all_lines.append({
                "timestamp": timestamp,
                "level": log_level,
                "message": message,
                "raw": line,
            })

    # 倒序（最新在前）
    all_lines.reverse()

    total = len(all_lines)
    start = (page - 1) * page_size
    end = start + page_size
    page_lines = all_lines[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "lines": page_lines,
    }