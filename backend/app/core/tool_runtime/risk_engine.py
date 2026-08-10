"""命令风险策略引擎 — 三态判定（Phase B-1）+ 统一执行决策（Phase 3 T3/T8）

替代 command_tools 的硬编码白名单，采用三层判定：
  L0 精确白名单（只读命令快速路径）→ allow
  L1 拒绝模式（shell 元字符 / 不可逆动词）→ deny
  L2 关键字规则（写入动词）→ ask（build 模式）/ deny（plan 模式）
  未知命令 → 保守默认 ask（fail-closed）

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
from typing import Dict, List, Tuple


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
    ("git", ["status"]),
    ("git", ["diff"]),
    ("git", ["log"]),
    ("git", ["show"]),
    ("git", ["branch"]),
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
]

# python 严格化：仅允许白名单内的 -m 模块与版本查询，封死 "python -m pip install" 等写操作
_ALLOWED_PY_MODULES = {"pytest", "unittest", "py_compile", "mypy", "ruff", "flake8"}


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

_DESTRUCTIVE_PATTERNS = [
    re.compile(r"(^|\s)(rm|rmdir|del|erase|format|mkfs|diskpart|shutdown|reboot|taskkill)(\s|$)", re.I),
    re.compile(r"git\s+(reset\s+--hard|clean\s+-f|push\s+--force|filter-branch)\b", re.I),
    re.compile(r"reg\s+(add|delete|import|copy|save)\b", re.I),
    re.compile(r"Remove-Item|Format-Volume|Clear-Content\b", re.I),
]

# ---- L2 关键字规则：写入/有副作用 ----
_WRITE_PATTERNS = [
    re.compile(r"(^|\s)(pip|pip3|npm|yarn|pnpm|gem|composer)\s+(install|uninstall|remove|update|upgrade|add|i)\b", re.I),
    re.compile(r"(^|\s)(python|py)\s+-m\s+pip\s+(install|uninstall)\b", re.I),
    re.compile(r"git\s+(add|commit|push|merge|rebase|reset|stash|tag)\b", re.I),
    re.compile(r"(^|\s)(copy|move|ren|mkdir|md|rd|attrib|setx|set|echo)\s", re.I),
    re.compile(r"(^|\s)(start|stop|restart)\s", re.I),
]

APPROVAL_REASON = "命令未在只读白名单内，出于安全需你确认后执行"


class CommandRiskEngine:
    """命令风险策略执行器（无状态单例）"""

    def evaluate(self, command: str, mode: str = "build") -> RiskDecision:
        command = (command or "").strip()
        if not command:
            return RiskDecision(Verdict.DENY, RiskLevel.READ_ONLY, "错误: command 不能为空", command)

        if _FORBIDDEN_RE.search(command):
            return RiskDecision(
                Verdict.DENY, RiskLevel.DESTRUCTIVE,
                "错误: 命令包含不允许的字符（; & | ` $ < > 等），拒绝执行", command,
            )

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

    def _is_allowlisted(self, argv: List[str]) -> bool:
        cmd = argv[0]
        if cmd == "python":
            return _allow_python(argv)
        if cmd == "netsh":
            return _allow_netsh(argv)
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

        if _FORBIDDEN_RE.search(command):
            return RiskDecision(
                Verdict.DENY, RiskLevel.DESTRUCTIVE,
                "错误: 命令包含不允许的字符（; & | ` $ < > 等），拒绝执行", command,
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
    "read_file", "list_files", "search_files",
    "git_status", "git_diff", "git_log", "git_branch_list", "git_remote", "git_fetch",
    "web_search", "fetch_url", "github_search",
    "date_time", "json_format",
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
