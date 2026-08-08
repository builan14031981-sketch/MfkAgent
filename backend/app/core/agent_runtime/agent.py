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

from typing import Optional, List
import asyncio

from .router import TaskRouter
from .context import AgentContext, AgentResult
from .context_builder import ContextBuilder, get_default_context_builder
from .recorder import runtime_event_recorder
from .states import RuntimePhase
from .task_graph_state import TaskGraphState
from .personas import get_persona_prompt
from app.core.task_graph.models import TaskNode
from .model_context_config import get_model_max_tokens, compute_watermark
from app.core.verification import verifier as default_verifier

# ──── 执行循环最大轮次 ────
MAX_ROUNDS = 3
MAX_STREAM_ROUNDS = 8


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

    def __init__(self, context_builder: ContextBuilder = None, verifier=None):
        self.router = TaskRouter()
        self.context_builder = context_builder or get_default_context_builder()
        self.verifier = verifier or default_verifier
        # G4-A: TaskGraph 状态机（初始为空，由 init_task_graph 注入）
        self.task_graph_state: Optional[TaskGraphState] = None

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
                "model_max_tokens": get_model_max_tokens(model_id),
                "watermark_percentage": 0.0,
            }

        prompt_tokens = usage.get("prompt_tokens", 0) or 0
        completion_tokens = usage.get("completion_tokens", 0) or 0
        total_tokens = usage.get("total_tokens") or (prompt_tokens + completion_tokens)
        max_tokens = get_model_max_tokens(model_id)
        watermark = compute_watermark(total_tokens, model_id)

        return {
            "type": "token_usage",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
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
    ) -> bool:
        """任务失败后尝试 LLM 反思并动态注入修复任务。

        流程：
          1. 构造 Reflection Prompt，调用轻量模型分析错误
          2. 解析 LLM 返回的 JSON 修复方案
          3. 如果方案有效，通过 dynamic_append_task 注入新节点
          4. 失败时优雅降级，不阻断原有错误处理流程

        Args:
            current_task: 失败的任务节点
            error: 错误信息
            model_id: 反思模型 ID（默认 REFLECTION_MODEL）
            run_id: 运行记录 ID（用于事件广播）

        Returns:
            bool: True 表示成功注入修复任务，False 表示降级到原始失败
        """
        if self.task_graph_state is None:
            return False

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
            return False

        if not response_text:
            return False

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
            return False

        fix_action = (plan.get("fix_action") or "").strip()
        if not fix_action:
            # LLM 判断无法修复 → 降级
            return False

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
            return False

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

        return True

    # ──── G6-B: 智能会话压缩引擎 ────

    DEFAULT_KEEP_RECENT = 4
    DEFAULT_MIN_MIDDLE = 4
    DEFAULT_SUMMARY_MAX_CHARS = 500
    DEFAULT_COMPRESSION_MODEL = "qwen-flash"

    SUMMARY_PROMPT_TEMPLATE = (
        "你是会话压缩引擎。请将以下对话与工具操作精炼成不超过{max_chars}字的核心摘要。"
        "必须保留：已获取的关键变量、文件路径和最终结论。"
        "忽略中间的报错和重试。直接输出摘要正文，不要任何解释或前缀。"
    )

    @staticmethod
    def _msg_to_dict(m) -> dict:
        """将单条消息（dict / ModelMessage / 其他对象）统一转为 dict。"""
        if isinstance(m, dict):
            return dict(m)
        if hasattr(m, "dict"):
            return m.dict()
        return {"role": getattr(m, "role", "user"), "content": str(m)}

    async def compress_history(
        self,
        messages: List,
        keep_recent: int = DEFAULT_KEEP_RECENT,
        *,
        model_id: Optional[str] = None,
        min_middle: int = DEFAULT_MIN_MIDDLE,
        max_summary_chars: int = DEFAULT_SUMMARY_MAX_CHARS,
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

        Args:
            messages: 已组装的消息列表（dict 或 ModelMessage 对象，保留输入类型）
            keep_recent: 结尾保留的近期消息条数
            model_id: 摘要模型 ID（默认取 settings.COMPRESSION_MODEL，未配置则用 DEFAULT_COMPRESSION_MODEL）
            min_middle: 触发压缩所需的最小中间消息数
            max_summary_chars: 摘要字数上限（注入 Prompt）

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

        # 构造摘要 Prompt
        to_summarize = "\n\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}"
            for m in map(self._msg_to_dict, middle)
        )
        prompt_messages = [
            {"role": "system", "content": self.SUMMARY_PROMPT_TEMPLATE.format(max_chars=max_summary_chars)},
            {"role": "user", "content": to_summarize or "（空内容）"},
        ]

        # 摘要模型：优先显式 model_id → settings.COMPRESSION_MODEL → 默认便宜模型
        from app.core.config import settings
        resolved_model = model_id or getattr(settings, "COMPRESSION_MODEL", "") or self.DEFAULT_COMPRESSION_MODEL

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

        if not summary:
            return messages

        memory_content = f"【历史记忆摘要】\n{summary}"
        if not input_is_model:
            memory_node: dict = {"role": "user", "content": memory_content}
        else:
            cls = next(type(m) for m in messages if not isinstance(m, dict))
            try:
                memory_node = cls(role="user", content=memory_content)
            except Exception:
                memory_node = {"role": "user", "content": memory_content}

        return head + [memory_node] + recent

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
        - 追加 role=tool 结果消息
        yield 工具事件（tool_start/tool_approval/tool_result）供上层透传 SSE。
        """
        from app.core.tool_runtime.executor import execute_tool, complete_approval
        from app.core.tool_runtime.events import ToolEventSource
        from app.core.tool_runtime.approval import approval_registry

        assistant_msg = {"role": "assistant", "content": None, "tool_calls": ordered}
        current_messages.append(assistant_msg)

        for tc in ordered:
            event_source = ToolEventSource()
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
                    })

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
        """执行工具调用 + 程序化验证（Phase E4）。

        yield 协议：
          - 透传 _exec_tool_calls 的工具事件（tool_start / tool_approval / tool_result）
          - 追加 verify_result 事件（每个成功动作一条，含 status/evidence）
          - 追加 verification_failed 事件（存在未通过验证时，含注入的反馈文本）

        验证语义：
          - 本轮 status == "success" 的动作 → verifier.verify_all 程序校验
          - 存在 passed 之外的结果 → 向 current_messages 注入【验证反馈】消息，
            驱动 LLM 在下一轮重新执行（Action → Verify → Retry）
          - 全部通过 → 不注入，流程正常继续
        """
        executed_start = len(all_tool_calls)
        async for event in self._exec_tool_calls(
            ordered, ctx, project_path, read_only, current_messages, all_tool_calls, support_approval
        ):
            yield event

        # 仅验证本轮真实发生的动作（status == success）
        round_records = all_tool_calls[executed_start:]
        results = self.verifier.verify_all(round_records, project_path)

        failed = [r for r in results if not r.passed]
        for r in results:
            yield {"type": "verify_result", **r.to_dict()}

        if failed:
            feedback = self._build_verification_feedback(failed)
            current_messages.append({"role": "user", "content": feedback})
            yield {
                "type": "verification_failed",
                "message": feedback,
                "results": [r.to_dict() for r in failed],
            }

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
                out.append({"role": getattr(m, "role", "user"), "content": str(m)})
        return out

    @staticmethod
    def _phase_str(phase) -> str:
        """归一化阶段为字符串（支持 RuntimePhase 枚举 / 字符串）。"""
        return phase.value if isinstance(phase, RuntimePhase) else str(phase)

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
        max_tokens: int = 4096,
        reasoning_effort: Optional[str] = None,
        read_only: bool = False,
    ) -> AgentResult:
        """执行 Agent 调用（非流式，含 Execution Loop）。

        Args:
            context: Agent 执行上下文
            messages: 已组装的 messages 列表（ModelMessage 对象）
            temperature: 模型温度
            max_tokens: 最大 token 数
            reasoning_effort: 推理强度
            read_only: 是否只读模式

        Returns:
            AgentResult: content / usage / rounds / finish_reason / tool_calls / metadata
        """
        from app.services.model import model_service

        # ──── Phase E2: 创建运行记录（status=running, state=pending）────
        run_id = runtime_event_recorder.create_run(
            chat_id=context.chat_id,
            agent_id=context.agent_id,
        )

        try:
            # ──── Phase E5: pending → building_context ────
            self._record_state(run_id, RuntimePhase.BUILDING_CONTEXT, "context build")

            # ──── Context Builder（暂留接口，透传）────
            messages = await self.context_builder.build(context, messages)

            # ──── Phase E5: building_context → routing ────
            self._record_state(run_id, RuntimePhase.ROUTING, "task router")

            # ──── Task Router 决策 ────
            user_message = messages[-1].content if messages else ""
            has_tools = context.tools is not None and len(context.tools) > 0

            decision = self.router.route(
                message=user_message,
                tool_decision=context.decision,
                has_tools=has_tools,
            )

            # ──── Phase E5: routing → llm_call ────
            self._record_state(run_id, RuntimePhase.LLM_CALL, "execution loop")

            # G4-B: TaskGraph 初始化
            has_task_graph = bool(getattr(context, 'plan', None))
            if has_task_graph:
                self.init_task_graph(context.plan)

            # ──── Execution Loop ────
            loop_messages = self._to_dict_messages(messages)
            ctx = {k: v for k, v in (context.memory_context or {}).items() if v is not None}

            all_tool_calls = []
            final_content = ""
            final_usage = None
            final_finish_reason = "stop"

            # G4-B: 外层 TaskGraph 任务循环（无 Plan 时只跑一轮）
            while True:
                current_task = None
                if has_task_graph:
                    current_task = self.get_next_ready_task()
                    if current_task is None:
                        # G4-C: 图中断/阻塞（无就绪节点且未全部终态）→ 剩余 pending 全部 skipped
                        if not self.task_graph_state.is_all_done():
                            self._skip_remaining_and_emit(run_id)
                        break
                    self.update_task_status(current_task.id, "running")
                    runtime_event_recorder.emit(run_id, "task_started",
                        self._task_event_payload(current_task, "running"))
                    # 战略4: Agent 状态可视化 — 任务启动
                    runtime_event_recorder.emit(run_id, "agent_state_update",
                        self._build_agent_state_event(
                            agent_role=self._agent_role_display_name(current_task.assigned_agent),
                            status="working",
                            action_detail=f"开始执行任务: {current_task.action}",
                            current_task_id=current_task.id,
                            task_progress=self._build_task_progress(current_task.id),
                        ))
                    loop_messages.append({
                        "role": "user",
                        "content": f"【当前任务】{current_task.action}",
                    })
                    # G5-B: 注入 persona prompt
                    persona_prompt = get_persona_prompt(current_task.assigned_agent)
                    if persona_prompt:
                        loop_messages.append({"role": "system", "content": persona_prompt})

                round_no = 0
                task_content = ""

                # G4-C: 单任务异常边界 — 任务失败不使整个 AgentRun failed，
                # 而是 failed + 级联 skip 依赖 + task_failed/task_skipped 事件后收尾
                try:
                    while round_no < MAX_ROUNDS:
                        round_tools = context.tools if round_no < MAX_ROUNDS - 1 else None

                        result = await model_service.call_once(
                            model_id=context.model_id,
                            messages=loop_messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            tools=round_tools,
                            reasoning_effort=reasoning_effort,
                            memory_text=context.memory_text if round_no == 0 and not has_task_graph else None,
                        )

                        final_usage = result.usage
                        final_finish_reason = result.finish_reason
                        # G6-A: emit token_usage 事件
                        if final_usage:
                            runtime_event_recorder.emit(run_id, "token_usage",
                                self._build_token_usage_event(final_usage, context.model_id))

                        if not result.tool_calls or not round_tools:
                            task_content = result.content
                            break

                        round_no += 1

                        # 战略4: Agent 状态可视化 — 工具调用前
                        tool_names = [tc.get("function", {}).get("name", "") for tc in result.tool_calls]
                        agent_role = self._agent_role_display_name(current_task.assigned_agent) if current_task else "Default Agent"
                        runtime_event_recorder.emit(run_id, "agent_state_update",
                            self._build_agent_state_event(
                                agent_role=agent_role,
                                status="waiting_for_tool",
                                action_detail=f"准备调用工具: {', '.join(tool_names)}",
                                current_task_id=current_task.id if current_task else None,
                                task_progress=self._build_task_progress(current_task.id if current_task else None),
                            ))

                        self._record_state(run_id, RuntimePhase.TOOL_EXECUTION, "tool execution")
                        async for event in self._exec_tool_calls_with_verification(
                            result.tool_calls,
                            ctx,
                            context.project_path,
                            read_only,
                            loop_messages,
                            all_tool_calls,
                            support_approval=False,
                        ):
                            runtime_event_recorder.emit(
                                run_id,
                                event.get("type", "event"),
                                {k: v for k, v in event.items() if k != "type"},
                            )

                        self._record_state(run_id, RuntimePhase.VERIFYING, "verification")
                        self._record_state(run_id, RuntimePhase.LLM_CALL, "next round")
                        # 战略4: Agent 状态可视化 — 工具执行完成
                        agent_role = self._agent_role_display_name(current_task.assigned_agent) if current_task else "Default Agent"
                        runtime_event_recorder.emit(run_id, "agent_state_update",
                            self._build_agent_state_event(
                                agent_role=agent_role,
                                status="working",
                                action_detail="工具执行完成，继续分析",
                                current_task_id=current_task.id if current_task else None,
                                task_progress=self._build_task_progress(current_task.id if current_task else None),
                            ))

                    # 轮次耗尽时无最终内容 → 补一次无工具调用获取总结
                    if not task_content:
                        result = await model_service.call_once(
                            model_id=context.model_id,
                            messages=loop_messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            tools=None,
                            reasoning_effort=reasoning_effort,
                            memory_text=None,
                        )
                        task_content = result.content
                        final_usage = result.usage
                        final_finish_reason = "max_rounds"

                    final_content = task_content

                    # G4-B: 任务完成 → emit + 继续下一个
                    if has_task_graph and current_task:
                        self.update_task_status(current_task.id, "completed")
                        # 战略4: Agent 状态可视化 — 任务完成
                        runtime_event_recorder.emit(run_id, "agent_state_update",
                            self._build_agent_state_event(
                                agent_role=self._agent_role_display_name(current_task.assigned_agent),
                                status="completed",
                                action_detail=f"任务完成: {current_task.action}",
                                current_task_id=current_task.id,
                                task_progress=self._build_task_progress(current_task.id),
                            ))
                        runtime_event_recorder.emit(run_id, "task_completed",
                            self._task_event_payload(current_task, "completed"))
                        continue

                    break  # 无 Plan → 结束
                except Exception as e:
                    # G4-C: 单任务异常 → failed + 级联 skip 依赖 + 事件；运行正常收尾
                    if has_task_graph and current_task:
                        # 战略4: Agent 状态可视化 — 任务失败
                        runtime_event_recorder.emit(run_id, "agent_state_update",
                            self._build_agent_state_event(
                                agent_role=self._agent_role_display_name(current_task.assigned_agent),
                                status="error",
                                action_detail=f"任务失败: {current_task.action}",
                                current_task_id=current_task.id,
                                task_progress=self._build_task_progress(current_task.id),
                            ))
                        healed = await self._handle_task_failure(run_id, current_task, e)
                        if healed:
                            continue  # 反思成功，继续执行循环
                        break
                    raise

            # ──── Phase E5: → completing → completed ────
            self._record_state(run_id, RuntimePhase.COMPLETING, "finishing")
            runtime_event_recorder.transition(run_id, RuntimePhase.COMPLETED.value, "completed")
            # Phase E2: 收尾（completed）
            runtime_event_recorder.finish_run(run_id, "completed")

            return AgentResult(
                content=final_content,
                usage=final_usage,
                rounds=round_no + 1 if final_content else round_no,
                finish_reason=final_finish_reason,
                tool_calls=all_tool_calls,
                metadata={
                    **(context.metadata or {}),  # G2-C: 透传 ContextBuilder metadata
                    "agent_id": context.agent_id,
                    "model_id": context.model_id,
                    "personality_level": context.personality_level,
                    "task_type": decision.task_type.value,
                    "intent": decision.intent,
                    "confidence": decision.confidence,
                    "reason": decision.reason,
                    # G6-A: Token 水位信息
                    "token_watermark": self._build_token_usage_event(final_usage, context.model_id) if final_usage else None,
                    # G4-C: TaskGraph 进度摘要（含 completed/failed/skipped/current_step）
                    "task_graph": self._task_graph_summary(),
                },
            )
        except asyncio.CancelledError:
            runtime_event_recorder.transition(run_id, RuntimePhase.CANCELLED.value, "cancelled")
            runtime_event_recorder.finish_run(run_id, "cancelled")
            raise
        except Exception as e:
            runtime_event_recorder.transition(run_id, RuntimePhase.FAILED.value, str(e)[:200])
            runtime_event_recorder.emit(run_id, "error", {"message": str(e)})
            runtime_event_recorder.finish_run(run_id, "failed")
            raise

    # ──── 流式执行 ────

    async def run_stream(
        self,
        context: AgentContext,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 4096,
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
        )
        try:
            async for event in self._run_stream_events(
                context, messages, temperature, max_tokens, reasoning_effort, read_only, max_tool_rounds
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
            runtime_event_recorder.transition(run_id, RuntimePhase.FAILED.value, str(e)[:200])
            runtime_event_recorder.emit(run_id, "error", {"message": str(e)})
            runtime_event_recorder.finish_run(run_id, "failed")
            raise

    async def _run_stream_events(
        self,
        context: AgentContext,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 4096,
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

        # G4-B: TaskGraph 初始化
        has_task_graph = bool(getattr(context, 'plan', None))
        if has_task_graph:
            self.init_task_graph(context.plan)

        # ──── Phase E5: building_context → llm_call（流式路径无独立 Router）────
        yield {"type": "state_change", "state": RuntimePhase.LLM_CALL.value, "reason": "execution loop"}

        ctx = {k: v for k, v in (context.memory_context or {}).items() if v is not None}

        current_messages = self._to_dict_messages(messages)
        all_tool_calls = []
        available_names = {t["function"]["name"] for t in (context.tools or [])} if context.tools else set()

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
                # 注入任务上下文，让 LLM 知道当前执行步骤
                current_messages.append({
                    "role": "user",
                    "content": f"【当前任务】{current_task.action}",
                })
                # G5-B: 注入 persona prompt
                persona_prompt = get_persona_prompt(current_task.assigned_agent)
                if persona_prompt:
                    current_messages.append({"role": "system", "content": persona_prompt})

            task_done = False
            try:
                for round_no in range(max_tool_rounds + 1):
                    round_tools = context.tools if round_no < max_tool_rounds else None

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
                        memory_text=context.memory_text if round_no == 0 and not has_task_graph else None,
                    ):
                        etype = event.get("type")
                        if etype == "text":
                            round_text += event.get("content", "")
                            yield event
                        elif etype == "thinking":
                            yield event
                        elif etype == "tool_calls":
                            collected_tool_calls = {i: c for i, c in enumerate(event.get("calls", []))}
                        elif etype == "finish":
                            final_finish = event.get("finish_reason", "stop")
                            # G6-A: 捕获 usage，yield token_usage 事件
                            round_usage = event.get("usage")
                            if round_usage:
                                yield self._build_token_usage_event(round_usage, context.model_id)

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
                        self.update_task_status(current_task.id, "completed")
                        # 战略4: Agent 状态可视化 — 任务完成
                        yield {"type": "agent_state_update", **self._build_agent_state_event(
                            agent_role=self._agent_role_display_name(current_task.assigned_agent),
                            status="completed",
                            action_detail=f"任务完成: {current_task.action}",
                            current_task_id=current_task.id,
                            task_progress=self._build_task_progress(current_task.id),
                        )}
                        yield {
                            "type": "task_completed",
                            **self._task_event_payload(current_task, "completed"),
                        }
                        task_done = True
                        break  # 跳出内层 for，回到外层 while 取下一个任务
                    else:
                        # 原始路径（无 Plan）：透传 finish + 工具调用汇总
                        yield {"type": "state_change", "state": RuntimePhase.COMPLETING.value, "reason": "finishing"}
                        yield {"type": "finish", "finish_reason": final_finish}
                        if all_tool_calls:
                            yield {"type": "tool_calls", "calls": all_tool_calls}
                        return

                # 内层 for 耗尽（rounds exhausted）
                if has_task_graph and current_task:
                    if not task_done:
                        # 标记为 completed（尽力而为，LLM 已有输出）
                        self.update_task_status(current_task.id, "completed")
                        # 战略4: Agent 状态可视化 — 任务完成（轮次耗尽）
                        yield {"type": "agent_state_update", **self._build_agent_state_event(
                            agent_role=self._agent_role_display_name(current_task.assigned_agent),
                            status="completed",
                            action_detail=f"任务完成（轮次耗尽）: {current_task.action}",
                            current_task_id=current_task.id,
                            task_progress=self._build_task_progress(current_task.id),
                        )}
                        yield {
                            "type": "task_completed",
                            **self._task_event_payload(current_task, "completed"),
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
                        yield {"type": "finish", "finish_reason": "stop"}
                        yield {"type": "tool_calls", "calls": all_tool_calls}
                    except Exception as e:
                        yield {"type": "error", "message": f"工具执行完成，但最终总结生成失败: {e}"}
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

                    # 战略方向: 尝试反思自愈
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
                        # 反思成功事件
                        yield {"type": "agent_state_update", **self._build_agent_state_event(
                            agent_role=self._agent_role_display_name(current_task.assigned_agent),
                            status="working",
                            action_detail="动态生成修复计划，恢复执行",
                            current_task_id=current_task.id,
                            task_progress=self._build_task_progress(current_task.id),
                        )}
                        continue  # 反思成功，回到外层循环取下一个任务

                    # 降级：原始失败路径
                    skipped = self.task_graph_state.mark_failed(
                        current_task.id, str(e)[:200]
                    )
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
        yield {"type": "state_change", "state": RuntimePhase.COMPLETING.value, "reason": "all tasks done"}
        yield {"type": "finish", "finish_reason": "stop"}
        if all_tool_calls:
            yield {"type": "tool_calls", "calls": all_tool_calls}
