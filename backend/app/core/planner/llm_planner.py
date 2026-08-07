"""LLMPlanner — Phase G2-B：LLM 辅助任务规划器。

使用 model_service.call_once() 调用 LLM 生成结构化 Plan。
失败时抛出异常，由 PlannerService 自动 fallback 到 heuristic。
"""

import json
import logging
from typing import List, Optional

from app.services.model import model_service
from .models import Plan, PlanStep, PlanningLevel
from .service import PLAN_MODE_CONSTRAINT

logger = logging.getLogger(__name__)

# ──── LLM Planner System Prompt ────

_SYSTEM_PROMPT = """你是一个任务规划助手。你的职责是根据用户请求，生成一个结构化的执行计划。

输出要求：
- 仅输出 JSON，不要输出任何其他文本
- 字段说明：
  - goal: 任务目标（一句话，不超过200字）
  - steps: 执行步骤列表，每个步骤包含：
    - action: 步骤描述
    - suggested_tools: 建议的工具名列表（可为空数组）
  - constraints: 约束条件列表（可为空数组）

JSON 格式示例：
{
  "goal": "分析项目性能瓶颈",
  "steps": [
    {"action": "定位性能热点代码", "suggested_tools": ["read_file", "run_command"]},
    {"action": "分析根因", "suggested_tools": ["read_file"]},
    {"action": "给出优化建议", "suggested_tools": []}
  ],
  "constraints": ["不能修改数据库结构"]
}

注意：
- 步骤数量控制在 1-5 个
- suggested_tools 中的工具名必须是真实可用的工具
- 如果用户请求是简单问答，返回 1 个步骤即可
"""

# ──── LLM Planner ────


class LLMPlanner:
    """LLM 辅助规划器（无状态，可共享单例）。

    使用 model_service.call_once() 进行单次 LLM 调用，
    不负责工具循环、不控制执行、不修改 AgentRuntime。
    """

    def __init__(self):
        pass

    async def plan(
        self,
        *,
        message: str,
        mode: str = "build",
        decision: Optional[dict] = None,
        model_id: str = "qwen-flash",
    ) -> Plan:
        """调用 LLM 生成任务计划。

        Args:
            message: 用户请求原文
            mode: "build" / "plan"
            decision: tool_runtime decision（含 intent）
            model_id: 模型 ID

        Returns:
            Plan 对象

        Raises:
            Exception: LLM 调用失败或输出解析失败时抛出，
                       由 PlannerService 捕获后 fallback heuristic。
        """
        intent = (decision or {}).get("intent", "general_chat")

        # 构建 messages（call_once 需要 dict，而非 pydantic 对象）
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(message=message, mode=mode, intent=intent)},
        ]

        # 调用 model_service.call_once()
        result = await model_service.call_once(
            model_id=model_id,
            messages=messages,
            temperature=0.3,  # 低温度，提高 JSON 输出稳定性
            max_tokens=1024,
            tools=None,       # Planner 不调用工具
            reasoning_effort=None,
            memory_text=None,
        )

        # 解析 LLM 输出
        return self._parse_response(result.content, message, mode)

    def _parse_response(self, raw: str, message: str, mode: str) -> Plan:
        """解析 LLM 输出的 JSON 为 Plan。

        Raises:
            ValueError: JSON 解析失败或字段缺失
        """
        # 提取 JSON（处理 LLM 可能包裹在 ```json 中的情况）
        content = raw.strip()
        if "```" in content:
            # 提取 ```json ... ``` 或 ``` ... ``` 中的内容
            lines = content.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    if in_block:
                        break
                    in_block = True
                    continue
                if in_block:
                    json_lines.append(line)
            if json_lines:
                content = "\n".join(json_lines)

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM Planner JSON 解析失败: {e}") from e

        if not isinstance(data, dict):
            raise ValueError(f"LLM Planner 输出不是 JSON 对象: {type(data)}")

        # 解析 steps
        steps = []
        for s in data.get("steps", []):
            if not isinstance(s, dict):
                continue
            steps.append(
                PlanStep(
                    action=str(s.get("action", "")),
                    suggested_tools=list(s.get("suggested_tools", [])),
                )
            )

        if not steps:
            raise ValueError("LLM Planner 输出缺少 steps")

        # 解析 constraints
        constraints = []
        raw_constraints = data.get("constraints", [])
        if isinstance(raw_constraints, list):
            constraints = [str(c) for c in raw_constraints]

        # mode 约束
        if mode == "plan":
            constraints.append(PLAN_MODE_CONSTRAINT)

        return Plan(
            goal=str(data.get("goal", message[:200])),
            steps=steps,
            constraints=constraints,
            mode=mode or "build",
        )


def _build_user_prompt(*, message: str, mode: str, intent: str) -> str:
    """构建发送给 LLM Planner 的用户提示。"""
    parts = [f"用户请求: {message}"]
    parts.append(f"当前模式: {mode}")
    if intent and intent != "general_chat":
        parts.append(f"识别意图: {intent}")
    parts.append("请生成执行计划。")
    return "\n".join(parts)


# 全局单例（无状态）
_llm_planner = LLMPlanner()


def get_llm_planner() -> LLMPlanner:
    return _llm_planner