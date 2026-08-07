"""默认工作目录 (Default Workspace) — 未绑定项目时的自动兜底机制。

当 Chat 未关联项目路径，但用户指令包含文件操作（新建文件夹 / 保存文件 / 写代码）时，
后端不再将 project_path 置为 None，而是自动指向系统默认数据目录：
    ~/MfkAgentWorkspaces/default_project    (Windows: C:\\Users\\<用户名>\\MfkAgentWorkspaces\\...)
并将该路径注入 Agent 上下文，让 Agent 主动汇报实际落盘位置。
"""

import os
import re
from pathlib import Path

DEFAULT_WORKSPACE_ROOT = "MfkAgentWorkspaces"
DEFAULT_PROJECT_NAME = "default_project"

# 文件操作触发词：命中任一即启用默认工作目录兜底
_FILE_OP_PATTERNS = [
    r"新建.*(文件夹|目录|文件)",
    r"创建.*(文件夹|目录|文件)",
    r"建一个.*(文件夹|目录|文件)",
    r"新建文件夹",
    r"保存.*(文件|文档)",
    r"写(个|一个)?.*(代码|脚本|文件|程序)",
    r"写.*(代码|脚本|文件)",
    r"写文件",
    r"保存文件",
    r"新建文件",
    r"创建一个",
    r"放.*东西",
    r"放.*文件",
]


def get_default_workspace_path() -> str:
    """返回默认工作目录绝对路径（不保证存在）。"""
    return str(Path.home() / DEFAULT_WORKSPACE_ROOT / DEFAULT_PROJECT_NAME)


def ensure_default_workspace() -> str:
    """确保默认工作目录存在并返回其绝对路径。"""
    path = get_default_workspace_path()
    os.makedirs(path, exist_ok=True)
    return path


def is_file_operation_request(message: str) -> bool:
    """判断用户指令是否包含文件操作语义（新建/保存/写代码/放文件等）。

    Args:
        message: 用户消息文本

    Returns:
        True 表示需要文件操作，可启用默认工作目录兜底
    """
    if not message:
        return False
    for pattern in _FILE_OP_PATTERNS:
        if re.search(pattern, message):
            return True
    return False


def get_default_workspace_context(path: str) -> str:
    """构造默认工作目录上下文文本（供 ⑤ 层注入，让 Agent 主动汇报落盘位置）。"""
    return (
        "## 当前工作目录（Default Workspace 兜底）\n"
        "当前会话未绑定项目路径，已自动启用软件默认数据目录作为本次文件操作的工作目录：\n"
        f"`{path}`\n"
        "请在此目录下执行文件操作，并在回答中明确告知用户实际创建/保存的文件位置。"
    )
