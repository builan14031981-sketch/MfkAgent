"""Completion Verification — LLM Judge 层（MfkAgent Autonomous Completion Loop V1）。

针对无法规则判断的任务，以独立的 LLM 调用作「完成判定」。
输入：任务目标 + 执行过程摘要 + 工具结果 + 最终输出
要求模型返回结构化 JSON：
    {"completed": true, "reason": "", "missing": [], "suggestion": ""}

设计原则：
  - Judge 只做验证，不负责执行；任何情况下不改变执行历史。
  - Judge 结果非结构化时视为「无法判定」→ 不通过，由 Runtime 走重试/收尾；
  - Judge 调用失败（网络/配置/模型不可用）不阻断主流程：视为运行期异常返回失败，
    Runtime 可安全收尾，避免验证成为故障源。
"""

import json
import logging
import re
from typing import Optional

from app.core.agent_runtime.completion.base import CompletionVerifier
from app.core.agent_runtime.completion.models import (
    CompletionContext,
    CompletionVerificationResult,
)

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = (
    "你是 MfkAgent 的任务完成判定员（Judge）。你的职责是判断 Agent 是否真正完成了用户任务，"
    "而不是仅仅停止调用工具。\n"
    "判断依据：\n"
    "1. 任务目标是否已达成（产出物存在、修改已生效）；\n"
    "2. 是否有未完成 / 缺失的关键步骤；\n"
    "3. 最终回答是否与任务目标相关。\n"
    "注意：你只做判定，绝不执行任何操作。\n"
    "必须严格返回如下 JSON（不要输出其它内容）：\n"
    '{"completed": true, "reason": "简短原因", "missing": [], "suggestion": ""}\n'
    "其中 completed=true 表示任务已完成；completed=false 时 missing 列出缺失项，"
    "suggestion 给出下一步建议。"
)

# Judge 请求内嵌的判别标记（SSE/测试可用它识别 Judge 调用与主循环调用）
JUDGE_MARKER = "MFKAGENT-COMPLETION-JUDGE"


def _summarize_tool_records(records) -> str:
    """将工具执行记录压缩为摘要文本（供 Judge 参考）。"""
    if not records:
        return "（无工具调用）"
    lines = []
    for r in (records or [])[-20:]:
        tool = r.get("tool") or r.get("name") or "?"
        status = r.get("status", "?")
        result = (r.get("result") or "")[:200]
        lines.append(f"- [{tool}] status={status} result={result}")
    return "\n".join(lines)


def parse_judge_json(content: str) -> Optional[dict]:
    """从 Judge 返回内容中提取 JSON 对象。

    容忍 markdown 代码围栏与前后修饰文本。无法解析返回 None。
    """
    if not content:
        return None
    text = content.strip().lstrip("`").rstrip("`").strip()
    if text.startswith("json"):
        text = text[4:].strip()
    # 提取第一个 { ... } 块（跨行、容忍围栏）
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


class LLMJudgeVerification(CompletionVerifier):
    """LLM Judge 完成判定层。"""

    name = "llm_judge"

    def __init__(self, temperature: float = 0.1, max_tokens: int = 512):
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _build_messages(self, ctx: CompletionContext) -> list:
        user_prompt = (
            f"请判定以下任务是否真正完成。\n\n"
            f"## 任务目标\n{ctx.task_goal}\n\n"
            f"## 工具执行摘要\n{_summarize_tool_records(ctx.tool_records)}\n\n"
            f"## Agent 最终输出\n{ctx.final_content}\n"
        )
        return [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT + f"\n（识别标记：{JUDGE_MARKER}）"},
            {"role": "user", "content": user_prompt},
        ]

    async def verify(self, ctx: CompletionContext) -> CompletionVerificationResult:
        from app.services.model import model_service

        model_id = ctx.model_id or "default"
        try:
            result = await model_service.call_once(
                model_id=model_id,
                messages=self._build_messages(ctx),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                tools=None,
                reasoning_effort=None,
                memory_text=None,
                vision_context=None,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("[completion-judge] Judge 调用失败（作为运行期异常返回失败）: %s", e)
            return CompletionVerificationResult(
                success=False,
                reason=f"LLM Judge 调用失败，无法判定任务完成",
                next_action="check_model_service",
                layer=self.name,
                evidence={"error": str(e)[:200]},
            )

        data = parse_judge_json(getattr(result, "content", "") or "")
        if data is None:
            return CompletionVerificationResult(
                success=False,
                reason="LLM Judge 无法解析结构化判定结果",
                next_action="retry_judge",
                layer=self.name,
            )

        completed = bool(data.get("completed"))
        if completed:
            return CompletionVerificationResult(
                success=True,
                reason=(data.get("reason") or "LLM Judge 判定任务完成"),
                layer=self.name,
                evidence={"judge": data},
            )

        return CompletionVerificationResult(
            success=False,
            reason=(data.get("reason") or "LLM Judge 判定任务尚未完成"),
            missing_items=list(data.get("missing") or []),
            next_action=(data.get("suggestion") or "continue_execution"),
            layer=self.name,
            evidence={"judge": data},
        )