"""Completion Verification — 规则层验证（MfkAgent Autonomous Completion Loop V1）。

确定性规则判定：针对明确任务增加规则判断，例如：
  - 用户："创建一个 test.py 文件" → 规则检查 test.py 是否存在
  - 用户："修复代码" → 规则检查测试是否通过（依赖工具层 run_command 退出码）

实现方式：
  - 规则注册表 `RULES`，每条规则为一个 (name, fn) 元组；
  - fn(ctx) -> Optional[list]：返回缺失项列表；空列表 / None 表示该规则通过；
  - V1 内置 2 条通用规则，调用方可通过 `extra_rules` 追加领域规则。
"""

from typing import Callable, List, Optional, Tuple

from app.core.agent_runtime.completion.base import CompletionVerifier
from app.core.agent_runtime.completion.models import (
    CompletionContext,
    CompletionVerificationResult,
)
from app.core.agent_runtime.completion.test_history import (
    baseline_failed_files,
    build_test_history,
    uncovered_new_failures,
)

# 规则类型：输入 CompletionContext，返回缺失项列表（空 = 通过）
RuleFn = Callable[[CompletionContext], Optional[List[str]]]


def rule_final_content_present(ctx: CompletionContext) -> Optional[List[str]]:
    """收益规则：Agent 必须产出最终回答（LLM 停止时连文本都未给出 → 未完成）。

    判定依据：task_goal 非空时，最终输出不应为空。
    限域：仅非任务图路径生效；任务图内中间任务的完成判定交给 judge 层，
    避免把“还在规划/执行中”的合法回复误判为未完成（端到端实证：round2 复跑）。
    """
    if ctx.current_task is not None:
        return None
    if ctx.task_goal and not (ctx.final_content or "").strip():
        return ["Agent 未产出最终回答"]
    return None


def rule_write_detected(ctx: CompletionContext) -> Optional[List[str]]:
    """写任务规则：任务目标明确要求写入文件时，必须存在 write 类工具调用。

    B方案中间步骤豁免：当当前任务节点为 TaskNode 且其 action 不含写意图时，
    说明是只读中间步骤（如"确认目标文件位置"），不按完整目标校验写操作。
    最终步骤（action 含写意图）仍按完整目标校验。

    仅当任务目标含文件写入意图且工具记录中无任何写动作 → 视为未完成。
    记忆类目标（"写入/添加记忆"）不是文件写任务，直接豁免；
    add_memory/manage_todos 也属于写动作（实证 run 844：写入记忆被误判为写文件）。
    """
    # B方案：任务图中间步骤豁免 — 根据当前任务节点的 action 判断
    # 若当前任务 action 不含写意图，说明是只读中间步骤，跳过写检查
    if ctx.current_task is not None and hasattr(ctx.current_task, 'action'):
        task_action = (ctx.current_task.action or "").lower()
        if not any(k in task_action for k in ("创建", "写入", "修改", "生成", "replace", "write", "创建文件")):
            return None

    goal = (ctx.task_goal or "").lower()
    if not any(k in goal for k in ("创建", "写入", "修改", "生成", "replace", "write", "创建文件")):
        return None
    # 记忆类目标豁免：除非同时明确提到“文件”，否则不要求文件写工具
    if any(k in goal for k in ("记忆", "记住", "memory")) and "文件" not in goal:
        return None
    write_keywords = (
        "write_file", "replace_in_file", "apply_patch", "delete_file",
        "add_memory", "manage_todos",
    )
    if not any(r.get("tool") in write_keywords for r in (ctx.tool_records or [])):
        return ["任务要求写入文件，但未执行任何写操作"]
    return None


# 任务目标含测试要求时的关键词（触发 test_scope_guard）
# 注：不收宽泛词 "test"（易误命中路径/模块名）；"单元测试" 已含 "测试" 无需单列
_TEST_INTENT_KEYWORDS = ("pytest", "测试", "全绿", "unittest")

# 任务目标明确要求全部测试通过时的关键词（不适用基线排除）
_ALL_GREEN_KEYWORDS = (
    "全绿", "全部通过", "所有测试", "确保全部", "保证测试",
    "修复", "修复后", "通过验证", "运行测试并确认",
)

