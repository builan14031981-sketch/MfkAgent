"""MfkAgent Planner LLM — Phase G2-B 单元测试。

覆盖：
  T1. PlanningLevel.allow_llm() 层级判断
  T2. LLMPlanner.plan() 成功 → 生成 Plan（mock call_once）
  T3. LLMPlanner 调用失败 → fallback heuristic
  T4. LLMPlanner JSON 解析失败 → fallback heuristic
  T5. LLMPlanner 输出空 steps → fallback heuristic
  T6. Level 0/1 → 仅 heuristic，不调用 LLM
  T7. PlannerService.plan() Level>=2 成功路径
  T8. PlannerService.plan() Level>=2 失败 → fallback
  T9. AgentRuntime 执行链回归（basic）
  T10. ContextBuilder planning_level 传递

运行：
  python backend/tests/test_planner_llm_phase_g2b.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import json
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.planner import (  # noqa: E402
    Plan,
    PlanStep,
    PlanningLevel,
    PlannerService,
    get_planner,
    LLMPlanner,
    get_llm_planner,
    TASK_INTENTS,
)
from app.services.model import SingleCallResult  # noqa: E402

results = []
failures = []


def run(name, fn):
    t0 = time.monotonic()
    try:
        detail = fn()
        ok = detail.pop("all_ok", True)
        elapsed = (time.monotonic() - t0) * 1000
        results.append({"name": name, "ok": ok, "detail": detail, "elapsed_ms": round(elapsed)})
        if ok:
            print(f"  PASS  {name}  ({elapsed:.0f}ms)")
        else:
            failures.append(f"{name}: {detail}")
            print(f"  FAIL  {name}  ({elapsed:.0f}ms)")
    except AssertionError as e:
        results.append({"name": name, "ok": False, "detail": str(e), "elapsed_ms": 0})
        failures.append(f"{name}: {e}")
        print(f"  FAIL  {name}\n        {e}")
    except Exception as e:
        results.append({"name": name, "ok": False, "detail": f"异常: {e!r}", "elapsed_ms": 0})
        failures.append(f"{name}: {e!r}")
        print(f"  ERROR {name}\n        {e!r}")


# ──── 辅助函数 ────

def _make_llm_response(goal: str, steps: list, constraints: list = None) -> SingleCallResult:
    """构造 LLM Planner 成功响应。"""
    return SingleCallResult(
        content=json.dumps({
            "goal": goal,
            "steps": steps,
            "constraints": constraints or [],
        }, ensure_ascii=False),
        tool_calls=None,
        finish_reason="stop",
        usage={"total_tokens": 100},
    )


def _make_llm_response_raw(text: str) -> SingleCallResult:
    """构造 LLM Planner 原始文本响应。"""
    return SingleCallResult(
        content=text,
        tool_calls=None,
        finish_reason="stop",
        usage={"total_tokens": 50},
    )


# ═════════════════════════════════════════════════════════════════════════
# T1. PlanningLevel.allow_llm() 层级判断
# ═════════════════════════════════════════════════════════════════════════

def _test_t1_planning_level():
    """验证 PlanningLevel 常量与 allow_llm() 判断。"""
    assert PlanningLevel.HEURISTIC == 0
    assert PlanningLevel.BASIC == 1
    assert PlanningLevel.LLM == 2
    assert PlanningLevel.LLM_THRESHOLD == 2

    # Level 0/1 → 不允许 LLM
    assert PlanningLevel.allow_llm(0) is False
    assert PlanningLevel.allow_llm(1) is False
    assert PlanningLevel.allow_llm(None) is False

    # Level >= 2 → 允许 LLM
    assert PlanningLevel.allow_llm(2) is True
    assert PlanningLevel.allow_llm(3) is True
    assert PlanningLevel.allow_llm(10) is True

    return {
        "HEURISTIC": 0, "BASIC": 1, "LLM": 2, "THRESHOLD": 2,
        "level_0": PlanningLevel.allow_llm(0),
        "level_1": PlanningLevel.allow_llm(1),
        "level_2": PlanningLevel.allow_llm(2),
        "level_none": PlanningLevel.allow_llm(None),
    }


# ═════════════════════════════════════════════════════════════════════════
# T2. LLMPlanner.plan() 成功 → 生成 Plan（mock call_once）
# ═════════════════════════════════════════════════════════════════════════

def _test_t2_llm_planner_success():
    """验证 LLMPlanner 调用 call_once() 成功生成 Plan。"""
    import asyncio

    async def _run():
        llm = get_llm_planner()
        expected_goal = "分析项目性能瓶颈"
        expected_steps = [
            {"action": "定位性能热点代码", "suggested_tools": ["read_file", "run_command"]},
            {"action": "分析根因", "suggested_tools": ["read_file"]},
            {"action": "给出优化建议", "suggested_tools": []},
        ]

        mock_result = _make_llm_response(expected_goal, expected_steps, ["不能修改数据库"])

        with patch("app.core.planner.llm_planner.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_result

            plan = await llm.plan(
                message="分析项目性能",
                mode="build",
                decision={"intent": "system_diagnosis"},
                model_id="qwen-flash",
            )

        # 验证 call_once() 被调用
        assert mock_call.called, "call_once() 应该被调用"
        call_kwargs = mock_call.call_args.kwargs
        assert call_kwargs["model_id"] == "qwen-flash"
        assert call_kwargs["tools"] is None, "Planner 不应传 tools"
        assert call_kwargs["temperature"] == 0.3

        # 验证 Plan 结构
        assert isinstance(plan, Plan)
        assert plan.goal == expected_goal
        assert len(plan.steps) == 3
        assert plan.steps[0].action == "定位性能热点代码"
        assert plan.steps[0].suggested_tools == ["read_file", "run_command"]
        assert plan.constraints == ["不能修改数据库"]
        assert plan.mode == "build"

        # 验证 to_task_context
        tc = plan.to_task_context()
        assert tc["goal"] == expected_goal
        assert tc["current_step"] == "定位性能热点代码"

        return {
            "goal": plan.goal,
            "steps": len(plan.steps),
            "constraints": plan.constraints,
            "call_once_called": mock_call.called,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T3. LLMPlanner 调用失败 → fallback heuristic
# ═════════════════════════════════════════════════════════════════════════

def _test_t3_llm_call_failure_fallback():
    """模拟 LLM call_once() 抛异常 → PlannerService 自动 fallback heuristic。"""
    import asyncio

    async def _run():
        svc = PlannerService()

        with patch("app.core.planner.llm_planner.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("模型服务不可用 (503)")

            plan = await svc.plan(
                message="检查系统状态并诊断网络问题",
                mode="build",
                decision={"intent": "system_diagnosis"},
                planning_level=2,  # Level >= 2，应尝试 LLM
            )

        # 验证：LLM 失败后，应该 fallback 到 heuristic
        assert mock_call.called, "LLM 应该被尝试调用"
        assert plan is not None, "fallback 应返回 heuristic Plan"
        assert plan.goal == "检查系统状态并诊断网络问题"
        assert len(plan.steps) == 3  # system_diagnosis 模板有 3 步
        assert plan.steps[0].action == "采集系统/网络/日志等真实状态信息"

        return {
            "plan_not_none": plan is not None,
            "goal": plan.goal,
            "steps": len(plan.steps),
            "llm_called": mock_call.called,
            "fallback_to_heuristic": True,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T4. LLMPlanner JSON 解析失败 → fallback heuristic
# ═════════════════════════════════════════════════════════════════════════

def _test_t4_parse_failure_fallback():
    """模拟 LLM 返回非法 JSON → PlannerService fallback heuristic。"""
    import asyncio

    async def _run():
        svc = PlannerService()

        # 返回不是 JSON 的文本
        mock_result = _make_llm_response_raw("好的，我来分析一下...这个项目需要优化...")

        with patch("app.core.planner.llm_planner.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_result

            plan = await svc.plan(
                message="分析项目结构",
                mode="build",
                decision={"intent": "file_operation"},
                planning_level=2,
            )

        assert mock_call.called, "LLM 应该被尝试调用"
        assert plan is not None, "fallback 应返回 heuristic Plan"
        assert plan.goal == "分析项目结构"
        assert len(plan.steps) == 3  # file_operation 模板

        return {
            "plan_not_none": plan is not None,
            "goal": plan.goal,
            "steps": len(plan.steps),
            "llm_called": mock_call.called,
            "fallback_to_heuristic": True,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T5. LLMPlanner 输出空 steps → fallback heuristic
# ═════════════════════════════════════════════════════════════════════════

def _test_t5_empty_steps_fallback():
    """模拟 LLM 返回 steps=[] → _parse_response 抛异常 → fallback。"""
    import asyncio

    async def _run():
        svc = PlannerService()

        # LLM 返回 goal 但 steps 为空
        mock_result = _make_llm_response("分析项目", steps=[], constraints=[])

        with patch("app.core.planner.llm_planner.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_result

            plan = await svc.plan(
                message="分析项目结构",
                mode="build",
                decision={"intent": "file_operation"},
                planning_level=2,
            )

        assert mock_call.called
        assert plan is not None, "fallback 应返回 heuristic Plan"
        assert len(plan.steps) == 3  # file_operation 模板有 3 步

        return {
            "plan_not_none": plan is not None,
            "steps": len(plan.steps),
            "fallback": True,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T6. Level 0/1 → 仅 heuristic，不调用 LLM
# ═════════════════════════════════════════════════════════════════════════

def _test_t6_heuristic_only_level_0_1():
    """验证 Level 0/1 时完全不调用 LLM。"""
    import asyncio

    async def _run():
        svc = PlannerService()

        with patch("app.core.planner.llm_planner.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = _make_llm_response("test", [{"action": "x", "suggested_tools": []}])

            # Level 0
            plan0 = await svc.plan(
                message="检查系统状态",
                mode="build",
                decision={"intent": "system_diagnosis"},
                planning_level=0,
            )
            assert not mock_call.called, "Level 0 不应调用 LLM"

            # Level 1
            plan1 = await svc.plan(
                message="检查系统状态",
                mode="build",
                decision={"intent": "system_diagnosis"},
                planning_level=1,
            )
            assert not mock_call.called, "Level 1 不应调用 LLM"

            # Level None
            plan_none = await svc.plan(
                message="检查系统状态",
                mode="build",
                decision={"intent": "system_diagnosis"},
                planning_level=None,
            )
            assert not mock_call.called, "Level None 不应调用 LLM"

        # 验证都返回 heuristic Plan
        assert plan0 is not None and plan1 is not None and plan_none is not None
        assert plan0.goal == "检查系统状态"
        assert plan1.goal == "检查系统状态"
        assert plan_none.goal == "检查系统状态"

        return {
            "level_0_llm_called": False,
            "level_1_llm_called": False,
            "level_none_llm_called": False,
            "all_heuristic": True,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T7. PlannerService.plan() Level>=2 成功路径
# ═════════════════════════════════════════════════════════════════════════

def _test_t7_planner_service_llm_success():
    """验证 PlannerService.plan() 在 Level>=2 时成功走 LLM 路径。"""
    import asyncio

    async def _run():
        svc = PlannerService()

        expected_goal = "分析项目性能瓶颈"
        llm_result = _make_llm_response(
            expected_goal,
            [
                {"action": "定位性能热点", "suggested_tools": ["read_file"]},
                {"action": "给出优化建议", "suggested_tools": []},
            ],
        )

        with patch("app.core.planner.llm_planner.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = llm_result

            plan = await svc.plan(
                message="分析项目性能",
                mode="build",
                decision={"intent": "system_diagnosis"},
                planning_level=2,
                model_id="qwen-flash",
            )

        assert mock_call.called
        assert plan is not None
        assert plan.goal == expected_goal
        assert len(plan.steps) == 2
        assert plan.steps[0].action == "定位性能热点"

        return {
            "goal": plan.goal,
            "steps": len(plan.steps),
            "llm_called": mock_call.called,
            "source": "LLM",
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T8. PlannerService.plan() 非任务型请求 → None（不调 LLM）
# ═════════════════════════════════════════════════════════════════════════

def _test_t8_non_task_returns_none():
    """验证 general_chat 等非任务型请求返回 None，不调用 LLM。"""
    import asyncio

    async def _run():
        svc = PlannerService()

        with patch("app.core.planner.llm_planner.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:

            plan = await svc.plan(
                message="你好，介绍一下自己",
                mode="build",
                decision={"intent": "general_chat"},
                planning_level=2,
            )

        # general_chat → 不走 LLM，直接返回 None
        assert not mock_call.called, "general_chat 不应调用 LLM"
        assert plan is None, "general_chat 应返回 None"

        return {
            "plan_is_none": plan is None,
            "llm_not_called": not mock_call.called,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T9. AgentRuntime 执行链回归
# ═════════════════════════════════════════════════════════════════════════

def _test_t9_agent_runtime_unchanged():
    """验证 AgentRuntime 核心执行链未被 G2-B 破坏。"""
    from app.core.agent_runtime.agent import AgentRuntime, MAX_ROUNDS
    from app.core.agent_runtime.context import AgentContext, AgentResult

    # 验证核心常量
    assert MAX_ROUNDS == 3, "MAX_ROUNDS 应保持 3"

    # 验证 AgentRuntime 类结构
    rt = AgentRuntime()
    assert hasattr(rt, "router"), "应有 router"
    assert hasattr(rt, "context_builder"), "应有 context_builder"
    assert hasattr(rt, "verifier"), "应有 verifier"
    assert hasattr(rt, "run"), "应有 run 方法"
    assert hasattr(rt, "run_stream"), "应有 run_stream 方法"

    # 验证 AgentContext 结构（G2-B 新增 planning_level 字段）
    ctx = AgentContext(
        agent_id="test",
        agent_identity="test identity",
        personality_level=50,
        model_id="test-model",
        planning_level=2,
    )
    assert ctx.planning_level == 2
    assert ctx.identity == "test identity"

    # 验证 AgentResult 结构不变
    result = AgentResult(
        content="test",
        rounds=1,
        finish_reason="stop",
        tool_calls=[],
        metadata={},
    )
    assert result.content == "test"
    assert result.rounds == 1

    return {
        "MAX_ROUNDS": MAX_ROUNDS,
        "has_router": hasattr(rt, "router"),
        "has_run": hasattr(rt, "run"),
        "has_run_stream": hasattr(rt, "run_stream"),
        "planning_level_field": ctx.planning_level,
        "agent_result_ok": result.content == "test",
    }


# ═════════════════════════════════════════════════════════════════════════
# T10. ContextBuilder planning_level 传递
# ═════════════════════════════════════════════════════════════════════════

def _test_t10_context_builder_planning_level():
    """验证 ContextBuildInput 和 AgentContext 正确传递 planning_level。"""
    from app.core.agent_runtime.context_builder import ContextBuildInput, ChatContextBuilder
    from app.core.agent_runtime.context import AgentContext

    # 验证 ContextBuildInput 包含 planning_level 字段
    inp = ContextBuildInput(
        chat_id=1,
        content="test",
        planning_level=2,
    )
    assert inp.planning_level == 2
    assert inp.chat_id == 1
    assert inp.content == "test"

    # 验证默认值
    inp_default = ContextBuildInput(chat_id=1, content="test")
    assert inp_default.planning_level is None

    # 验证 ChatContextBuilder 实例化
    builder = ChatContextBuilder()
    assert hasattr(builder, "_planner_service"), "应有 _planner_service"

    return {
        "planning_level_passed": inp.planning_level == 2,
        "default_none": inp_default.planning_level is None,
        "builder_has_planner": hasattr(builder, "_planner_service"),
    }


# ═════════════════════════════════════════════════════════════════════════
# T11. LLMPlanner 处理 ```json 包裹的响应
# ═════════════════════════════════════════════════════════════════════════

def _test_t11_llm_code_fence_parsing():
    """验证 LLMPlanner._parse_response 能正确处理 ```json 包裹的响应。"""
    llm = get_llm_planner()

    # 模拟 LLM 返回 ```json ... ``` 包裹的 JSON
    raw = """```json
{
  "goal": "分析项目",
  "steps": [
    {"action": "读取文件", "suggested_tools": ["read_file"]}
  ],
  "constraints": []
}
```"""

    plan = llm._parse_response(raw, "分析项目", "build")
    assert plan.goal == "分析项目"
    assert len(plan.steps) == 1
    assert plan.steps[0].action == "读取文件"

    return {
        "goal": plan.goal,
        "steps": len(plan.steps),
        "code_fence_parsed": True,
    }


# ═════════════════════════════════════════════════════════════════════════
# T12. LLMPlanner plan 模式注入只读约束
# ═════════════════════════════════════════════════════════════════════════

def _test_t12_llm_plan_mode_constraint():
    """验证 LLMPlanner 在 plan 模式下注入只读约束。"""
    import asyncio

    async def _run():
        llm = get_llm_planner()

        mock_result = _make_llm_response(
            "分析项目",
            [{"action": "读取文件", "suggested_tools": ["read_file"]}],
        )

        with patch("app.core.planner.llm_planner.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_result

            plan = await llm.plan(
                message="分析项目",
                mode="plan",
                decision={"intent": "file_operation"},
            )

        assert plan.mode == "plan"
        # plan 模式应注入只读约束
        assert any("只读" in c for c in plan.constraints), \
            f"plan 模式应注入只读约束，实际: {plan.constraints}"

        return {
            "mode": plan.mode,
            "has_readonly_constraint": any("只读" in c for c in plan.constraints),
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T13. LLMPlanner.plan() 传递 intent 到 user prompt
# ═════════════════════════════════════════════════════════════════════════

def _test_t13_llm_prompt_contains_intent():
    """验证 LLMPlanner 构建的 user prompt 包含 intent 信息。"""
    import asyncio

    async def _run():
        llm = get_llm_planner()

        mock_result = _make_llm_response(
            "分析项目",
            [{"action": "读取文件", "suggested_tools": ["read_file"]}],
        )

        with patch("app.core.planner.llm_planner.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_result

            await llm.plan(
                message="分析项目",
                mode="build",
                decision={"intent": "file_operation"},
            )

        # 获取发送给 LLM 的 messages（call_once 接收 dict，而非 pydantic 对象）
        messages = mock_call.call_args.kwargs["messages"]
        user_msg = messages[1]["content"]  # messages[0]=system, messages[1]=user

        assert "用户请求: 分析项目" in user_msg
        assert "当前模式: build" in user_msg
        assert "识别意图: file_operation" in user_msg
        assert "请生成执行计划" in user_msg

        # 验证 system prompt
        sys_msg = messages[0]["content"]
        assert "任务规划助手" in sys_msg

        return {
            "user_prompt_has_intent": "file_operation" in user_msg,
            "system_prompt_ok": "任务规划助手" in sys_msg,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T14. Plan 携带 planner_source — LLM 成功路径
# ═════════════════════════════════════════════════════════════════════════

def _test_t14_plan_planner_source_llm():
    """验证 LLM Planner 成功时 Plan.planner_source == 'llm'。"""
    import asyncio

    async def _run():
        svc = PlannerService()

        mock_result = _make_llm_response(
            "分析项目", [{"action": "读取文件", "suggested_tools": ["read_file"]}],
        )

        with patch("app.core.planner.llm_planner.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_result

            plan = await svc.plan(
                message="分析项目",
                mode="build",
                decision={"intent": "file_operation"},
                planning_level=2,
            )

        assert mock_call.called
        assert plan is not None
        assert plan.planner_source == "llm", f"LLM 成功路径 planner_source 应为 'llm'，实际: {plan.planner_source}"

        return {"planner_source": plan.planner_source, "source_is_llm": plan.planner_source == "llm"}

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T15. Plan 携带 planner_source — LLM 失败 fallback 路径
# ═════════════════════════════════════════════════════════════════════════

def _test_t15_plan_planner_source_fallback():
    """验证 LLM 失败 fallback 时 Plan.planner_source != 'llm'。"""
    import asyncio

    async def _run():
        svc = PlannerService()

        with patch("app.core.planner.llm_planner.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("模型服务不可用 (503)")

            plan = await svc.plan(
                message="检查系统状态",
                mode="build",
                decision={"intent": "system_diagnosis"},
                planning_level=2,
            )

        assert mock_call.called, "LLM 应该被尝试"
        assert plan is not None, "fallback 应返回 Plan"
        assert plan.planner_source == "heuristic", \
            f"LLM 失败 fallback 时 planner_source 应为 'heuristic'，实际: {plan.planner_source}"

        return {"planner_source": plan.planner_source, "source_is_heuristic": plan.planner_source == "heuristic"}

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T16. Plan 携带 planner_source — Level 0/1 纯 heuristic
# ═════════════════════════════════════════════════════════════════════════

def _test_t16_plan_planner_source_heuristic():
    """验证 Level 0/1 时 Plan.planner_source == 'heuristic'。"""
    import asyncio

    async def _run():
        svc = PlannerService()

        with patch("app.core.planner.llm_planner.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:

            plan0 = await svc.plan(
                message="检查系统状态",
                mode="build",
                decision={"intent": "system_diagnosis"},
                planning_level=0,
            )
            plan1 = await svc.plan(
                message="检查系统状态",
                mode="build",
                decision={"intent": "system_diagnosis"},
                planning_level=1,
            )

        assert not mock_call.called, "Level 0/1 不应调用 LLM"
        assert plan0 is not None and plan1 is not None
        assert plan0.planner_source == "heuristic", \
            f"Level 0 planner_source 应为 'heuristic'，实际: {plan0.planner_source}"
        assert plan1.planner_source == "heuristic", \
            f"Level 1 planner_source 应为 'heuristic'，实际: {plan1.planner_source}"

        return {
            "level_0_source": plan0.planner_source,
            "level_1_source": plan1.planner_source,
            "llm_not_called": not mock_call.called,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T17. AgentContext.metadata 包含 planner 字段
# ═════════════════════════════════════════════════════════════════════════

def _test_t17_agent_context_planner_metadata():
    """验证 AgentContext.metadata 结构包含 planner 字段。"""
    from app.core.agent_runtime.context import AgentContext

    # 模拟 ContextBuilder 产出的 metadata（含 planner 字段）
    ctx = AgentContext(
        agent_id="test",
        agent_identity="test identity",
        personality_level=50,
        model_id="test-model",
        metadata={
            "mode": "build",
            "use_tools": True,
            "intent": "file_operation",
            "planner_source": "llm",
            "planner_level": 2,
            "planner_goal": "分析项目结构",
            "planner_steps": 3,
        },
    )

    assert ctx.metadata is not None
    assert ctx.metadata["planner_source"] == "llm"
    assert ctx.metadata["planner_level"] == 2
    assert ctx.metadata["planner_goal"] == "分析项目结构"
    assert ctx.metadata["planner_steps"] == 3

    return {
        "planner_source": ctx.metadata["planner_source"],
        "planner_level": ctx.metadata["planner_level"],
        "planner_goal": ctx.metadata["planner_goal"],
        "planner_steps": ctx.metadata["planner_steps"],
    }


# ═════════════════════════════════════════════════════════════════════════
# T18. AgentResult.metadata 透传 context.metadata
# ═════════════════════════════════════════════════════════════════════════

def _test_t18_agent_result_metadata_passthrough():
    """验证 AgentResult.metadata 包含透传的 planner 字段。"""
    from app.core.agent_runtime.context import AgentResult

    # 模拟 AgentRuntime 构造的 AgentResult（含 context.metadata 透传）
    result = AgentResult(
        content="分析完成",
        rounds=2,
        finish_reason="stop",
        tool_calls=[],
        metadata={
            "mode": "build",
            "use_tools": True,
            "intent": "file_operation",
            "planner_source": "llm",
            "planner_level": 2,
            "planner_goal": "分析项目结构",
            "planner_steps": 3,
            "agent_id": "test",
            "model_id": "test-model",
            "personality_level": 50,
            "task_type": "action",
            "confidence": 0.9,
            "reason": "文件操作",
        },
    )

    assert result.metadata["planner_source"] == "llm"
    assert result.metadata["planner_level"] == 2
    assert result.metadata["planner_goal"] == "分析项目结构"
    assert result.metadata["planner_steps"] == 3
    # 原有字段不受影响
    assert result.metadata["agent_id"] == "test"
    assert result.metadata["task_type"] == "action"

    return {
        "planner_source_passed": result.metadata["planner_source"] == "llm",
        "planner_level_passed": result.metadata["planner_level"] == 2,
        "planner_goal_passed": result.metadata["planner_goal"] == "分析项目结构",
        "planner_steps_passed": result.metadata["planner_steps"] == 3,
        "existing_fields_ok": result.metadata["agent_id"] == "test",
    }


# ═════════════════════════════════════════════════════════════════════════
# 执行
# ═════════════════════════════════════════════════════════════════════════

def main() -> int:
    print("=" * 70)
    print("MfkAgent Planner LLM 单元测试（Phase G2-B）")
    print("=" * 70)

    run("T1  PlanningLevel.allow_llm() 层级判断", _test_t1_planning_level)
    run("T2  LLMPlanner.plan() 成功 → 生成 Plan", _test_t2_llm_planner_success)
    run("T3  LLM 调用失败 → fallback heuristic", _test_t3_llm_call_failure_fallback)
    run("T4  JSON 解析失败 → fallback heuristic", _test_t4_parse_failure_fallback)
    run("T5  空 steps → fallback heuristic", _test_t5_empty_steps_fallback)
    run("T6  Level 0/1 → 仅 heuristic", _test_t6_heuristic_only_level_0_1)
    run("T7  PlannerService LLM 成功路径", _test_t7_planner_service_llm_success)
    run("T8  非任务型请求 → None", _test_t8_non_task_returns_none)
    run("T9  AgentRuntime 执行链回归", _test_t9_agent_runtime_unchanged)
    run("T10 ContextBuilder planning_level 传递", _test_t10_context_builder_planning_level)
    run("T11 LLM ```json 包裹解析", _test_t11_llm_code_fence_parsing)
    run("T12 LLM plan 模式只读约束", _test_t12_llm_plan_mode_constraint)
    run("T13 LLM prompt 包含 intent", _test_t13_llm_prompt_contains_intent)
    run("T14 Plan.planner_source LLM 成功", _test_t14_plan_planner_source_llm)
    run("T15 Plan.planner_source fallback", _test_t15_plan_planner_source_fallback)
    run("T16 Plan.planner_source heuristic", _test_t16_plan_planner_source_heuristic)
    run("T17 AgentContext.metadata planner 字段", _test_t17_agent_context_planner_metadata)
    run("T18 AgentResult.metadata 透传", _test_t18_agent_result_metadata_passthrough)

    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        BACKEND_DIR / "tests" / "phase_g2b_planner_llm_report.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# MfkAgent Planner LLM 测试报告（Phase G2-B）\n",
        f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        "## 结果总览\n",
        "| # | 用例 | 结果 | 耗时 |",
        "|---|------|------|------|",
    ]
    for i, r in enumerate(results, 1):
        lines.append(
            f"| {i} | {r['name']} | {'✅ PASS' if r['ok'] else '❌ FAIL'} | {r['elapsed_ms']}ms |"
        )
    passed = sum(1 for r in results if r["ok"])
    lines.append(f"\n**通过率: {passed}/{len(results)}**\n")
    lines.append("## 验证明细\n")
    for i, r in enumerate(results, 1):
        lines.append(f"### {i}. {r['name']}\n")
        d = r["detail"]
        if isinstance(d, dict):
            for k, v in d.items():
                lines.append(f"- {k}: {v}")
        else:
            lines.append(f"- 说明: {d}")
        lines.append("")
        if not r["ok"]:
            lines.append(f"> 失败: {d}\n")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n报告已生成:", report_path)

    print(f"结果: {passed}/{len(results)} 通过")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())