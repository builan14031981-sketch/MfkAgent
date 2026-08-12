"""Completion Verification — 统一验证入口抽象（MfkAgent Autonomous Completion Loop V1）。

`CompletionVerifier.verify()` 是唯一完成验证入口：
  - 输入：CompletionContext（任务目标 / 执行历史 / 工具结果 / 当前状态）
  - 输出：CompletionVerificationResult（success / reason / missing_items / next_action）

V1 提供三类实现（缺省由 CompletionPipeline 组合）：
  1. ToolVerification          — 复用 Phase E4 工具级程序化验证
  2. RuleBasedVerification     — 确定性规则判定（注册表可扩展）
  3. LLMJudgeVerification     — LLM Judge 结构化判定（无法规则判断时兜底）

设计原则：
  - verify() 为 async（Judge 层需调用模型服务）；
  - Judge 只做验证，不负责执行；
  - 验证失败不抛异常，返回 failure 结果，由 Runtime 决定重试/收尾。
"""

from abc import ABC, abstractmethod

from app.core.agent_runtime.completion.models import (
    CompletionContext,
    CompletionVerificationResult,
)


class CompletionVerifier(ABC):
    """完成验证器统一接口。"""

    name: str = "base"

    @abstractmethod
    async def verify(self, ctx: CompletionContext) -> CompletionVerificationResult:
        """验证任务是否真正完成。

        Args:
            ctx: 完成验证输入上下文

        Returns:
            CompletionVerificationResult: 验证结果
        """