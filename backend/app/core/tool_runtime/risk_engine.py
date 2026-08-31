r"""命令风险策略引擎 — 三态判定（Phase B-1）+ 统一执行决策（Phase 3 T3/T8）

替代 command_tools 的硬编码白名单，采用三层判定：
  L0 精确白名单（只读命令快速路径）→ allow
  L1 拒绝模式（shell 元字符 / 不可逆动词）→ deny
  L2 关键字规则（写入动词）→ ask（build 模式）/ deny（plan 模式）
  未知命令 → 保守默认 ask（fail-closed）
T11: 链式/wrapper 命令（bash -c / cmd /c / powershell -Command，&& || ; | 链）经安全
  解析后拆段、逐段走同一梯子再合并最严判定；无法安全解析（$ 展开、反引号、嵌套引号、
  \ 续行等）维持整体判定 fail-closed。回滚开关：settings.command_split_enabled（默认开）。

risk_level 仅作展示元数据（前端卡片文案/图标），不参与判定。
判定收敛为三态：allow / ask / deny。

Plan / Build 权限模型（Phase E5 修正）：
  设计原则：Plan 与 Build 的区别不是工具能力区别，而是修改权限区别。
  - 只读工具（READ_ONLY_TOOLS）在 Plan / Build 均自动放行。
  - 写入/有副作用工具：Build 模式按 TOOL_RISK_POLICY 触发审批（ask）；
    Plan 模式一律拒绝（deny）。
  - 未声明工具（非只读、不在策略表）：Plan 模式 fail-closed 直接拒绝；
    Build 模式放行（工具目录已由 PermissionFilter 收敛）。
  单一事实来源：TOOL_RISK_POLICY + READ_ONLY_TOOLS 为唯一权限清单，
  PermissionFilter 的 plan 目录过滤从本模块派生，避免两处清单漂移。

Phase 3 T3/T8 统一执行决策模型：
  RiskEngine → RiskDecision（原始风险判断）
       ↓
  ApprovalPolicy.apply() → ExecutionDecision（最终执行决策）
       ↓
  AgentRuntime 仅消费 ExecutionDecision，不再自行判断 auto_approve
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Dict, List, Optional, Tuple


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class Verdict(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"  # Phase 12: 可被 auto_approve 自动放行
    HIGH_RISK = "high_risk"                # Phase 12: 高危操作，无视 auto_approve，强制人工审批
    DENY = "deny"                          # 始终阻断（shell 元字符等）


class ExecutionAction(str, Enum):
    """Phase 3 T3/T8: 统一执行动作 — AgentRuntime 唯一消费的决策结果。"""
    EXECUTE = "execute"              # 直接执行
    REQUIRE_APPROVAL = "require_approval"  # 需要用户审批
    BLOCK = "block"                  # 拒绝执行


class RiskDecision:
    __slots__ = ("verdict", "risk_level", "reason", "command")

    def __init__(self, verdict: Verdict, risk_level: RiskLevel, reason: str, command: str):
        self.verdict = verdict
        self.risk_level = risk_level
        self.reason = reason
        self.command = command

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "command": self.command,
        }


class ExecutionDecision:
    """Phase 3 T3/T8: 统一执行决策 — RiskEngine + ApprovalPolicy 后产生的最终决策。

    AgentRuntime 只消费此对象，不再自行判断 auto_approve / safe / standard / autonomous。
    """
    __slots__ = ("action", "risk_level", "reason", "command", "original_verdict")

    def __init__(
        self,
        action: ExecutionAction,
        risk_level: RiskLevel,
        reason: str,
        command: str,
        original_verdict: Optional[Verdict] = None,
    ):
        self.action = action
        self.risk_level = risk_level
        self.reason = reason
        self.command = command
        self.original_verdict = original_verdict

    @property
    def is_approved(self) -> bool:
        return self.action == ExecutionAction.EXECUTE

    @property
    def needs_approval(self) -> bool:
        return self.action == ExecutionAction.REQUIRE_APPROVAL

    @property
    def is_blocked(self) -> bool:
        return self.action == ExecutionAction.BLOCK

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "command": self.command,
        }


# ---- L0 精确白名单：只读命令快速路径（与旧 _ALLOWED_COMMANDS 兼容并扩充）----
# 形如 (命令, [argv[1] 允许值列表])；空列表 = 该命令任意参数都放行（仅受 L1 元字符约束）
_ALLOWED_COMMANDS: List[Tuple[str, List[str]]] = [
    # 测试/验证类
    ("pytest", []),
    ("node", ["--version"]),
    ("node", ["-e", "--check"]),
    ("npm", ["run", "lint"]),
    ("npm", ["run", "test"]),
    ("npm", ["run", "build"]),
    ("npm", ["run", "typecheck"]),
    ("npm", ["test"]),
    ("npm", ["run"]),
    # G7: 只读依赖查询（npm install/uninstall 仍落入 L2 写操作）
    ("npm", ["ls"]),
    ("npm", ["view"]),
    ("git", ["status"]),
    ("git", ["diff"]),
    ("git", ["log"]),
    ("git", ["show"]),
    ("git", ["branch"]),
    # G7: git 只读子命令（仅 argv[1] 即只读者；remote add / tag 等可写子命令不放宽）
    ("git", ["ls-files"]),
    ("git", ["rev-parse"]),
    # G7: Python 包查询（只读；python -m pip install 仍落入 L2 写操作）
    ("pip", ["list"]),
    ("pip", ["freeze"]),
    ("pip", ["show"]),
    # 网络/系统只读诊断
    ("ipconfig", []),
    ("netstat", []),
    ("ping", ["-n"]),
    ("nslookup", []),
    ("tracert", []),
    ("systeminfo", []),
    ("hostname", []),
    ("whoami", []),
    ("ver", []),
    ("getmac", []),
    ("tasklist", []),
    ("route", ["print"]),
    ("arp", ["-a"]),
    ("sc", ["query"]),
    ("dir", []),
    ("where", []),
    ("find", []),
    ("findstr", []),
    ("type", []),
    ("more", []),
    ("tree", []),
    ("reg", ["query"]),
    # G7: 追加只读系统/网络诊断（原本误判需审批）
    ("driverquery", []),
    ("pathping", []),
    ("nbtstat", []),
    ("fc", []),
    ("comp", []),
    ("vol", []),
    ("schtasks", ["/query"]),
    ("query", ["user", "session"]),
    ("powercfg", ["/a", "/getactivescheme"]),
]

# python 严格化：仅允许白名单内的 -m 模块与版本查询，封死 "python -m pip install" 等写操作
_ALLOWED_PY_MODULES = {"pytest", "unittest", "py_compile", "mypy", "ruff", "flake8"}


# PowerShell 只读 Cmdlet 清单（T11 起提升为模块常量：整体判定与链式拆分逐段判定共用，避免两处漂移）
_PS_READONLY_CMDLETS = (
    "get-itemproperty", "get-childitem", "select-string", "test-path",
    "get-content", "get-item", "write-output", "get-command", "get-process",
    # G7: 追加常用只读查询/管道 Cmdlet（原本误判需审批；写动词 Cmdlet 不含在内）
    "get-service", "get-date", "get-location", "get-help", "get-alias",
    "get-ciminstance", "get-wmiobject", "get-acl", "get-clipboard", "get-history",
    "select-object", "where-object", "measure-object", "sort-object",
    "format-list", "format-table", "resolve-path",
)


def _allow_powershell(command: str, argv: List[str]) -> bool:
    """PowerShell 只读查询检测：当包含 Get-ItemProperty / Get-ChildItem / Select-String / Test-Path 等只读Cmdlet且无写动词时放行。"""
    cmd = argv[0].lower()
    if cmd not in ("powershell", "powershell.exe", "pwsh", "pwsh.exe"):
        return False
    if any(p.search(command) for p in _DESTRUCTIVE_PATTERNS) or any(p.search(command) for p in _WRITE_PATTERNS):
        return False
    cmd_lower = command.lower()
    return any(kw in cmd_lower for kw in _PS_READONLY_CMDLETS)


def _allow_python(argv: List[str]) -> bool:
    if argv[0] != "python":
        return False
    if len(argv) == 1:
        return True
    if argv[1] in ("--version", "-V"):
        return True
    if argv[1] == "-m" and len(argv) >= 3 and argv[2] in _ALLOWED_PY_MODULES:
        return True

    return False


def _allow_netsh(argv: List[str]) -> bool:
    """netsh 仅放行 winhttp 的 show/dump（只读），import/reset 等写操作落入 L2。"""
    if argv[0] != "netsh" or len(argv) < 3:
        return False
    return argv[1] == "winhttp" and argv[2] in ("show", "dump")


# ---- L1 拒绝模式：shell 元字符 / 不可逆动词 ----
_FORBIDDEN_RE = re.compile(r"[;&|`$<>]|\(|\)")

def _has_forbidden_chars(command: str) -> bool:
    cmd_lower = (command or "").lower().strip()
    if cmd_lower.startswith("powershell") or cmd_lower.startswith("pwsh"):
        # 对 powershell，允许语法符号 ($ ; () 等)，仅拦截重定向、反引号与管道
        return bool(re.search(r"[`&|<>]", command))
    return bool(_FORBIDDEN_RE.search(command))

_DESTRUCTIVE_PATTERNS = [
    re.compile(r"(^|\s)(rm|rmdir|del|erase|format|mkfs|diskpart|shutdown|reboot|taskkill)(\s|$)", re.I),
    re.compile(r"git\s+(reset\s+--hard|clean\s+-f|push\s+--force|filter-branch)\b", re.I),
    re.compile(r"reg\s+(add|delete|import|copy|save)\b", re.I),
    re.compile(r"Remove-Item|Format-Volume|Clear-Content\b", re.I),
]

# ---- L2 关键字规则：写入/有副作用 ----
_WRITE_PATTERNS = [
    re.compile(r"comfy_call\.py", re.I),
    re.compile(r"(^|\s)(pip|pip3|npm|yarn|pnpm|gem|composer)\s+(install|uninstall|remove|update|upgrade|add|i)\b", re.I),
    re.compile(r"(^|\s)(python|py)\s+-m\s+pip\s+(install|uninstall)\b", re.I),
    re.compile(r"git\s+(add|commit|push|merge|rebase|reset|stash|tag)\b", re.I),
    re.compile(r"(^|\s)(copy|move|ren|mkdir|md|rd|attrib|setx|set|echo)\s", re.I),
    re.compile(r"(^|\s)(start|stop|restart)\s", re.I),
]

APPROVAL_REASON = "命令未在只读白名单内，出于安全需你确认后执行"


# ---- T11: 链式命令安全拆分判定（Codex execpolicy 思路）----
# 背景：L1 对 shell 元字符整体拒绝，bash -c "mkdir x && cd x" 这类安全组合命令被一刀切 DENY。
# 方案：能被无歧义静态解析的链式命令按 && || ; | 拆段，逐段走现有 L0/L1/L2 判定后合并；
#       全部段通过才放行，任一段拒绝 → 整条 DENY，任一段写入 → 整条 REQUIRE_APPROVAL。
# fail-closed 不放松：$ 变量展开/$() 注入、反引号、嵌套/混用引号、\ 续行、单 &、
#       重定向、括号/花括号、空段、悬挂操作符等无法安全解析的结构 → 返回 None 回退整体判定（旧行为）。
# 回滚开关：settings.command_split_enabled（backend/.env，默认开）。
def _command_split_enabled() -> bool:
    """T11 回滚开关读取：默认开。异常/未设置一律视为开启（fail-closed 语义只影响拆分与否）。"""
    try:
        from app.core.config import settings  # 局部导入：避免测试环境与启动顺序耦合
    except Exception:
        return True
    value = getattr(settings, "command_split_enabled", None)
    if value is None:
        return True
    return str(value).strip().lower() not in ("0", "false", "no", "off")


# 段级解释器拒绝清单：链中任何一段以这些 shell/解释器开头 → 整条 DENY。
# 理由：编码变体攻击的经典落点是 "echo <payload> | base64 -d | sh"——解释器段本身就是
# 不透明代码执行，不拆、不放、也不放宽为审批，维持拒绝。python/perl/node 等不在清单内
# （作为段命令时仍走标准梯子：python -m pytest 等白名单用法可按段放行）。
_INNER_INTERPRETERS = frozenset({
    "sh", "bash", "zsh", "dash", "ksh", "csh", "tcsh", "fish",
    "eval", "exec", "source", "cmd", "cmd.exe",
})

# 各 shell 语义下"无法安全静态解析"的段内字符（fail-closed）：
#   bash  : $ 变量展开/$() 命令替换、` 反引号、() 子 shell、{} 花括号扩展、<> 重定向、单 &（后台/串接歧义）
#   cmd   : %VAR% 变量、! 延迟扩展、() 括号、{}、<> 重定向、单 &（cmd 单 & 是合法串接符 → 不可静态判定）
#   powershell: $ 变量/$( ) 子表达式、` 转义、() 表达式、{} 脚本块、<> 重定向、单 &（PS7 串接）
_BASH_UNSAFE_RE = re.compile(r"[$`(){}<>]|&(?!&)")
_CMD_UNSAFE_RE = re.compile(r"[%!(){}<>]|&(?!&)")
_PS_UNSAFE_RE = re.compile(r"[$`(){}<>]|&(?!&)")

# 包装命令识别：bash/sh -c '<script>' / cmd /c '<command>' / powershell -Command '<script>'
# （前缀仅允许无参数的单 token 开关；内层必须引号包裹且引号外无残留，否则 fail-closed）
_BASH_WRAPPER_RE = re.compile(r"^(?P<sh>bash|sh|zsh|dash|ksh)(?P<exe>\.exe)?\s+-c\s+(?P<arg>.+)$")
_CMD_WRAPPER_RE = re.compile(r"^cmd(?P<exe>\.exe)?\s+/c\s+(?P<arg>.+)$", re.I)
_PS_WRAPPER_RE = re.compile(
    r"^(?P<sh>powershell|pwsh)(?P<exe>\.exe)?\s+(?P<pre>(?:-\S+\s+)*?)-Command\s+(?P<arg>.+)$", re.I
)

# 合并段判定时的严重度序：DENY > HIGH_RISK > REQUIRE_APPROVAL > ALLOW
_VERDICT_SEVERITY = {
    Verdict.ALLOW: 0,
    Verdict.REQUIRE_APPROVAL: 1,
    Verdict.HIGH_RISK: 2,
    Verdict.DENY: 3,
}


def _scan_chain_segments(command: str, kind: str, require_op: bool = True) -> Optional[List[str]]:
    """按 && || ; | 把链式命令拆成段（引号感知，段保留原始引号原样）。

    kind: "bash" | "cmd" | "powershell"，决定段内不安全字符集。
    require_op: True 时无链式操作符的命令返回 None（裸命令走整体判定）；
                wrapper 内层传 False（无操作符时作为单段判定）。
    返回 None 表示无法安全解析（调用方 fail-closed 回退整体判定）。
    """
    unsafe_re = {"bash": _BASH_UNSAFE_RE, "cmd": _CMD_UNSAFE_RE, "powershell": _PS_UNSAFE_RE}.get(kind)
    if unsafe_re is None or not (command or "").strip():
        return None
    command = command.strip()
    segments: List[str] = []
    buf: List[str] = []
    quote: Optional[str] = None
    saw_op = False
    i, n = 0, len(command)
    while i < n:
        ch = command[i]
        if quote == "'":
            buf.append(ch)
            if ch == "'":
                quote = None
            i += 1
            continue
        if quote == '"':
            if ch == '"':
                quote = None
            elif kind == "bash" and ch == "\\" and i + 1 < n and command[i + 1] in ('"', '\\', '`', '$'):
                # bash 双引号内转义；转义 $ 或 ` 仍是命令替换/展开，fail-closed
                if command[i + 1] in ("`", "$"):
                    return None
                buf.append(ch)
                buf.append(command[i + 1])
                i += 2
                continue
            elif ch in ("$", "`"):
                return None
            buf.append(ch)
            i += 1
            continue
        # ---- 引号外 ----
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "\\":
            # \ 续行/行尾转义 → 无法静态判定行边界，fail-closed；其余转义按字面保留
            if i + 1 >= n or command[i + 1] in (" ", "\t", "\n"):
                return None
            buf.append(ch)
            buf.append(command[i + 1])
            i += 2
            continue
        if command.startswith("&&", i) or command.startswith("||", i):
            seg = "".join(buf).strip()
            if not seg:
                return None
            saw_op = True
            segments.append(seg)
            buf = []
            i += 2
            continue
        if ch in ";|":
            seg = "".join(buf).strip()
            if not seg:
                return None
            saw_op = True
            segments.append(seg)
            buf = []
            i += 1
            continue
        if unsafe_re.search(ch):
            return None
        buf.append(ch)
        i += 1
    if quote is not None:
        return None  # 引号未闭合
    tail = "".join(buf).strip()
    if not tail:
        return None  # 悬挂操作符（如 "git status &&"）
    segments.append(tail)
    if not saw_op and require_op:
        return None  # 非链式命令 → 整体判定
    return segments


def _extract_wrapper(command: str) -> Optional[Tuple[str, str]]:
    """识别 bash -c / cmd /c / powershell -Command 包装命令，返回 (kind, 内层命令)。

    fail-closed：内层必须引号包裹；引号外有残留、内层含任何引号字符（嵌套/混用引号）、
    内层为空 → 一律 None（回退整体判定）。
    """
    arg: Optional[str] = None
    kind: Optional[str] = None
    m = _BASH_WRAPPER_RE.match(command)
    if m:
        kind, arg = "bash", m.group("arg").strip()
    if kind is None:
        m = _CMD_WRAPPER_RE.match(command)
        if m:
            kind, arg = "cmd", m.group("arg").strip()
    if kind is None:
        m = _PS_WRAPPER_RE.match(command)
        if m:
            kind, arg = "powershell", m.group("arg").strip()
    if kind is None or not arg:
        return None
    if arg[0] not in ("'", '"'):
        return None  # 裸词内层歧义大（bash -c a&&b 语义分界不明），fail-closed
    closing = arg.rfind(arg[0])
    if closing <= 0:
        return None  # 引号未闭合
    inner = arg[1:closing].strip()
    if not inner:
        return None
    if arg[closing + 1:].strip():
        return None  # 引号外有残留（"bash -c 'x' extra"）→ 语义不明，fail-closed
    if "'" in inner or '"' in inner:
        return None  # 内层含任何引号字符（嵌套/混用引号）→ 维持整体判定
    return kind, inner


def _try_parse_chain(command: str) -> Optional[Tuple[str, List[str]]]:
    """尝试把命令解析为 (kind, segments)；非链式或无法安全解析 → None（旧行为）。

    优先做 wrapper 提取（bash -c "a && b" 的操作符在引号内，顶层扫描看不见），
    再做顶层链拆分（裸链，如 pip install x && pytest）。
    """
    wrapper = _extract_wrapper(command)
    if wrapper is not None:
        kind, inner = wrapper
        segments = _scan_chain_segments(inner, kind, require_op=False)
        if segments is None:
            return None
        return kind, segments
    segments = _scan_chain_segments(command, "bash", require_op=True)
    if segments is None:
        return None
    return "bash", segments


def chain_gate_allows(command: str) -> bool:
    """T11: run_command 纵深防御元字符门的豁免判定（供 command_tools 判定入口调用）。

    与 RiskEngine 共用同一解析器：命令为可安全拆分的链式/wrapper 命令 → True（放行，
    逐段风险判定已在 CommandRiskEngine.evaluate 完成）；否则 False（维持元字符拒绝）。
    回滚开关关闭或解析器任何异常 → False（行为与 T11 前完全一致）。
    """
    if not _command_split_enabled():
        return False
    try:
        return _try_parse_chain((command or "").strip()) is not None
    except Exception:
        return False


class CommandRiskEngine:
    """命令风险策略执行器（无状态单例）"""

    def evaluate(self, command: str, mode: str = "build") -> RiskDecision:
        command = (command or "").strip()
        if not command:
            return RiskDecision(Verdict.DENY, RiskLevel.READ_ONLY, "错误: command 不能为空", command)

        # T11: 链式/wrapper 命令按段判定；解析失败或开关关闭 → None 回退整体判定（fail-closed）
        if _command_split_enabled():
            parsed = _try_parse_chain(command)
            if parsed is not None:
                kind, segments = parsed
                decisions = [self._judge_segment(kind, seg, mode) for seg in segments]
                return self._merge_segment_decisions(decisions, command)

        if _has_forbidden_chars(command):
            return RiskDecision(
                Verdict.DENY, RiskLevel.DESTRUCTIVE,
                "错误: 命令包含不允许的字符（& | ` < > 等），拒绝执行", command,
            )

        return self._decide_single(command, mode)

    def _decide_single(self, command: str, mode: str) -> RiskDecision:
        """单命令 L0/L1/L2 梯子（evaluate 既有逻辑原样收敛，整体判定与逐段判定共用）。"""
        argv = re.split(r"\s+", command)
        if not argv or not argv[0]:
            return RiskDecision(Verdict.DENY, RiskLevel.READ_ONLY, "错误: 命令不能为空", command)

        if self._is_allowlisted(argv):
            return RiskDecision(Verdict.ALLOW, RiskLevel.READ_ONLY, "只读白名单命令，自动放行", command)

        # 未在白名单内 → 按风险分类，plan 模式一律拒绝，build 模式按风险等级分流
        if self._is_destructive(command):
            risk = RiskLevel.DESTRUCTIVE
            verdict = Verdict.HIGH_RISK  # Phase 12: 高危命令，强制人工审批
        elif self._is_write(command):
            risk = RiskLevel.WRITE
            verdict = Verdict.REQUIRE_APPROVAL  # Phase 12: 常规写操作，可被 auto_approve 放行
        else:
            risk = RiskLevel.DESTRUCTIVE
            verdict = Verdict.HIGH_RISK  # Phase 12: 未知命令 → 保守默认 HIGH_RISK

        if mode == "plan":
            return RiskDecision(
                Verdict.DENY, risk,
                f"错误: plan 只读模式拒绝执行（仅允许只读命令）: {APPROVAL_REASON}", command,
            )
        return RiskDecision(verdict, risk, APPROVAL_REASON, command)

    def _judge_segment(self, kind: str, segment: str, mode: str) -> RiskDecision:
        """T11: 链式命令逐段判定 — 沿用现有 L0/L1/L2 判定（与整体判定同一梯子）。"""
        segment = (segment or "").strip()
        if not segment:
            return RiskDecision(
                Verdict.DENY, RiskLevel.READ_ONLY, "错误: 链式命令存在空段，拒绝执行", segment,
            )
        if _has_forbidden_chars(segment):
            # 解析器不应放行含元字符的段（如引号内残留 & | 等）；命中即拒绝（纵深防御）
            return RiskDecision(
                Verdict.DENY, RiskLevel.DESTRUCTIVE,
                "错误: 链式命令段包含不允许的字符，拒绝执行", segment,
            )
        argv = re.split(r"\s+", segment)
        if not argv or not argv[0]:
            return RiskDecision(
                Verdict.DENY, RiskLevel.READ_ONLY, "错误: 链式命令存在空段，拒绝执行", segment,
            )

        # 解释器段拒绝：编码变体攻击（echo <payload> | base64 -d | sh）的落点段，
        # 不透明代码执行不拆不放，维持 DENY（python/perl/node 不在清单，走标准梯子）
        if kind != "powershell" and argv[0].lower() in _INNER_INTERPRETERS:
            return RiskDecision(
                Verdict.DENY, RiskLevel.DESTRUCTIVE,
                "错误: 链式命令段调用解释器（sh/bash/eval 等），拒绝执行", segment,
            )

        if self._is_allowlisted(argv):
            return RiskDecision(Verdict.ALLOW, RiskLevel.READ_ONLY, "只读白名单命令，自动放行", segment)

        # PowerShell 内层段：只读 Cmdlet 段级放行（与 _allow_powershell 同一清单，精确首词匹配）
        if (
            kind == "powershell"
            and not self._is_destructive(segment)
            and not self._is_write(segment)
            and argv[0].lower() in _PS_READONLY_CMDLETS
        ):
            return RiskDecision(Verdict.ALLOW, RiskLevel.READ_ONLY, "PowerShell 只读 Cmdlet，自动放行", segment)

        if self._is_destructive(segment):
            risk = RiskLevel.DESTRUCTIVE
            verdict = Verdict.HIGH_RISK
        elif self._is_write(segment):
            risk = RiskLevel.WRITE
            verdict = Verdict.REQUIRE_APPROVAL
        else:
            risk = RiskLevel.DESTRUCTIVE
            verdict = Verdict.HIGH_RISK  # 未知命令 → 保守默认 HIGH_RISK

        if mode == "plan":
            return RiskDecision(
                Verdict.DENY, risk,
                f"错误: plan 只读模式拒绝执行（仅允许只读命令）: {APPROVAL_REASON}", segment,
            )
        return RiskDecision(verdict, risk, f"链式命令按段判定，段「{segment}」{APPROVAL_REASON}", segment)

    def _merge_segment_decisions(self, decisions: List[RiskDecision], command: str) -> RiskDecision:
        """T11: 合并各段判定 — 任一段 DENY → 整条 DENY；任一段写入/高危 → 按最严段；
        全部段 ALLOW → 整条 ALLOW（全部段通过才放行）。"""
        worst = max(decisions, key=lambda d: _VERDICT_SEVERITY[d.verdict])
        if worst.verdict == Verdict.ALLOW:
            return RiskDecision(
                Verdict.ALLOW, RiskLevel.READ_ONLY,
                "链式命令已按段判定，所有段均为只读白名单命令，自动放行", command,
            )
        return RiskDecision(
            worst.verdict, worst.risk_level,
            f"链式命令按段判定（共 {len(decisions)} 段），最严段「{worst.command}」: {worst.reason}",
            command,
        )

    def _is_allowlisted(self, argv: List[str]) -> bool:
        cmd = argv[0]
        if cmd == "python":
            return _allow_python(argv)
        if cmd == "netsh":
            return _allow_netsh(argv)
        if _allow_powershell(" ".join(argv), argv):
            return True
        for allowed_cmd, prefixes in _ALLOWED_COMMANDS:
            if cmd != allowed_cmd:
                continue
            if not prefixes:
                return True
            if len(argv) >= 2 and argv[1] in prefixes:
                return True
        return False

    def _is_destructive(self, command: str) -> bool:
        return any(p.search(command) for p in _DESTRUCTIVE_PATTERNS)

    def _is_write(self, command: str) -> bool:
        return any(p.search(command) for p in _WRITE_PATTERNS)

    # ──── execute_command 专用风险策略（Secure Execution Runtime V1）────

    def evaluate_execute(self, command: str, mode: str = "build") -> RiskDecision:
        """execute_command 工具的专用风险判定。

        与 evaluate() 不同：execute_command 面向项目命令，采用更宽松的安全策略：
          - 安全项目命令（pytest / npm test / npm run build 等）→ ALLOW
          - 危险命令（rm / del / format 等）→ HIGH_RISK
          - 未知命令 → REQUIRE_APPROVAL（保守默认）
        """
        command = (command or "").strip()
        if not command:
            return RiskDecision(Verdict.DENY, RiskLevel.READ_ONLY, "错误: command 不能为空", command)

        if _has_forbidden_chars(command):
            return RiskDecision(
                Verdict.DENY, RiskLevel.DESTRUCTIVE,
                "错误: 命令包含不允许的字符（& | ` < > 等），拒绝执行", command,
            )

        argv = re.split(r"\s+", command)
        if not argv or not argv[0]:
            return RiskDecision(Verdict.DENY, RiskLevel.READ_ONLY, "错误: 命令不能为空", command)

        # 1. 危险命令 → HIGH_RISK（plan 模式下 DENY）
        if self._is_destructive(command):
            if mode == "plan":
                return RiskDecision(
                    Verdict.DENY, RiskLevel.DESTRUCTIVE,
                    f"错误: plan 只读模式拒绝执行危险命令", command,
                )
            return RiskDecision(
                Verdict.HIGH_RISK, RiskLevel.DESTRUCTIVE,
                "危险命令，需你确认后执行", command,
            )

        # 2. 安全项目命令 → ALLOW
        if self._is_safe_project_command(argv):
            return RiskDecision(Verdict.ALLOW, RiskLevel.READ_ONLY, "安全项目命令，自动放行", command)

        # 3. 未知命令 → REQUIRE_APPROVAL（plan 模式 DENY）
        if mode == "plan":
            return RiskDecision(
                Verdict.DENY, RiskLevel.WRITE,
                f"错误: plan 只读模式拒绝执行未知命令", command,
            )
        return RiskDecision(
            Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE,
            "未知命令，需你确认后执行", command,
        )

    # ──── run_outside_command 专用风险策略（沙箱外命令 · 强制人工审批）────

    def evaluate_outside(self, command: str, mode: str = "build") -> RiskDecision:
        """run_outside_command 工具的专用风险判定（沙箱外命令）。

        与 evaluate()/evaluate_execute() 不同：沙箱外命令不做白名单/读写分类，
        **一律返回 HIGH_RISK** —— 经 ApprovalPolicy 的 HIGH_RISK 强制人工审批，
        任何权限模式（SAFE/STANDARD/AUTONOMOUS）都不可自动放行，确保每一步都由人类把关。
        """
        command = (command or "").strip()
        if not command:
            return RiskDecision(Verdict.DENY, RiskLevel.READ_ONLY, "错误: command 不能为空", command)

        if _has_forbidden_chars(command):
            return RiskDecision(
                Verdict.DENY, RiskLevel.DESTRUCTIVE,
                "错误: 命令包含不允许的字符（& | ` < > 等），拒绝执行", command,
            )

        argv = re.split(r"\s+", command)
        # 沙箱外只读操作在 plan 模式下允许放行/由用户确认，仅毁灭性/写入命令拦截
        if mode == "plan":
            if self._is_destructive(command) or self._is_write(command):
                return RiskDecision(
                    Verdict.DENY, RiskLevel.DESTRUCTIVE,
                    "错误: plan 只读模式拒绝执行包含写入/删除的沙箱外命令", command,
                )
            if self._is_allowlisted(argv):
                return RiskDecision(Verdict.ALLOW, RiskLevel.READ_ONLY, "沙箱外只读白名单命令，Plan 模式放行", command)
            return RiskDecision(
                Verdict.REQUIRE_APPROVAL, RiskLevel.READ_ONLY,
                "沙箱外只读命令，Plan 模式下需你确认后执行", command,
            )

        # 沙箱外命令：恒定 HIGH_RISK → 所有权限模式强制人工审批
        return RiskDecision(
            Verdict.HIGH_RISK, RiskLevel.DESTRUCTIVE,
            "沙箱外命令，需你确认后执行", command,
        )

    # execute_command 安全命令白名单（仅可执行文件，不含 shell 内置命令）
    _SAFE_EXECUTE_COMMANDS: Dict[str, frozenset] = {
        "pytest": frozenset(),
        "python": frozenset({"-m", "--version", "-V"}),
        "node": frozenset({"--version", "-v"}),
        "npm": frozenset({"test", "run", "--version", "-v"}),
        "npx": frozenset(),
        "yarn": frozenset({"test", "build", "lint", "typecheck", "--version", "-v"}),
        "pnpm": frozenset({"test", "build", "lint", "typecheck", "--version", "-v"}),
        "go": frozenset({"test", "build", "vet", "fmt", "version"}),
        "cargo": frozenset({"test", "build", "check", "clippy", "fmt", "--version", "-V"}),
        "make": frozenset({"test", "build", "lint", "check"}),
        "dotnet": frozenset({"test", "build", "--version"}),
        "tsc": frozenset({"--version", "-v", "--noEmit"}),
        "eslint": frozenset(),
        "prettier": frozenset({"--check"}),
        "ruff": frozenset({"check"}),
        "mypy": frozenset(),
        "flake8": frozenset(),
        "black": frozenset({"--check"}),
        "cmd": frozenset(),  # cmd /c <command> for shell builtins
        "git": frozenset({"status", "diff", "log", "branch", "remote", "show", "fetch"}),
    }

    # npm run 子命令白名单（仅测试/构建类命令放行）
    _SAFE_NPM_RUN_SCRIPTS = frozenset({
        "build", "test", "lint", "typecheck",
        "check", "format", "prepare", "prepublishOnly",
    })

    def _is_safe_project_command(self, argv: List[str]) -> bool:
        """判断是否为安全项目命令（execute_command 专用）。"""
        if not argv:
            return False
        cmd = argv[0].lower()

        # 检查命令是否在白名单中
        if cmd not in self._SAFE_EXECUTE_COMMANDS:
            return False

        allowed_sub = self._SAFE_EXECUTE_COMMANDS[cmd]

        # 空 frozenset = 该命令任意参数都安全
        if not allowed_sub:
            return True

        # python -m 模块白名单
        if cmd == "python" and len(argv) >= 2 and argv[1] == "-m":
            if len(argv) >= 3:
                return argv[2] in _ALLOWED_PY_MODULES
            return True

        # python --version / -V → 安全
        if cmd == "python" and len(argv) >= 2 and argv[1] in ("--version", "-V"):
            return True

        # npm run <script> → 检查脚本名是否在白名单
        if cmd == "npm" and len(argv) >= 3 and argv[1] == "run":
            return argv[2] in self._SAFE_NPM_RUN_SCRIPTS

        # npm test / npm --version → 安全
        if cmd == "npm" and len(argv) >= 2:
            return argv[1] in allowed_sub

        # 其他命令：检查子命令
        if len(argv) >= 2:
            return argv[1] in allowed_sub

        # 无子命令的命令（如 pytest）→ 安全
        return True


command_risk_engine = CommandRiskEngine()


# ---- 工具级风险策略（Phase B-2：write_file / git 等统一纳入审批）----
# 非命令工具也走三态判定：只读工具自动放行，写入/破坏性工具 build 模式 ask、plan 模式 deny。
# 命令工具（run_command）仍由 CommandRiskEngine 单独判定。
#
# 本表 + READ_ONLY_TOOLS 是 Plan/Build 权限模型的唯一事实来源：
#   - 表内工具 = 写入/有副作用工具（Build 按 verdict 处理，Plan 一律 deny）
#   - READ_ONLY_TOOLS = 只读工具（两模式均 allow）
#   - 两处之外的未知工具：Plan fail-closed deny，Build 放行
TOOL_RISK_POLICY: Dict[str, Tuple[Verdict, RiskLevel, str]] = {
    "write_file": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "写文件操作会修改项目文件，需你确认后执行"),
    # Phase H: 增量替换 / 补丁应用与整文件写入同级（修改项目文件）
    "edit_file": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "增量替换会修改项目文件，需你确认后执行"),
    "apply_patch": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "应用补丁会批量修改项目文件，需你确认后执行"),
    # Phase H: 文生图调用外部付费 API + 落盘图片，需审批
    "generate_image": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "文生图会调用外部付费服务并保存图片，需你确认后执行"),
    "git_commit": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "Git 提交会写入提交历史，需你确认后执行"),
    "git_add": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "Git 暂存会变更索引，需你确认后执行"),
    "git_push": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "Git 推送会上传提交到远端，需你确认后执行"),
    "git_pull": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "Git 拉取会变更本地分支，需你确认后执行"),
    "git_clone": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "Git clone 会下载外部仓库到本地，需你确认后执行"),
    "git_restore": (Verdict.HIGH_RISK, RiskLevel.DESTRUCTIVE, "Git 恢复会覆盖/丢弃本地改动，需你确认后执行"),
    "git_reset": (Verdict.HIGH_RISK, RiskLevel.DESTRUCTIVE, "Git 回退会重写历史/丢弃改动，需你确认后执行"),
    "git_clean": (Verdict.HIGH_RISK, RiskLevel.DESTRUCTIVE, "Git 清理会删除未跟踪文件，需你确认后执行"),
    "git_revert": (Verdict.HIGH_RISK, RiskLevel.DESTRUCTIVE, "Git 回滚会生成反向提交，需你确认后执行"),
    "github_create_pr": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "创建 Pull Request 会在 GitHub 上提交变更，需你确认后执行"),
    # 飞书多维表格写入（修改云端数据，需审批）
    "feishu_write_records": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "飞书写入会修改多维表格数据，需你确认后执行"),
    "feishu_create_base": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "创建飞书多维表格会创建云端新资源，需你确认后执行"),
    # 飞书 IM 外发（P1：向群/用户发送消息、图片、文件，需审批）
    "feishu_send_message": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "会向飞书群/用户发送消息，需你确认后执行"),
    "feishu_send_image": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "会向飞书群/用户发送图片，需你确认后执行"),
    "feishu_send_file": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "会向飞书群/用户发送文件，需你确认后执行"),
    # 数据库写入（plan 禁止修改数据库）：Build 放行（后台记忆），Plan deny
    "add_memory": (Verdict.ALLOW, RiskLevel.WRITE, "保存记忆会写入数据库，Plan 模式禁止修改数据库"),
    # 待办事项管理（Build 放行，Plan deny — 与 add_memory 同策略）
    "manage_todos": (Verdict.ALLOW, RiskLevel.WRITE, "管理待办会写入数据库，Plan 模式禁止修改数据库"),
    # 预留：当前无对应实现，注册后自动被 Plan 拒绝（fail-closed）
    "delete_file": (Verdict.HIGH_RISK, RiskLevel.DESTRUCTIVE, "删除文件操作不可恢复，需你确认后执行"),
    "rename_file": (Verdict.REQUIRE_APPROVAL, RiskLevel.WRITE, "重命名文件会变更项目结构，需你确认后执行"),
}

# 只读工具白名单（Plan / Build 均自动放行）：
# 文件/结构/搜索只读 + git 只读 + 网络只读 + 通用只读。run_command 由命令引擎单独判定。
READ_ONLY_TOOLS = frozenset({
    "read_file", "list_files", "find_files", "search_files",
    "git_status", "git_diff", "git_log", "git_branch_list", "git_remote", "git_fetch",
    "web_search", "fetch_url", "github_search",
    "date_time", "json_format",
    # 规格校验：只读文件做正则断言，无副作用，自动放行（弱模型防偏差护栏）
    "verify_spec",
    # 抉择工具：无副作用的交互询问，Plan/Build 均放行
    "ask_user_choice",
    # Phase 4 T2: GitHub 只读工具（自动 ALLOW，无需审批）
    "github_list_issues", "github_read_issue",
    "github_list_pull_requests", "github_read_pull_request",
    # 飞书多维表格只读（自动 ALLOW，无需审批）
    "feishu_list_bases", "feishu_query_records",
    # 飞书列群（P1：只读，自动放行）
    "feishu_list_chats",
    # UI 自检工具：打开本机前端页面抓样式/截图，只读无副作用，自动放行
    "probe_ui", "capture_screenshot", "analyze_screenshot",
})

# Plan 模式应从工具目录移除的写入/有副作用工具（单一来源派生，供 PermissionFilter 使用）
PLAN_FORBIDDEN_TOOLS = frozenset(TOOL_RISK_POLICY.keys())


def evaluate_tool(tool_name: str, mode: str = "build") -> RiskDecision:
    """非命令工具的审批判定（write_file / git / 通用工具等）。

    Plan / Build 权限模型：
      - 只读工具（READ_ONLY_TOOLS）→ 两模式均 ALLOW
      - 写入/破坏性工具（TOOL_RISK_POLICY）→ build 模式按表 verdict、plan 模式 DENY
      - 未声明工具（非只读、不在策略表）→ plan 模式 fail-closed DENY、build 模式放行
    """
    if tool_name in READ_ONLY_TOOLS:
        return RiskDecision(Verdict.ALLOW, RiskLevel.READ_ONLY, "只读工具，自动放行", tool_name)

    if tool_name in TOOL_RISK_POLICY:
        verdict, risk, reason = TOOL_RISK_POLICY[tool_name]
        if mode == "plan":
            return RiskDecision(
                Verdict.DENY, risk,
                f"错误: plan 只读模式拒绝执行（{reason}）", tool_name,
            )
        return RiskDecision(verdict, risk, reason, tool_name)

    if mode == "plan":
        return RiskDecision(
            Verdict.DENY, RiskLevel.WRITE,
            f"错误: plan 只读模式拒绝执行（工具 {tool_name} 未声明为只读，Plan 模式禁止调用）",
            tool_name,
        )
    return RiskDecision(Verdict.ALLOW, RiskLevel.READ_ONLY, "只读工具，自动放行", tool_name)
