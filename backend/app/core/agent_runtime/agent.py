"""Agent Runtime Phase E1+E4 — 统一执行链路

职责：
  1. 唯一执行入口（Chat API → AgentRuntime → Context Builder → Execution Loop）
  2. Execution Loop 控制多轮工具调用（判断是否继续 / 管理 tool round / 行为决策）
  3. 调用 model_service.call_once() / stream_once()（单次 LLM 调用）
  4. 工具执行 + 结果回喂 + 审批闭环
  5. 支持普通执行（run）与流式输出（run_stream）

Phase E4 新增：
  - Action → Observation → Verification → Decision → Finish / Retry
  - 工具执行完成后对本轮成功动作运行程序化验证（write_file 重读 / run_command 退出码）
  - 验证失败 → 向 LLM 注入反馈消息，进入下一轮重新执行；通过 → 继续/结束
"""

from typing import Any, Awaitable, Callable, List, Optional
import asyncio
import os
import re

from .router import TaskRouter
from .context import AgentContext, AgentResult
from .context_builder import ContextBuilder, get_default_context_builder, build_test_infra_summary
from .recorder import runtime_event_recorder
from .states import RuntimePhase
from .task_graph_state import TaskGraphState
from .personas import get_persona_prompt
from app.core.task_graph.models import TaskNode
from .model_context_config import get_model_max_tokens, compute_watermark
from app.core.verification import verifier as default_verifier
from app.services.model import ModelNotFoundError, ModelConfigError
from app.core.tool_runtime.strategy import get_strategy_engine, StrategyStatus
from app.core.agent_runtime.completion import (
    CompletionContext,
    CompletionPipeline,
)
from app.core.agent_runtime.completion.base import CompletionVerifier

# ──── 执行循环最大轮次 ────
MAX_ROUNDS = 10
MAX_STREAM_ROUNDS = 10
DEFAULT_MAX_TOOL_ROUNDS = 10

# ──── G6-B Auto: 自动压缩触发配置 ────
COMPRESS_WATERMARK_THRESHOLD = 50.0   # 上下文水位超过 50% 触发自动压缩（留足压缩后继续对话的余量）
COMPRESS_MIN_INTERVAL_ROUNDS = 2      # 两次自动压缩间的最小轮次间隔（防反复触发）

# ──── T9: 缓存友好压缩 ────
# 灰度开关：settings 表 key。T91 灰度放开 —— 缺失/值非法/DB 不可用时默认开启
# （摘要调用复用主对话前缀 + 自批评为默认路径）。
# 回滚路径：settings 显式置 false/0/off/no 即恢复旧摘要调用路径
# （独立两条消息 prompt 只发 middle 段拼接、不做自批评），无需回滚代码。
_CACHE_AWARE_COMPACTION_SETTING_KEY = "cache_aware_compaction_enabled"


def is_cache_aware_compaction_enabled() -> bool:
    """读取 cache_aware_compaction_enabled 开关（T91 默认开，显式 false 回滚）。

    默认开：settings 缺失/值非法/DB 不可用时启用"摘要调用复用主对话前缀 + 自批评"。
    回滚路径：settings 显式置 false/0/off/no 即恢复旧摘要调用路径
    （独立两条消息 prompt 只发 middle 段拼接、不做自批评），无需回滚代码。
    """
    try:
        from app.core.database import SessionLocal
        from app.models.agent import Setting

        db = SessionLocal()
        try:
            row = db.query(Setting).filter(Setting.key == _CACHE_AWARE_COMPACTION_SETTING_KEY).first()
        finally:
            db.close()
        if row is None or row.value is None:
            return True  # T91: 默认开（灰度已放开）
        # T91 opt-out 语义：仅显式 false/0/off/no 回滚旧路径；其余（true/1/on/yes/非法值）默认开
        return str(row.value).strip().lower() not in ("false", "0", "off", "no")
    except Exception:  # noqa: BLE001 — DB 不可用时按默认开启处理
        return True

# ──── Phase 12: Completion Loop V1 配置 ────
DEFAULT_MAX_COMPLETION_RETRY = 3

# ──── Phase 11: 写操作工具集合（用于强制自查判定）────
WRITE_TOOLS = {"write_file", "replace_in_file", "apply_patch", "delete_file", "run_command"}

# ──── Phase 11: 倒数预警与自查提示文本 ────
COUNTDOWN_WARNING = "[系统提示]: 你的工具调用轮次即将达到上限，请在下一轮结束工具调用并向用户总结最终结果。"
SELF_CHECK_PROMPT = "[系统强制自查]: 你在本次任务中进行了代码或文件修改。请仔细核对改动，确保没有引入语法错误、格式错乱或非预期的功能破坏。确认无误后给出最终汇报。"

# ──── Round 3 修复: 剥除残留的工具调用序列化文本 ────
_TOOL_CALL_BLOCK_RE = re.compile(
    r"<tool_call>.*?</tool_call>|"
    r"<arg_key>.*?</arg_key>|"
    r"<arg_value>.*?</arg_value>|"
    r"<tool_call_id>.*?</tool_call_id>",
    flags=re.DOTALL | re.IGNORECASE,
)


def _strip_tool_call_blocks(content: str) -> str:
    """移除 LLM 输出中残留的 <tool_call> / <arg_*_> 序列化文本，保留正常正文。"""
    if not content:
        return ""
    stripped = _TOOL_CALL_BLOCK_RE.sub("", content)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    return stripped

# ──── Phase 3.5: Runtime Context 边界隔离标记 ────

_RUNTIME_CTX_PREAMBLE = (
    "<runtime_context>\n"
    "来源: MfkAgent Runtime\n"
    "说明: 以下内容为系统内部执行辅助信息，不是用户输入。\n"
    "规则:\n"
    "- 不代表用户要求\n"
    "- 不覆盖用户真实意图\n"
    "- 不应作为用户原话引用\n"
    "- 不能主动向用户展示内部标签\n"
    "- 不能因为 Runtime Context 自动切换角色\n"
    "内容:\n"
)

_RUNTIME_CTX_SUFFIX = "</runtime_context>"


def _wrap_runtime_context(content: str, source: str = "MfkAgent Runtime") -> str:
    """将 Runtime 内部上下文包装为隔离标记块，防止 LLM 误认为用户输入。

    Args:
        content: 原始上下文内容
        source: 来源标识（如 MfkAgent TaskGraph / MfkAgent AgentRouter）

    Returns:
        带边界标记的完整上下文块
    """
    preamble = _RUNTIME_CTX_PREAMBLE.replace("来源: MfkAgent Runtime", f"来源: {source}")
    return preamble + content + "\n" + _RUNTIME_CTX_SUFFIX


def _apply_turn_reminder(messages: list, reminder: Optional[str]) -> list:
    """T1 缓存前缀契约：把本轮 turn_reminder 包裹到最后一条 user 消息副本末尾。

    逐轮变化的 ⑦⑧⑨⑩（intent_hint/task_context/tool_guidance/attachments）以
    <system-reminder> 注入消息尾部，使 system prompt 保持多轮字节稳定、命中
    Provider 前缀缓存。仅修改发往 LLM 的 messages 副本（copy-on-write），
    绝不改动数据库里的历史消息。reminder 为空时原样返回。
    """
    if not reminder:
        return messages
    for idx in range(len(messages) - 1, -1, -1):
        m = messages[idx]
        if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str):
            messages[idx] = {**m, "content": m["content"] + "\n\n" + reminder}
            break
    return messages


# ──── T4: run() 消费者侧（事件聚合 + pending 续跑）────

_pending_continuations: set = set()  # pending_approval 后台续跑任务引用（防 GC）


async def _drain_agent_stream(stream, aggregator: "_AgentResultAggregator", stop_on_approval: bool = True):
    """drain run_stream() 事件流喂给聚合器。

    抉择卡沿用旧契约：非流式不挂起，自动采纳推荐项（resolve 后，下一次
    __anext__ 进入 complete_choice 时 Future 已就绪，立即返回）。
    stop_on_approval=True 时遇首个 tool_approval 即返回该事件（generator 悬停
    在该 yield 上，尚未进入 complete_approval 等待）；流自然结束返回 None。
    """
    from app.core.tool_runtime.choice import choice_registry

    async for event in stream:
        etype = event.get("type")
        if etype == "choice_request":
            # 旧行为保留：自动采纳推荐项（与 legacy support_approval=False 分支一致）
            choice_registry.resolve(event.get("choice_id", ""), {
                "selected": None,
                "custom_text": None,
                "note": "（非流式接口不支持交互抉择，已自动采纳推荐项）",
            })
            continue
        if etype == "tool_approval" and stop_on_approval:
            return event
        aggregator.feed(event)
    return None


class _AgentResultAggregator:
    """把 run_stream() 事件流聚合为与旧 run() 返回结构兼容的 AgentResult。"""

    def __init__(self, context: AgentContext):
        self.context = context
        self._content_parts: list = []
        self._finish_reason = "stop"
        self._tool_calls: list = []
        self._usage_event: Optional[dict] = None
        self._task_graph = None
        self._llm_calls = 0

    def feed(self, event: dict) -> None:
        etype = event.get("type")
        if etype == "text":
            self._content_parts.append(event.get("content", ""))
        elif etype == "finish":
            self._finish_reason = event.get("finish_reason", "stop")
        elif etype == "tool_calls":
            self._tool_calls = event.get("calls") or self._tool_calls
        elif etype == "token_usage":
            self._usage_event = event
        elif etype == "task_graph":
            self._task_graph = event.get("task_graph")
        elif etype == "state_change" and event.get("state") == RuntimePhase.LLM_CALL.value:
            self._llm_calls += 1
        elif etype == "completion_verify_failed":
            # 完成验证驳回 → 该轮文本被反馈重试取代，不进入最终 content（对齐旧实现
            # task_content 末轮覆写语义；验证通过路径不受影响）
            self._content_parts = []
        elif etype == "task_started":
            # 旧实现口径：final_content 逐任务覆写（最后一个任务的内容胜出）
            self._content_parts = []

    def _usage(self) -> Optional[dict]:
        if not self._usage_event:
            return None
        usage = {
            k: self._usage_event[k]
            for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            if k in self._usage_event
        }
        if "cached_tokens" in self._usage_event:
            usage["cached_tokens"] = self._usage_event["cached_tokens"]
        return usage

    def _base_metadata(self) -> dict:
        ctx = self.context
        ctx_meta = ctx.metadata or {}
        metadata = {
            # G2-C: 透传 ContextBuilder metadata（含 T1 turn_reminder / T4 TaskRouter 决策）
            **{k: v for k, v in ctx_meta.items() if not k.startswith("_t4_")},
            "agent_id": ctx.agent_id,
            "model_id": ctx.model_id,
            "personality_level": ctx.personality_level,
        }
        # TaskRouter 决策（统一实现写入 context.metadata；仅写 metadata，不改变执行路径）
        for key in ("task_type", "intent", "confidence", "reason"):
            if key in ctx_meta:
                metadata[key] = ctx_meta[key]
        metadata["token_watermark"] = self._usage_event
        if self._task_graph is not None:
            metadata["task_graph"] = self._task_graph
        if "_t4_completion" in ctx_meta:
            metadata["completion"] = ctx_meta["_t4_completion"]
        return metadata

    def build(self) -> AgentResult:
        content = "".join(self._content_parts)
        # 旧实现口径：空回复兜底文案，杜绝 content=None/空串导致的消息悬空
        if not content.strip():
            content = "已为您完成相关的处理与工具调用。" if self._tool_calls else "处理完成。"
        return AgentResult(
            content=content,
            usage=self._usage(),
            rounds=self._llm_calls or 1,
            finish_reason=self._finish_reason,
            tool_calls=self._tool_calls,
            metadata=self._base_metadata(),
        )

    def build_pending(self, pending: dict) -> AgentResult:
        metadata = self._base_metadata()
        metadata["pending_approval"] = pending
        return AgentResult(
            content="".join(self._content_parts),  # pending 不做空回复兜底：轮次尚未收尾
            usage=None,
            rounds=self._llm_calls or 1,
            finish_reason="pending_approval",
            tool_calls=self._tool_calls,
            metadata=metadata,
        )


