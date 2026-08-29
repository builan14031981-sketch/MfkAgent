# -*- coding: utf-8 -*-
"""T4 归档：旧版非流式 run() 实现（独立双循环，已被 run_stream() 消费者取代）。

保留一个发布周期（自 feat/t4-unify-loop 合入起算），期满删除。
仅作回滚对照 / 行为审计用：运行时无任何引用（AgentRuntime.run 现为
run_stream() 事件流的消费者，见 agent.py）。
回滚方式：整单 revert feat/t4-unify-loop（单分支单 revert）。

如需对照行为，可手动调用：await legacy_run(runtime, context, messages, ...)
"""
from __future__ import annotations

from typing import Optional

# 归档实现引用的 agent.py 模块级名字（单向依赖：本模块 → agent.py，agent.py 不回引）
from app.core.agent_runtime.agent import (  # noqa: F401
    AgentContext,
    AgentResult,
    COMPRESS_MIN_INTERVAL_ROUNDS,
    COUNTDOWN_WARNING,
    ModelConfigError,
    ModelNotFoundError,
    RuntimePhase,
    SELF_CHECK_PROMPT,
    WRITE_TOOLS,
    _apply_turn_reminder,
    _strip_tool_call_blocks,
    _wrap_runtime_context,
    build_test_infra_summary,
    get_persona_prompt,
    runtime_event_recorder,
)


