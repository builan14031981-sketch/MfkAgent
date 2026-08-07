"""Runtime 状态管理 — Phase E5 正式化：规范状态机 + 事件类型注册表。

单一事实来源：
  - `RuntimePhase`        ：AgentRun 生命周期各阶段（pending → 活跃阶段 → 终态）
  - `VALID_TRANSITIONS`   ：合法状态流转表（transition 校验用）
  - `RuntimeEventType`    ：RuntimeEvent.event_type 规范注册表（回放/审计/前端判别）

设计原则：
  - AgentRun.status（running/completed/failed/cancelled）是粗粒度生命周期；
    AgentRun.state（本模块 RuntimePhase）是细粒度阶段，由 RuntimeState 表记录流转历史。
  - 非法流转不抛出异常：仅记日志并拒绝更新（旁路语义，绝不阻断 Agent 执行）。
"""

from enum import Enum
from typing import Dict, FrozenSet, Set


class RuntimePhase(str, Enum):
    """AgentRun 生命周期阶段（pending → 活跃阶段 → 终态）。"""

    PENDING = "pending"
    BUILDING_CONTEXT = "building_context"   # Context Builder 组装
    ROUTING = "routing"                     # Task Router 决策
    LLM_CALL = "llm_call"                   # 单次模型调用（可多轮）
    TOOL_EXECUTION = "tool_execution"       # 工具执行（含审批）
    VERIFYING = "verifying"                 # Phase E4 程序化验证
    COMPLETING = "completing"               # 收尾（持久化 / 总结）
    COMPLETED = "completed"                 # 终态：正常结束
    FAILED = "failed"                       # 终态：异常终止
    CANCELLED = "cancelled"                 # 终态：流断开 / 取消


# 活跃阶段（非终态）：执行过程中允许互转
_ACTIVE_PHASES: FrozenSet[str] = frozenset({
    RuntimePhase.BUILDING_CONTEXT.value,
    RuntimePhase.ROUTING.value,
    RuntimePhase.LLM_CALL.value,
    RuntimePhase.TOOL_EXECUTION.value,
    RuntimePhase.VERIFYING.value,
    RuntimePhase.COMPLETING.value,
})

# 终态：不可再流转
TERMINAL_PHASES: FrozenSet[str] = frozenset({
    RuntimePhase.COMPLETED.value,
    RuntimePhase.FAILED.value,
    RuntimePhase.CANCELLED.value,
})

# 初始阶段
INITIAL_PHASE = RuntimePhase.PENDING.value


def _build_transition_map() -> Dict[str, Set[str]]:
    """构造合法流转表。

    规则：
      - pending → 任意活跃阶段或终态
      - 活跃阶段 → 其它活跃阶段（同阶段循环允许）、任意终态
      - 终态 → 不可再流转（空集）
    """
    mapping: Dict[str, Set[str]] = {}
    all_phases = {p.value for p in RuntimePhase}

    mapping[INITIAL_PHASE] = set(all_phases) - {INITIAL_PHASE}

    for phase in _ACTIVE_PHASES:
        mapping[phase] = set(all_phases) - {INITIAL_PHASE, phase}

    for phase in TERMINAL_PHASES:
        mapping[phase] = set()

    return mapping


VALID_TRANSITIONS: Dict[str, Set[str]] = _build_transition_map()


def is_valid_transition(from_state: str, to_state: str) -> bool:
    """判断 from_state → to_state 是否为合法流转（未知状态一律拒绝）。"""
    return to_state in VALID_TRANSITIONS.get(from_state or INITIAL_PHASE, set())


class RuntimeEventType(str, Enum):
    """RuntimeEvent.event_type 规范注册表（与 SSE 协议顶层 type 对齐 + E5 扩展）。"""

    TEXT = "text"
    THINKING = "thinking"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    TOOL_APPROVAL = "tool_approval"
    TOOL_CALLS = "tool_calls"
    VERIFY_RESULT = "verify_result"
    VERIFICATION_FAILED = "verification_failed"
    STATE_CHANGE = "state_change"   # E5：AgentRun.state 阶段流转
    # G4-B: TaskGraph 任务级生命周期事件
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    # G4-C: 依赖失败/图中断导致的后继任务跳过
    TASK_SKIPPED = "task_skipped"
    # G6-A: Token 水位监控
    TOKEN_USAGE = "token_usage"
    FINISH = "finish"
    ERROR = "error"


RUNTIME_EVENT_TYPES: FrozenSet[str] = frozenset(t.value for t in RuntimeEventType)


def is_registered_event_type(event_type: str) -> bool:
    """事件类型是否为注册表内规范类型（未知类型仍可写，仅记日志）。"""
    return event_type in RUNTIME_EVENT_TYPES
