"""Completion Verification — 完成验证输入 / 输出模型（MfkAgent Autonomous Completion Loop V1）。

唯一事实来源：
  - `CompletionContext`        验证输入（任务目标 / 执行历史 / 工具结果 / 当前状态）
  - `CompletionVerificationResult`  验证输出（success / reason / missing_items / next_action）

语义约定：
  - success=True    验证通过 → 任务可标记完成 / Agent 结束
  - success=False   验证失败 → 生成反馈上下文，重新进入 Agent Loop（受 max_completion_retry 保护）
  - 与工具级 VerificationResult（Phase E4）互补，但语义更高一层：
    工具级别管「单个动作是否做对」，完成级别管「整个任务是否做完」。
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class CompletionContext:
    """完成验证的输入上下文。

    由 AgentRuntime 在「LLM 停止调用工具（完成候选）」处组装。
    """

    task_goal: str = ""                            # 任务目标（TaskGraph 节点 action / 用户首条消息）
    final_content: str = ""                        # LLM 最终输出（完成候选文本）
    tool_records: List[dict] = field(default_factory=list)   # 本轮及历史工具执行记录
    execution_history: list = field(default_factory=list)     # loop 消息历史（LLM Judge 参考）
    project_path: Optional[str] = None             # 项目路径（工具层磁盘校验用）
    current_task: Any = None                       # TaskGraph 当前节点（可选）
    model_id: Optional[str] = None                 # LLM Judge 使用的模型
    options: dict = field(default_factory=dict)    # 扩展选项（语义开关等）

    def to_dict(self) -> dict:
        return {
            "task_goal": self.task_goal,
            "final_content": self.final_content,
            "tool_count": len(self.tool_records),
            "model_id": self.model_id,
        }


@dataclass
class CompletionVerificationResult:
    """完成验证输出。

    Attributes:
        success:        验证是否通过
        reason:         判定原因（可读文本，注入反馈 / 事件）
        missing_items:  缺失/未完成项列表（可执行指令）
        next_action:    建议下一步动作（continue / fix:xxx / 空=无需再动）
        layer:          最终做出判定的层（tool / rule / llm_judge）
        evidence:       结构化证据（供事件 / Memory 学习）
    """

    success: bool = False
    reason: str = ""
    missing_items: List[str] = field(default_factory=list)
    next_action: str = ""
    layer: str = ""
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        out = {
            "success": self.success,
            "reason": self.reason,
            "missing_items": list(self.missing_items),
            "next_action": self.next_action,
            "layer": self.layer,
        }
        if self.evidence:
            out["evidence"] = self.evidence
        return out