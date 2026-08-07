"""Planner Runtime 接入点 — TaskContext → Execution Loop 消费桥（Phase G1）。

位置（Phase G1 流程）：
  User Request → ContextBuilder → PlannerService.plan → AgentContext.task_context
              → RuntimeTaskContextAdapter.render → Execution Loop（LLM 可见）

职责：
  - 把 AgentContext.task_context（V1: goal/constraints/current_step）渲染为
    system prompt 的"任务计划"段落（⑧ 层）。
  - 只读消费：不修改 task_context、不控制/执行任何工具。
  - AgentRuntime 无需改动：prompt 由 ChatContextBuilder 组装后，经 Execution Loop
    原样送入模型，任务计划对模型生效。
"""

from typing import Optional

SECTION_TITLE = "## 当前任务计划（Planner V1）"


class RuntimeTaskContextAdapter:
    """Runtime 接入点：task_context dict → system prompt 段落。"""

    def render(self, task_context: Optional[dict]) -> str:
        """渲染任务计划段落；task_context 为空时返回空字符串（不注入）。"""
        if not task_context:
            return ""

        goal = task_context.get("goal") or ""
        constraints = task_context.get("constraints") or []
        current_step = task_context.get("current_step")

        lines = [SECTION_TITLE, f"目标: {goal}"]
        if constraints:
            lines.append("约束: " + "；".join(constraints))
        if current_step:
            lines.append(f"当前步骤: {current_step}")
        lines.append("按计划推进；若实际进展与计划不符，请先说明再调整。")
        return "\n".join(lines)


_adapter = RuntimeTaskContextAdapter()


def get_runtime_task_context_adapter() -> RuntimeTaskContextAdapter:
    return _adapter
