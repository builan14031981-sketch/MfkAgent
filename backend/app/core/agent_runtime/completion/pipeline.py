"""Completion Verification — 三层验证管道（MfkAgent Autonomous Completion Loop V1）。

按序执行三层验证，任一失败即短路返回（并记录各层判定）：
  1. ToolVerification          — 复用 Phase E4 程序化验证复核工具结果
  2. RuleBasedVerification     — 确定性规则判定
  3. LLMJudgeVerification     — LLM Judge 兜底（可通过 use_llm_judge 关闭，纯工具+规则模式）

语义：
  - 工具成功 ≠ 任务完成；三层全部通过才认为「任务真正完成」。
  - 失败结果携带 failure_layer + 各层 evidence，供事件 / 反馈上下文 / Memory 学习使用。
"""

from typing import List, Optional

from app.core.agent_runtime.completion.base import CompletionVerifier
from app.core.agent_runtime.completion.models import (
    CompletionContext,
    CompletionVerificationResult,
)
from app.core.agent_runtime.completion.rules import RuleBasedVerification
from app.core.agent_runtime.completion.tool_check import ToolVerification

# 导入 Judge 不引入副作用（构造时惰性加载模型服务）
DEFAULT_LLM_JUDGE_MODULE = "app.core.agent_runtime.completion.llm_judge"


class CompletionPipeline(CompletionVerifier):
    """完成验证管道：按序执行 Tool → Rule → LLM Judge。"""

    name = "pipeline"

    def __init__(
        self,
        *,
        use_llm_judge: bool = True,
        verifiers: Optional[List[CompletionVerifier]] = None,
    ):
        self.use_llm_judge = use_llm_judge
        self.verifiers: List[CompletionVerifier] = verifiers or [
            ToolVerification(),
            RuleBasedVerification(),
        ]
        if use_llm_judge:
            from app.core.agent_runtime.completion.llm_judge import LLMJudgeVerification
            self.verifiers.append(LLMJudgeVerification())

    async def verify(self, ctx: CompletionContext) -> CompletionVerificationResult:
        chain = []
        for v in self.verifiers:
            result = await v.verify(ctx)
            chain.append({"layer": v.name, "result": result.to_dict()})
            if not result.success:
                return CompletionVerificationResult(
                    success=False,
                    reason=result.reason,
                    missing_items=result.missing_items,
                    next_action=result.next_action,
                    layer=result.layer,
                    evidence={"chain": chain, "failure_layer": result.layer},
                )
        return CompletionVerificationResult(
            success=True,
            reason="三层完成验证全部通过",
            layer=self.name,
            evidence={"chain": chain},
        )