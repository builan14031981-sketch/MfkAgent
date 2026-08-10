"""Verification 模块 — Phase E4 基础验证框架 + Verification Loop V1。

VerificationResult 是工具动作验证的统一载体：
  - status: "passed" | "failed" | "need_retry" | "loop_exhausted"
  - message: 可读说明（注入 LLM 反馈 / 事件透传）
  - evidence: 结构化证据（exit_code / path / size 等）
  - retry_count: 当前重试次数（Verification Loop V1）
  - max_retries: 最大重试次数（Verification Loop V1）

语义约定：
  - passed          验证通过 → Runtime 正常继续 / 结束
  - need_retry      动作已发生但结果不符合预期（如命令非零退出 / 内容不一致）
                    → Runtime 向 LLM 注入反馈，进入下一轮重新执行
  - failed          动作本身未达成（文件未创建 / 无法解析）
                    → Runtime 向 LLM 注入反馈，进入下一轮修正
  - loop_exhausted  重试次数耗尽 → Runtime 停止重试，向用户报告失败

Verification Loop V1 新增：
  - 重试次数跟踪（per tool_call_id）
  - 最大重试次数限制（默认 3 次）
  - 循环耗尽检测和反馈
"""

from dataclasses import dataclass, field
from typing import Optional

PASSED = "passed"
FAILED = "failed"
NEED_RETRY = "need_retry"
LOOP_EXHAUSTED = "loop_exhausted"

# Verification Loop V1 配置
DEFAULT_MAX_RETRIES = 3


@dataclass
class VerificationResult:
    """工具动作验证结果。"""

    status: str = PASSED
    message: str = ""
    evidence: dict = field(default_factory=dict)
    strategy: Optional[str] = None
    tool: Optional[str] = None
    tool_call_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = DEFAULT_MAX_RETRIES

    @property
    def passed(self) -> bool:
        return self.status == PASSED

    @property
    def should_retry(self) -> bool:
        """判断是否应该重试（need_retry 且未超过最大重试次数）。"""
        return self.status == NEED_RETRY and self.retry_count < self.max_retries

    @property
    def loop_exhausted(self) -> bool:
        """判断重试次数是否已耗尽。"""
        return self.status == NEED_RETRY and self.retry_count >= self.max_retries

    def to_dict(self) -> dict:
        """序列化（供 SSE 事件 / 持久化使用，不含 None 冗余字段）。"""
        out = {
            "status": self.status,
            "message": self.message,
            "evidence": self.evidence,
        }
        if self.strategy:
            out["strategy"] = self.strategy
        if self.tool:
            out["tool"] = self.tool
        if self.tool_call_id:
            out["tool_call_id"] = self.tool_call_id
        if self.retry_count > 0:
            out["retry_count"] = self.retry_count
        if self.max_retries != DEFAULT_MAX_RETRIES:
            out["max_retries"] = self.max_retries
        return out
