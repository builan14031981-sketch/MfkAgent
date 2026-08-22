"""Completion Verification — 工具层验证（MfkAgent Autonomous Completion Loop V1）。

复用 Phase E4 的程序化验证能力（Verifier），对本轮与历史的工具执行记录做统一复核：
  - 文件修改   → 文件是否存在 + 内容是否一致（write_file / replace_in_file / apply_patch）
  - 命令执行   → exit code / 输出（run_command）
  - 测试任务   → pytest / npm test 退出码（run_command）

原则：
  - 工具成功 ≠ 任务完成：本层只保证「已发生的动作本身是健康的」；
    任务是否做完由规则层 / LLM Judge 层继续判定。
  - 只对 status == "success" 的记录做程序化验证；执行失败的记录直接计入 missing_items。
"""

from typing import Optional

from app.core.agent_runtime.completion.base import CompletionVerifier
from app.core.agent_runtime.completion.models import (
    CompletionContext,
    CompletionVerificationResult,
)
from app.core.verification import get_verifier


class ToolVerification(CompletionVerifier):
    """工具层完成验证：复用 Phase E4 程序化验证复核工具执行结果。

    P1 修复（2026-08-13）：只校验每个工具「最后一次出现」的记录。
    早先的失败/拦截记录被后续成功覆盖时自动豁免（重试成功语义）——
    命令被策略拦截→重试→最终成功 = 最终状态健康，不构成未完成项。
    规则层 test_scope_guard 仍保留最后一次 pytest exit_code + 防逃逸判定。
    """

    name = "tool"

    def __init__(self, verifier=None):
        self._verifier = verifier or get_verifier()

    # run_command / execute_command / run_outside_command 同属命令执行族，聚合时按族取最后一次
    _COMMAND_FAMILY = "command"
    _COMMAND_TOOLS = ("run_command", "execute_command", "run_outside_command")
    # risk_engine / Strategy Layer 拦截文本前缀（命令从未真正运行，无副作用）
    _CMD_INTERCEPT_PREFIXES = ("错误:", "策略阻止:")

    @classmethod
    def _family_key(cls, tool_name: str) -> str:
        return cls._COMMAND_FAMILY if tool_name in cls._COMMAND_TOOLS else tool_name

    @classmethod
    def _is_intercepted(cls, record: dict) -> bool:
        """判断命令记录是否「被策略拦截而未真正运行」（非执行失败）。

        被拦截不产生副作用，不构成未完成项；是否真的跑过 pytest 由规则层把关。
        """
        if record.get("status") == "blocked":
            return True
        if record.get("status") == "success":
            return False
        tool_name = record.get("tool") or record.get("name") or ""
        if tool_name not in cls._COMMAND_TOOLS:
            return False
        result = str(record.get("result") or "")
        return any(result.startswith(p) for p in cls._CMD_INTERCEPT_PREFIXES)

    @staticmethod
    def _build_last_healthy_records(records: list) -> list:
        """按工具族聚合：仅保留每个族最后一次出现的记录（维持首次出现顺序）。

        重试语义：同一族的早期失败/拦截记录被后续记录覆盖，最终状态为准。
        run_command 与 execute_command 归一为一族，避免同命令双名互相打断豁免。
        """
        order: list = []
        last_by_name: dict = {}
        for record in records or []:
            name = record.get("tool") or record.get("name") or "?"
            key = ToolVerification._family_key(name)
            if key not in last_by_name:
                last_by_name[key] = record
                order.append(key)
            else:
                last_by_name[key] = record
        return [last_by_name[key] for key in order]

    async def verify(self, ctx: CompletionContext) -> CompletionVerificationResult:
        records = ctx.tool_records or []
        if not records:
            return CompletionVerificationResult(
                success=True,
                reason="本轮无工具调用，工具层验证通过（无动作可校验）",
                layer=self.name,
            )

        missing_items = []
        detail = []
        for record in self._build_last_healthy_records(records):
            tool_name = record.get("tool") or record.get("name") or "?"
            if record.get("status") != "success":
                if self._is_intercepted(record):
                    # 被策略拦截且从未运行 → 不构成未完成项（降级为 evidence）
                    detail.append({"tool": tool_name, "verdict": "intercepted_blocked"})
                    continue
                missing_items.append(f"{tool_name}: 执行失败")
                detail.append({"tool": tool_name, "verdict": "exec_failed"})
                continue

            # 复用 Phase E4 程序化验证（write_file 重读 / run_command 退出码等）
            vr = self._verifier.verify(record, ctx.project_path)
            detail.append({"tool": tool_name, "verdict": vr.status})
            if not vr.passed:
                missing_items.append(f"{tool_name}: {vr.message}")

        if missing_items:
            return CompletionVerificationResult(
                success=False,
                reason="工具执行结果存在未通过程序化验证的项目",
                missing_items=missing_items,
                next_action="fix_tool_actions",
                layer=self.name,
                evidence={"detail": detail},
            )

        return CompletionVerificationResult(
            success=True,
            reason="工具执行结果均通过程序化验证",
            layer=self.name,
            evidence={"detail": detail},
        )