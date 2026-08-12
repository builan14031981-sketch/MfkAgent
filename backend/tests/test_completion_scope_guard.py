# -*- coding: utf-8 -*-
"""Round 2 优化：验证逃逸防御（test_history + rule_test_scope_guard）单测。

覆盖：
  1. 逃逸拦截：全量红 → 只跑必过子集绿 → 判「验证范围缩水」
  2. 定点复跑放行：全量红 → 针对失败文件复跑绿 → 通过
  3. 全量收敛放行：全量红 → 全量绿 → 通过
  4. 基线排除：首次执行即失败的文件视为既有失败，不拦截
  5. 未全绿：最后一次执行 exit 非 0 → 拦截
  6. 任务要求测试但从未跑 pytest → 拦截
  7. 无测试意图且无 pytest 记录 → 不拦截
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.agent_runtime.completion.models import CompletionContext  # noqa: E402
from app.core.agent_runtime.completion.rules import rule_test_scope_guard  # noqa: E402
from app.core.agent_runtime.completion.test_history import (  # noqa: E402
    build_test_history,
    uncovered_new_failures,
)


def _cmd(command: str, result: str, success: bool = True) -> dict:
    return {
        "tool": "run_command",
        "name": "run_command",
        "success": success,
        "status": "success" if success else "failed",
        "arguments": {"command": command},
        "result": result,
    }


RED_FULL = (
    "$ python -m pytest tests -q\n[exit code 1]\n"
    "FAILED tests/test_token_stats.py::test_stats - assert\n"
    "FAILED tests/test_token_stats.py::test_empty - assert\n"
    "=== 3 failed, 29 passed ==="
)
GREEN_SUBSET = (
    "$ python -m pytest tests/test_api_flow.py -q\n[exit code 0]\n=== 6 passed ==="
)
GREEN_TARGET = (
    "$ python -m pytest tests/test_token_stats.py -q\n[exit code 0]\n=== 3 passed ==="
)
GREEN_FULL = "$ python -m pytest tests -q\n[exit code 0]\n=== 32 passed ==="

GOAL_WITH_TEST = "实现功能并编写 pytest 测试，完成后确保全部通过"
GOAL_TEST_NO_ALLGREEN = "实现功能并编写 pytest 测试"
GOAL_NO_TEST = "读取项目结构并汇报"


def _ctx(goal: str, records: list) -> CompletionContext:
    return CompletionContext(task_goal=goal, final_content="done", tool_records=records)


class TestEscapeInterception:
    def test_subset_escape_blocked(self):
        """Round 2 真实逃逸场景：全量红后只跑必过的 test_api_flow.py。"""
        records = [_cmd("python -m pytest tests -q", RED_FULL, success=False),
                   _cmd("python -m pytest tests/test_api_flow.py -q", GREEN_SUBSET)]
        missing = rule_test_scope_guard(_ctx(GOAL_WITH_TEST, records))
        assert missing is not None
        assert any("验证范围缩水" in m for m in missing)
        assert any("test_token_stats.py" in m for m in missing)

    def test_targeted_rerun_allowed(self):
        """定点复跑失败文件并修绿 → 放行（范围覆盖）。"""
        records = [_cmd("python -m pytest tests -q", RED_FULL, success=False),
                   _cmd("python -m pytest tests/test_token_stats.py -q", GREEN_TARGET)]
        assert rule_test_scope_guard(_ctx(GOAL_WITH_TEST, records)) is None

    def test_full_green_allowed(self):
        """全量红 → 全量绿 → 放行。"""
        records = [_cmd("python -m pytest tests -q", RED_FULL, success=False),
                   _cmd("python -m pytest tests -q", GREEN_FULL)]
        assert rule_test_scope_guard(_ctx(GOAL_WITH_TEST, records)) is None

    def test_last_run_red_blocked(self):
        """最后一次执行未全绿 → 拦截。"""
        records = [_cmd("python -m pytest tests -q", RED_FULL, success=False)]
        missing = rule_test_scope_guard(_ctx(GOAL_WITH_TEST, records))
        assert missing is not None
        assert any("未全绿" in m for m in missing)


class TestBaselineExclusion:
    def test_preexisting_failure_not_blocking(self):
        """基线排除（任务未要求全绿）：首次即失败的文件（既有失败）不纳入覆盖要求。

        首跑全量：old_legacy.py（既有）+ test_new.py（新引入）都红；
        修复后只复跑 test_new.py 绿 → 应放行（old_legacy 属基线既有失败）。
        注：若任务要求全绿，则不适用基线排除（见 TestEscapeInterception）。
        """
        red = (
            "$ python -m pytest tests -q\n[exit code 1]\n"
            "FAILED tests/old_legacy.py::test_a - assert\n"
            "FAILED tests/test_new.py::test_b - assert\n"
            "=== 2 failed ==="
        )
        green = "$ python -m pytest tests/test_new.py -q\n[exit code 0]\n=== 1 passed ==="
        records = [_cmd("python -m pytest tests -q", red, success=False),
                   _cmd("python -m pytest tests/test_new.py -q", green)]
        assert uncovered_new_failures(build_test_history(records)) == []
        assert rule_test_scope_guard(_ctx(GOAL_TEST_NO_ALLGREEN, records)) is None
        # 对照：同一记录序列在要求全绿时应拦截（old_legacy 未被覆盖）
        missing = rule_test_scope_guard(_ctx(GOAL_WITH_TEST, records))
        assert missing is not None and any("验证范围缩水" in m for m in missing)

    def test_new_failure_still_tracked_over_baseline(self):
        """要求全绿时基线排除不生效，曾失败的 test_new.py 未被最后范围覆盖仍被追踪。

        首跑全量：old_legacy.py + test_new.py 都红；
        定点复跑 test_new.py 绿；再次全量红（test_new.py 回归失败）；
        最后只跑 old_legacy.py 绿 → test_new.py 未被覆盖，应拦截。
        """
        red1 = (
            "$ python -m pytest tests -q\n[exit code 1]\n"
            "FAILED tests/old_legacy.py::test_a - assert\n"
            "FAILED tests/test_new.py::test_b - assert\n"
            "=== 2 failed ==="
        )
        green_new = "$ python -m pytest tests/test_new.py -q\n[exit code 0]\n=== 1 passed ==="
        red2 = (
            "$ python -m pytest tests -q\n[exit code 1]\n"
            "FAILED tests/old_legacy.py::test_a - assert\n"
            "FAILED tests/test_new.py::test_b - assert\n"
            "=== 2 failed ==="
        )
        green_legacy = "$ python -m pytest tests/old_legacy.py -q\n[exit code 0]\n=== 1 passed ==="
        records = [_cmd("python -m pytest tests -q", red1, success=False),
                   _cmd("python -m pytest tests/test_new.py -q", green_new),
                   _cmd("python -m pytest tests -q", red2, success=False),
                   _cmd("python -m pytest tests/old_legacy.py -q", green_legacy)]
        history = build_test_history(records)
        # 要求全绿 → 不适用基线排除 → test_new.py 被追踪
        assert uncovered_new_failures(history, require_all_green=True) == ["tests/test_new.py"]
        missing = rule_test_scope_guard(_ctx(GOAL_WITH_TEST, records))
        assert missing is not None and any("test_new.py" in m for m in missing)
        # 对照：不要求全绿时 old_legacy/test_new 均属基线 → 不拦截
        assert uncovered_new_failures(history) == []


class TestIntentGuard:
    def test_no_pytest_but_test_required(self):
        """任务要求测试但从未执行 pytest → 拦截。"""
        missing = rule_test_scope_guard(_ctx(GOAL_WITH_TEST, []))
        assert missing is not None
        assert any("未执行任何 pytest" in m for m in missing)

    def test_no_test_intent_no_records_passes(self):
        """无测试意图且无 pytest 记录 → 不拦截。"""
        assert rule_test_scope_guard(_ctx(GOAL_NO_TEST, [])) is None

    def test_windows_path_scope_normalized(self):
        """Windows 反斜杠路径的范围归一化。"""
        red = (
            "$ python -m pytest tests -q\n[exit code 1]\n"
            "FAILED tests\\test_x.py::test_a - assert\n=== 1 failed ==="
        )
        green = "$ python -m pytest tests\\test_x.py -q\n[exit code 0]\n=== 1 passed ==="
        records = [_cmd("python -m pytest tests -q", red, success=False),
                   _cmd("python -m pytest tests\\test_x.py -q", green)]
        assert rule_test_scope_guard(_ctx(GOAL_WITH_TEST, records)) is None
