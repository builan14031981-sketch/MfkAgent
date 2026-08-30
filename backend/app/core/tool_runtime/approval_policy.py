"""Approval Policy Layer — 审批策略层（Phase 3 T3/T8）

职责：
  根据配置的 ApprovalMode，将 RiskDecision 转换为统一 ExecutionDecision。
  AgentRuntime 只消费 ExecutionDecision，不再自行判断 auto_approve。

设计原则：
  - 不修改 RiskEngine 的判定逻辑
  - 不修改 ApprovalRegistry 的注册机制
  - 统一输出 ExecutionDecision（EXECUTE / REQUIRE_APPROVAL / BLOCK）

ApprovalMode:
  - SAFE: 所有写入操作需要审批（最严格）
  - STANDARD: 普通写入自动批准，高风险需要审批（默认）
  - AUTONOMOUS: REQUIRE_APPROVAL 自动批准，HIGH_RISK 仍需审批（最宽松）

流程：
  RiskEngine.evaluate() → RiskDecision
      ↓
  ApprovalPolicy.decide() → ExecutionDecision
      ↓
  Executor / AgentRuntime 消费
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from .risk_engine import (
    RiskDecision, Verdict, RiskLevel,
    ExecutionDecision, ExecutionAction,
)
from .preapproval import command_matches_preapproval, autonomous_preapproval_enabled
from . import approval_memory


class ApprovalMode(str, Enum):
    """审批模式 — 持久化在 settings 表 agent_permission_mode 中。"""
    SAFE = "safe"           # 所有写入需要审批
    STANDARD = "standard"   # 普通写入自动，高风险需审批（默认）
    AUTONOMOUS = "autonomous"  # REQUIRE_APPROVAL 自动，HIGH_RISK 仍需审批


# 默认审批模式
DEFAULT_APPROVAL_MODE = ApprovalMode.STANDARD


class ApprovalPolicy:
    """审批策略执行器 — 将 RiskDecision 转换为 ExecutionDecision。"""

    def __init__(self, mode: Optional[ApprovalMode] = None):
        self._mode = mode or DEFAULT_APPROVAL_MODE

    @property
    def mode(self) -> ApprovalMode:
        return self._mode

    def decide(
        self,
        decision: RiskDecision,
        memory_exemption: Optional["approval_memory.MemoryExemption"] = None,
    ) -> ExecutionDecision:
        """根据审批模式返回最终 ExecutionDecision。

        Args:
            decision: RiskEngine 返回的原始判定
            memory_exemption: 审批记忆豁免证据（T5）。由 executor 在判定为
                REQUIRE_APPROVAL 后、进入本方法前查询 approval_memory 得到；
                不传（None）则完全走原有模式逻辑，行为与现状一致。

        Returns:
            ExecutionDecision，action 为 EXECUTE / REQUIRE_APPROVAL / BLOCK
        """
        # ALLOW → 直接执行
        if decision.verdict == Verdict.ALLOW:
            return ExecutionDecision(
                ExecutionAction.EXECUTE,
                decision.risk_level,
                decision.reason,
                decision.command,
                original_verdict=decision.verdict,
            )

        # DENY → 始终阻断
        if decision.verdict == Verdict.DENY:
            return ExecutionDecision(
                ExecutionAction.BLOCK,
                decision.risk_level,
                decision.reason,
                decision.command,
                original_verdict=decision.verdict,
            )

        # HIGH_RISK: 所有模式下都强制审批（安全底线）
        if decision.verdict == Verdict.HIGH_RISK:
            return ExecutionDecision(
                ExecutionAction.REQUIRE_APPROVAL,
                decision.risk_level,
                decision.reason,
                decision.command,
                original_verdict=decision.verdict,
            )

        # REQUIRE_APPROVAL: 根据模式决定
        if decision.verdict == Verdict.REQUIRE_APPROVAL:
            # ── T5 审批记忆豁免（前置检查）──
            # 仅 REQUIRE_APPROVAL 可被历史豁免：HIGH_RISK 与 DENY 已在上方先行返回，
            # run_outside_command 由 approval_memory.check() 硬边界拦截（恒返 None），
            # 三道防线缺一不可。豁免证据（模式/次数/原因）来自近 90 天 approval_requests
            # 聚合：≥3 次 approve 且 0 次 deny；开关关闭或查询异常时 executor 不会传入。
            if memory_exemption is not None:
                return ExecutionDecision(
                    ExecutionAction.EXECUTE,
                    decision.risk_level,
                    memory_exemption.reason,
                    decision.command,
                    original_verdict=decision.verdict,
                )

            if self._mode == ApprovalMode.SAFE:
                # SAFE: 所有写入需要审批
                return ExecutionDecision(
                    ExecutionAction.REQUIRE_APPROVAL,
                    decision.risk_level,
                    decision.reason,
                    decision.command,
                    original_verdict=decision.verdict,
                )

            elif self._mode == ApprovalMode.STANDARD:
                # STANDARD: 普通写入自动批准
                if decision.risk_level == RiskLevel.WRITE:
                    return ExecutionDecision(
                        ExecutionAction.EXECUTE,
                        decision.risk_level,
                        f"[STANDARD] {decision.reason}",
                        decision.command,
                        original_verdict=decision.verdict,
                    )
                return ExecutionDecision(
                    ExecutionAction.REQUIRE_APPROVAL,
                    decision.risk_level,
                    decision.reason,
                    decision.command,
                    original_verdict=decision.verdict,
                )

            elif self._mode == ApprovalMode.AUTONOMOUS:
                # AUTONOMOUS: REQUIRE_APPROVAL 全部自动
                return ExecutionDecision(
                    ExecutionAction.EXECUTE,
                    decision.risk_level,
                    f"[AUTONOMOUS] {decision.reason}",
                    decision.command,
                    original_verdict=decision.verdict,
                )

        # 未知判定 → 保守阻断
        return ExecutionDecision(
            ExecutionAction.BLOCK,
            decision.risk_level,
            f"未知判定: {decision.reason}",
            decision.command,
            original_verdict=decision.verdict,
        )

    def decide_with_preapproval(
        self,
        decision: RiskDecision,
        *,
        command: Optional[str] = None,
        project_path: Optional[str] = None,
        allow_preapproval: bool = True,
        memory_exemption: Optional["approval_memory.MemoryExemption"] = None,
    ) -> ExecutionDecision:
        """工单J：autonomous 会话预授权清单 → 命中清单的命令自动放行。

        仅当全部满足时命中预授权（旁路放行，不修改 risk_engine 判定本体）：
          - allow_preapproval（plan 模式必须为 False，plan 写入一律拒绝）
          - 本策略模式为 AUTONOMOUS
          - 开关 autonomous_preapproval_enabled 开启（默认开）
          - command 非空（仅项目内命令工具传入；run_outside_command 不传）
          - command_matches_preapproval 命中清单

        命中 → EXECUTE 并标注 auto_approved_by_policy；
        未命中 → 回落 decide()（透传 T5 memory_exemption，第二条通路保持不变）。
        """
        if (
            allow_preapproval
            and self._mode == ApprovalMode.AUTONOMOUS
            and command
            and autonomous_preapproval_enabled()
        ):
            reason = command_matches_preapproval(command, project_path=project_path)
            if reason:
                return ExecutionDecision(
                    ExecutionAction.EXECUTE,
                    decision.risk_level,
                    f"[PREAPPROVAL] auto_approved_by_policy: {reason}",
                    decision.command,
                    original_verdict=decision.verdict,
                )
        return self.decide(decision, memory_exemption=memory_exemption)

    # 保留向后兼容方法
    def apply(self, decision: RiskDecision) -> RiskDecision:
        """向后兼容：返回调整后的 RiskDecision（旧接口）。"""
        ed = self.decide(decision)
        if ed.action == ExecutionAction.EXECUTE:
            return RiskDecision(Verdict.ALLOW, ed.risk_level, ed.reason, ed.command)
        elif ed.action == ExecutionAction.BLOCK:
            return RiskDecision(Verdict.DENY, ed.risk_level, ed.reason, ed.command)
        else:
            return decision

    def should_auto_approve(self, decision: RiskDecision) -> bool:
        """判断是否应该自动批准该操作（向后兼容）。"""
        return self.decide(decision).action == ExecutionAction.EXECUTE


# 全局单例（延迟初始化，从 Settings 读取配置）
_approval_policy: Optional[ApprovalPolicy] = None


def get_approval_policy() -> ApprovalPolicy:
    """获取全局 ApprovalPolicy 单例。

    首次调用时从 Settings 读取 agent_permission_mode 配置。
    """
    global _approval_policy
    if _approval_policy is None:
        from app.core.database import SessionLocal
        from app.models.agent import Setting

        db = SessionLocal()
        try:
            setting = db.query(Setting).filter(Setting.key == "agent_permission_mode").first()
            if setting and setting.value:
                mode = ApprovalMode(setting.value)
            else:
                mode = DEFAULT_APPROVAL_MODE
        except Exception:
            mode = DEFAULT_APPROVAL_MODE
        finally:
            db.close()

        _approval_policy = ApprovalPolicy(mode)

    return _approval_policy


def set_approval_mode(mode: ApprovalMode) -> None:
    """设置全局审批模式（运行时动态切换），同步到数据库。"""
    global _approval_policy
    _approval_policy = ApprovalPolicy(mode)

    from app.core.database import SessionLocal
    from app.models.agent import Setting

    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == "agent_permission_mode").first()
        if setting:
            setting.value = mode.value
        else:
            setting = Setting(key="agent_permission_mode", value=mode.value)
            db.add(setting)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()