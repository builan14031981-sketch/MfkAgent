"""Planner Service — V1 最小启发式任务规划 + G2-B LLM 辅助（Phase G1 → G2-B）。

与 ToolPlanner（soft_hint）的职责区别：
  - ToolPlanner   ：意图 → 工具建议软提示（system prompt ⑦ 层）
  - PlannerService：意图/模式 → 结构化 Plan → AgentContext.task_context（⑧ 层）

G2-B 升级：
  - planning_level >= 2 时，优先使用 LLMPlanner（model_service.call_once()）
  - LLM 失败或输出解析失败时，自动 fallback 到 heuristic
  - Level 0/1 保持纯启发式，零额外开销

设计约束：
  - 不控制工具：仅产出文本计划与建议工具（reference），不 gate、不执行。
  - 不破坏 Runtime：Plan 仅通过 task_context 注入，AgentRuntime 不感知 Planner 内部实现。
  - 非任务型请求（general_chat / 空消息）→ 返回 None，task_context 保持 None
"""

import logging
from typing import Dict, List, Optional

from .models import Plan, PlanStep, PlanningLevel

logger = logging.getLogger(__name__)

# 任务型意图（对应 tool_runtime.intent 输出；general_chat 不在此集合）
TASK_INTENTS = frozenset(
    {
        "system_diagnosis",
        "file_operation",
        "project_debug",
        "git_operation",
        "web_search",
        "memory_operation",
    }
)

# 各意图的建议步骤模板（suggested_tools 仅为参考，不构成权限/gate）
_STEP_TEMPLATES: Dict[str, List[PlanStep]] = {
    "system_diagnosis": [
        PlanStep("采集系统/网络/日志等真实状态信息", ["run_command"]),
        PlanStep("分析采集结果，定位问题根因", ["run_command", "read_file"]),
        PlanStep("给出诊断结论与可选修复方案", []),
    ],
    "file_operation": [
        PlanStep("确认目标文件/目录位置与工作目录", ["list_files", "read_file"]),
        PlanStep("执行文件读取或修改", ["read_file", "write_file"]),
        PlanStep("验证结果并汇报", ["read_file", "run_command"]),
    ],
    "project_debug": [
        PlanStep("定位相关代码/日志并尝试复现问题", ["run_command", "read_file"]),
        PlanStep("分析根因", ["read_file", "run_command", "git_diff"]),
        PlanStep("实施修复并验证", ["run_command", "read_file"]),
    ],
    "git_operation": [
        PlanStep("查看仓库当前状态与变更", ["git_status", "git_diff"]),
        PlanStep("查看历史记录确认上下文", ["git_log"]),
        PlanStep("执行提交/恢复等操作", ["git_commit", "git_restore"]),
    ],
    "web_search": [
        PlanStep("搜索相关资料", ["web_search"]),
        PlanStep("阅读并筛选关键来源", ["fetch_url"]),
        PlanStep("汇总为结论", []),
    ],
    # 记忆操作降为单步：多步模板会诱导模型逐条重复调用 add_memory，
    # 且步骤名含“写入”曾触发 rule_write_detected 误判（见 completion/rules.py）
    "memory_operation": [
        PlanStep("记住用户的重要信息", ["add_memory"]),
    ],
}

PLAN_MODE_CONSTRAINT = "Plan 模式：只读分析与方案制定，禁止任何写入/修改/提交操作"


def _extract_goal(message: str, max_len: int = 200) -> str:
    """取消息首行作为目标（去空白、截断）。"""
    raw = (message or "").strip()
    if not raw:
        return ""
    return raw.splitlines()[0].strip()[:max_len]


class PlannerService:
    """最小启发式 Planner + LLM 辅助（G2-B 升级，无状态，可共享单例）。"""

    def __init__(self):
        # 深拷贝模板，避免共享可变对象
        self._templates = {
            k: [PlanStep(s.action, list(s.suggested_tools)) for s in v]
            for k, v in _STEP_TEMPLATES.items()
        }
        # LLM Planner 懒加载（避免循环导入）
        self._llm_planner = None

    def _get_llm_planner(self):
        """懒加载 LLMPlanner 单例。"""
        if self._llm_planner is None:
            from .llm_planner import get_llm_planner
            self._llm_planner = get_llm_planner()
        return self._llm_planner

    async def plan(
        self,
        *,
        message: str,
        mode: str = "build",
        decision: Optional[dict] = None,
        planning_level: Optional[int] = None,
        model_id: str = "qwen-flash",
    ) -> Optional[Plan]:
        """生成任务计划；非任务型请求返回 None。

        G2-B: planning_level >= 2 时优先使用 LLMPlanner，
        LLM 失败时自动 fallback 到 heuristic。

        Args:
            message: 用户请求原文
            mode: "build" / "plan"
            decision: tool_runtime.process 的 decision（含 intent），可缺省
            planning_level: 规划层级（0/1=heuristic，>=2=LLM 辅助）
            model_id: LLM Planner 使用的模型 ID

        Returns:
            Plan 或 None（非任务型请求，task_context 保持 None）
        """
        intent = (decision or {}).get("intent", "general_chat")
        if intent not in TASK_INTENTS:
            return None

        # G2-B: Level >= 2 时尝试 LLM Planner
        if PlanningLevel.allow_llm(planning_level):
            try:
                plan = await self._get_llm_planner().plan(
                    message=message,
                    mode=mode,
                    decision=decision,
                    model_id=model_id,
                )
                plan.planner_source = "llm"  # G2-C: 标记实际来源
                logger.info("LLM Planner 成功生成 Plan: goal=%s, steps=%d",
                            plan.goal, len(plan.steps))
                return plan
            except Exception as e:
                logger.warning("LLM Planner 失败，fallback heuristic: %s", e)

        # Fallback: heuristic（Plan 默认 planner_source="heuristic"）
        return self._plan_heuristic(message=message, mode=mode, decision=decision)

    def _plan_heuristic(
        self,
        *,
        message: str,
        mode: str = "build",
        decision: Optional[dict] = None,
    ) -> Plan:
        """纯启发式计划生成（原 PlannerService.plan 逻辑）。"""
        intent = (decision or {}).get("intent", "general_chat")
        steps = [
            PlanStep(s.action, list(s.suggested_tools))
            for s in self._templates.get(intent, [])
        ]
        constraints: List[str] = []
        if (mode or "build") == "plan":
            constraints.append(PLAN_MODE_CONSTRAINT)

        return Plan(
            goal=_extract_goal(message),
            steps=steps,
            constraints=constraints,
            mode=mode or "build",
        )


# 全局单例（无状态）
_planner = PlannerService()


def get_planner() -> PlannerService:
    return _planner
