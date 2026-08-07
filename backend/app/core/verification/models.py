"""Verification 模块 — Phase E4 基础验证框架。

VerificationResult 是工具动作验证的统一载体：
  - status: "passed" | "failed" | "need_retry"
  - message: 可读说明（注入 LLM 反馈 / 事件透传）
  - evidence: 结构化证据（exit_code / path / size 等）

语义约定：
  - passed     验证通过 → Runtime 正常继续 / 结束
  - need_retry 动作已发生但结果不符合预期（如命令非零退出 / 内容不一致）
               → Runtime 向 LLM 注入反馈，进入下一轮重新执行
  - failed     动作本身未达成（文件未创建 / 无法解析）
               → Runtime 向 LLM 注入反馈，进入下一轮修正

本阶段不做：
  - LLM 自主判定验证结果（程序验证优先）
  - 自动规划 / 多 Agent / Vision
"""

from dataclasses import dataclass, field
from typing import Optional

PASSED = "passed"
FAILED = "failed"
NEED_RETRY = "need_retry"


@dataclass
class VerificationResult:
    """工具动作验证结果。"""

    status: str = PASSED
    message: str = ""
    evidence: dict = field(default_factory=dict)
    strategy: Optional[str] = None
    tool: Optional[str] = None
    tool_call_id: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.status == PASSED

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
        return out
