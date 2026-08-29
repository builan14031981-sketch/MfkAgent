"""审批记忆（T5）— 近 90 天审批历史聚合，重复命令自动免审。

目标：用户近期反复批准的同一命令（归一化同模式）后续自动放行，减少审批骚扰；
同时绝不放宽安全边界：

硬边界（任一命中即不豁免，与历史记录无关）：
  - tool_name == "run_outside_command"（沙箱外命令）永不豁免
  - Verdict.HIGH_RISK 永不豁免（由 ApprovalPolicy.decide 结构性保证：仅
    REQUIRE_APPROVAL 分支消费豁免；executor 也仅对 REQUIRE_APPROVAL 判定发起查询）
  - 该模式出现过任何一次 deny → 永不豁免（deny 不限 90 天窗口，全史扫描）
  - settings 开关 approval_memory_enabled 默认关闭，用户手动开启灰度

数据来源：approval_requests 表（executor._persist_approval_request 落库、
complete_approval / chat.py 审批接口回写 status）。status 仅统计
approve / deny；pending / timeout / cancelled 不计入（超时与断开不算明确意愿，
避免把"用户没看到"当作"用户信任"）。

失败语义：本模块任何异常一律返回 None（不豁免），绝不能因记忆查询故障放大权限。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

# 近 90 天窗口内的 approve 才计数
MEMORY_WINDOW_DAYS = 90
# 同模式近 90 天 ≥3 次 approve 且 0 次 deny → 豁免
MEMORY_MIN_APPROVES = 3
# settings 开关 key（DEFAULT_SETTINGS 注册，默认 "false"）
MEMORY_ENABLED_KEY = "approval_memory_enabled"
# 豁免原因标签：写入 ExecutionDecision.reason / 审计行 risk_reason / 日志，
# executor 依据该标签判定"本次 EXECUTE 来自记忆豁免"（而非 STANDARD/AUTONOMOUS 常规放行）
MEMORY_EXEMPT_TAG = "[auto_approved_by_history]"
# 审计行状态（approval_requests.status 新增值，/api/security/approvals 可按此筛选豁免来源）
AUTO_APPROVED_STATUS = "auto_approved"
# 全史扫描行数上限（桌面单机场景审批量极小；防极端大表拖慢每次判定）
_MAX_SCAN_ROWS = 5000

_QUOTE_RE = re.compile(r"[\"'`]+")
_BRACKET_PREFIX_RE = re.compile(r"^\[[^\]]*\]\s*")   # 去 run_outside_command 的 [cwd: ...] 前缀
_TOOL_DESC_PAREN_RE = re.compile(r"^([^\s(：:]+)[（(]")  # 工具描述形态: git_commit(a=1) → git_commit
_TOOL_DESC_COLON_RE = re.compile(r"^([^\s：:]+)[：:](\s|$)")  # 工具描述形态: 写入文件: x → 写入文件
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class MemoryExemption:
    """一次命中历史豁免的证据（写入决策原因与审计行，可追溯）。"""
    pattern: str
    approve_count: int
    deny_count: int
    reason: str


def normalize_command_pattern(raw: str) -> str:
    """归一化命令为可聚合模式：去引号、去参数值，保留命令首 token 与子命令。

    例：
      git status --porcelain -b   → "git status"
      pip install requests==2.1   → "pip install"
      npm run build               → "npm run"        （首 token + 子命令）
      git commit -m "fix bug"     → "git commit"     （去引号、去 flag 值）
      写入文件: src/a.py          → "写入文件"        （工具描述取描述头）
      git_commit(path=x)          → "git_commit"
    """
    if not raw:
        return ""
    text = _BRACKET_PREFIX_RE.sub("", str(raw).strip())
    text = _QUOTE_RE.sub("", text)
    text = _WS_RE.sub(" ", text).strip()
    if not text:
        return ""

    # 工具描述形态（审批表 command 列存的是 _describe_tool_command 的可读描述）
    m = _TOOL_DESC_PAREN_RE.match(text)
    if m:
        return m.group(1).lower()
    m = _TOOL_DESC_COLON_RE.match(text)
    if m:
        return m.group(1).lower()

    # shell 命令形态：tokenize → 丢弃 flag（-/ 前缀）及其紧随的参数值 →
    # 位置参数中仅保留前两个（命令首 token + 子命令），其余视为参数值丢弃
    positionals = []
    prev_was_flag = False
    for token in text.split(" "):
        if token.startswith("-") or token.startswith("/"):
            prev_was_flag = True
            continue
        if prev_was_flag:
            prev_was_flag = False
            continue
        positionals.append(token)
    if not positionals:
        return text.lower()
    head = positionals[0].lower()
    sub = positionals[1].lower() if len(positionals) > 1 else ""
    return f"{head} {sub}".strip()


def build_exempt_reason(pattern: str, approve_count: int) -> str:
    """豁免原因文案（带机器可读标签，前端/日志/审批表可追溯）。"""
    return (
        f"{MEMORY_EXEMPT_TAG} 命令模式「{pattern}」近{MEMORY_WINDOW_DAYS}天已获人工批准"
        f"{approve_count}次且无拒绝记录，按审批记忆自动放行"
    )


def _read_enabled(db) -> bool:
    """读取 settings 开关；未配置或值非法一律视为关闭（默认灰度关闭）。"""
    from app.models.agent import Setting

    row = db.query(Setting).filter(Setting.key == MEMORY_ENABLED_KEY).first()
    if not row or row.value is None:
        return False
    return str(row.value).strip().lower() in ("true", "1", "yes", "on")


def collect_stats(
    db,
    tool_name: str,
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Tuple[int, int]]:
    """按 (tool_name, 归一化命令) 聚合审批历史。

    Returns:
        {pattern: (approve_count_90d, deny_count_全史)}
        approve 只认近 90 天；deny 不限窗口（出现过即永不豁免）。
    """
    from app.models.agent import ApprovalRequest

    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=MEMORY_WINDOW_DAYS)
    rows = (
        db.query(
            ApprovalRequest.command,
            ApprovalRequest.status,
            ApprovalRequest.created_at,
        )
        .filter(
            ApprovalRequest.tool_name == tool_name,
            ApprovalRequest.status.in_(("approve", "deny")),
        )
        .order_by(ApprovalRequest.id.desc())
        .limit(_MAX_SCAN_ROWS)
        .all()
    )
    stats: Dict[str, Tuple[int, int]] = {}
    for command, status, created_at in rows:
        pattern = normalize_command_pattern(command or "")
        if not pattern:
            continue
        approves, denies = stats.get(pattern, (0, 0))
        if status == "deny":
            denies += 1
        elif created_at is not None and created_at >= cutoff:
            approves += 1
        stats[pattern] = (approves, denies)
    return stats


def check(
    tool_name: str,
    command: str,
    *,
    enabled: Optional[bool] = None,
    db=None,
    now: Optional[datetime] = None,
) -> Optional[MemoryExemption]:
    """查询审批历史，判断该 (tool_name, 归一化命令) 是否可免审。

    Returns:
        MemoryExemption（命中豁免）或 None（不豁免）。
        开关关闭 / run_outside_command / 历史不足 / 出现过 deny / 任何异常 → None。
    """
    owns_db = False
    try:
        if db is None:
            from app.core.database import SessionLocal
            db = SessionLocal()
            owns_db = True
        if enabled is None:
            enabled = _read_enabled(db)
        if not enabled:
            return None

        # 硬边界：沙箱外命令无论历史如何永不豁免（即使 plan 模式下其判定为
        # REQUIRE_APPROVAL，也不得被记忆放行）
        if tool_name == "run_outside_command":
            return None

        pattern = normalize_command_pattern(command)
        if not pattern:
            return None

        approves, denies = collect_stats(db, tool_name, now=now).get(pattern, (0, 0))
        if approves >= MEMORY_MIN_APPROVES and denies == 0:
            return MemoryExemption(
                pattern=pattern,
                approve_count=approves,
                deny_count=denies,
                reason=build_exempt_reason(pattern, approves),
            )
        return None
    except Exception:  # noqa: BLE001 旁路：记忆查询故障绝不放大权限
        return None
    finally:
        if owns_db and db is not None:
            try:
                db.close()
            except Exception:  # noqa: BLE001
                pass
