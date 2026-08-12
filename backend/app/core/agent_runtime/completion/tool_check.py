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
    """工具层完成验证：复用 Phase E4 程序化验证复核工具执行结果。"""

    name = "tool"

    def __init__(self, verifier=None):
        self._verifier = verifier or get_verifier()

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
        for record in records:
            tool_name = record.get("tool") or record.get("name") or "?"
            # 执行失败的动作 → 直接判定缺失
            if record.get("status") != "success":
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