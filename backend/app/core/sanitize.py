"""Phase 9 P1: 文件名与路径非法字符过滤。

Windows 文件名中禁止出现以下字符：< > : " / \\ | ? *
此外，还有一些额外的命名限制（如不能以空格/点结尾、不能是保留名等）。

本模块提供：
  - sanitize_filename(name): 清理单个文件名/目录名
  - sanitize_path(path): 逐级清理完整路径的每个组件
  - is_valid_filename(name): 检查文件名是否合法

跨平台安全：Mac / Linux 下仅做基本的空字符过滤，不做过度清理。
"""

import os
import re
import sys
import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"

# Windows 文件名/目录名非法字符（不含路径分隔符，分隔符由逐级清理处理）
_WINDOWS_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*]')

# Windows 控制字符（0x00-0x1F，不含 0x00 已在前面处理）
_WINDOWS_CONTROL_CHARS = re.compile(r'[\x01-\x1F]')

# Windows 保留文件名（不区分大小写）
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# 替换字符：非法字符的统一替换
_REPLACEMENT_CHAR = "_"


def sanitize_filename(name: str, replacement: str = _REPLACEMENT_CHAR) -> str:
    """清理单个文件名或目录名，移除 Windows 非法字符。

    处理规则：
      1. 移除首尾空白
      2. 替换 Windows 非法字符 < > : " / \\ | ? *
      3. 替换控制字符（0x01-0x1F）
      4. 移除首尾空格和点（Windows 不允许）
      5. 若为 Windows 保留名（如 CON、NUL），追加下划线
      6. 若结果为空，返回 "untitled"

    Mac / Linux 下仅做基本清理（移除空字符，首尾空白裁剪）。

    Args:
        name: 原始文件名或目录名
        replacement: 非法字符的替换字符（默认 "_"）

    Returns:
        str: 清理后的文件名
    """
    if not name:
        return "untitled"

    # 去除首尾空白
    name = name.strip()

    if not name:
        return "untitled"

    if IS_WINDOWS:
        # 替换非法字符
        name = _WINDOWS_ILLEGAL_CHARS.sub(replacement, name)
        # 替换控制字符
        name = _WINDOWS_CONTROL_CHARS.sub(replacement, name)
        # 去除首尾空格和点（Windows 不允许以空格或点结尾）
        name = name.strip(" .")
        # 压缩连续替换字符
        name = re.sub(rf'{re.escape(replacement)}+', replacement, name)

        if not name:
            return "untitled"

        # 检查是否为保留名
        name_upper = name.upper()
        # 去除扩展名后检查（如 "CON.txt" 中 "CON" 是保留名）
        base = name_upper.split(".")[0]
        if base in _WINDOWS_RESERVED_NAMES:
            name = f"_{name}"

    else:
        # Mac / Linux：仅移除空字符，裁剪首尾空白
        name = name.replace("\x00", replacement)
        name = name.strip()

        if not name:
            return "untitled"

    return name


def sanitize_path(path: Union[str, Path], replacement: str = _REPLACEMENT_CHAR) -> str:
    """逐级清理完整路径的每个组件。

    将路径按分隔符拆分，对每个组件调用 sanitize_filename，
    然后重新拼接。盘符（Windows）和根路径保留不变。

    Args:
        path: 完整文件路径
        replacement: 非法字符替换字符

    Returns:
        str: 清理后的路径
    """
    path_str = str(path)

    # 分离盘符/根路径
    drive = ""
    if IS_WINDOWS and len(path_str) >= 2 and path_str[1] == ":":
        drive = path_str[:2]
        path_str = path_str[2:]
    elif path_str.startswith("\\\\"):
        # UNC 路径：保留 \\server\share 前缀
        parts = path_str.split("\\", 4)
        if len(parts) >= 4:
            drive = "\\\\" + "\\".join(parts[1:3])
            path_str = "\\" + "\\".join(parts[3:])
    elif path_str.startswith("/"):
        drive = "/"

    # 使用 os.sep 拆分组件（而不是硬编码 \\）
    components = []
    for part in path_str.replace("\\", os.sep).replace("/", os.sep).split(os.sep):
        part = part.strip()
        if not part:
            continue
        components.append(sanitize_filename(part, replacement))

    # 重新拼接
    if drive:
        return drive + os.sep.join(components)
    return os.sep.join(components)


def is_valid_filename(name: str) -> bool:
    """检查文件名是否在 Windows 上合法。

    Args:
        name: 文件名（不含路径）

    Returns:
        bool: 是否合法
    """
    if not name or not name.strip():
        return False

    if IS_WINDOWS:
        # 检查非法字符
        if _WINDOWS_ILLEGAL_CHARS.search(name):
            return False
        # 检查控制字符
        if _WINDOWS_CONTROL_CHARS.search(name):
            return False
        # 检查首尾空格/点
        if name != name.strip(" ."):
            return False
        # 检查保留名
        base = name.upper().split(".")[0]
        if base in _WINDOWS_RESERVED_NAMES:
            return False

    return True