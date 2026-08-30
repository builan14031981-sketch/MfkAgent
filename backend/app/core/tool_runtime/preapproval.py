"""工单J · autonomous 会话预授权清单（Pre-Approval Policy Layer）

背景（实测复现）：
  autonomous 无人值守模式下，HIGH_RISK 命令仍走人工审批，300 秒无人批 → 超时失败。
  平台 agent 执行 `cd backend`、`git push`、`cd backend && python -m pytest` 全部卡死。

方案：
  为 autonomous 会话引入「预授权清单」——命中清单的命令模式自动放行，
  并标注 `auto_approved_by_policy`：
    - git add / commit / push / pull / status / log
    - python -m pytest / mypy / ruff
    - pip install（限项目内；拒绝 --user/--system/--prefix 等全局作用域）
    - cd <项目内相对目录>（支撑 `cd backend && ...` 组合链；拒绝越界/盘符根/..）
    - 组合命令（&&）逐段拆分，每一段都命中清单时整链放行

硬边界（永不预授权，仍走人工审批）：
    - rm / format / reg add 等破坏性动词
    - run_outside_command（沙箱外命令，由 executor 层直接排除）
    - 写盘符根 / 系统目录的操作（cd 逃逸、绝对盘符、UNC 等）
    - 段内出现注入类元字符（; | ` $ < > ( ) 及非 && 的 &）

设计约束：
    - 不修改 risk_engine 判定本体（HIGH_RISK / DENY 仍由 risk_engine 产出）；
      本模块只在 approval_policy 决策层做「命中清单 → 升为 EXECUTE」的旁路放行。
    - T5 approval_memory（90 天 3 批准免审）为独立第二条通路，本模块不触碰。
    - 开关 autonomous_preapproval_enabled 默认开；写 false 一键关闭 = 回旧行为。
"""
from __future__ import annotations

import os
import re
from typing import List, Optional

# ── settings 开关 ────────────────────────────────────────────────────────────
AUTONOMOUS_PREAPPROVAL_SETTING_KEY = "autonomous_preapproval_enabled"

_TRUTHY = ("1", "true", "yes", "on")

# ── 预授权清单 ────────────────────────────────────────────────────────────────
# git 子命令白名单
_PREAPPROVED_GIT_SUBCOMMANDS = frozenset({"add", "commit", "push", "pull", "status", "log"})

# python -m 模块白名单
_PREAPPROVED_PY_MODULES = frozenset({"pytest", "mypy", "ruff"})

# pip 操作白名单（仅 install 类；uninstall / remove 等不入清单）
_PREAPPROVED_PIP_ACTIONS = frozenset({"install", "i"})

# ── 硬边界 ────────────────────────────────────────────────────────────────────
# 破坏性动词：与 risk_engine._DESTRUCTIVE_PATTERNS 对齐并兜底（含 PowerShell 别名）
_HARD_BOUNDARY_VERBS = frozenset({
    "rm", "rmdir", "del", "erase", "format", "mkfs", "diskpart",
    "shutdown", "reboot", "taskkill",
    "remove-item", "format-volume", "clear-content", "wipe",
})

# reg 子命令黑名单（add/delete/import/copy/save 均改写系统注册表）
_HARD_BOUNDARY_REG_VERBS = frozenset({"add", "delete", "import", "copy", "save"})

# git 危险旗标：改写远端历史 / 强制推送 → 永不预授权
_GIT_FORBIDDEN_FLAGS = ("--force", "-f", "--force-with-lease", "--delete", "--mirror", "--hard")

# pip 全局/系统作用域旗标：违反「限项目内」
_PIP_GLOBAL_FLAGS = ("--user", "--system", "--global", "--prefix", "--break-system-packages")

# 段内禁止的注入类元字符（&& 已在 split 时去除；单个 & 也禁止）
_FORBIDDEN_SEGMENT_CHARS = re.compile(r"[&;|`$<>]|\(|\)")