async def legacy_run(
    self,
    context: AgentContext,
    messages: list,
    temperature: float = 0.7,
    max_tokens: int = 16384,
    reasoning_effort: Optional[str] = None,
    read_only: bool = False,
    max_tool_rounds: Optional[int] = None,
) -> AgentResult:
    """【归档】旧版非流式执行（独立 Execution Loop；T4 前的 run() 原实现）。"""
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
    # Phase H: parent_run_id 记录 checkpoint 血缘（断点续跑追溯）
    run_id = runtime_event_recorder.create_run(
        chat_id=context.chat_id,
        agent_id=context.agent_id,
        parent_run_id=getattr(context, "parent_run_id", None),
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
        ctx.setdefault("chat_id", context.chat_id)

        # ──── Phase 11: 解析 max_tool_rounds & 初始化自查状态 ────
        resolved_max_rounds = self._resolve_max_tool_rounds(context, max_tool_rounds)
        has_modified_code = False
        self_check_done = False

        all_tool_calls = []
        final_content = ""
        final_usage = None
        final_finish_reason = "stop"

        # ──── Phase 12: Completion Loop V1 配置 ────
        completion_enabled = self._completion_enabled(context, has_task_graph)
        max_completion_retry = getattr(context, "max_completion_retry", None) or DEFAULT_MAX_COMPLETION_RETRY
        completion_retry_count = 0
        completion_exhausted = None
        # Round 2 优化：run 级失败标记与最后一次验证失败（用于兜底失败汇报）
        any_completion_failed = False
        run_completion_exhausted = None
        # G6-B Auto: 自动压缩轮次跟踪
        last_compress_round = 0

        # Round 2 优化：测试基建（conftest fixture）摘要一次性注入，避免重复 read_file
        _test_infra = build_test_infra_summary(
            context.project_path, self._extract_task_goal(loop_messages)
        )
        if _test_infra:
            loop_messages.append({
                "role": "system",
                "content": _wrap_runtime_context(_test_infra, source="MfkAgent TestInfra"),
            })

        # T1 缓存前缀契约：逐轮动态内容（⑦⑧⑨⑩）以 <system-reminder> 包裹到
        # 本轮最后一条 user 消息副本末尾（仅 LLM payload，不动 DB 历史消息）
        _apply_turn_reminder(loop_messages, (context.metadata or {}).get("turn_reminder"))

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
                # Round 2 优化：任务间隔离完成验证状态 + 轮次预算差异化（P6）
                completion_retry_count = 0
                completion_exhausted = None
                task_rounds = self._task_round_budget(current_task.action, resolved_max_rounds)
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
                # Phase 3.5: Runtime Context 边界隔离 — 任务上下文以 system 角色注入
                loop_messages.append({
                    "role": "system",
                    "content": _wrap_runtime_context(
                        f"【当前任务】{current_task.action}",
                        source="MfkAgent TaskGraph",
                    ),
                })
                # G5-B: 注入 persona prompt（Phase 3.5: 包装为 Runtime Context）
                persona_prompt = get_persona_prompt(current_task.assigned_agent)
                if persona_prompt:
                    loop_messages.append({
                        "role": "system",
                        "content": _wrap_runtime_context(persona_prompt, source="MfkAgent AgentRouter"),
                    })

            round_no = 0
            task_content = ""
            if not has_task_graph:
                task_rounds = resolved_max_rounds

            # G4-C: 单任务异常边界 — 任务失败不使整个 AgentRun failed，
            # 而是 failed + 级联 skip 依赖 + task_failed/task_skipped 事件后收尾
            try:
                while round_no < task_rounds:
                    # G6-B Auto: 水位超阈值自动压缩历史（基于上一轮 usage，首轮跳过）
                    if (
                        round_no > 0
                        and final_usage
                        and (round_no - last_compress_round) >= COMPRESS_MIN_INTERVAL_ROUNDS
                    ):
                        if await self._maybe_auto_compress(
                            run_id, loop_messages, final_usage, context.model_id
                        ):
                            last_compress_round = round_no
                            # 压缩可能吞掉本轮任务上下文 → 重新注入
                            if has_task_graph and current_task is not None:
                                loop_messages.append({
                                    "role": "system",
                                    "content": _wrap_runtime_context(
                                        f"【当前任务】{current_task.action}",
                                        source="MfkAgent TaskGraph",
                                    ),
                                })

                    round_tools = context.tools if round_no < task_rounds - 1 else None

                    # ──── Phase 11: 倒数预警（第 task_rounds - 1 轮，即最后一轮有工具时）────
                    if round_no == task_rounds - 2:
                        loop_messages.append({
                            "role": "system",
                            "content": COUNTDOWN_WARNING,
                        })

                    result = await model_service.call_once(
                        model_id=context.model_id,
                        messages=loop_messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=round_tools,
                        reasoning_effort=reasoning_effort,
                        # T1: 记忆每轮一致常驻（确定性文本，保证 system 前缀跨轮稳定）
                        memory_text=context.memory_text,
                        vision_context=context.vision_context if round_no == 0 else None,
                    )

                    final_usage = result.usage
                    final_finish_reason = result.finish_reason
                    # G6-A: emit token_usage 事件
                    if final_usage:
                        runtime_event_recorder.emit(run_id, "token_usage",
                            self._build_token_usage_event(final_usage, context.model_id))

                    if not result.tool_calls or not round_tools:
                        # ──── Phase 11: 强制自查插队拦截 ────
                        if has_modified_code and not self_check_done and round_no < task_rounds:
                            loop_messages.append({
                                "role": "system",
                                "content": SELF_CHECK_PROMPT,
                            })
                            self_check_done = True
                            continue

                        # Round 3 修复：最后一轮工具已禁用（round_tools 为 None）但模型仍输出
                        # 工具调用 → 强制纯文本收尾，避免 final_content 变成原始 <tool_call>
                        # 序列化文本（子代理编排断链根因）
                        if result.tool_calls:
                            runtime_event_recorder.emit(run_id, "agent_state_update",
                                self._build_agent_state_event(
                                    agent_role=self._agent_role_display_name(
                                        current_task.assigned_agent if current_task else "default_agent"
                                    ),
                                    status="working",
                                    action_detail="工具已禁用但模型仍请求工具，强制纯文本收尾",
                                    current_task_id=current_task.id if current_task else None,
                                    task_progress=self._build_task_progress(
                                        current_task.id if current_task else None
                                    ),
                                ))
                            loop_messages.append({
                                "role": "system",
                                "content": "工具调用已不可用。请基于你已获得的工具执行结果，直接以纯文本输出最终结论或报告，"
                                           "严禁再输出任何 <tool_call> / <arg_*_> 格式的工具调用内容。",
                            })
                            result = await model_service.call_once(
                                model_id=context.model_id,
                                messages=loop_messages,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                tools=None,
                                reasoning_effort=reasoning_effort,
                            )
                            final_usage = result.usage
                            final_finish_reason = result.finish_reason
                            if result.tool_calls:
                                # 模型仍固执输出工具调用格式 → 剥壳兜底
                                task_content = _strip_tool_call_blocks(result.content or "") \
                                    or "[执行完成：工具已执行，但模型未输出文本总结]"
                            else:
                                task_content = result.content
                        else:
                            task_content = result.content

                        # ──── Phase 12: Completion Loop V1 — 完成候选验证 ────
                        if completion_enabled:
                            # 规则层语义判定（write/test 意图）以用户真实目标为准；
                            # 模板任务名（如“执行文件读取或修改”）不作判定依据，避免误伤只读任务
                            task_goal = self._extract_task_goal(loop_messages)
                            runtime_event_recorder.emit(
                                run_id, "completion_verify_started",
                                {"task_goal": task_goal, "round_no": round_no},
                            )
                            completion_result = await self._verify_completion(
                                context, task_goal, task_content, current_task,
                                all_tool_calls, loop_messages,
                            )
                            if completion_result.success:
                                runtime_event_recorder.emit(
                                    run_id, "completion_verify_passed",
                                    completion_result.to_dict(),
                                )
                                break

                            # 验证失败 → 生成反馈上下文，重新进入 Agent Loop
                            runtime_event_recorder.emit(run_id, "completion_verify_failed", {
                                **completion_result.to_dict(),
                                "retry_count": completion_retry_count,
                                "max_retry": max_completion_retry,
                            })
                            if completion_retry_count < max_completion_retry:
                                completion_retry_count += 1
                                loop_messages.append({
                                    "role": "user",
                                    "content": self._build_completion_feedback(completion_result, completion_retry_count),
                                })
                                continue
                            # 超过重试上限 → 安全收尾（保留已完成内容 + 未完成原因 + 最后失败点）
                            completion_exhausted = completion_result
                            run_completion_exhausted = completion_result
                            final_finish_reason = "completion_exhausted"
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

                    # ──── Phase 11: 写操作检测 ────
                    if not has_modified_code:
                        for tc in result.tool_calls:
                            tool_name = tc.get("function", {}).get("name", "")
                            if tool_name in WRITE_TOOLS:
                                has_modified_code = True
                                break

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

                    # Phase 12: 轮次耗尽的兜底完成候选同样过验证（失败不再重试，安全收尾）
                    if completion_enabled:
                        task_goal = self._extract_task_goal(loop_messages)
                        runtime_event_recorder.emit(
                            run_id, "completion_verify_started",
                            {"task_goal": task_goal, "round_no": round_no, "fallback": True},
                        )
                        completion_result = await self._verify_completion(
                            context, task_goal, task_content, current_task,
                            all_tool_calls, loop_messages,
                        )
                        if completion_result.success:
                            runtime_event_recorder.emit(
                                run_id, "completion_verify_passed",
                                completion_result.to_dict(),
                            )
                        else:
                            runtime_event_recorder.emit(run_id, "completion_verify_failed", {
                                **completion_result.to_dict(),
                                "retry_count": completion_retry_count,
                                "max_retry": max_completion_retry,
                            })
                            completion_exhausted = completion_result
                            run_completion_exhausted = completion_result

                final_content = task_content

                # G4-B: 任务完成 → emit + 继续下一个
                if has_task_graph and current_task:
                    if self._is_hard_completion_failure(completion_exhausted):
                        # Round 2 优化：硬性缺失 → failed + 级联 skip（此前为强制 completed 短路）
                        skipped = self.task_graph_state.mark_failed(
                            current_task.id,
                            "; ".join(getattr(completion_exhausted, "missing_items", None) or [])[:200],
                        )
                        runtime_event_recorder.emit(run_id, "agent_state_update",
                            self._build_agent_state_event(
                                agent_role=self._agent_role_display_name(current_task.assigned_agent),
                                status="error",
                                action_detail=f"任务失败（完成验证未通过）: {current_task.action}",
                                current_task_id=current_task.id,
                                task_progress=self._build_task_progress(current_task.id),
                            ))
                        runtime_event_recorder.emit(run_id, "task_failed", {
                            **self._task_event_payload(
                                current_task, "failed",
                                error=getattr(completion_exhausted, "reason", "")[:200],
                            ),
                            **self._completion_event_suffix(completion_enabled, completion_exhausted),
                        })
                        for skip_id in skipped:
                            skip_node = self.task_graph_state.get_task(skip_id)
                            if skip_node is not None:
                                runtime_event_recorder.emit(run_id, "task_skipped",
                                    self._task_event_payload(skip_node, "skipped"))
                        any_completion_failed = True
                        continue
                    self.update_task_status(current_task.id, "completed")
                    if completion_exhausted is not None:
                        # 软性缺失 → completed_unverified：不级联中断，但计入 run 级失败标记
                        any_completion_failed = True
                    # 战略4: Agent 状态可视化 — 任务完成
                    runtime_event_recorder.emit(run_id, "agent_state_update",
                        self._build_agent_state_event(
                            agent_role=self._agent_role_display_name(current_task.assigned_agent),
                            status="completed",
                            action_detail=(
                                f"任务完成（未通过完成验证）: {current_task.action}"
                                if completion_exhausted is not None
                                else f"任务完成: {current_task.action}"
                            ),
                            current_task_id=current_task.id,
                            task_progress=self._build_task_progress(current_task.id),
                        ))
                    runtime_event_recorder.emit(run_id, "task_completed",
                        {
                            **self._task_event_payload(current_task, "completed"),
                            **self._completion_event_suffix(completion_enabled, completion_exhausted),
                        })
                    continue

                # 无 Plan → 结束
                break
            except ModelNotFoundError as e:
                # 模型不存在 → 直接熔断，不尝试反思（反思用同一模型也会失败）
                if has_task_graph and current_task:
                    runtime_event_recorder.emit(run_id, "agent_state_update",
                        self._build_agent_state_event(
                            agent_role=self._agent_role_display_name(current_task.assigned_agent),
                            status="error",
                            action_detail=f"模型不可用: {e}",
                            current_task_id=current_task.id,
                            task_progress=self._build_task_progress(current_task.id),
                        ))
                    self.task_graph_state.mark_failed(current_task.id, str(e)[:200])
                raise
            except ModelConfigError as e:
                # 模型配置错误（无 Key / 未注册）→ 直接熔断，不尝试反思
                # 反思用同一无 Key 模型也会失败，无意义
                if has_task_graph and current_task:
                    runtime_event_recorder.emit(run_id, "agent_state_update",
                        self._build_agent_state_event(
                            agent_role=self._agent_role_display_name(current_task.assigned_agent),
                            status="error",
                            action_detail=f"模型配置错误: {e}",
                            current_task_id=current_task.id,
                            task_progress=self._build_task_progress(current_task.id),
                        ))
                    self.task_graph_state.mark_failed(current_task.id, str(e)[:200])
                raise
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

        # Round 2 优化：完成验证失败时覆写 finish_reason；无内容时生成结构化失败汇报（杜绝空回复）
        if any_completion_failed or run_completion_exhausted is not None:
            final_finish_reason = "completion_failed"
            if not (final_content or "").strip() and run_completion_exhausted is not None:
                final_content = self._build_completion_failure_report(run_completion_exhausted)

        # 杜绝空回复：当 final_content 为空时保底生成说明文本，解决数据库 content=None 导致的空消息悬空问题
        if not (final_content or "").strip():
            if all_tool_calls:
                final_content = "已为您完成相关的处理与工具调用。"
            else:
                final_content = "处理完成。"

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
                # Phase 12: Completion Loop V1 结果信息
                "completion": self._completion_metadata(completion_enabled, completion_exhausted, completion_retry_count),
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

