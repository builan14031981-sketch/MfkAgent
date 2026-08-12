"""Completion Verification 模块 — MfkAgent Autonomous Completion Loop V1。

统一完成验证入口：
  - `CompletionVerifier.verify()` 判定「任务是否真正完成」
  - 三层验证：Tool（复用 Phase E4）→ Rule（确定性规则）→ LLM Judge（结构化兜底）

用法：
    from app.core.agent_runtime.completion import CompletionPipeline, CompletionContext

    ctx = CompletionContext(task_goal=..., final_content=..., tool_records=...)
    result = await CompletionPipeline().verify(ctx)
"""

from app.core.agent_runtime.completion.base import CompletionVerifier
from app.core.agent_runtime.completion.models import (
    CompletionContext,
    CompletionVerificationResult,
)
from app.core.agent_runtime.completion.pipeline import CompletionPipeline
from app.core.agent_runtime.completion.rules import RuleBasedVerification
from app.core.agent_runtime.completion.tool_check import ToolVerification

__all__ = [
    "CompletionContext",
    "CompletionVerificationResult",
    "CompletionVerifier",
    "CompletionPipeline",
    "ToolVerification",
    "RuleBasedVerification",
]