# cd 逃逸判定统一收敛到 _cd_segment_safe（解析目标路径做严格校验，见下）。
# 早期仅用 _CD_ESCAPE_RE/_CD_ROOT_RE 匹配「cd 后紧跟盘符/..」，存在绕过：
#   - `cd /d C:\Windows\System32`（/d 旗标破坏「cd 后紧跟」形态）
#   - `cd sub\..\..\Windows`（.. 在路径中段，不在 cd 后紧跟位置）
#   - `cd "C:\Windows"`（引号包裹）
# 现已改为解析出 cd 目标后按 绝对盘符/UNC/根/..越界/越出项目根 判定。


def autonomous_preapproval_enabled() -> bool:
    """读取 autonomous_preapproval_enabled 开关（默认开）。

    写 `false` 一键关闭 = 回旧行为（autonomous 下 HIGH_RISK 仍强制人工审批）。
    读取失败时保守回退为开（默认开语义）。
    """
    try:
        from app.core.database import SessionLocal
        from app.models.agent import Setting

        db = SessionLocal()
        try:
            row = db.query(Setting).filter(Setting.key == AUTONOMOUS_PREAPPROVAL_SETTING_KEY).first()
        finally:
            db.close()
        if row is not None and row.value is not None:
            return str(row.value).strip().lower() in _TRUTHY
    except Exception:  # noqa: BLE001  DB 不可用（纯单元测试等）→ 默认开
        pass
    return True


# ── 命令解析 ──────────────────────────────────────────────────────────────────

def _parse_argv(command: str) -> List[str]:
    """引号感知拆分 argv（与 command_tools._split_command 一致，支持含空格参数）。"""
    args: List[str] = []
    buf: List[str] = []
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


def split_chain(command: str) -> List[str]:
    """引号感知拆分 `&&` 链。

    例：`a && b && "c && d"` → ["a", "b", "c && d"]（引号内的 && 不拆分）。
    """
    segments: List[str] = []
    buf: List[str] = []
    in_quote = False
    i, n = 0, len(command)
    while i < n:
        ch = command[i]
        if ch == '"':
            in_quote = not in_quote
            buf.append(ch)
            i += 1
        elif ch == "&" and i + 1 < n and command[i + 1] == "&" and not in_quote:
            segments.append("".join(buf).strip())
            buf = []
            i += 2
        else:
            buf.append(ch)
            i += 1
    if buf:
        segments.append("".join(buf).strip())
    return [s for s in segments if s]


# ── 分段判定 ──────────────────────────────────────────────────────────────────

def _git_segment_safe(argv: List[str]) -> Optional[str]:
    """git 段判定：子命令命中清单且无危险旗标 → 返回原因，否则 None。"""
    sub = argv[1].lower()
    if sub not in _PREAPPROVED_GIT_SUBCOMMANDS:
        return None
    rest = argv[2:]
    if sub == "push":
        for a in rest:
            low = a.lower()
            if low in _GIT_FORBIDDEN_FLAGS or low.startswith(":"):
                return None  # --force / --delete / origin :branch 删除远端 → 不预授权
    elif sub == "pull":
        for a in rest:
            if a.lower() in ("--force", "-f"):
                return None
    return f"git {sub}"


def _pip_install_allowed(args: List[str], project_path: Optional[str]) -> Optional[str]:
    """pip install 段判定（限项目内）：命中 → 返回原因，否则 None。

    - 必须绑定项目（project_path 非空）才预授权，否则视为全局安装不入清单；
    - 拒绝 --user/--system/--prefix 等全局作用域旗标；
    - --target <path> 目标目录必须在项目内。
    """
    if not project_path:
        return None
    if not args:
        return None
    action = args[0].lower()
    if action not in _PREAPPROVED_PIP_ACTIONS:
        return None
    lowered = [a.lower() for a in args]
    if any(flag in lowered for flag in _PIP_GLOBAL_FLAGS):
        return None
    for idx, a in enumerate(args):
        if a.lower() != "--target" or idx + 1 >= len(args):
            continue
        target = args[idx + 1].strip(" \"'")
        if not target:
            return None
        t = os.path.normpath(target)
        p = os.path.normpath(project_path)
        if not (t == p or t.startswith(p + os.sep) or t.startswith(p + "/")):
            return None
    return f"pip {action}"


