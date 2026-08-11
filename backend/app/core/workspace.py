"""默认工作目录 (Default Workspace) — 未绑定项目时的自动兜底机制。

当 Chat 未关联项目路径，但用户指令包含文件操作（新建文件夹 / 保存文件 / 写代码）时，
后端不再将 project_path 置为 None，而是自动指向系统默认数据目录：
    ~/MfkAgentWorkspaces/default_project    (Windows: C:\\Users\\<用户名>\\MfkAgentWorkspaces\\...)
并将该路径注入 Agent 上下文，让 Agent 主动汇报实际落盘位置。

V3 增强（2026-08-11）：路径感知 — 未绑定项目时若用户消息中直接给出绝对路径
（如 `e:\\project\\chat.py 帮我修改一下`），优先以该路径作为本次会话工作目录，
而非固定兜底到默认目录。
"""

import os
import re
from pathlib import Path
from typing import List, Optional

DEFAULT_WORKSPACE_ROOT = "MfkAgentWorkspaces"
DEFAULT_PROJECT_NAME = "default_project"

# 文件操作触发词：命中任一即启用默认工作目录兜底
# 2026-08-11 扩展：对齐 _is_casual_chat._ACTION_TRIGGERS 的操作类语义
# （修改/修复/删除/查看/读取/打开/分析），避免"帮我改一下文件"这类指令被漏判
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
    r"修改.*(文件|代码|脚本)",
    r"改一下",
    r"改下",
    r"修复.*(文件|代码|bug|问题)",
    r"删除.*(文件|目录)",
    r"查看.*(文件|目录|代码)",
    r"看一下.*(文件|目录|代码)",
    r"看下.*(文件|目录|代码)",
    r"读取.*(文件|目录)",
    r"打开.*(文件|目录)",
    r"分析.*(文件|代码|目录)",
]

# ── 路径提取（2026-08-11）：未绑定项目时，从用户消息中识别绝对路径 ──
# 引号/反引号包裹的路径最可信，优先提取；其余按格式匹配候选。
_PATH_QUOTED_RE = re.compile(r"[`\"']((?:[A-Za-z]:[\\/]|\\\\|/)[^`\"'\r\n]+)[`\"']")
# Windows 盘符路径：C:\\... / C:/...（允许中文与空格，排除中文标点/引号/控制符）
_PATH_WINDOWS_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]:[\\/][^\s，。；、：\"'`<>|?*\r\n]+)")
# UNC 路径：\\\\server\\share\\...
_PATH_UNC_RE = re.compile(r"(?<![\\/])(\\\\[^\s，。；、：\"'`<>|?*\r\n]+)")
# POSIX 绝对路径（保守：仅字母数字 / _ . -，避免误吞句子）
_PATH_POSIX_RE = re.compile(r"(?<![A-Za-z0-9])(/[A-Za-z0-9_./-]{2,})")


def extract_path_candidates(message: str) -> List[str]:
    """从用户消息中提取绝对路径候选（按可信度排序）。

    优先级：引号/反引号包裹路径 > Windows 盘符路径 > UNC > POSIX。
    仅做格式提取，不校验存在性（由 extract_workspace_path 完成）。
    """
    if not message:
        return []
    candidates: List[str] = []
    seen = set()
    for m in _PATH_QUOTED_RE.finditer(message):
        p = m.group(1).strip().rstrip(".,;:，。；、")
        if p and p not in seen:
            candidates.append(p)
            seen.add(p)
    for m in _PATH_WINDOWS_RE.finditer(message):
        p = m.group(1).rstrip(".,;:，。；、")
        if p and p not in seen:
            candidates.append(p)
            seen.add(p)
    for m in _PATH_UNC_RE.finditer(message):
        p = m.group(1).rstrip(".,;:，。；、")
        if p and p not in seen:
            candidates.append(p)
            seen.add(p)
    for m in _PATH_POSIX_RE.finditer(message):
        p = m.group(1)
        if p not in seen:
            candidates.append(p)
            seen.add(p)
    return candidates


def extract_workspace_path(message: str) -> Optional[str]:
    """从消息中解析可用的工作目录绝对路径。

    规则：
      - 依次取候选中的第一个「已存在」路径；
      - 路径为文件 → 取其父目录作为工作目录；
      - 目录 → 直接使用；
      - 无候选或均不存在 → 返回 None（由调用方回退默认目录）。
    """
    for candidate in extract_path_candidates(message):
        candidate = candidate.strip()
        if os.path.isfile(candidate):
            return os.path.dirname(candidate)
        if os.path.isdir(candidate):
            return candidate
    return None


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


def get_user_path_workspace_context(path: str) -> str:
    """构造用户指定路径的工作目录上下文文本（2026-08-11 新增）。

    未绑定项目但用户消息中直接给出绝对路径时，以该路径（或其父目录）作为
    本次会话工作目录，并明确告知 Agent 操作边界。
    """
    return (
        "## 当前工作目录（用户指定路径）\n"
        "当前会话未绑定项目，已按你提供的路径作为本次操作的工作目录：\n"
        f"`{path}`\n"
        "请在此目录范围内执行文件操作（读取/修改/搜索），不要越出该目录；"
        "若用户给出的是具体文件路径，优先操作该文件。"
    )
