"""OrchestrationPlanner — 任务分析：复杂度分级 + 角色推荐 + 子任务拆分。

输入：用户任务文本
输出：OrchestrationPlan（complexity / need_orchestration / subtasks / reason）

策略（分层降级，保证任何情况下都能给出计划）：
  1. LLM 分析：调用 model_service.call_once 让主模型输出 JSON（复杂度 + 角色 + 子任务拆分）。
     产出必须为合法 JSON，解析失败逐层降级。
  2. 启发式兜底：按任务文本特征（长度、领域关键词、是否多阶段）给保守估计；
     拿不准时默认 SIMPLE（不编排），宁可不编排也不误导主 Agent。

LLM 提示词要求子代理角色必须来自 ORCHESTRATION_ROLES 目录，
超出目录的角色会被过滤，避免注入任意身份。
"""

import json
import re
from typing import Optional

from app.core.orchestrator.models import (
    OrchestrationPlan,
    SubTaskSpec,
    TaskComplexity,
)
from app.core.orchestrator.roles import (
    ORCHESTRATION_ROLES,
    get_orchestration_role,
    role_ids,
)

_PLANNER_SYSTEM_PROMPT = """你是任务编排规划器。你的职责是判断一个用户任务是否需要拆解给多个专业子代理协作完成。

可用角色目录（只能从中选择）:
{roles}

决策规则:
1. SIMPLE（简单）: 单步即可完成的问答、单文件查询、简单说明。直接判定 need_orchestration=false，不要拆子任务。
2. MODERATE（中等）: 需要多步骤但单个主 Agent 足以完成（如实现一个小功能、修改一个模块）。可拆 1-2 个子任务辅助，或判定不需编排。
3. COMPLEX（复杂）: 跨领域/多阶段/大型工程（如"开发一个完整的商城系统"、多模块重构、系统级设计），需拆分为多个专业子代理并行协作。必须输出 2-5 个子任务。

输出严格 JSON（不要 markdown 代码块、不要注释、不要多余文字）:
{{
  "complexity": "simple|moderate|complex",
  "reason": "简短判定依据（人类可读，中文）",
  "subtasks": [
    {{"role": "角色id", "task": "自包含子任务描述：背景+目标+期望输出", "output_format": "期望输出格式"}}
  ]
}}

要求:
- 角色 id 必须来自目录；不在目录的角色一律不要输出。
- 每个子任务的 task 必须自包含（子代理看不到主会话历史），描述背景、目标与交付物。
- 如果判定为 simple 或不需要编排，subtasks 输出空数组。
- 复杂度与子任务数量要匹配，不要为了凑数而拆任务。
"""

_COMPLEXITY_PATTERNS = [
    # 明显的复杂工程信号
    (re.compile(r"系统|平台|商城|电商|全栈|前端.*后端|后端.*前端|架构|多模块|项目", re.I), TaskComplexity.COMPLEX),
    (re.compile(r"重构|重构.*模块|迁移|升级|大型", re.I), TaskComplexity.COMPLEX),
]


def _heuristic_fallback(task: str) -> OrchestrationPlan:
    """无 LLM 或解析失败时的启发式兜底（保守：不编排）。"""
    task = (task or "").strip()
    for pat, complexity in _COMPLEXITY_PATTERNS:
        if pat.search(task):
            return OrchestrationPlan(
                complexity=complexity,
                need_orchestration=False,
                subtasks=[],
                reason="启发式：任务文本包含工程化信号，但未启用自动编排（保守兜底）",
                planner_source="heuristic",
            )
    return OrchestrationPlan(
        complexity=TaskComplexity.SIMPLE,
        need_orchestration=False,
        subtasks=[],
        reason="启发式：任务较短或未命中复杂信号，默认简单任务直接执行",
        planner_source="heuristic",
    )


def _parse_llm_json(text: str) -> Optional[dict]:
    """解析 LLM 返回的 JSON（容忍 markdown 代码块包裹）。"""
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned).strip()
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # 尝试提取第一个 { ... } 块
    m = re.search(r"\{.*\}", cleaned, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _build_subtasks(raw_subtasks: list) -> list:
    """把 LLM 的子任务列表过滤为合法角色 + 自包含描述。"""
    subtasks = []
    for item in raw_subtasks or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip()
        task = str(item.get("task", "") or "").strip()
        if not role or not task:
            continue
        role_def = get_orchestration_role(role)
        if not role_def:
            # 非法角色：跳过（不注入任意身份）
            continue
        subtasks.append(SubTaskSpec(
            role=role,
            task=task,
            output_format=str(item.get("output_format", "") or "").strip(),
            max_tokens=role_def.max_tokens,
        ))
    return subtasks


async def orchestration_plan(task: str, model_id: Optional[str] = None) -> OrchestrationPlan:
    """分析任务并返回编排计划。

    流程：LLM 分析 → 解析 JSON → 校验角色 → 合法则采用；
    任何一步失败降级到启发式兜底。LLM 失败不会向上抛异常。
    """
    task = (task or "").strip()
    if not task:
        return _heuristic_fallback("")

    # 延迟导入：context_builder → services.model → services.tools → orchestrator_tool
    # 若顶层导入会形成循环依赖，故在函数内按需加载。
    from app.core.agent_runtime.context_builder import get_default_model
    from app.services.model import model_service

    effective_model = model_id or get_default_model()
    role_doc = "\n".join(
        f"- {rid}: {r.name} — {r.description}"
        for rid, r in ORCHESTRATION_ROLES.items()
    )
    messages = [
        {"role": "system", "content": _PLANNER_SYSTEM_PROMPT.format(roles=role_doc)},
        {"role": "user", "content": f"任务：{task}\n\n请分析并输出编排计划 JSON。"},
    ]

    try:
        result = await model_service.call_once(
            model_id=effective_model,
            messages=messages,
            temperature=0.2,
            max_tokens=2048,
        )
        data = _parse_llm_json(result.content)
        if not data:
            return _heuristic_fallback(task)

        complexity_raw = str(data.get("complexity", "simple") or "simple").lower().strip()
        try:
            complexity = TaskComplexity(complexity_raw)
        except ValueError:
            complexity = TaskComplexity.SIMPLE

        subtasks = _build_subtasks(data.get("subtasks") or [])
        need_orchestration = (
            complexity == TaskComplexity.COMPLEX
            and len(subtasks) >= 2
        )
        # MODERATE 且 LLM 明确给了子任务且 ≥2 个时也允许编排（尊重 LLM 判断）
        if not need_orchestration and complexity == TaskComplexity.MODERATE and len(subtasks) >= 2:
            need_orchestration = True

        return OrchestrationPlan(
            complexity=complexity,
            need_orchestration=need_orchestration,
            subtasks=subtasks,
            reason=str(data.get("reason", "") or "") or "LLM 分析结果",
            planner_source="llm",
        )
    except Exception:
        # LLM 调用失败 → 保守兜底，不阻塞主流程
        return _heuristic_fallback(task)


__all__ = ["orchestration_plan", "OrchestrationPlan"]