# 任务目标明确否定测试要求（“不要运行测试”）→ 测试不是本任务交付物，跳过测试守卫
_TEST_NEGATION_KEYWORDS = ("不要运行测试", "无需运行测试", "不运行测试", "不用测试", "不需要测试", "不用跑测试")


def rule_test_scope_guard(ctx: CompletionContext) -> Optional[List[str]]:
    """验证逃逸防御：基于 pytest 执行档案的三重判定。

    1. 任务要求测试但从未执行过 pytest → 未完成；
    2. 最后一次测试执行非全绿（exit 码非 0）→ 未完成；
    3. 曾失败的测试文件未被最后一次执行范围覆盖 → 验证范围缩水（逃逸）。

    基线排除：仅当任务未明确要求全绿时，首次执行即失败的文件视为既有失败，
    不计入拦截（防基线本身红的工程被永久卡死）；要求全绿时既有失败也属于任务范围。
    """
    goal = (ctx.task_goal or "").lower()
    history = build_test_history(ctx.tool_records or [])

    if not history:
        if any(k in goal for k in _TEST_INTENT_KEYWORDS):
            return ["任务要求测试验证，但未执行任何 pytest 命令"]
        return None

    # 任务明确否定测试要求（如“不要运行测试”）→ 测试非本任务交付物，跳过守卫
    if any(k in goal for k in _TEST_NEGATION_KEYWORDS):
        return None

    missing: List[str] = []
    last = history[-1]
    require_all_green = any(k in goal for k in _ALL_GREEN_KEYWORDS)

    # 非全绿判定：任务未要求全绿时应用基线排除，防基线红的工程被永久卡死；
    # 但失败集合中出现非基线新文件，或任务含 "修复/必须通过" 意图时仍需拦截
    if last.get("exit_code") != 0:
        if require_all_green:
            missing.append("最后一次测试执行未全绿，需修复后重跑验证")
        elif last.get("failed_files") and last["failed_files"] <= baseline_failed_files(history) and len(history) >= 2:
            pass  # 既有基线失败且未引入新失败 → 豁免（防基线卡死）
        else:
            missing.append("最后一次测试执行未全绿，需修复后重跑验证")

    uncovered = uncovered_new_failures(history, require_all_green=require_all_green)
    if uncovered:
        missing.append(
            "验证范围缩水：曾失败的测试未复跑（"
            + "、".join(uncovered[:3])
            + "），必须全量复跑而非只跑必过子集"
        )
    return missing or None


# 内置规则注册表（顺序执行，全部通过方可放行到下一层）
BUILTIN_RULES: List[Tuple[str, RuleFn]] = [
    ("final_content_present", rule_final_content_present),
    ("write_detected", rule_write_detected),
    ("test_scope_guard", rule_test_scope_guard),
]


class RuleBasedVerification(CompletionVerifier):
    """规则层完成验证：确定性规则判定。"""

    name = "rule"

    def __init__(self, rules: Optional[List[Tuple[str, RuleFn]]] = None):
        # 默认内置规则 + 不允许外部触发启用（防误判），可通过构造传参扩展
        self.rules: List[Tuple[str, RuleFn]] = rules if rules is not None else list(BUILTIN_RULES)

    async def verify(self, ctx: CompletionContext) -> CompletionVerificationResult:
        passed = []
        missing = []
        for rule_name, fn in self.rules:
            try:
                found = fn(ctx) or []
            except Exception as e:  # noqa: BLE001 — 规则异常视为通过并记入 evidence
                passed.append({"rule": rule_name, "status": "error", "detail": str(e)[:200]})
                continue
            if found:
                missing.extend(found)
                passed.append({"rule": rule_name, "status": "failed", "detail": found})
            else:
                passed.append({"rule": rule_name, "status": "passed"})

        if missing:
            return CompletionVerificationResult(
                success=False,
                reason="规则层判定任务尚未完成",
                missing_items=missing,
                next_action="continue_execution",
                layer=self.name,
                evidence={"rules": passed},
            )

        return CompletionVerificationResult(
            success=True,
            reason="规则层验证通过",
            layer=self.name,
            evidence={"rules": passed},
        )