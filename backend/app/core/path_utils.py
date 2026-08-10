"""Phase 9 P1: Windows 长路径兼容与 Junction 过滤。

在 Windows 环境下，默认路径上限为 260 字符（MAX_PATH），深层嵌套目录极易触发
FileNotFoundError / OSError。本模块提供跨平台安全的长路径包装：

  - ensure_long_path(path): 在 Windows 上为绝对路径挂载 \\\\?\\ 前缀，突破 260 字符限制
  - is_junction(path): 检测 Windows NTFS Junction / 目录符号链接
  - safe_resolve(path): 解析路径但不穿透 Junction（避免循环遍历）
  - safe_scandir(path): 安全的目录遍历，自动跳过 Junction

Mac / Linux 下所有函数透明传递，不做任何转换。
"""

import os
import sys
import stat
import logging
import ctypes
from pathlib import Path
from typing import Iterator, Optional, Union

logger = logging.getLogger(__name__)

# ── 平台检测 ──
IS_WINDOWS = sys.platform == "win32"

# \\?\ 前缀：Windows 内核路径命名空间，绕过 Win32 路径规范化（含 260 字符限制）
# 注意：仅适用于绝对路径，相对路径不能加此前缀
_LONG_PATH_PREFIX = "\\\\?\\"

# UNC 长路径前缀
_LONG_UNC_PREFIX = "\\\\?\\UNC\\"


def is_windows() -> bool:
    """跨平台安全：返回当前是否在 Windows 环境。"""
    return IS_WINDOWS


# ──────────────────────────────────────────────────────────────────────────
# 长路径前缀
# ──────────────────────────────────────────────────────────────────────────

def ensure_long_path(path: Union[str, Path]) -> str:
    """在 Windows 上为绝对路径添加 \\\\?\\ 前缀，突破 260 字符路径长度限制。

    - 已是 \\\\?\\ 前缀的路径不重复添加
    - UNC 路径（\\\\server\\share）转换为 \\\\?\\UNC\\server\\share
    - 相对路径不添加前缀（原样返回）
    - Mac / Linux 下原样返回，不做任何转换

    Args:
        path: 文件或目录路径

    Returns:
        str: 可能带 \\\\?\\ 前缀的路径字符串（Windows），或原始路径（非 Windows）
    """
    if not IS_WINDOWS:
        return str(path)

    path_str = str(path)

    # 已有长路径前缀，不重复添加
    if path_str.startswith(_LONG_PATH_PREFIX):
        return path_str

    # 转为绝对路径
    abs_path = os.path.abspath(path_str)

    # UNC 路径
    if abs_path.startswith("\\\\"):
        # \\server\share\... → \\?\UNC\server\share\...
        return _LONG_UNC_PREFIX + abs_path[2:]

    # 盘符路径：C:\... → \\?\C:\...
    return _LONG_PATH_PREFIX + abs_path


def strip_long_path(path: Union[str, Path]) -> str:
    """移除 \\\\?\\ 前缀，恢复为可读的普通路径。

    Args:
        path: 可能带 \\\\?\\ 前缀的路径

    Returns:
        str: 普通格式路径
    """
    path_str = str(path)
    if path_str.startswith(_LONG_UNC_PREFIX):
        return "\\\\" + path_str[len(_LONG_UNC_PREFIX):]
    if path_str.startswith(_LONG_PATH_PREFIX):
        return path_str[len(_LONG_PATH_PREFIX):]
    return path_str


# ──────────────────────────────────────────────────────────────────────────
# Junction / 符号链接 检测
# ──────────────────────────────────────────────────────────────────────────

# Windows 文件属性常量
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003
_IO_REPARSE_TAG_SYMLINK = 0xA000000C

# 缓存 ctypes 调用（避免重复加载 kernel32.dll）
_kernel32 = None


def _get_kernel32():
    """延迟加载 kernel32.dll（非 Windows 环境不需要）。"""
    global _kernel32
    if _kernel32 is None and IS_WINDOWS:
        _kernel32 = ctypes.windll.kernel32
    return _kernel32


def _get_reparse_tag(path: str) -> int:
    """通过 Win32 API 获取重解析点标签（Reparse Tag）。

    仅 Windows 调用，非 Windows 返回 0。
    """
    if not IS_WINDOWS:
        return 0

    kernel32 = _get_kernel32()
    if kernel32 is None:
        return 0

    long_path = ensure_long_path(path)
    # FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS
    handle = kernel32.CreateFileW(
        long_path,
        0,  # dwDesiredAccess = 0（仅查询属性）
        0x00000001,  # FILE_SHARE_READ
        None,  # lpSecurityAttributes
        3,  # OPEN_EXISTING
        0x02000000 | 0x00200000,  # FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS
        None,  # hTemplateFile
    )

    if handle == -1:  # INVALID_HANDLE_VALUE
        return 0

    try:
        # 分配足够大的缓冲区（MAXIMUM_REPARSE_DATA_BUFFER_SIZE = 16KB）
        buf_size = 16384
        buf = (ctypes.c_byte * buf_size)()
        returned = ctypes.c_ulong(0)

        success = kernel32.DeviceIoControl(
            handle,
            0x000900A8,  # FSCTL_GET_REPARSE_POINT
            None, 0,
            buf, buf_size,
            ctypes.byref(returned),
            None,
        )

        if not success:
            return 0

        # ReparseTag 在缓冲区的前 4 字节（DWORD）
        tag = ctypes.c_uint.from_buffer(buf, 0).value
        return tag
    finally:
        kernel32.CloseHandle(handle)