class AgentRuntime:
    """Agent 统一执行入口 — Phase E1。

    run() 流程（普通执行）：
      1. Context Builder（暂留，透传）
      2. TaskRouter.route() → 任务类型决策
      3. Execution Loop（最多 MAX_ROUNDS 轮）:
         a. call_once() → 单次非流式 LLM 调用
         b. 无 tool_calls → 最终回答，退出循环
         c. 有 tool_calls → 执行工具 → 回喂结果 → 继续循环
      4. 返回 AgentResult

    run_stream() 流程（流式输出）：
      1. Context Builder（暂留，透传）
      2. Execution Loop（最多 MAX_STREAM_ROUNDS 轮）:
         a. stream_once() → 单次流式 LLM 调用（透传 text/thinking/tool_calls/finish）
         b. 无 tool_calls → 输出文本，结束
         c. 有 tool_calls → 执行工具（含审批）→ 回喂结果 → 继续
         d. 无结构化调用时尝试 Normalizer 解析非标准调用
      3. 事件流（text/thinking/tool_start/tool_result/tool_approval/verify_result/finish/error）

    Phase E4：Action → Verification → Decision；验证失败注入反馈驱动下一轮重试。
    """

    def __init__(self, context_builder: ContextBuilder = None, verifier=None, completion_verifier: CompletionVerifier = None):
        self.router = TaskRouter()
        self.context_builder = context_builder or get_default_context_builder()
        self.verifier = verifier or default_verifier
        # Phase 12: Completion Loop V1 — 完成验证器（None → 按 context 开关惰性构建；
        # 显式传入时使用自定义实现；默认三层管道，LLM Judge 仅在 context.completion_verification=True 时启用）
        self.completion_verifier = completion_verifier
        # G4-A: TaskGraph 状态机（初始为空，由 init_task_graph 注入）
        self.task_graph_state: Optional[TaskGraphState] = None

    def _resolve_completion_verifier(self, context: AgentContext) -> CompletionVerifier:
        """解析完成验证器：显式注入优先；否则构建三层管道（Judge 按 context 开关启用）。"""
        if self.completion_verifier is not None:
            return self.completion_verifier
        use_judge = getattr(context, "completion_verification", None) is True
        return CompletionPipeline(use_llm_judge=use_judge)

    # ──── G6-A: Token 水位监控 ────

    def _build_token_usage_event(self, usage: dict, model_id: str) -> dict:
        """构建 token_usage 事件 payload。

        Args:
            usage: LLM 返回的 usage 字典（含 prompt_tokens / completion_tokens）
            model_id: 模型 ID

        Returns:
            token_usage 事件 dict
        """
        if not usage:
            return {
                "type": "token_usage",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cached_tokens": 0,
                "model_max_tokens": get_model_max_tokens(model_id),
                "watermark_percentage": 0.0,
            }

        prompt_tokens = usage.get("prompt_tokens", 0) or 0
        completion_tokens = usage.get("completion_tokens", 0) or 0
        total_tokens = usage.get("total_tokens") or (prompt_tokens + completion_tokens)
        max_tokens = get_model_max_tokens(model_id)
        watermark = compute_watermark(total_tokens, model_id)

        # T1: 前缀缓存命中 token 透出（model.py 已归一化为 usage["cached_tokens"]；
        # 此处兜底兼容原始字段 prompt_tokens_details.cached_tokens / prompt_cache_hit_tokens）
        cached_tokens = usage.get("cached_tokens")
        if cached_tokens is None:
            details = usage.get("prompt_tokens_details")
            if isinstance(details, dict):
                cached_tokens = details.get("cached_tokens")
            if not cached_tokens:
                cached_tokens = usage.get("prompt_cache_hit_tokens") or 0
        try:
            cached_tokens = int(cached_tokens or 0)
        except (TypeError, ValueError):
            cached_tokens = 0

        return {
            "type": "token_usage",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "model_max_tokens": max_tokens,
            "watermark_percentage": watermark,
        }

    # ──── G4-A: TaskGraph 状态机集成 ────

    def init_task_graph(self, plan) -> TaskGraphState:
        """从 Plan 构建 TaskGraph 并初始化状态机。

        Args:
            plan: Plan 对象或 None

        Returns:
            TaskGraphState: 初始化后的状态机实例
        """
        self.task_graph_state = TaskGraphState.from_plan(plan)
        return self.task_graph_state

    def get_next_ready_task(self):
        """获取下一个可执行的 TaskNode（pending + 依赖全 completed）。

        Returns:
            TaskNode 或 None（全部完成或被阻塞时）
        """
        if self.task_graph_state is None:
            return None
        return self.task_graph_state.get_next_ready_task()

    def update_task_status(self, task_id: str, new_status: str) -> bool:
        """更新指定节点的状态。

        Args:
            task_id: 节点 ID（如 task_0）
            new_status: 新状态（running / completed / failed / skipped）

        Returns:
            bool: True 表示更新成功
        """
        if self.task_graph_state is None:
            return False
        return self.task_graph_state.update_task_status(task_id, new_status)

    # ──── G4-C: TaskGraph 任务事件 / 失败处理辅助 ────

    def _task_event_payload(self, task, status: str, error: Optional[str] = None) -> dict:
        """构建任务级事件 payload（含 step_index / total_steps 进度字段）。

        G4-C current_step 同步：不修改 Plan，进度由 TaskGraphState 追踪并随事件透出。
        """
        payload = {
            "task_id": task.id,
            "action": task.action,
            "status": status,
        }
        if self.task_graph_state is not None:
            payload["step_index"] = self.task_graph_state.get_step_index(task.id)
            payload["total_steps"] = self.task_graph_state.total_steps
        if error:
            payload["error"] = str(error)[:200]
        return payload

    async def _handle_task_failure(self, run_id, current_task, error) -> bool:
        """单任务异常处理（run 非流式路径）：先尝试反思自愈，失败则降级。

        战略方向（Auto-Healing）：
          1. 先尝试 _reflect_and_heal 反思并注入修复任务
          2. 如果反思成功 → 不标记失败，继续执行循环（返回 True）
          3. 如果反思失败 → 降级到原始失败路径（failed + 级联 skip）

        G4-C 状态一致性：当前节点 → failed，依赖链上 pending 节点 → skipped；
        AgentRun 本身仍正常收尾（completed），失败以 task_failed / task_skipped 事件记录。

        Returns:
            bool: True 表示反思成功应继续执行，False 表示已降级为失败
        """
        if self.task_graph_state is None:
            return False

        # 战略方向: 尝试反思自愈
        healed = await self._reflect_and_heal(
            current_task,
            str(error),
            run_id=run_id,
        )
        if healed:
            # 反思成功：不标记失败，让外层循环继续取下一个就绪任务
            return True

        # 降级：原始失败路径
        skipped = self.task_graph_state.mark_failed(current_task.id, str(error)[:200])
        runtime_event_recorder.emit(
            run_id,
            "task_failed",
            self._task_event_payload(current_task, "failed", error=str(error)),
        )
        for skip_id in skipped:
            skip_node = self.task_graph_state.get_task(skip_id)
            if skip_node is not None:
                runtime_event_recorder.emit(
                    run_id,
                    "task_skipped",
                    self._task_event_payload(skip_node, "skipped"),
                )
        return False

    def _skip_remaining_and_emit(self, run_id) -> None:
        """图中断兜底（run 非流式路径）：剩余 pending 节点全部 skipped + 事件。

        保证 is_all_done() 收敛到 True，不存在"永远 pending"的悬空节点。
        """
        if self.task_graph_state is None:
            return
        for skip_id in self.task_graph_state.mark_pending_skipped():
            skip_node = self.task_graph_state.get_task(skip_id)
            if skip_node is not None:
                runtime_event_recorder.emit(
                    run_id,
                    "task_skipped",
                    self._task_event_payload(skip_node, "skipped"),
                )

    def _task_graph_summary(self) -> Optional[dict]:
        """任务图进度摘要（run 结果 metadata 用）；无图返回 None。"""
        if self.task_graph_state is None:
            return None
        return self.task_graph_state.get_progress()

    # ──── 战略4: Agent 状态可视化 ────

    @staticmethod
    def _build_agent_state_event(
        agent_role: str,
        status: str,
        action_detail: str,
        current_task_id: Optional[str] = None,
        task_progress: str = "",
    ) -> dict:
        """构建 agent_state_update 事件 payload。

        Args:
            agent_role: 当前 Agent 角色名（如 "Coder Agent"）
            status: 状态 — "working" | "waiting_for_tool" | "completed" | "error"
            action_detail: 具体动作描述（如 "正在分析项目结构"）
            current_task_id: 正在执行的 Task ID
            task_progress: 进度描述（如 "任务 1/5"）
        """
        return {
            "agent_role": agent_role,
            "status": status,
            "action_detail": action_detail,
            "current_task_id": current_task_id,
            "task_progress": task_progress,
        }

    def _build_task_progress(self, current_task_id: Optional[str] = None) -> str:
        """构建任务进度字符串（如 "任务 1/5"）。"""
        if self.task_graph_state is None:
            return ""
        total = self.task_graph_state.total_steps
        if total <= 0:
            return ""
        if current_task_id:
            idx = self.task_graph_state.get_step_index(current_task_id)
            if idx >= 0:
                return f"任务 {idx + 1}/{total}"
        # 无 current_task_id 时，用已完成数推算
        progress = self.task_graph_state.get_progress()
        done = progress.get("completed", 0) + progress.get("failed", 0) + progress.get("skipped", 0)
        return f"任务 {done}/{total}"

    # ──── Agent 角色显示名映射 ────

    AGENT_ROLE_DISPLAY_NAMES: dict[str, str] = {
        "coding_agent": "Coder Agent",
        "research_agent": "Research Agent",
        "default_agent": "Default Agent",
    }

    @staticmethod
    def _agent_role_display_name(assigned_agent: str) -> str:
        """将内部 assigned_agent key 转为前端展示用的角色名。"""
        return AgentRuntime.AGENT_ROLE_DISPLAY_NAMES.get(
            assigned_agent, assigned_agent or "Default Agent"
        )

    # ──── 战略方向: TaskGraph 动态自愈与反思 (Auto-Healing & Reflection) ────

    REFLECTION_MODEL = "qwen-flash"  # 反思用轻量模型，降低成本
    REFLECTION_MAX_TOKENS = 512
    REFLECTION_TEMPERATURE = 0.3

    REFLECTION_PROMPT_TEMPLATE = (
        "你是任务执行诊断专家。以下任务在执行过程中遭遇了失败，请分析原因并给出修复方案。\n\n"
        "【失败任务】\n{task_action}\n\n"
        "【错误信息】\n{error_message}\n\n"
        "请以 JSON 格式输出修复方案（只输出 JSON，不要其他内容）：\n"
        '{{"analysis": "根因分析（一句话）", "fix_action": "修复动作描述", "suggested_tools": ["工具名1", "工具名2"]}}\n\n'
        "如果无法修复，请输出：\n"
        '{{"analysis": "无法修复的原因", "fix_action": "", "suggested_tools": []}}'
    )

    async def _reflect_and_heal(
        self,
        current_task,
        error: str,
        *,
        model_id: Optional[str] = None,
        run_id: Optional[int] = None,
    ) -> Optional[TaskNode]:
        """任务失败后尝试 LLM 反思并动态注入修复任务。

        流程：
          1. 自愈深度上限校验（连续失败达 max_heal_depth 直接阻断，走降级）
          2. 构造 Reflection Prompt，调用轻量模型分析错误
          3. 解析 LLM 返回的 JSON 修复方案
          4. 如果方案有效，通过 dynamic_append_task 注入新节点
          5. 失败时优雅降级，不阻断原有错误处理流程

        Args:
            current_task: 失败的任务节点
            error: 错误信息
            model_id: 反思模型 ID（默认 REFLECTION_MODEL）
            run_id: 运行记录 ID（用于事件广播）

        Returns:
            Optional[TaskNode]: 成功时返回注入的修复节点（heal_N），
                失败或触达自愈上限时返回 None（调用方据此降级到原始失败）
        """
        if self.task_graph_state is None or current_task is None:
            return None

        # 自愈深度上限：连续失败达到 max_heal_depth 后阻断反思，直接降级
        if not self.task_graph_state.can_heal(current_task.id):
            if run_id:
                runtime_event_recorder.emit(run_id, "agent_state_update",
                    self._build_agent_state_event(
                        agent_role=self._agent_role_display_name(
                            current_task.assigned_agent if current_task else "default_agent"
                        ),
                        status="error",
                        action_detail="已到达自愈上限，停止修复尝试，任务判定失败",
                        current_task_id=current_task.id if current_task else None,
                        task_progress=self._build_task_progress(current_task.id if current_task else None),
                    ))
            return None

        # 发送反思开始事件
        if run_id:
            runtime_event_recorder.emit(run_id, "agent_state_update",
                self._build_agent_state_event(
                    agent_role=self._agent_role_display_name(
                        current_task.assigned_agent if current_task else "default_agent"
                    ),
                    status="working",
                    action_detail="触发自我反思，分析错误原因...",
                    current_task_id=current_task.id if current_task else None,
                    task_progress=self._build_task_progress(current_task.id if current_task else None),
                ))

        # 构造反思 Prompt
        prompt = self.REFLECTION_PROMPT_TEMPLATE.format(
            task_action=getattr(current_task, "action", str(current_task)),
            error_message=error[:1000],
        )

        try:
            from app.services.model import model_service
            result = await model_service.call_once(
                model_id=model_id or self.REFLECTION_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个 JSON 输出专家，只输出 JSON，不输出任何其他内容。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.REFLECTION_TEMPERATURE,
                max_tokens=self.REFLECTION_MAX_TOKENS,
                tools=None,
            )
            response_text = (result.content or "").strip()
        except Exception:
            # LLM 调用失败 → 降级
            return None

        if not response_text:
            return None

        # 解析 JSON 修复方案
        import json as _json
        try:
            # 提取 JSON 块（兼容 markdown code block）
            if "```" in response_text:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start >= 0 and end > start:
                    response_text = response_text[start:end]
            plan = _json.loads(response_text)
        except Exception:
            return None

        fix_action = (plan.get("fix_action") or "").strip()
        if not fix_action:
            # LLM 判断无法修复 → 降级
            return None

        suggested_tools = plan.get("suggested_tools") or []

        # 动态注入修复任务
        new_task = self.task_graph_state.dynamic_append_task(
            action=fix_action,
            parent_task_id=current_task.id,
            suggested_tools=suggested_tools,
            assigned_agent=getattr(current_task, "assigned_agent", "default_agent"),
            task_type=getattr(current_task, "task_type", "action"),
        )

        if new_task is None:
            return None

        # 发送修复注入事件
        if run_id:
            runtime_event_recorder.emit(run_id, "agent_state_update",
                self._build_agent_state_event(
                    agent_role=self._agent_role_display_name(
                        current_task.assigned_agent if current_task else "default_agent"
                    ),
                    status="working",
                    action_detail=f"动态生成修复计划，恢复执行: {fix_action[:80]}",
                    current_task_id=new_task.id,
                    task_progress=self._build_task_progress(new_task.id),
                ))

        return new_task

    # ──── G6-B: 智能会话压缩引擎 ────

    DEFAULT_KEEP_RECENT = 4
    DEFAULT_MIN_MIDDLE = 4
    DEFAULT_SUMMARY_MAX_CHARS = 500
    # 压缩模型不硬编码：优先使用调用方传入的 model_id（当前主模型），
    # 其次使用 settings.COMPRESSION_MODEL，最后兜底为用户配置的默认主模型。
    # 后端不假设用户启用了哪些特定模型。

    SUMMARY_PROMPT_TEMPLATE = (
        "你是会话压缩引擎。请将以下对话与工具操作精炼成不超过{max_chars}字的核心摘要。"
        "必须保留：已获取的关键变量、文件路径和最终结论。"
        "忽略中间的报错和重试。直接输出摘要正文，不要任何解释或前缀。"
    )

    # T9 缓存友好：摘要指令追加在完整对话前缀之后（前缀与主循环上一轮请求逐字节一致，
    # 命中 provider 前缀缓存；指令只描述"压缩除最后 keep_recent 条之外的内容"）
    CACHE_AWARE_SUMMARY_INSTRUCTION = (
        "（系统指令）请将以上对话历史中除最后{keep_recent}条消息之外的内容，"
        "精炼成不超过{max_chars}字的核心摘要。"
        "必须覆盖：1）涉及文件/代码路径；2）已做出的决策及理由；"
        "3）待办与未完成事项；4）已获取的关键变量与最终结论。"
        "忽略中间的报错和重试。直接输出摘要正文，不要任何解释或前缀。"
    )
    # T9 摘要自批评：单轮有界复核（不做摘要链）；无缺漏只回 OK，有缺漏输出修订全文
    SUMMARY_CRITIQUE_INSTRUCTION = (
        "（系统指令）请自检你刚才输出的摘要是否完整准确："
        "1）涉及文件/代码路径是否齐全；2）决策及理由是否遗漏；"
        "3）待办与未完成事项是否遗漏；4）关键变量与最终结论是否准确。"
        "若无缺漏，只回复：OK；"
        "若有缺漏，直接输出修订后的完整摘要正文（不超过{max_chars}字，不要任何解释）。"
    )
    # 自批评回复为这些值（忽略大小写与尾部标点）时视为"无修订"，保留 v1 摘要
    SUMMARY_CRITIQUE_NO_REVISION = ("OK", "无缺漏", "无修订", "无需修订")

    # T91 摘要链（previousSummary）：本会话此前已有旧摘要时，把旧摘要作为输入合并更新。
    # 追加在摘要指令之后（缓存友好路径前缀不变，不破坏 provider 前缀缓存）。
    SUMMARY_CHAIN_INSTRUCTION = (
        "（系统指令）本会话此前已有一版历史摘要（见下方【旧摘要】）。"
        "请将其与以上对话中新出现的内容合并更新：保留旧摘要中仍然有效的信息"
        "（已涉及的文件/代码路径、已做出的决策及理由、待办与未完成事项、"
        "关键变量与最终结论），并纳入新增内容，输出合并后的完整摘要正文"
        "（不超过{max_chars}字，不要任何解释或前缀）。\n"
        "【旧摘要】\n{previous_summary}"
    )
    # T91 工作记忆恢复：压缩后把最近被读/写的文件路径注入记忆节点，
    # 保证压缩后追问"刚才改了哪些文件"等上下文细节仍可定位。
    WORKING_MEMORY_BLOCK_TEMPLATE = "【工作记忆】最近操作过的文件：{paths}"


    @staticmethod
    def _msg_to_dict(m) -> dict:
        """将单条消息（dict / ModelMessage / 其他对象）统一转为 dict。"""
        if isinstance(m, dict):
            return dict(m)
        if hasattr(m, "dict"):
            return m.dict()
        return {"role": getattr(m, "role", "user"), "content": str(m)}

    @staticmethod
    def _extract_previous_summary(messages: List) -> Optional[str]:
        """从消息列表头部（system 之后）提取既有历史摘要节点作为 previousSummary。

        摘要链（T91）：自动压缩路径二次压缩时，首条非 system 消息即为上一轮写入的
        【历史记忆摘要】（或规则截断的【历史截断摘要】）节点；手动 /compress 视图层
        使用【历史摘要】前缀。命中任一前缀即取其正文（剥离工作记忆等附加块），
        供压缩 prompt 作为旧摘要输入合并。未发现 → 返回 None。
        """
        for m in messages:
            d = m if isinstance(m, dict) else getattr(m, "dict", lambda: {})()
            if d.get("role") == "system":
                continue
            content = d.get("content") or ""
            if not isinstance(content, str):
                content = str(content)
            for prefix in ("【历史记忆摘要】", "【历史截断摘要】", "【历史摘要】"):
                if content.startswith(prefix):
                    rest = content[len(prefix):].strip()
                    # 只取摘要正文首段；剥离【工作记忆】等附加块，避免摘要链重复注入
                    return rest.split("\n\n")[0].strip() or None
            return None
        return None

    @staticmethod
    def _extract_working_files(messages: List, limit: int = 5) -> List[str]:
        """从消息的 tool_calls / timeline 中提取最近被读/写的文件路径（去重保序，取末 limit 个）。

        数据源：
          - assistant 消息 tool_calls 的 function.arguments.path（自动压缩内存路径）
          - timeline 事件（tool_start/tool_result）的 input.path（手动 /compress 的 DB 行路径）

        返回空列表表示无文件操作（不注入工作记忆块，不改变原输出形状）。
        """
        import json as _json

        file_tools = {
            "read_file", "write_file", "edit_file", "replace_in_file",
            "apply_patch", "delete_file", "list_files", "find_files",
        }
        paths: List[str] = []
        seen = set()

        def _add(p) -> None:
            if not p or not isinstance(p, str):
                return
            p = p.strip().strip("\"'")
            if p and p not in seen:
                seen.add(p)
                paths.append(p)

        for m in messages:
            if isinstance(m, dict):
                tool_calls = m.get("tool_calls")
                timeline = m.get("timeline")
            else:
                tool_calls = getattr(m, "tool_calls", None)
                timeline = getattr(m, "timeline", None)
            # tool_calls：assistant 消息 function.arguments.path
            if tool_calls:
                for call in tool_calls:
                    if not isinstance(call, dict):
                        continue
                    fn = call.get("function") or {}
                    if isinstance(fn, dict) and fn.get("name") in file_tools:
                        args = fn.get("arguments") or "{}"
                        try:
                            argd = _json.loads(args) if isinstance(args, str) else (args or {})
                        except Exception:  # noqa: BLE001 — 参数解析失败仅跳过该调用
                            argd = {}
                        if isinstance(argd, dict):
                            _add(argd.get("path"))
            # timeline：tool_start/tool_result 事件的 input.path
            if timeline:
                for ev in timeline:
                    if not isinstance(ev, dict):
                        continue
                    if ev.get("type") in ("tool_start", "tool_result") and ev.get("tool") in file_tools:
                        _inp = ev.get("input")
                        if isinstance(_inp, dict):
                            _add(_inp.get("path"))
        return paths[-limit:]

    async def compress_history(
        self,
        messages: List,
        keep_recent: int = DEFAULT_KEEP_RECENT,
        *,
        model_id: Optional[str] = None,
        min_middle: int = DEFAULT_MIN_MIDDLE,
        max_summary_chars: int = DEFAULT_SUMMARY_MAX_CHARS,
        previous_summary: Optional[str] = None,
    ) -> List:
        """G6-B: 会话压缩 — 将冗长中间消息提炼为一段历史摘要。

        三段式拆解：
          1. head：开头的 System / 任务设定（永远保留）
          2. recent：结尾 keep_recent 条消息（近期工作窗口，永远保留）
          3. middle：中间内容（待压缩）

        规则：
          - 中间内容不足 min_middle（默认 4）条 → 直接返回原列表，不压缩。
          - 摘要模型调用失败 / 返回空 → 直接返回原列表（fail-safe，不破坏执行流）。
          - 压缩结果 = [System] + [Memory] + [Recent]。

        T9 缓存友好（cache_aware_compaction_enabled，T91 起默认开）：
          - 开关开启时：摘要调用复用主对话前缀——完整 messages 原样作为前缀（与主循环
            上一轮请求逐字节一致 → 命中 provider 前缀缓存），摘要指令作为本轮新增的
            最后一条 user 消息追加；只改发往 LLM 的副本，绝不改动调用方 messages / DB
            历史。摘要自批评：单轮有界复核，有缺漏输出修订版；失败/无缺漏均保留 v1。
          - 开关关闭 → 旧路径：独立两条消息 prompt，只发 middle 段拼接，无自批评。

        T91 摘要链（previousSummary）：
          - previous_summary 显式传入（手动 /compress 传 chats.summary），或未传时自动
            从 messages 头部既有【历史记忆摘要】等节点提取（自动压缩二次压缩场景）。
          - 缓存友好路径下合并指令追加在摘要指令之后（前缀不变，不破坏缓存）；
            旧路径下旧摘要前置拼接。输出为"旧摘要 + 新增内容"合并后的完整摘要。

        T91 工作记忆恢复：
          - 压缩后从消息的 tool_calls / timeline 提取最近 5 个被读/写文件路径，
            以【工作记忆】块注入记忆节点，保证压缩后追问文件细节仍可定位。

        Args:
            messages: 已组装的消息列表（dict 或 ModelMessage 对象，保留输入类型）
            keep_recent: 结尾保留的近期消息条数
            model_id: 摘要模型 ID（默认取 settings.COMPRESSION_MODEL，未配置则用 DEFAULT_COMPRESSION_MODEL）
            min_middle: 触发压缩所需的最小中间消息数
            max_summary_chars: 摘要字数上限（注入 Prompt）
            previous_summary: 上一轮历史摘要（摘要链输入；为 None 时自动从 messages 检测）

        Returns:
            压缩后的消息列表；未达阈值或失败时返回原列表。
        """
        if not messages:
            return messages

        # 记录输入形态，输出时保持同类型
        input_is_model = any(not isinstance(m, dict) for m in messages)

        head = []
        i = 0
        while i < len(messages) and self._msg_to_dict(messages[i]).get("role") == "system":
            head.append(messages[i])
            i += 1

        rest = messages[i:]
        if len(rest) <= keep_recent:
            return messages
        recent = rest[-keep_recent:]
        middle = rest[:-keep_recent]

        if len(middle) < min_middle:
            return messages

        # T91 摘要链：未显式传入旧摘要时，从 messages 头部既有历史摘要节点自动提取
        if not previous_summary:
            previous_summary = self._extract_previous_summary(messages)

        # T9: 缓存友好开关——开 = 复用主对话前缀 + 自批评；关 = 旧路径（回滚闸）
        cache_aware = is_cache_aware_compaction_enabled()
        if cache_aware:
            # 摘要调用复用主对话前缀：完整 messages 原样作为前缀（与主循环上一轮请求
            # 逐字节一致 → 命中 provider 前缀缓存），摘要指令作为本轮新增的最后一条
            # user 消息追加。_msg_to_dict 逐条拷贝，绝不改动调用方 messages / DB 历史消息。
            prompt_messages = [self._msg_to_dict(m) for m in messages]
            instruction = self.CACHE_AWARE_SUMMARY_INSTRUCTION.format(
                keep_recent=keep_recent, max_chars=max_summary_chars
            )
            if previous_summary:
                # 摘要链：合并指令追加在摘要指令之后（前缀不变，不破坏 provider 前缀缓存）
                instruction += "\n\n" + self.SUMMARY_CHAIN_INSTRUCTION.format(
                    max_chars=max_summary_chars, previous_summary=previous_summary
                )
            prompt_messages.append({"role": "user", "content": instruction})
        else:
            # 旧路径：独立摘要 prompt，只发 middle 段拼接
            to_summarize = "\n\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}"
                for m in map(self._msg_to_dict, middle)
            )
            if previous_summary:
                # 摘要链：旧摘要前置，指示模型与新增内容合并更新
                to_summarize = (
                    "（本会话此前的历史摘要，请与下方新增内容合并更新，"
                    "保留其中仍有效的信息，输出合并后的完整摘要）\n"
                    f"{previous_summary}\n\n"
                    "——以上为旧摘要，以下是需要新增合并的对话——\n\n"
                    + to_summarize
                )
            prompt_messages = [
                {"role": "system", "content": self.SUMMARY_PROMPT_TEMPLATE.format(max_chars=max_summary_chars)},
                {"role": "user", "content": to_summarize or "（空内容）"},
            ]

        # 摘要模型：优先显式 model_id（当前主模型）→ settings.COMPRESSION_MODEL → 用户配置的默认主模型
        # 不硬编码任何特定模型名，所有选择基于用户实际配置
        from app.core.config import settings
        from app.core.agent_runtime.context_builder import get_default_model
        resolved_model = model_id or getattr(settings, "COMPRESSION_MODEL", "") or get_default_model()

        if not resolved_model:
            # 无可用模型时 fail-safe，返回原消息不压缩
            return messages

        try:
            from app.services.model import model_service
            result = await model_service.call_once(
                resolved_model,
                prompt_messages,
                temperature=0.2,
                max_tokens=1024,
            )
            summary = (result.content or "").strip()
        except Exception:
            # fail-safe：摘要失败不阻塞会话
            return messages

        # T9 摘要自批评：同一前缀上追加 assistant(v1) + 自批评指令，单轮有界复核。
        # 复核失败 / 回复无修订 → 保留 v1；有修订且长度合理 → 采用修订版。不做摘要链。
        if cache_aware and summary:
            try:
                critique_messages = prompt_messages + [
                    {"role": "assistant", "content": summary},
                    {"role": "user", "content": self.SUMMARY_CRITIQUE_INSTRUCTION.format(
                        max_chars=max_summary_chars
                    )},
                ]
                critique_result = await model_service.call_once(
                    resolved_model,
                    critique_messages,
                    temperature=0.2,
                    max_tokens=1024,
                )
                revised = (critique_result.content or "").strip()
                critique_head = revised.rstrip(".。！!").upper()
                # "OK" 及其短变体（"OK。" / "OK，无缺漏" 等）均视为无修订，保留 v1
                no_revision = (
                    critique_head in self.SUMMARY_CRITIQUE_NO_REVISION
                    or critique_head.startswith("OK")
                )
                # 超长护栏：修订版明显超出字数约束（>4x）视为模型输出失控，保留 v1
                if revised and not no_revision and len(revised) <= max_summary_chars * 4:
                    summary = revised
            except Exception:
                pass  # 自批评失败不阻塞会话，保留 v1

        if not summary:
            return messages

        # T91 工作记忆恢复：压缩后把最近被读/写的文件路径注入记忆节点，
        # 保证压缩后追问"刚才改了哪些文件"等上下文细节仍可定位。
        memory_content = f"【历史记忆摘要】\n{summary}"
        working_files = self._extract_working_files(messages)
        if working_files:
            memory_content += "\n\n" + self.WORKING_MEMORY_BLOCK_TEMPLATE.format(
                paths="、".join(working_files)
            )
        if not input_is_model:
            memory_node: dict = {"role": "user", "content": memory_content}
        else:
            cls = next(type(m) for m in messages if not isinstance(m, dict))
            try:
                memory_node = cls(role="user", content=memory_content)
            except Exception:
                memory_node = {"role": "user", "content": memory_content}

        return head + [memory_node] + recent

    @staticmethod
    def _truncate_history_fallback(messages: List, keep_recent: int = DEFAULT_KEEP_RECENT) -> List:
        """规则截断降级：LLM 摘要不可用时，将中间消息按条截断合并为一条摘要节点。

        与 compress_history 同构（head 保留 + 中间截断合并 + recent 保留），
        保证自动压缩在摘要模型不可用时仍有兜底，避免上下文无界膨胀。
        """
        if not messages:
            return messages
        head = []
        i = 0
        while i < len(messages) and messages[i].get("role") == "system":
            head.append(messages[i])
            i += 1
        rest = messages[i:]
        if len(rest) <= keep_recent:
            return messages
        recent = rest[-keep_recent:]
        middle = rest[:-keep_recent]
        if len(middle) < 4:
            return messages
        parts = []
        for m in middle:
            role = m.get("role", "user")
            content = m.get("content") or ""
            if not isinstance(content, str):
                content = str(content)
            parts.append(f"{role}: {content[:300]}")
        memory_node = {
            "role": "user",
            "content": "【历史截断摘要】\n" + "\n".join(parts)[:12000],
        }
        return head + [memory_node] + recent

    async def _maybe_auto_compress(
        self,
        run_id: str,
        messages: List,
        usage: dict,
        model_id: str,
    ) -> bool:
        """G6-B Auto: 水位超阈值时自动压缩历史（LLM 摘要 + 规则截断双保险）。

        触发条件：prompt_tokens 水位 >= COMPRESS_WATERMARK_THRESHOLD。
        压缩链路：先 LLM 摘要（compress_history），失败降级规则截断；
        两者都未生效 → 返回 False（不破坏执行流）。

        Returns:
            bool: True 表示发生了压缩（messages 已被原地替换为压缩结果）
        """
        if not usage:
            return False
        prompt_tokens = usage.get("prompt_tokens", 0) or 0
        if prompt_tokens <= 0:
            return False
        watermark = compute_watermark(prompt_tokens, model_id)
        if watermark < COMPRESS_WATERMARK_THRESHOLD:
            return False

        before = len(messages)
        compressed = await self.compress_history(messages, model_id=model_id)
        mode = "llm_summary"
        if compressed is messages or len(compressed) >= before:
            compressed = self._truncate_history_fallback(messages)
            mode = "truncate_fallback"
            if compressed is messages or len(compressed) >= before:
                return False

        messages[:] = compressed
        runtime_event_recorder.emit(run_id, "session_compressed", {
            "before": before,
            "after": len(compressed),
            "watermark": watermark,
            "prompt_tokens": prompt_tokens,
            "mode": mode,
        })
        return True

    # ──── 工具执行（流式 + 非流式共用）────

    async def _exec_tool_calls(
        self,
        ordered: list,
        ctx: dict,
        project_path: Optional[str],
        read_only: bool,
        current_messages: list,
        all_tool_calls: list,
        support_approval: bool = True,
    ):
        """执行一批工具调用（结构化或归一化），透传工具事件，回喂结果。

        - 追加 assistant tool_calls 消息
        - 逐个执行工具
        - 需审批时：support_approval=True → 等待审批闭环；False → 明确拒绝
        - Phase 3 T3/T8: 权限决策统一由 ApprovalPolicy 处理，不再接收 auto_approve 参数
        - 追加 role=tool 结果消息
        - Strategy Layer V1：执行前策略检查（read-before-write、危险命令、失败循环）
        - 追加 role=tool 结果消息
        yield 工具事件（tool_start/tool_approval/tool_result）供上层透传 SSE。
        """
        from app.core.tool_runtime.executor import execute_tool, complete_approval, complete_choice
        from app.core.tool_runtime.events import ToolEventSource
        from app.core.tool_runtime.approval import approval_registry
        from app.core.tool_runtime.choice import choice_registry
        import json

        assistant_msg = {"role": "assistant", "content": None, "tool_calls": ordered}
        current_messages.append(assistant_msg)

        # 获取策略引擎实例（基于 chat_id）
        chat_id = ctx.get("chat_id")
        strategy_engine = get_strategy_engine(str(chat_id)) if chat_id else None

        for tc in ordered:
            event_source = ToolEventSource()
            
            # 解析工具调用参数
            tool_name = tc.get("function", {}).get("name", "")
            try:
                tool_args = json.loads(tc.get("function", {}).get("arguments", "{}") or "{}")
            except Exception:
                tool_args = {}
            
            # Strategy Layer V1: 执行前策略检查
            if strategy_engine:
                strategy_result = strategy_engine.check_before_execution(tool_name, tool_args)
                
                if strategy_result.status == StrategyStatus.BLOCK:
                    # 策略阻止执行，直接返回错误信息
                    record = {
                        "name": tool_name,
                        "tool": tool_name,
                        "path": tool_args.get("path", ""),
                        "success": False,
                        "status": "blocked",
                        "arguments": tool_args,
                        "result": f"策略阻止: {strategy_result.reason}",
                        "duration_ms": 0,
                        "tool_call_id": tc.get("id", ""),
                    }
                    event_source.emit({
                        "type": "tool_start",
                        "tool_call_id": tc.get("id", ""),
                        "tool": tool_name,
                        "input": tool_args,
                    })
                    event_source.emit({
                        "type": "tool_result",
                        "tool_call_id": tc.get("id", ""),
                        "tool": tool_name,
                        "success": False,
                        "result": record["result"],
                        "duration_ms": 0,
                    })
                    for event in event_source.drain():
                        yield event
                    all_tool_calls.append(record)
                    current_messages.append({
                        "tool_call_id": tc.get("id", ""),
                        "role": "tool",
                        "content": record["result"],
                    })
                    continue
                
                elif strategy_result.status == StrategyStatus.REQUIRE_CONFIRM:
                    # 需要用户确认（当前实现：记录警告但继续执行）
                    # TODO: 未来可以集成用户确认流程
                    pass
            
            record = await execute_tool(
                tool_call=tc,
                project_path=project_path,
                read_only=read_only,
                ctx=ctx,
                emit=event_source.emit,
            )
            for event in event_source.drain():
                yield event

            # 需用户确认的工具：等待审批后完成执行闭环
            if record.get("status") == "awaiting_approval":
                if support_approval:
                    record = await complete_approval(
                        record,
                        project_path=project_path,
                        emit=event_source.emit,
                    )
                    for event in event_source.drain():
                        yield event
                else:
                    # 非流式路径不支持审批 → 明确拒绝，禁止空 result 回喂
                    approval_registry.resolve(record["approval_id"], "cancelled")
                    approval_registry.remove(record["approval_id"])
                    record = dict(record)
                    record.pop("approval_future", None)
                    record.pop("approval_timeout", None)
                    record.update({
                        "success": False,
                        "status": "failed",
                        "result": "错误: 该操作需要用户审批，但非流式接口不支持审批，已拒绝执行。请改用流式接口重试。",
                        "_skip_strategy": True,
                    })

            # 抉择工具：等待用户抉择后完成执行闭环（同审批架构；choice_request 事件已随 drain 到达前端）
            if record.get("status") == "awaiting_choice":
                if support_approval:
                    record = await complete_choice(record, emit=event_source.emit)
                    for event in event_source.drain():
                        yield event
                else:
                    # 非流式路径不支持交互抉择 → 自动采纳推荐项，禁止空 result 回喂
                    choice_registry.resolve(record["choice_id"], {
                        "selected": None,
                        "custom_text": None,
                        "note": "（非流式接口不支持交互抉择，已自动采纳推荐项）",
                    })
                    record = await complete_choice(record)

            # Strategy Layer V1: 执行后策略检查
            if strategy_engine and not record.get("_skip_strategy"):
                post_result = strategy_engine.check_after_execution(
                    tool_name,
                    tool_args,
                    record.get("success", False),
                    record.get("result", ""),
                )
                if post_result and post_result.status == StrategyStatus.NEED_FEEDBACK:
                    # 注入反馈信息到工具结果中
                    original_result = record.get("result", "")
                    feedback_msg = f"\n\n[策略提示] {post_result.reason}\n建议: {post_result.suggestion}"
                    record["result"] = original_result + feedback_msg
                    # 更新 current_messages 中的内容
                    if current_messages and current_messages[-1].get("tool_call_id") == tc.get("id"):
                        current_messages[-1]["content"] = record["result"]

            all_tool_calls.append(record)
            current_messages.append({
                "tool_call_id": tc.get("id", ""),
                "role": "tool",
                "content": record["result"],
            })

    async def _exec_tool_calls_with_verification(
        self,
        ordered: list,
        ctx: dict,
        project_path: Optional[str],
        read_only: bool,
        current_messages: list,
        all_tool_calls: list,
        support_approval: bool = True,
    ):
        """执行工具调用 + 程序化验证（Phase E4 + Verification Loop V1）。

        yield 协议：
          - 透传 _exec_tool_calls 的工具事件（tool_start / tool_approval / tool_result）
          - 追加 verify_result 事件（每个成功动作一条，含 status/evidence）
          - 追加 verification_failed 事件（存在未通过验证时，含注入的反馈文本）
          - 追加 verification_loop_exhausted 事件（验证重试次数耗尽时）

        验证语义：
          - 本轮 status == "success" 的动作 → verifier.verify_all 程序校验
          - 存在 passed 之外的结果 → 向 current_messages 注入【验证反馈】消息，
            驱动 LLM 在下一轮重新执行（Action → Verify → Retry）
          - 全部通过 → 不注入，流程正常继续
        
        Verification Loop V1:
          - 验证失败时，通过 Strategy Engine 跟踪重试次数
          - 达到 MAX_VERIFICATION_RETRIES 后停止重试，注入停止提示
          - 验证成功时重置重试计数
        """
        executed_start = len(all_tool_calls)
        async for event in self._exec_tool_calls(
            ordered, ctx, project_path, read_only, current_messages, all_tool_calls, support_approval
        ):
            yield event

        # 仅验证本轮真实发生的动作（status == success）
        round_records = all_tool_calls[executed_start:]
        
        # Verification Loop V1: 传入 chat_id 以启用循环跟踪
        chat_id = ctx.get("chat_id")
        results = self.verifier.verify_all(round_records, project_path, chat_id=str(chat_id) if chat_id else None)

        failed = [r for r in results if not r.passed]
        for r in results:
            yield {"type": "verify_result", **r.to_dict()}

        # 获取策略引擎（用于验证循环跟踪）
        strategy_engine = get_strategy_engine(str(chat_id)) if chat_id else None

        if failed:
            # 记录验证失败
            if strategy_engine:
                strategy_engine.record_verification_failure()
                
                # 检查是否达到重试上限
                if strategy_engine.should_stop_verification_retry():
                    # 达到上限，注入停止提示
                    feedback = self._build_verification_loop_exhausted_feedback(
                        failed, 
                        strategy_engine.get_verification_retry_count()
                    )
                    current_messages.append({"role": "user", "content": feedback})
                    yield {
                        "type": "verification_loop_exhausted",
                        "message": feedback,
                        "retry_count": strategy_engine.get_verification_retry_count(),
                        "results": [r.to_dict() for r in failed],
                    }
                    # 重置计数器，避免后续任务继续受限
                    strategy_engine.record_verification_success()
                    return
            
            # 未达上限，正常注入验证反馈
            feedback = self._build_verification_feedback(failed)
            current_messages.append({"role": "user", "content": feedback})
            yield {
                "type": "verification_failed",
                "message": feedback,
                "results": [r.to_dict() for r in failed],
            }
        else:
            # 验证成功，重置重试计数
            if strategy_engine:
                strategy_engine.record_verification_success()

    @staticmethod
    def _build_verification_feedback(failed: list) -> str:
        """构造验证失败反馈文本（注入下一轮 LLM 消息）。"""
        lines = [
            "【验证反馈】上一轮工具动作未通过程序化验证，请根据结果修正后重新执行，"
            "直到验证通过或说明无法完成。",
        ]
        for r in failed:
            tool = r.tool or ""
            tc_id = f"（tool_call: {r.tool_call_id}）" if r.tool_call_id else ""
            lines.append(f"- {tool}{tc_id}: {r.message}")
        return "\n".join(lines)

    @staticmethod
    def _build_verification_loop_exhausted_feedback(failed: list, retry_count: int) -> str:
        """构造验证循环耗尽反馈文本（达到重试上限时注入）。"""
        lines = [
            f"【验证循环停止】工具动作已连续 {retry_count} 次未通过验证，停止自动重试。",
            "请检查以下问题并手动修正：",
        ]
        for r in failed:
            tool = r.tool or ""
            tc_id = f"（tool_call: {r.tool_call_id}）" if r.tool_call_id else ""
            lines.append(f"- {tool}{tc_id}: {r.message}")
        lines.append("\n建议：")
        lines.append("1. 检查文件路径和权限是否正确")
        lines.append("2. 检查命令语法和参数是否正确")
        lines.append("3. 如果问题无法解决，请向用户说明情况")
        return "\n".join(lines)

    # ──── Phase 12: Completion Loop V1 — 完成验证辅助 ────

    @staticmethod
    def _completion_enabled(context: AgentContext, has_task_graph: bool) -> bool:
        """判断完成验证是否启用。

        优先级：显式开关 > 默认（有 TaskGraph 时参与节点完成判断，无图时仅显式开启）。
        """
        flag = getattr(context, "completion_verification", None)
        if flag is True:
            return True
        if flag is False:
            return False
        return has_task_graph

    @staticmethod
    def _extract_task_goal(messages: list) -> str:
        """从 messages 提取任务目标（最后一个真实 user 消息，跳过压缩摘要/验证反馈节点）。

        G6-B Auto: 自动压缩会把中间 user 消息替换为「历史记忆摘要」节点，
        其 role 同样是 user，若不跳过会把摘要误当成任务目标。
        P1-1（run 844）: 验证反馈以 user 角色追加到末尾，同样跳过；
        取最后一个真实用户请求，避免多轮对话后仍取首轮旧意图。
        """
        last_goal = ""
        for m in messages:
            if isinstance(m, dict) and m.get("role") == "user":
                content = m.get("content") or ""
                if isinstance(content, str) and (
                    content.startswith("【历史") or content.startswith("【验证反馈")
                ):
                    continue
                last_goal = content[:500] if isinstance(content, str) else str(content)[:500]
            elif hasattr(m, "role") and getattr(m, "role") == "user":
                content = str(getattr(m, "content", ""))[:500]
                if content.startswith("【历史") or content.startswith("【验证反馈"):
                    continue
                last_goal = content
        return last_goal

    async def _verify_completion(
        self,
        context: AgentContext,
        task_goal: str,
        final_content: str,
        current_task,
        all_tool_calls: list,
        loop_messages: list,
    ) -> object:
        """运行完成验证管道并返回 CompletionVerificationResult。"""
        ctx = CompletionContext(
            task_goal=task_goal,
            final_content=final_content,
            tool_records=all_tool_calls,
            execution_history=loop_messages,
            project_path=context.project_path,
            current_task=current_task,
            model_id=context.model_id,
        )
        verifier = self._resolve_completion_verifier(context)
        return await verifier.verify(ctx)

    @staticmethod
    def _build_completion_feedback(result: object, retry_count: int = 0) -> str:
        """构造完成验证失败反馈文本（注入下一轮 LLM 消息，驱动继续执行）。

        Round 2 优化：反馈按 next_action 分级；连续失败时追加防逃逸强制约束。
        """
        lines = [
            "任务尚未完成。",
        ]
        if getattr(result, "reason", ""):
            lines.append(f"原因：{result.reason}")
        missing = list(getattr(result, "missing_items", None) or [])
        if missing:
            lines.append("需要：")
            lines.extend(f"- {m}" for m in missing)
        next_action = getattr(result, "next_action", "") or ""
        if next_action == "fix_tool_actions":
            lines.append("要求：修正上述失败的工具动作后重新执行，并确认结果。")
        elif next_action == "continue_execution":
            lines.append("要求：继续执行，直至上述缺失项全部消除。")
        elif next_action:
            lines.append(f"建议：{next_action}")
        if retry_count >= 2:
            # 防验证逃逸定向压制（Round 2 实证：连续失败后模型倾向只跑必过子集）
            lines.append(
                "【强制约束】禁止只运行测试子集制造绿色假象；必须全量执行 pytest tests "
                "复跑所有测试，曾失败的测试文件不得跳过。"
            )
        lines.append("请继续处理！")
        return "\n".join(lines)

    # ──── Round 2 优化：完成验证失败的分级处置辅助 ────

    # 硬性缺失关键词：命中则任务标记 failed（测试未绿/逃逸/工具失败）；
    # 其余为软性缺失（如未产出最终回答）→ completed_unverified，不级联中断后续任务。
    _HARD_MISSING_KEYWORDS = (
        "未全绿", "验证范围缩水", "pytest", "执行失败", "验证失败", "写入文件",
    )

    @classmethod
    def _is_hard_completion_failure(cls, result: object) -> bool:
        """判定完成验证失败是否属于硬性缺失（决定任务 failed 还是 completed_unverified）。"""
        if result is None:
            return False
        missing = list(getattr(result, "missing_items", None) or [])
        if not missing:
            return False
        return any(
            any(k in item for k in cls._HARD_MISSING_KEYWORDS)
            for item in missing
        )

    @staticmethod
    def _build_completion_failure_report(result: object) -> str:
        """结构化失败汇报（验证耗尽且无最终内容时的兜底回复，杜绝空回复静默结束）。"""
        lines = ["【任务未完全完成】完成验证未通过，如实汇报如下："]
        missing = list(getattr(result, "missing_items", None) or [])
        if missing:
            lines.append("未完成项：")
            lines.extend(f"- {m}" for m in missing)
        if getattr(result, "reason", ""):
            lines.append(f"判定原因：{result.reason}")
        lines.append("建议下一步：针对上述未完成项继续处理，或告知我调整任务范围。")
        return "\n".join(lines)

    # 探索型任务关键词（预算收紧，防探索任务吃光轮次，Round 2 P6）
    _EXPLORE_TASK_KEYWORDS = ("确认", "查看", "了解", "探索", "定位", "检查", "分析", "阅读")

    @classmethod
    def _task_round_budget(cls, action: str, base: int) -> int:
        """按任务类型差异化轮次预算：探索类收紧到 6，执行类保持默认。"""
        if action and any(k in action for k in cls._EXPLORE_TASK_KEYWORDS):
            return max(3, min(6, base))
        return base

    @staticmethod
    def _completion_event_suffix(completion_enabled: bool, completion_exhausted: object) -> dict:
        """Task 事件附加完成验证结果字段（用于 task_completed / task_failed 事件）。"""
        suffix = {"completion_verified": None}
        if not completion_enabled:
            return suffix
        if completion_exhausted is None:
            return {"completion_verified": True}
        return {
            "completion_verified": False,
            "completion_reason": (getattr(completion_exhausted, "reason", "") or "")[:200],
        }

    @staticmethod
    def _completion_metadata(completion_enabled: bool, completion_exhausted: object, retry_count: int) -> Optional[dict]:
        """AgentResult.metadata 透出的完成验证汇总信息。"""
        if not completion_enabled:
            return None
        if completion_exhausted is None:
            return {
                "enabled": True,
                "verified": True,
                "retry_count": retry_count,
            }
        return {
            "enabled": True,
            "verified": False,
            "retry_count": retry_count,
            "reason": getattr(completion_exhausted, "reason", "") or "",
            "missing_items": list(getattr(completion_exhausted, "missing_items", None) or []),
            "next_action": getattr(completion_exhausted, "next_action", "") or "",
        }

    @staticmethod
    def _normalizer_feedback(issues: list) -> str:
        """构造归一化失败回馈模型的结构化错误文本（不静默）。"""
        detail = "\n".join(f"- {it.get('reason')}: {it.get('raw', '')[:160]}" for it in issues)
        return (
            "【系统】检测到你的回复试图调用工具，但格式无法可靠解析，因此工具未执行。\n"
            f"解析失败原因:\n{detail}\n"
            "请重新以标准工具调用格式（tool_calls）调用工具，或使用明确格式："
            "<invoke name=\"工具名\">JSON参数</invoke> 或 调用 run_command: <命令>。"
        )

    @staticmethod
    def _to_dict_messages(messages: list) -> list:
        """将 ModelMessage / dict / 对象 统一转为可变 dict 列表。"""
        out = []
        for m in messages:
            if isinstance(m, dict):
                out.append(m)
            elif hasattr(m, "dict"):
                out.append(m.dict())
            else:
                # 对象消息：优先取 content 属性（而非整体 repr，避免 repr 中的模块/路径文本污染语义判定）
                out.append({
                    "role": getattr(m, "role", "user"),
                    "content": str(getattr(m, "content", m)),
                })
        return out

    @staticmethod
    def _phase_str(phase) -> str:
        """归一化阶段为字符串（支持 RuntimePhase 枚举 / 字符串）。"""
        return phase.value if isinstance(phase, RuntimePhase) else str(phase)

    # ──── Phase 11: 工具轮次解析 ────

    @staticmethod
    def _resolve_max_tool_rounds(context: AgentContext, max_tool_rounds: Optional[int] = None) -> int:
        """解析 max_tool_rounds 优先级：显式参数 > AgentContext > 环境变量 > 默认值。

        Args:
            context: Agent 执行上下文
            max_tool_rounds: 显式传入的轮次上限

        Returns:
            int: 解析后的工具轮次上限
        """
        if max_tool_rounds is not None:
            return max_tool_rounds
        ctx_val = getattr(context, "max_tool_rounds", None)
        if ctx_val is not None:
            return ctx_val
        env_val = os.environ.get("MAX_TOOL_ROUNDS")
        if env_val is not None:
            try:
                return int(env_val)
            except ValueError:
                pass
        return DEFAULT_MAX_TOOL_ROUNDS

    def _record_state(self, run_id: Optional[int], phase, reason: Optional[str] = None) -> None:
        """非流式路径：更新 AgentRun.state（含审计）并持久化 state_change 事件。

        流式路径不使用本方法（由 run_stream 包装器统一 transition + emit）。
        """
        if not run_id:
            return
        phase_str = self._phase_str(phase)
        runtime_event_recorder.transition(run_id, phase_str, reason)
        runtime_event_recorder.emit(
            run_id,
            "state_change",
            {"state": phase_str, "reason": reason},
        )

    # ──── 普通执行（非流式）────

    async def run(
        self,
        context: AgentContext,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 16384,
        reasoning_effort: Optional[str] = None,
        read_only: bool = False,
        max_tool_rounds: Optional[int] = None,
        on_complete: Optional[Callable[["AgentResult"], Any]] = None,
    ) -> AgentResult:
        """执行 Agent 调用（非流式；T4 双循环合一后为 run_stream() 的消费者）。

        run() 不再持有独立的 Execution Loop（旧实现归档于 _legacy_run.py，保留一个
        发布周期）：内部调用 run_stream()，drain 统一事件流，聚合出与旧返回结构
        兼容的 AgentResult。工具轮次循环、审批、TaskRouter、TaskGraph、完成验证、
        自动压缩、自查插队在两条路径上由同一实现驱动，行为天然一致。

        聚合规则（事件协议见 run_stream docstring / 现状文档 3.5）：
          text（累计）→ content；finish → finish_reason；
          tool_calls（汇总）→ tool_calls；token_usage（最后一次）→ usage 与
          metadata.token_watermark；task_graph → metadata.task_graph；
          state_change(llm_call) 计数 → rounds；
          统一实现写入 context.metadata 的 _t4_usage/_t4_completion →
          usage 与 metadata.completion（消费端读取，不出现在事件协议中）。

        审批契约（T4）：遇 tool_approval 立即返回 finish_reason="pending_approval"
        的 AgentResult，metadata.pending_approval 携带 approval_id / tool / command
        等摘要；绝不在非流式 HTTP 请求里同步等待审批。审批条目保留在
        approval_registry（不再 resolve cancelled / remove），由前端复用
        POST /{chat_id}/approve 闭环；审批 Future 由后台续跑任务等待，决策后
        执行继续至收尾，完整结果经 on_complete 回调交付。
        抉择卡（choice_request）沿用旧契约：自动采纳推荐项，不挂起。

        Args:
            context: Agent 执行上下文
            messages: 已组装的 messages 列表（ModelMessage 对象）
            temperature: 模型温度
            max_tokens: 最大 token 数
            reasoning_effort: 推理强度
            read_only: 是否只读模式
            max_tool_rounds: 工具轮次上限（None → 按 context/env/默认值解析，与旧口径一致）
            on_complete: pending_approval 后台续跑完成时的回调（sync 或 async，可选）

        Returns:
            AgentResult: content / usage / rounds / finish_reason / tool_calls / metadata
        """
        # 旧 run() 的轮次解析口径（context.max_tool_rounds → env → 默认值），
        # 先解析再传给统一实现，保证非流式轮次预算与合一前一致。
        resolved_rounds = self._resolve_max_tool_rounds(context, max_tool_rounds)

        aggregator = _AgentResultAggregator(context)
        stream = self.run_stream(
            context=context,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
            read_only=read_only,
            max_tool_rounds=resolved_rounds,
        )

        approval_event = await _drain_agent_stream(stream, aggregator)
        if approval_event is None:
            return aggregator.build()

        # pending_approval：generator 此刻悬停在 tool_approval yield 上（尚未进入
        # complete_approval 等待），审批条目仍在 approval_registry 挂起等待 /approve；
        # 事件流交给后台任务续跑（等待审批闭环 → 执行至收尾 → on_complete），本请求立即返回。
        pending = {
            "approval_id": approval_event.get("approval_id", ""),
            "tool_call_id": approval_event.get("tool_call_id", ""),
            "tool": approval_event.get("tool", ""),
            "command": approval_event.get("command", ""),
            "risk_level": approval_event.get("risk_level", ""),
            "risk_reason": approval_event.get("risk_reason", ""),
            "chat_id": approval_event.get("chat_id"),
        }
        self._spawn_pending_continuation(stream, aggregator, on_complete)
        return aggregator.build_pending(pending)

    def _spawn_pending_continuation(
        self,
        stream,
        aggregator: "_AgentResultAggregator",
        on_complete: Optional[Callable[["AgentResult"], Any]],
    ) -> None:
        """pending_approval 后台续跑：drain 剩余事件流至收尾并交付完整结果。

        续跑中的后续审批等待既有 300s 超时（超时视为拒绝——非流式场景用户无
        实时卡片时的有界兜底）；异常只记日志，不影响已返回的 pending 响应。
        """
        import logging

        _logger = logging.getLogger(__name__)

        async def _continue():
            try:
                await _drain_agent_stream(stream, aggregator, stop_on_approval=False)
                final = aggregator.build()
                if on_complete is not None:
                    result = on_complete(final)
                    if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
                        await result
            except asyncio.CancelledError:
                _logger.warning("[T4] pending 续跑被取消 chat_id=%s", aggregator.context.chat_id)
            except Exception as e:  # noqa: BLE001
                _logger.error("[T4] pending 续跑异常 chat_id=%s error=%s", aggregator.context.chat_id, e)

        task = asyncio.create_task(_continue())
        _pending_continuations.add(task)
        task.add_done_callback(_pending_continuations.discard)

    # ──── 流式执行 ────

    async def run_stream(
        self,
        context: AgentContext,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 16384,
        reasoning_effort: Optional[str] = None,
        read_only: bool = False,
        max_tool_rounds: int = MAX_STREAM_ROUNDS,
    ):
        """执行 Agent 调用（流式，含 Execution Loop + Phase E2 事件持久化）。

        yield 协议（统一信封，顶层 type 判别，与 chat.py SSE 透传兼容）：
          {"type": "text", "content": str}                    文本增量
          {"type": "thinking", "content": str}                思考段增量
          {"type": "tool_start", ...}                         工具开始事件
          {"type": "tool_result", ...}                        工具结束事件（含结果/耗时）
          {"type": "tool_approval", ...}                      审批请求事件
          {"type": "tool_calls", "calls": [...]}              累计工具调用汇总（含结果，供持久化）
          {"type": "finish", "finish_reason": str}
          {"type": "error", "message": str}

        Phase E2：
          - 进入即创建 AgentRun（status=running）
          - 所有 yield 事件先经 runtime_event_recorder 持久化（sequence 自增）
          - 正常结束 → completed；CancelledError → cancelled；异常 → failed

        Args:
            context: Agent 执行上下文
            messages: 已组装的 messages 列表（ModelMessage 对象）
            temperature: 模型温度
            max_tokens: 最大 token 数
            reasoning_effort: 推理强度
            read_only: 是否只读模式
            max_tool_rounds: 工具轮次上限
        """
        run_id = runtime_event_recorder.create_run(
            chat_id=context.chat_id,
            agent_id=context.agent_id,
            parent_run_id=getattr(context, "parent_run_id", None),
        )
        try:
            async for event in self._run_stream_events(
                context, messages, run_id, temperature, max_tokens, reasoning_effort, read_only, max_tool_rounds
            ):
                # Phase E5: state_change 事件先更新 AgentRun.state（含审计），再统一持久化
                if event.get("type") == "state_change":
                    runtime_event_recorder.transition(
                        run_id,
                        event.get("state", ""),
                        event.get("reason"),
                    )
                runtime_event_recorder.emit(
                    run_id,
                    event.get("type", "event"),
                    {k: v for k, v in event.items() if k != "type"},
                )
                yield event
            runtime_event_recorder.transition(run_id, RuntimePhase.COMPLETED.value, "completed")
            runtime_event_recorder.finish_run(run_id, "completed")
        except asyncio.CancelledError:
            runtime_event_recorder.transition(run_id, RuntimePhase.CANCELLED.value, "cancelled")
            runtime_event_recorder.finish_run(run_id, "cancelled")
            raise
        except Exception as e:
            error_msg = str(e)
            runtime_event_recorder.transition(run_id, RuntimePhase.FAILED.value, error_msg[:200])
            runtime_event_recorder.emit(run_id, "error", {"message": error_msg})
            runtime_event_recorder.finish_run(run_id, "failed")
            # 向 SSE 流 yield error 事件，确保前端收到友好提示再断流
            yield {"type": "error", "message": error_msg}
            raise

    async def _run_stream_events(
        self,
        context: AgentContext,
        messages: list,
        run_id: Optional[int] = None,
        temperature: float = 0.7,
        max_tokens: int = 16384,
        reasoning_effort: Optional[str] = None,
        read_only: bool = False,
        max_tool_rounds: int = MAX_STREAM_ROUNDS,
    ):
        """流式执行循环（yield 事件，不含持久化/生命周期；由 run_stream 包装）。

        G4-B：当 context.plan 存在时，外层按 TaskGraph 任务循环驱动，
        内层保留原有 LLM + 工具执行逻辑。无 Plan 时走原始路径，行为不变。
        """
        from app.services.model import model_service
        from app.core.tool_runtime.normalizer import normalize_tool_call_text

        # ──── Phase E5: pending → building_context ────
        yield {"type": "state_change", "state": RuntimePhase.BUILDING_CONTEXT.value, "reason": "context build"}

        # ──── Context Builder（暂留接口，透传）────
        messages = await self.context_builder.build(context, messages)

        # ──── TaskRouter 决策（T4 双循环合一：两路统一在唯一实现中调用，结果仅写 metadata）────
        if context.metadata is None:
            context.metadata = {}
        _last_msg = messages[-1] if messages else None
        user_message = (
            _last_msg.get("content", "")
            if isinstance(_last_msg, dict)
            else getattr(_last_msg, "content", "")
        ) or ""
        has_tools = context.tools is not None and len(context.tools) > 0
        decision = self.router.route(
            message=user_message,
            tool_decision=context.decision,
            has_tools=has_tools,
        )
        context.metadata.update({
            "task_type": decision.task_type.value,
            "intent": decision.intent,
            "confidence": decision.confidence,
            "reason": decision.reason,
        })

        # G4-B: TaskGraph 初始化
        has_task_graph = bool(getattr(context, 'plan', None))
        if has_task_graph:
            self.init_task_graph(context.plan)

        # ──── Phase E5: building_context → llm_call ────
        yield {"type": "state_change", "state": RuntimePhase.LLM_CALL.value, "reason": "execution loop"}

        ctx = {k: v for k, v in (context.memory_context or {}).items() if v is not None}
        ctx.setdefault("chat_id", context.chat_id)

        current_messages = self._to_dict_messages(messages)
        all_tool_calls = []
        available_names = {t["function"]["name"] for t in (context.tools or [])} if context.tools else set()

        # ──── Phase 11: 初始化自查状态 ────
        has_modified_code = False
        self_check_done = False

        # ──── Phase 12: Completion Loop V1 配置 ────
        completion_enabled = self._completion_enabled(context, has_task_graph)
        max_completion_retry = getattr(context, "max_completion_retry", None) or DEFAULT_MAX_COMPLETION_RETRY
        # Round 2 优化：run 级失败标记与最后一次验证失败（用于兜底失败汇报）
        any_completion_failed = False
        run_completion_exhausted = None
        # T4: 外层预初始化（逐任务重置仍在任务循环内做），零任务收尾时 _t4_completion 可安全引用
        completion_retry_count = 0
        completion_exhausted = None

        # Round 2 优化：测试基建（conftest fixture）摘要一次性注入，避免重复 read_file
        _test_infra = build_test_infra_summary(
            context.project_path, self._extract_task_goal(current_messages)
        )
        if _test_infra:
            current_messages.append({
                "role": "system",
                "content": _wrap_runtime_context(_test_infra, source="MfkAgent TestInfra"),
            })

        # T1 缓存前缀契约：逐轮动态内容（⑦⑧⑨⑩）以 <system-reminder> 包裹到
        # 本轮最后一条 user 消息副本末尾（仅 LLM payload，不动 DB 历史消息）
        _apply_turn_reminder(current_messages, (context.metadata or {}).get("turn_reminder"))

        # ──── T10: 任务图 × 子代理委托（task_graph_subagent_enabled，灰度默认关）────
        # 开启后：就绪节点 assigned_agent 指向 is_sub_agent 子代理 → 委托 run_sub_agent
        # （独立上下文、只带任务文本），主循环仅经 runtime_context 回注结果摘要；
        # 无依赖的就绪可委托节点 asyncio.gather 并行分派（并发上限复用编排 MAX_CONCURRENCY）。
        # 关闭（默认）→ 完全走下方原有串行路径，行为与现状一致。
        subagent_delegation_enabled = False
        _run_sub_agent_fn = None
        _is_sub_agent_fn = None
        _sub_agent_id_cache: dict = {}
        if has_task_graph:
            try:
                from app.services.sub_agent import (
                    is_sub_agent_id as _is_sub_agent_fn,
                    is_task_graph_subagent_enabled as _tg_subagent_enabled,
                    run_sub_agent as _run_sub_agent_fn,
                )
                subagent_delegation_enabled = _tg_subagent_enabled()
            except Exception:  # noqa: BLE001 — 导入失败按未启用处理，走原串行路径
                subagent_delegation_enabled = False

        def _task_delegatable(agent_key: str) -> bool:
            """assigned_agent 是否指向 is_sub_agent 子代理（本 run 内缓存判定）。"""
            if not subagent_delegation_enabled or not agent_key or _is_sub_agent_fn is None:
                return False
            if agent_key not in _sub_agent_id_cache:
                _sub_agent_id_cache[agent_key] = _is_sub_agent_fn(agent_key)
            return _sub_agent_id_cache[agent_key]

        # G4-B: 外层 TaskGraph 任务循环（无 Plan 时只跑一轮）
        while True:
            current_task = None
            if has_task_graph:
                current_task = self.get_next_ready_task()
                if current_task is None:
                    # G4-C: 图中断/阻塞 → 剩余 pending 全部 skipped（收敛 is_all_done）
                    if not self.task_graph_state.is_all_done():
                        for skip_id in self.task_graph_state.mark_pending_skipped():
                            skip_node = self.task_graph_state.get_task(skip_id)
                            if skip_node is not None:
                                yield {
                                    "type": "task_skipped",
                                    **self._task_event_payload(skip_node, "skipped"),
                                }
                    break  # 全部完成或被阻塞

                self.update_task_status(current_task.id, "running")
                yield {
                    "type": "task_started",
                    **self._task_event_payload(current_task, "running"),
                }
                # 战略4: Agent 状态可视化 — 任务启动
                yield {"type": "agent_state_update", **self._build_agent_state_event(
                    agent_role=self._agent_role_display_name(current_task.assigned_agent),
                    status="working",
                    action_detail=f"开始执行任务: {current_task.action}",
                    current_task_id=current_task.id,
                    task_progress=self._build_task_progress(current_task.id),
                )}
                # ──── T10: 子代理委托分派（task_graph_subagent_enabled 开启时）────
                # 就绪节点 assigned_agent 指向 is_sub_agent 子代理 → 委托 run_sub_agent
                # （独立上下文、只带任务文本），主循环仅经 runtime_context 回注结果摘要；
                # 从当前节点扩展并行批：连续就绪的可委托节点 asyncio.gather 并行
                # （并发上限复用编排 MAX_CONCURRENCY），有依赖节点由状态机保证等待。
                if _task_delegatable(current_task.assigned_agent):
                    batch = [current_task]
                    while True:
                        _nxt = self.get_next_ready_task()
                        if _nxt is None or not _task_delegatable(_nxt.assigned_agent):
                            break
                        self.update_task_status(_nxt.id, "running")
                        yield {"type": "task_started", **self._task_event_payload(_nxt, "running")}
                        yield {"type": "agent_state_update", **self._build_agent_state_event(
                            agent_role=self._agent_role_display_name(_nxt.assigned_agent),
                            status="working",
                            action_detail=f"开始执行任务: {_nxt.action}",
                            current_task_id=_nxt.id,
                            task_progress=self._build_task_progress(_nxt.id),
                        )}
                        batch.append(_nxt)

                    from app.core.orchestrator.runner import MAX_CONCURRENCY as _TG_SUBAGENT_MAX_CONCURRENCY
                    _sem = asyncio.Semaphore(_TG_SUBAGENT_MAX_CONCURRENCY)

                    async def _delegate_one(node):
                        """委托单个节点给子代理（独立上下文、只带任务文本）。"""
                        try:
                            async with _sem:
                                summary = await _run_sub_agent_fn(
                                    node.assigned_agent,
                                    node.action,
                                    chat_id=ctx.get("chat_id"),
                                    project_path=context.project_path,
                                    model_id=context.model_id,
                                    temperature=temperature,
                                )
                            return (node, summary, None)
                        except Exception as e:  # noqa: BLE001 — 失败走既有 failed+级联skip 语义
                            return (node, None, e)

                    _batch_results = await asyncio.gather(*[_delegate_one(n) for n in batch])

                    for _node, _summary, _err in _batch_results:
                        if _err is not None:
                            # 失败语义不变：failed + 级联 skip（对齐模型异常路径，不吞错）
                            yield {"type": "agent_state_update", **self._build_agent_state_event(
                                agent_role=self._agent_role_display_name(_node.assigned_agent),
                                status="error",
                                action_detail=f"任务失败: {_node.action}",
                                current_task_id=_node.id,
                                task_progress=self._build_task_progress(_node.id),
                            )}
                            _skipped = self.task_graph_state.mark_failed(_node.id, str(_err)[:200])
                            yield {
                                "type": "task_failed",
                                **self._task_event_payload(_node, "failed", error=str(_err)),
                            }
                            for _skip_id in _skipped:
                                _skip_node = self.task_graph_state.get_task(_skip_id)
                                if _skip_node is not None:
                                    yield {
                                        "type": "task_skipped",
                                        **self._task_event_payload(_skip_node, "skipped"),
                                    }
                            # 失败简报也经 runtime_context 回注（下游独立节点可感知）
                            current_messages.append({
                                "role": "system",
                                "content": _wrap_runtime_context(
                                    f"【任务结果】{_node.action}（执行失败：{str(_err)[:200]}）",
                                    source="MfkAgent TaskGraph",
                                ),
                            })
                        else:
                            self.update_task_status(_node.id, "completed")
                            yield {"type": "agent_state_update", **self._build_agent_state_event(
                                agent_role=self._agent_role_display_name(_node.assigned_agent),
                                status="completed",
                                action_detail=f"任务完成: {_node.action}",
                                current_task_id=_node.id,
                                task_progress=self._build_task_progress(_node.id),
                            )}
                            yield {
                                "type": "task_completed",
                                **self._task_event_payload(_node, "completed"),
                            }
                            # 子任务结果摘要经 runtime_context 回注（不直写完整输出，
                            # 摘要上限 500 字，对齐 chats.summary 列宽惯例）
                            _summary_text = (_summary or "").strip()
                            current_messages.append({
                                "role": "system",
                                "content": _wrap_runtime_context(
                                    f"【任务结果】{_node.action}：{_summary_text[:500]}",
                                    source="MfkAgent TaskGraph",
                                ),
                            })
                    # 批内全部节点已终态 → 回外层 while 取下一批 / 下一任务
                    continue

                # Phase 3.5: Runtime Context 边界隔离 — 任务上下文以 system 角色注入
                current_messages.append({
                    "role": "system",
                    "content": _wrap_runtime_context(
                        f"【当前任务】{current_task.action}",
                        source="MfkAgent TaskGraph",
                    ),
                })
                # G5-B: 注入 persona prompt（Phase 3.5: 包装为 Runtime Context）
                persona_prompt = get_persona_prompt(current_task.assigned_agent)
                if persona_prompt:
                    current_messages.append({
                        "role": "system",
                        "content": _wrap_runtime_context(persona_prompt, source="MfkAgent AgentRouter"),
                    })
                # Round 2 优化：轮次预算差异化（P6：探索类任务收紧）
                task_budget = self._task_round_budget(current_task.action, max_tool_rounds)

            task_done = False
            if not has_task_graph:
                task_budget = max_tool_rounds
            # Phase 12: 每个任务独立的完成验证重试计数
            completion_retry_count = 0
            completion_exhausted = None
            # G6-B Auto: 自动压缩轮次跟踪 + 上一轮 usage（finish 事件更新）
            last_compress_round = 0
            last_round_usage = None
            try:
                for round_no in range(task_budget + 1):
                    # G6-B Auto: 水位超阈值自动压缩历史（基于上一轮 usage，首轮跳过）
                    if (
                        round_no > 0
                        and last_round_usage
                        and (round_no - last_compress_round) >= COMPRESS_MIN_INTERVAL_ROUNDS
                    ):
                        if await self._maybe_auto_compress(
                            run_id, current_messages, last_round_usage, context.model_id
                        ):
                            last_compress_round = round_no
                            # 压缩可能吞掉本轮任务上下文 → 重新注入
                            if has_task_graph and current_task is not None:
                                current_messages.append({
                                    "role": "system",
                                    "content": _wrap_runtime_context(
                                        f"【当前任务】{current_task.action}",
                                        source="MfkAgent TaskGraph",
                                    ),
                                })

                    round_tools = context.tools if round_no < task_budget else None

                    # ──── Phase 11: 倒数预警（第 task_budget - 1 轮，即最后一轮有工具时）────
                    if round_no == task_budget - 2:
                        current_messages.append({
                            "role": "system",
                            "content": COUNTDOWN_WARNING,
                        })

                    collected_tool_calls: dict = {}
                    final_finish = "stop"
                    round_text = ""

                    async for event in model_service.stream_once(
                        model_id=context.model_id,
                        messages=current_messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=round_tools,
                        reasoning_effort=reasoning_effort,
                        # T1: 记忆每轮一致常驻（确定性文本，保证 system 前缀跨轮稳定）
                        memory_text=context.memory_text,
                        vision_context=context.vision_context if round_no == 0 else None,
                    ):
                        etype = event.get("type")
                        if etype == "text":
                            round_text += event.get("content", "")
                            yield event
                        elif etype == "thinking":
                            yield event
                        elif etype == "tool_calls":
                            collected_tool_calls = {i: c for i, c in enumerate(event.get("calls") or [])}
                        elif etype == "finish":
                            final_finish = event.get("finish_reason", "stop")
                            # G6-A: 捕获 usage，yield token_usage 事件
                            last_round_usage = event.get("usage")
                            if last_round_usage:
                                # T4: 原始 usage 写入 context.metadata 供非流式消费者聚合
                                context.metadata["_t4_usage"] = last_round_usage
                                yield self._build_token_usage_event(last_round_usage, context.model_id)

                    if final_finish == "tool_calls" and collected_tool_calls and round_tools:
                        ordered = [collected_tool_calls[i] for i in sorted(collected_tool_calls)]
                        # 战略4: Agent 状态可视化 — 工具调用前
                        tool_names = [tc.get("function", {}).get("name", "") for tc in ordered]
                        agent_role = self._agent_role_display_name(current_task.assigned_agent) if current_task else "Default Agent"
                        yield {"type": "agent_state_update", **self._build_agent_state_event(
                            agent_role=agent_role,
                            status="waiting_for_tool",
                            action_detail=f"准备调用工具: {', '.join(tool_names)}",
                            current_task_id=current_task.id if current_task else None,
                            task_progress=self._build_task_progress(current_task.id if current_task else None),
                        )}
                        yield {"type": "state_change", "state": RuntimePhase.TOOL_EXECUTION.value, "reason": "tool execution"}
                        async for event in self._exec_tool_calls_with_verification(
                            ordered, ctx, context.project_path, read_only, current_messages, all_tool_calls,
                            support_approval=True,
                        ):
                            yield event
                        # ──── Phase 11: 写操作检测 ────
                        if not has_modified_code:
                            for tc in ordered:
                                tool_name = tc.get("function", {}).get("name", "")
                                if tool_name in WRITE_TOOLS:
                                    has_modified_code = True
                                    break
                        # 战略4: Agent 状态可视化 — 工具执行完成
                        agent_role = self._agent_role_display_name(current_task.assigned_agent) if current_task else "Default Agent"
                        yield {"type": "agent_state_update", **self._build_agent_state_event(
                            agent_role=agent_role,
                            status="working",
                            action_detail="工具执行完成，继续分析",
                            current_task_id=current_task.id if current_task else None,
                            task_progress=self._build_task_progress(current_task.id if current_task else None),
                        )}
                        yield {"type": "state_change", "state": RuntimePhase.VERIFYING.value, "reason": "verification"}
                        yield {"type": "state_change", "state": RuntimePhase.LLM_CALL.value, "reason": "next round"}
                        continue

                    if round_tools and round_text and not collected_tool_calls:
                        norm = normalize_tool_call_text(round_text, available_names)
                        if norm["calls"] and not norm["issues"]:
                            # 战略4: Agent 状态可视化 — 归一化工具调用前
                            norm_tool_names = [tc.get("function", {}).get("name", "") for tc in norm["calls"]]
                            agent_role = self._agent_role_display_name(current_task.assigned_agent) if current_task else "Default Agent"
                            yield {"type": "agent_state_update", **self._build_agent_state_event(
                                agent_role=agent_role,
                                status="waiting_for_tool",
                                action_detail=f"准备调用工具: {', '.join(norm_tool_names)}",
                                current_task_id=current_task.id if current_task else None,
                                task_progress=self._build_task_progress(current_task.id if current_task else None),
                            )}
                            yield {"type": "state_change", "state": RuntimePhase.TOOL_EXECUTION.value, "reason": "normalizer tool"}
                            async for event in self._exec_tool_calls_with_verification(
                                norm["calls"], ctx, context.project_path, read_only, current_messages, all_tool_calls,
                                support_approval=True,
                            ):
                                yield event
                            # ──── Phase 11: 写操作检测（归一化路径）────
                            if not has_modified_code:
                                for tc in norm["calls"]:
                                    tool_name = tc.get("function", {}).get("name", "")
                                    if tool_name in WRITE_TOOLS:
                                        has_modified_code = True
                                        break
                            # 战略4: Agent 状态可视化 — 归一化工具执行完成
                            yield {"type": "agent_state_update", **self._build_agent_state_event(
                                agent_role=agent_role,
                                status="working",
                                action_detail="工具执行完成，继续分析",
                                current_task_id=current_task.id if current_task else None,
                                task_progress=self._build_task_progress(current_task.id if current_task else None),
                            )}
                            yield {"type": "state_change", "state": RuntimePhase.VERIFYING.value, "reason": "verification"}
                            yield {"type": "state_change", "state": RuntimePhase.LLM_CALL.value, "reason": "next round"}
                            continue
                        if norm["issues"]:
                            feedback = self._normalizer_feedback(norm["issues"])
                            current_messages.append({"role": "assistant", "content": round_text or None})
                            current_messages.append({"role": "user", "content": feedback})
                            continue

                    # 正常结束：任务完成或整体完成
                    if has_task_graph and current_task:
                        # Phase 12: Completion Loop V1 — TaskGraph 节点完成候选验证
                        if completion_enabled:
                            # 规则层语义判定以用户真实目标为准（模板任务名不作依据）
                            task_goal = self._extract_task_goal(current_messages)
                            yield {"type": "completion_verify_started", "task_goal": task_goal, "round_no": round_no}
                            completion_result = await self._verify_completion(
                                context, task_goal, round_text, current_task,
                                all_tool_calls, current_messages,
                            )
                            if completion_result.success:
                                yield {"type": "completion_verify_passed", **completion_result.to_dict()}
                            else:
                                yield {"type": "completion_verify_failed", **completion_result.to_dict(),
                                       "retry_count": completion_retry_count, "max_retry": max_completion_retry}
                                if completion_retry_count < max_completion_retry:
                                    completion_retry_count += 1
                                    current_messages.append({"role": "assistant", "content": round_text or None})
                                    current_messages.append({
                                        "role": "user",
                                        "content": self._build_completion_feedback(completion_result, completion_retry_count),
                                    })
                                    continue
                                completion_exhausted = completion_result
                                run_completion_exhausted = completion_result

                        if self._is_hard_completion_failure(completion_exhausted):
                            # Round 2 优化：硬性缺失 → failed + 级联 skip（此前为强制 completed 短路）
                            skipped = self.task_graph_state.mark_failed(
                                current_task.id,
                                "; ".join(getattr(completion_exhausted, "missing_items", None) or [])[:200],
                            )
                            yield {"type": "agent_state_update", **self._build_agent_state_event(
                                agent_role=self._agent_role_display_name(current_task.assigned_agent),
                                status="error",
                                action_detail=f"任务失败（完成验证未通过）: {current_task.action}",
                                current_task_id=current_task.id,
                                task_progress=self._build_task_progress(current_task.id),
                            )}
                            yield {
                                "type": "task_failed",
                                **self._task_event_payload(
                                    current_task, "failed",
                                    error=getattr(completion_exhausted, "reason", "")[:200],
                                ),
                                **self._completion_event_suffix(completion_enabled, completion_exhausted),
                            }
                            for skip_id in skipped:
                                skip_node = self.task_graph_state.get_task(skip_id)
                                if skip_node is not None:
                                    yield {
                                        "type": "task_skipped",
                                        **self._task_event_payload(skip_node, "skipped"),
                                    }
                            any_completion_failed = True
                            task_done = True
                            break  # 跳出内层 for，回到外层 while（依赖任务已级联 skip）

                        self.update_task_status(current_task.id, "completed")
                        if completion_exhausted is not None:
                            # 软性缺失 → completed_unverified：不级联中断，但计入 run 级失败标记
                            any_completion_failed = True
                        else:
                            run_completion_exhausted = None  # 后续任务验证通过 → 清除旧失败快照
                        # 战略4: Agent 状态可视化 — 任务完成
                        yield {"type": "agent_state_update", **self._build_agent_state_event(
                            agent_role=self._agent_role_display_name(current_task.assigned_agent),
                            status="completed",
                            action_detail=(
                                f"任务完成（未通过完成验证）: {current_task.action}"
                                if completion_exhausted is not None
                                else f"任务完成: {current_task.action}"
                            ),
                            current_task_id=current_task.id,
                            task_progress=self._build_task_progress(current_task.id),
                        )}
                        yield {
                            "type": "task_completed",
                            **self._task_event_payload(current_task, "completed"),
                            **self._completion_event_suffix(completion_enabled, completion_exhausted),
                        }
                        task_done = True
                        break  # 跳出内层 for，回到外层 while 取下一个任务
                    else:
                        # ──── Phase 11: 强制自查插队拦截（流式非 TaskGraph 路径）────
                        if has_modified_code and not self_check_done and round_no < task_budget:
                            current_messages.append({
                                "role": "system",
                                "content": SELF_CHECK_PROMPT,
                            })
                            self_check_done = True
                            continue

                        # ──── Phase 12: Completion Loop V1 — 无图路径完成候选验证 ────
                        if completion_enabled:
                            task_goal = self._extract_task_goal(current_messages)
                            yield {"type": "completion_verify_started", "task_goal": task_goal, "round_no": round_no}
                            completion_result = await self._verify_completion(
                                context, task_goal, round_text, None,
                                all_tool_calls, current_messages,
                            )
                            if completion_result.success:
                                yield {"type": "completion_verify_passed", **completion_result.to_dict()}
                            else:
                                yield {"type": "completion_verify_failed", **completion_result.to_dict(),
                                       "retry_count": completion_retry_count, "max_retry": max_completion_retry}
                                if completion_retry_count < max_completion_retry:
                                    completion_retry_count += 1
                                    current_messages.append({"role": "assistant", "content": round_text or None})
                                    current_messages.append({
                                        "role": "user",
                                        "content": self._build_completion_feedback(completion_result, completion_retry_count),
                                    })
                                    continue
                                completion_exhausted = completion_result
                                run_completion_exhausted = completion_result

                        # 原始路径（无 Plan）：透传 finish + 工具调用汇总
                        yield {"type": "state_change", "state": RuntimePhase.COMPLETING.value, "reason": "finishing"}
                        # T4: 完成验证汇总写入 context.metadata 供非流式消费者聚合（不改事件协议）
                        context.metadata["_t4_completion"] = self._completion_metadata(
                            completion_enabled, completion_exhausted, completion_retry_count
                        )
                        # Round 2 优化：完成验证失败时以 completion_failed 收尾 + 兜底结构化失败汇报
                        if completion_exhausted is not None:
                            any_completion_failed = True
                            yield {"type": "text", "content": self._build_completion_failure_report(completion_exhausted)}
                            yield {"type": "finish", "finish_reason": "completion_failed"}
                        else:
                            yield {"type": "finish", "finish_reason": final_finish}
                        if all_tool_calls:
                            yield {"type": "tool_calls", "calls": all_tool_calls}
                        # Phase 1.6: 结束事件附带 TaskGraph 汇总（供消费端落库/切页重放）
                        yield {"type": "task_graph", "task_graph": self._task_graph_summary()}
                        return

                # 内层 for 耗尽（rounds exhausted）
                if has_task_graph and current_task:
                    if not task_done:
                        # Round 2 优化：轮次耗尽的兜底候选同样过验证（与非流式路径对齐，此前为直接强制 completed）
                        if completion_enabled:
                            task_goal = self._extract_task_goal(current_messages)
                            yield {"type": "completion_verify_started",
                                   "task_goal": task_goal, "round_no": round_no, "fallback": True}
                            completion_result = await self._verify_completion(
                                context, task_goal, round_text, current_task,
                                all_tool_calls, current_messages,
                            )
                            if completion_result.success:
                                yield {"type": "completion_verify_passed", **completion_result.to_dict()}
                            else:
                                yield {"type": "completion_verify_failed", **completion_result.to_dict(),
                                       "retry_count": completion_retry_count, "max_retry": max_completion_retry}
                                completion_exhausted = completion_result
                                run_completion_exhausted = completion_result
                        if self._is_hard_completion_failure(completion_exhausted):
                            # 硬性缺失 → failed + 级联 skip
                            skipped = self.task_graph_state.mark_failed(
                                current_task.id,
                                "; ".join(getattr(completion_exhausted, "missing_items", None) or [])[:200],
                            )
                            yield {"type": "agent_state_update", **self._build_agent_state_event(
                                agent_role=self._agent_role_display_name(current_task.assigned_agent),
                                status="error",
                                action_detail=f"任务失败（轮次耗尽且完成验证未通过）: {current_task.action}",
                                current_task_id=current_task.id,
                                task_progress=self._build_task_progress(current_task.id),
                            )}
                            yield {
                                "type": "task_failed",
                                **self._task_event_payload(
                                    current_task, "failed",
                                    error=getattr(completion_exhausted, "reason", "")[:200],
                                ),
                                **self._completion_event_suffix(completion_enabled, completion_exhausted),
                            }
                            for skip_id in skipped:
                                skip_node = self.task_graph_state.get_task(skip_id)
                                if skip_node is not None:
                                    yield {
                                        "type": "task_skipped",
                                        **self._task_event_payload(skip_node, "skipped"),
                                    }
                            any_completion_failed = True
                            continue
                        # 软性缺失 / 验证通过 → completed（尽力而为），未过验证时标记 unverified
                        self.update_task_status(current_task.id, "completed")
                        if completion_exhausted is not None:
                            any_completion_failed = True
                        # 战略4: Agent 状态可视化 — 任务完成（轮次耗尽）
                        yield {"type": "agent_state_update", **self._build_agent_state_event(
                            agent_role=self._agent_role_display_name(current_task.assigned_agent),
                            status="completed",
                            action_detail=(
                                f"任务完成（轮次耗尽，未通过验证）: {current_task.action}"
                                if completion_exhausted is not None
                                else f"任务完成（轮次耗尽）: {current_task.action}"
                            ),
                            current_task_id=current_task.id,
                            task_progress=self._build_task_progress(current_task.id),
                        )}
                        yield {
                            "type": "task_completed",
                            **self._task_event_payload(current_task, "completed"),
                            **self._completion_event_suffix(completion_enabled, completion_exhausted),
                        }
                    continue  # 回到外层 while 取下一个任务

                # 原始路径兜底：工具轮把循环耗尽仍无总结 → 再补一次无工具收尾请求
                if all_tool_calls:
                    try:
                        async for event in model_service.stream_once(
                            model_id=context.model_id,
                            messages=current_messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            tools=None,
                            reasoning_effort=reasoning_effort,
                            memory_text=None,
                        ):
                            if event.get("type") == "text":
                                yield event
                            elif event.get("type") == "finish" and event.get("usage"):
                                context.metadata["_t4_usage"] = event.get("usage")
                        context.metadata["_t4_completion"] = self._completion_metadata(
                            completion_enabled, completion_exhausted, completion_retry_count
                        )
                        yield {"type": "finish", "finish_reason": "stop"}
                        yield {"type": "tool_calls", "calls": all_tool_calls}
                    except Exception as e:
                        yield {"type": "error", "message": f"工具执行完成，但最终总结生成失败: {e}"}
                return

            except ModelNotFoundError as e:
                # 模型不存在 → 直接熔断，不尝试反思（反思用同一模型也会失败）
                if has_task_graph and current_task:
                    yield {"type": "agent_state_update", **self._build_agent_state_event(
                        agent_role=self._agent_role_display_name(current_task.assigned_agent),
                        status="error",
                        action_detail=f"模型不可用: {e}",
                        current_task_id=current_task.id,
                        task_progress=self._build_task_progress(current_task.id),
                    )}
                    skipped = self.task_graph_state.mark_failed(current_task.id, str(e)[:200])
                    yield {
                        "type": "task_failed",
                        **self._task_event_payload(current_task, "failed", error=str(e)),
                    }
                    for skip_id in skipped:
                        skip_node = self.task_graph_state.get_task(skip_id)
                        if skip_node is not None:
                            yield {
                                "type": "task_skipped",
                                **self._task_event_payload(skip_node, "skipped"),
                            }
                    break
                raise

            except ModelConfigError as e:
                # 模型配置错误（无 Key / 未注册）→ 直接熔断，不尝试反思
                # 反思用同一无 Key 模型也会失败，无意义
                if has_task_graph and current_task:
                    yield {"type": "agent_state_update", **self._build_agent_state_event(
                        agent_role=self._agent_role_display_name(current_task.assigned_agent),
                        status="error",
                        action_detail=f"模型配置错误: {e}",
                        current_task_id=current_task.id,
                        task_progress=self._build_task_progress(current_task.id),
                    )}
                    skipped = self.task_graph_state.mark_failed(current_task.id, str(e)[:200])
                    yield {
                        "type": "task_failed",
                        **self._task_event_payload(current_task, "failed", error=str(e)),
                    }
                    for skip_id in skipped:
                        skip_node = self.task_graph_state.get_task(skip_id)
                        if skip_node is not None:
                            yield {
                                "type": "task_skipped",
                                **self._task_event_payload(skip_node, "skipped"),
                            }
                    break
                yield {"type": "error", "message": f"模型配置错误: {e}"}
                return

            except Exception as e:
                # 战略方向: 先尝试反思自愈，失败则降级
                if has_task_graph and current_task:
                    # 战略4: Agent 状态可视化 — 任务失败
                    yield {"type": "agent_state_update", **self._build_agent_state_event(
                        agent_role=self._agent_role_display_name(current_task.assigned_agent),
                        status="error",
                        action_detail=f"任务失败: {current_task.action}",
                        current_task_id=current_task.id,
                        task_progress=self._build_task_progress(current_task.id),
                    )}

                    if self.task_graph_state is not None and not self.task_graph_state.can_heal(current_task.id):
                        # 自愈深度上限：跳过反思，直接降级失败 + 级联跳过
                        yield {"type": "agent_state_update", **self._build_agent_state_event(
                            agent_role=self._agent_role_display_name(current_task.assigned_agent),
                            status="error",
                            action_detail="已到达自愈上限，停止修复尝试，任务判定失败",
                            current_task_id=current_task.id,
                            task_progress=self._build_task_progress(current_task.id),
                        )}
                        skipped = self.task_graph_state.mark_failed(
                            current_task.id, str(e)[:200]
                        )
                    else:
                        # 反思开始事件
                        yield {"type": "agent_state_update", **self._build_agent_state_event(
                            agent_role=self._agent_role_display_name(current_task.assigned_agent),
                            status="working",
                            action_detail="触发自我反思，分析错误原因...",
                            current_task_id=current_task.id,
                            task_progress=self._build_task_progress(current_task.id),
                        )}
                        healed = await self._reflect_and_heal(
                            current_task,
                            str(e),
                            run_id=None,  # 流式路径事件通过 yield 透出
                        )
                        if healed:
                            # 反思成功事件（使用新注入的 heal_N 节点 id，与非流式对齐）
                            yield {"type": "agent_state_update", **self._build_agent_state_event(
                                agent_role=self._agent_role_display_name(current_task.assigned_agent),
                                status="working",
                                action_detail=f"动态生成修复计划，恢复执行: {healed.action[:80]}",
                                current_task_id=healed.id,
                                task_progress=self._build_task_progress(healed.id),
                            )}
                            continue  # 反思成功，回到外层循环取下一个任务
                        skipped = self.task_graph_state.mark_failed(
                            current_task.id, str(e)[:200]
                        )

                    # 降级：原始失败路径
                    yield {
                        "type": "task_failed",
                        **self._task_event_payload(current_task, "failed", error=str(e)),
                    }
                    for skip_id in skipped:
                        skip_node = self.task_graph_state.get_task(skip_id)
                        if skip_node is not None:
                            yield {
                                "type": "task_skipped",
                                **self._task_event_payload(skip_node, "skipped"),
                            }
                    break  # 失败后终止任务循环
                raise  # 无 Plan 路径：原样抛出

        # G4-B: 全部任务完成
        context.metadata["_t4_completion"] = self._completion_metadata(
            completion_enabled, completion_exhausted, completion_retry_count
        )
        yield {"type": "state_change", "state": RuntimePhase.COMPLETING.value, "reason": "all tasks done"}
        # Round 2 优化：存在完成验证失败时以 completion_failed 收尾 + 结构化失败汇报（杜绝空回复静默结束）
        if any_completion_failed:
            if run_completion_exhausted is not None:
                yield {"type": "text", "content": self._build_completion_failure_report(run_completion_exhausted)}
            yield {"type": "finish", "finish_reason": "completion_failed"}
        else:
            yield {"type": "finish", "finish_reason": "stop"}
        if all_tool_calls:
            yield {"type": "tool_calls", "calls": all_tool_calls}
        # Phase 1.6: 结束事件附带 TaskGraph 汇总（供消费端落库/切页重放）
        yield {"type": "task_graph", "task_graph": self._task_graph_summary()}