def _cd_segment_safe(segment: str, argv: List[str], project_path: Optional[str]) -> Optional[str]:
    """cd 预授权：仅允许项目内相对目录（支撑 `cd backend && ...` 组合链）。

    拒绝（永不预授权）：
      - 绝对盘符 / 裸盘符：C:\\...、D:（写盘符根/系统目录硬边界）
      - UNC：\\\\server\\share
      - 根目录：/、\\
      - 路径中段 `..` 越界：`cd sub\\..\\..\\Windows`（归一化后越出项目根）
      - 越出项目根的任何目标
    支持 cmd.exe 的 `cd /d <path>` 旗标（目标本身仍按上述规则校验）。
    """
    target = argv[1]
    if target.lower() == "/d" and len(argv) >= 3:
        target = argv[2]
    target = target.strip("\"'")
    if not target:
        return None
    # 绝对盘符（含裸盘符 D:）与 UNC → 拒绝
    if re.match(r"^[A-Za-z]:([\\/]|$)", target):
        return None
    if target.startswith("\\\\") or target.startswith("//"):
        return None
    # 根目录 → 拒绝
    if target in ("/", "\\"):
        return None
    # 绑定项目：归一化后必须仍落在项目根内（拦下路径中段 .. 越界）
    if project_path:
        pp = os.path.normpath(project_path)
        joined = os.path.normpath(os.path.join(pp, target))
        if joined != pp and not joined.startswith(pp + os.sep):
            return None
    else:
        # 未绑定项目：至少拦下 `..` 越界形态
        norm = os.path.normpath(target)
        if norm == ".." or norm.startswith(".." + os.sep):
            return None
    return f"cd {target}"


def _segment_match_reason(segment: str, project_path: Optional[str]) -> Optional[str]:
    """单个命令段是否命中预授权清单：命中返回原因，否则 None。"""
    segment = segment.strip()
    if not segment:
        return None
    # 段内注入类元字符（& ; | ` $ < > 与括号）→ 不预授权
    if _FORBIDDEN_SEGMENT_CHARS.search(segment):
        return None
    argv = _parse_argv(segment)
    if not argv:
        return None
    cmd = argv[0].lower()

    # 硬边界：破坏性动词 → 永不预授权
    if cmd in _HARD_BOUNDARY_VERBS:
        return None
    if cmd == "reg" and len(argv) >= 2 and argv[1].lower() in _HARD_BOUNDARY_REG_VERBS:
        return None

    # git
    if cmd == "git":
        if len(argv) < 2:
            return None
        return _git_segment_safe(argv)

    # cd：仅允许项目内相对目录（拒绝绝对盘符 / UNC / .. 越界 / 根目录）
    if cmd == "cd":
        if len(argv) < 2:
            return None
        return _cd_segment_safe(segment, argv, project_path)

    # python / py
    if cmd in ("python", "python3", "py"):
        if len(argv) >= 3 and argv[1] == "-m":
            mod = argv[2].lower()
            if mod in _PREAPPROVED_PY_MODULES:
                return f"python -m {mod}"
            if mod == "pip":
                return _pip_install_allowed(argv[3:], project_path)
        return None

    # pip / pip3
    if cmd in ("pip", "pip3"):
        return _pip_install_allowed(argv[1:], project_path)

    # 裸 pytest（本就 ALLOW，兜底进清单）
    if cmd == "pytest":
        return "pytest"

    return None


def command_matches_preapproval(
    command: str,
    project_path: Optional[str] = None,
) -> Optional[str]:
    """判断命令（或其 `&&` 链）是否命中预授权清单。

    Args:
        command: 完整命令文本
        project_path: 项目根（pip install 限项目内判定用）

    Returns:
        命中返回人类可读原因（供标注 auto_approved_by_policy），否则 None。
    """
    command = (command or "").strip()
    if not command:
        return None
    segments = split_chain(command)
    if not segments:
        return None
    reasons: List[str] = []
    for seg in segments:
        reason = _segment_match_reason(seg, project_path)
        if reason is None:
            return None  # 任一段未命中 → 整链不预授权
        reasons.append(reason)
    if len(reasons) == 1:
        return reasons[0]
    return " && ".join(reasons) + "（整链命中预授权清单）"
