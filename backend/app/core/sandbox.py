"""统一路径沙箱与子进程执行封装（Phase 8 P0 + Phase 9 P1 长路径兼容 + Phase 4 T1 增强）。

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
  4. Phase 4 T1: 禁执行目录黑名单 + 磁盘配额检查
     - is_forbidden_cwd(): 检测路径是否落在 Windows 系统目录/Program Files/用户根目录等
     - check_disk_quota(): 检查目标磁盘剩余空间是否满足操作阈值

所有本地文件读写 / 目录列举 / 命令执行工具都必须经由本模块，禁止自行拼路径。
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Phase 9 P1: 长路径与 Junction 过滤
from app.core.path_utils import safe_resolve as _safe_resolve, ensure_long_path, IS_WINDOWS

# Windows Node.js 常见安装目录（run_subprocess 里用于补齐 PATH，让 Agent 能执行 npm/tsc）。
# 仅追加已存在且 PATH 未包含的目录；纯本机路径，随环境可增补。
_NODEJS_BIN_DIRS: List[str] = [
    r"E:\Program Files\nodejs",
    r"C:\Program Files\nodejs",
    os.path.expandvars(r"%ProgramFiles%\nodejs"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\nodejs"),
]


class SandboxViolation(PermissionError):
    """路径越权异常：既是 PermissionError（明确的越权语义），也便于上层精确捕获。"""


# ──── Phase 4 T1: 禁执行目录黑名单 ────
# 与 resolve_sandbox_path() 叠加：先做项目根沙箱校验 → 再做黑名单兜底
# 双保险：即使项目根被错误配置，禁执行目录也绝对不能落入命令 cwd


def _build_forbidden_dirs() -> List[str]:
    """动态构建禁执行目录列表（基于当前系统 + 环境变量）。

    包含：
      - Windows 系统目录（C:\\Windows, C:\\Windows\\System32, C:\\Windows\\SysWOW64）
      - Program Files（C:\\Program Files, C:\\Program Files (x86)）
      - ProgramData（C:\\ProgramData）
      - 用户根目录直接子目录外（USERPROFILE\\Documents 等用户文档目录）
      - 当前盘符根目录（C:\\, D:\\ 等）
    """
    dirs: List[str] = []

    if IS_WINDOWS:
        # 1. Windows 系统目录
        win_dir = os.environ.get("WINDIR") or os.environ.get("SystemRoot") or r"C:\Windows"
        dirs.append(win_dir)
        dirs.append(os.path.join(win_dir, "System32"))
        dirs.append(os.path.join(win_dir, "SysWOW64"))
        dirs.append(os.path.join(win_dir, "System"))

        # 2. Program Files / Program Files (x86)
        pf = os.environ.get("ProgramFiles") or r"C:\Program Files"
        dirs.append(pf)
        pf86 = os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)"
        dirs.append(pf86)
        dirs.append(os.path.join(pf, "WindowsApps"))
        dirs.append(os.path.join(pf86, "WindowsApps"))

        # 3. ProgramData
        dirs.append(r"C:\ProgramData")

        # 4. 当前盘符根目录（任意盘符如 C:\, D:\, E:\）
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            root = f"{letter}:\\"
            if os.path.exists(root):
                dirs.append(root)
    else:
        # 非 Windows 系统：兜底禁执行目录
        dirs.extend(["/etc", "/usr", "/bin", "/sbin", "/var", "/boot", "/root"])

    return dirs


# 启动时构建一次（环境变量不变的话无需重复构建）
_FORBIDDEN_DIRS: List[str] = _build_forbidden_dirs()


def _normalize_for_comparison(path: str) -> str:
    """规范化路径用于比较：绝对路径 + 统一分隔符 + 去除末尾分隔符 + 小写（Windows）。"""
    p = os.path.abspath(path)
    p = p.rstrip(os.sep)
    if IS_WINDOWS:
        p = p.lower()
    return p


# 盘符根目录（只允许精确匹配，不作为前缀匹配，避免误判 C:\Users）
# 注意：与 _FORBIDDEN_DIRS 一样保存为用户传入的大小写，匹配时单独归一化
_DRIVE_ROOT_DIRS: List[str] = [
    f"{letter}:\\" for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{letter}:\\")
] if IS_WINDOWS else []
_DRIVE_ROOT_DIRS_NORMALIZED: set = {_normalize_for_comparison(p) for p in _DRIVE_ROOT_DIRS}


def is_forbidden_cwd(work_dir: str) -> Tuple[bool, str]:
    """检测工作目录是否落在禁执行目录黑名单内。

    Args:
        work_dir: 待检查的工作目录绝对路径

    Returns:
        (is_forbidden, reason) — is_forbidden=True 时 reason 为人类可读的原因
    """
    if not work_dir:
        return False, ""

    normalized = _normalize_for_comparison(work_dir)

    for forbidden in _FORBIDDEN_DIRS:
        forbidden_norm = _normalize_for_comparison(forbidden)
        # 盘符根目录仅精确匹配（前缀匹配会误判 C:\Users\xxx 为 C:\ 子路径）
        if forbidden_norm in _DRIVE_ROOT_DIRS_NORMALIZED:
            if normalized == forbidden_norm:
                return True, f"工作目录命中禁执行目录: {forbidden}"
            continue
        # 其他黑名单目录：精确匹配 或 子目录匹配
        if normalized == forbidden_norm:
            return True, f"工作目录命中禁执行目录: {forbidden}"
        if normalized.startswith(forbidden_norm + os.sep):
            return True, f"工作目录位于禁执行子目录: {forbidden}"

    return False, ""


# ──── Phase 4 T1: 磁盘配额检查 ────

# 各高风险操作最低剩余空间阈值（字节）
# 阈值依据：
#   - git clone: 大型仓库（chromium / tensorflow）常达 1-2GB，预留缓冲到 2GB
#   - npm install: 完整前端项目依赖常达 500MB-1GB，预留 5GB（含 dev 依赖 + cache）
#   - pip install: 单项目依赖 <500MB，预留 1GB
DISK_QUOTA_BYTES = {
    "git_clone": 2 * 1024 * 1024 * 1024,      # 2 GB
    "npm_install": 5 * 1024 * 1024 * 1024,    # 5 GB
    "pip_install": 1 * 1024 * 1024 * 1024,    # 1 GB
}


def check_disk_quota(target_path: str, required_bytes: int) -> Tuple[bool, str]:
    """检查目标路径所在磁盘的剩余空间是否满足要求。

    Args:
        target_path: 目标路径（其所在磁盘的剩余空间将被检查）
        required_bytes: 所需最低剩余字节数

    Returns:
        (ok, message) — ok=True 表示通过；ok=False 时 message 为人类可读原因
    """
    if required_bytes <= 0:
        return True, ""

    try:
        target = _safe_resolve(target_path)
        usage = shutil.disk_usage(target)
    except Exception as e:
        return False, f"无法获取磁盘空间信息: {e}"

    free = usage.free
    if free < required_bytes:
        free_gb = free / (1024 ** 3)
        req_gb = required_bytes / (1024 ** 3)
        return False, (
            f"磁盘空间不足：剩余 {free_gb:.2f} GB，需要至少 {req_gb:.2f} GB。"
            f"请清理磁盘或选择其他目录。"
        )

    return True, f"磁盘空间充足（剩余 {free / (1024 ** 3):.2f} GB）"


def detect_high_risk_disk_op(command: str) -> Optional[str]:
    """检测命令是否属于需要磁盘配额检查的高风险操作。

    Returns:
        None: 非高风险磁盘操作
        "git_clone" / "npm_install" / "pip_install": 命中对应类别
    """
    if not command:
        return None
    cmd = command.strip()
    cmd_lower = cmd.lower()

    # git clone（含 git clone https://...）
    if cmd_lower.startswith("git ") and "clone " in cmd_lower:
        return "git_clone"

    # npm install（含 npm i / npm install / npm ci / yarn install / pnpm install）
    if any(p in cmd_lower for p in ("npm install", "npm i ", "npm i\n", "npm ci", "yarn install", "yarn add", "pnpm install", "pnpm add")):
        return "npm_install"

    # pip install（含 pip3 / python -m pip / pip install / pip install -r requirements.txt）
    if any(p in cmd_lower for p in ("pip install", "pip3 install", "-m pip install", "-m pip3 install")):
        return "pip_install"

    return None



def resolve_sandbox_path(
    target_path: str,
    project_root: Optional[str] = None,
    allow_outside: bool = False,
) -> Path:
    """解析并校验路径，防止 Path Traversal 路径穿越。

    Phase 9: 使用 safe_resolve() 替代 Path.resolve()，避免穿透 Windows Junction
    导致路径解析到项目目录之外。

    - 支持 ~ 路径展开与 %USERPROFILE% 等环境变量自动展开
    - 只读模式 (allow_outside=True)：
      - 允许访问项目之外的绝对路径（如用户主目录配置 %USERPROFILE%/.config/opencode/opencode.json）
      - 只要不命中系统级危险保护目录（is_forbidden_cwd 目录）即允许只读
    - 写入模式 (allow_outside=False)：
      - 严格要求在 project_root 沙箱边界内，严禁越界修改

    Args:
        target_path: 目标路径（支持相对路径或绝对路径，如 src/app.py / C:\\proj\\x / ~/.config/x）
        project_root: 项目根目录绝对路径（沙箱边界，可选）。
        allow_outside: 是否允许跨目录只读访问（只读工具传 True，写工具传 False）。

    Returns:
        Path: 规范化后的真实路径

    Raises:
        SandboxViolation(PermissionError): 真实路径越权
    """
    # 自动展开 ~ 用户主目录与 Windows/Linux 环境变量（如 %USERPROFILE%）
    expanded = os.path.expanduser(os.path.expandvars(target_path.strip()))

    if not project_root:
        if Path(expanded).is_absolute():
            target = _safe_resolve(expanded)
        else:
            target = _safe_resolve(Path.cwd() / expanded)
        forbidden, reason = is_forbidden_cwd(str(target))
        if forbidden:
            raise SandboxViolation(f"【安全拦截】禁止访问系统受保护目录: {target_path} ({reason})")
        return target

    # project_root 统一归一为绝对路径
    root = _safe_resolve(os.path.abspath(project_root))
    is_abs = Path(expanded).is_absolute()
    if is_abs:
        target = _safe_resolve(expanded)
    else:
        target = _safe_resolve(root / expanded)

    # 如果允许外部只读（如读取系统配置、全局配置）且传入的是绝对路径：
    if allow_outside and is_abs:
        forbidden, reason = is_forbidden_cwd(str(target))
        if forbidden:
            raise SandboxViolation(f"【安全拦截】禁止访问系统受保护目录: {target_path} ({reason})")
        return target

    if not (target == root or target.is_relative_to(root)):
        if allow_outside and is_abs:
            return target
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
    # Windows：补齐 Node.js 可执行目录到 PATH（后端进程若由 start.bat/cmd 启动，
    # 可能缺少用户级 nodejs 目录，导致 Agent 执行 npm/tsc 时报"找不到命令"）。
    # 仅追加存在且 PATH 中未包含的目录；npm.cmd 依赖 PATHEXT 解析（.ps1 无法被 subprocess 调用）。
    if os.name == "nt":
        _paths = run_env.get("PATH", "").split(os.pathsep)
        _has = {p.strip().lower().rstrip("\\") for p in _paths if p.strip()}
        for _node_dir in _NODEJS_BIN_DIRS:
            if os.path.isdir(_node_dir):
                _key = _node_dir.strip().lower().rstrip("\\")
                if _key not in _has:
                    _paths.append(_node_dir)
                    _has.add(_key)
        run_env["PATH"] = os.pathsep.join(_paths)

    # Windows: subprocess(shell=False) 不会自动按 PATHEXT 解析 .cmd/.bat（如 npm->npm.cmd）。
    # 用 shutil.which（按 run_env PATH + PATHEXT）把无扩展名命令解析为真实可执行文件路径。
    if os.name == "nt" and argv and not os.path.splitext(argv[0])[1]:
        _resolved = shutil.which(argv[0], path=run_env.get("PATH", ""))
        if _resolved:
            argv = [_resolved] + list(argv[1:])

    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=False,
        timeout=timeout,
        env=run_env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