def is_junction(path: Union[str, Path]) -> bool:
    """检测路径是否为 Windows NTFS Junction（目录挂载点）或目录符号链接。

    - Windows: 通过 Win32 API 获取 Reparse Tag 判断
    - Mac / Linux: 通过 os.path.islink() 判断
    - 仅对 目录 生效；文件符号链接在 Windows 上极罕见，暂不处理

    Args:
        path: 文件系统路径

    Returns:
        bool: 是否为 Junction / 目录符号链接
    """
    path_str = str(path)

    if not os.path.isdir(path_str):
        return False

    if IS_WINDOWS:
        # 首先检查是否为重解析点（快速路径）
        try:
            attrs = os.stat(path_str).st_file_attributes
            if not (attrs & _FILE_ATTRIBUTE_REPARSE_POINT):
                return False
        except (AttributeError, OSError):
            return False

        # 获取 Reparse Tag 精确判断
        tag = _get_reparse_tag(path_str)
        return tag in (_IO_REPARSE_TAG_MOUNT_POINT, _IO_REPARSE_TAG_SYMLINK)
    else:
        return os.path.islink(path_str)


def safe_resolve(path: Union[str, Path], strict: bool = False) -> Path:
    """解析路径为绝对路径，但在 Windows 上不穿透 Junction。

    标准 Path.resolve() 在 Windows 上会穿透 Junction（如 AppData 目录链接），
    导致解析结果指向真实路径（可能超出预期目录范围）。

    本函数：
    - 使用 os.path.realpath() 做基础规范化（解析 .. 和 .）
    - 在 Windows 上检测到路径在 Junction 下时，不继续穿透
    - strict=True 时，在 Junction 下抛出 ValueError

    Args:
        path: 文件系统路径
        strict: 是否严格模式（Junction 路径抛异常）

    Returns:
        Path: 规范化后的绝对路径
    """
    path_obj = Path(path)
    if not path_obj.is_absolute():
        raise ValueError(f"safe_resolve 需要绝对路径，收到: {path}")

    path_str = str(path_obj)

    # 逐级检测是否经过 Junction
    if IS_WINDOWS:
        parts = path_obj.parts
        # 逐级向上检测（从盘符根开始）
        for i in range(2, len(parts) + 1):
            current = str(Path(*parts[:i]))
            if is_junction(current):
                if strict:
                    raise ValueError(
                        f"路径经过 Junction，严格模式下拒绝: {current}"
                    )
                logger.debug(
                    "Phase9 path: 检测到 Junction，停止解析: %s", current
                )
                # 返回 Junction 路径 + 剩余部分（不做 resolve 穿透）
                remaining = Path(*parts[i:]) if i < len(parts) else Path(".")
                return Path(current) / remaining

    # 非 Windows 或无 Junction：标准 realpath
    return Path(os.path.realpath(path_str))


def safe_scandir(path: Union[str, Path]) -> Iterator[os.DirEntry]:
    """安全的目录遍历：自动跳过 Junction / 符号链接目录。

    用法：
        for entry in safe_scandir("/some/path"):
            print(entry.name)

    Args:
        path: 目录路径

    Yields:
        os.DirEntry: 非 Junction 的目录条目
    """
    path_str = str(path)
    try:
        for entry in os.scandir(path_str):
            if entry.is_dir(follow_symlinks=False) and is_junction(entry.path):
                logger.debug(
                    "Phase9 path: 跳过 Junction 目录: %s", entry.name
                )
                continue
            yield entry
    except OSError as e:
        logger.warning("Phase9 path: scandir 失败 %s: %s", path_str, e)
        return


# ──────────────────────────────────────────────────────────────────────────
# 便捷函数：安全打开文件（自动挂载长路径前缀）
# ──────────────────────────────────────────────────────────────────────────

def safe_open(
    path: Union[str, Path],
    mode: str = "r",
    encoding: str = "utf-8",
    **kwargs,
):
    """跨平台安全的 open() 包装，Windows 上自动挂载长路径前缀。

    用法与内置 open() 完全一致。
    """
    if IS_WINDOWS:
        return open(ensure_long_path(path), mode, encoding=encoding, **kwargs)
    return open(str(path), mode, encoding=encoding, **kwargs)


def safe_os_makedirs(path: Union[str, Path], exist_ok: bool = True) -> None:
    """跨平台安全的 os.makedirs() 包装。

    Windows 上自动挂载长路径前缀。
    """
    if IS_WINDOWS:
        os.makedirs(ensure_long_path(path), exist_ok=exist_ok)
    else:
        os.makedirs(str(path), exist_ok=exist_ok)


def safe_os_path_exists(path: Union[str, Path]) -> bool:
    """跨平台安全的 os.path.exists() 包装。"""
    if IS_WINDOWS:
        return os.path.exists(ensure_long_path(path))
    return os.path.exists(str(path))