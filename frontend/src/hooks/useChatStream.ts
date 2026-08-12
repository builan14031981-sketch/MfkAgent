import { useCallback, useRef, useEffect, useMemo } from "react";
import type { Message, useMessages, TimelineEvent } from "@/hooks/useMessages";
import type { ToolCall } from "@/components/ToolCallCard";
import type { ReasoningEffort } from "@/components/ChatInput";
import type { PermissionMode } from "@/components/chat-input/PermissionSelector";
import { FALLBACK_MODEL_ID } from "@/lib/modelDefaults";
import type { Attachment } from "@/components/FileDropZone";
import { apiPost } from "@/lib/api";
import { showDesktopNotification } from "@/lib/notify";
import { formatDuration } from "@/lib/format";
import { useStreamStore, OrbStage } from "@/lib/streamStore";
import type { RuntimeEvent, ApprovalRequest, TaskNode, TaskEvent, TokenUsageEvent, AgentStateUpdateEvent, ThinkingIndicatorEvent } from "@/types/runtime";

type SendMessageStream = ReturnType<typeof useMessages>["sendMessageStream"];
type AppendMessage = ReturnType<typeof useMessages>["appendMessage"];

export type { ApprovalRequest };

/** @deprecated 兼容旧引用：请改用 RuntimeEvent（判别联合更完整，含未来扩展类型） */
export type TimelineSegment = RuntimeEvent;

export interface UseChatStreamParams {
  chatId: number | null;
  sendMessageStream: SendMessageStream;
  appendMessage: AppendMessage;
  refetch: () => Promise<void>;
}

export interface SendStreamOptions {
  /** 模型 id；缺省回退默认模型 */
  modelId?: string | null;
  personalityLevel?: number;
  reasoningEffort?: ReasoningEffort;
  /** 权限/执行模式：safe（安全）/ standard（标准）/ autonomous（自主） */
  permissionMode?: PermissionMode;
  /** 是否乐观追加用户消息到本地列表（重试/重新生成时已有消息，置 false） */
  appendUserMessage?: boolean;
  /** 发送前对消息做变换（如拼接项目文件上下文）；返回原始值则不拼 */
  buildContent?: (content: string) => Promise<string> | string;
  /** 本条消息关联的附件元数据（传递给后端，后端实现前由 buildContent 兜底） */
  attachments?: Attachment[];
}

/**
 * 聊天流式发送统一管线（Phase 2 多会话并发架构）：
 *
 * 核心变更：
 * - 所有流状态（timeline / isSending / tasks 等）存储在全局 useStreamStore 中，按 chatId 索引
 * - 废弃"切换 chatId 时 abort 旧 SSE"的错误逻辑 —— 切换会话仅切换 UI 订阅的 chatId
 * - 每个 chatId 维护独立的 AbortController，仅在用户手动点击"停止生成"时 abort
 * - 后台 SSE 连接持续运行，切回会话时 UI 自动恢复最新 timeline
 * - appendMessage / refetch 使用 activeChatIdRef 守卫：仅当目标 chatId 是当前活跃会话时才操作本地消息列表
 */
export function useChatStream({
  chatId,
  sendMessageStream,
  appendMessage,
  refetch,
}: UseChatStreamParams) {
  // 从全局 store 读取当前 chatId 的会话状态
  const session = useStreamStore((s) => (chatId != null ? s.sessions[chatId] : undefined));
  const store = useStreamStore();

  // 派生响应式状态（session 不存在时使用默认值）
  const isSending = session?.isSending ?? false;
  const timeline = session?.timeline ?? [];
  const tasks = session?.tasks ?? [];
  const tokenUsage = session?.tokenUsage ?? null;
  const streamingError = session?.streamingError ?? null;
  const reasoningActive = session?.reasoningActive ?? false;
  const currentAgentState = session?.currentAgentState ?? null;

  /** activeChatIdRef：始终跟踪当前 UI 活跃的 chatId（用于 appendMessage/refetch 守卫） */
  const activeChatIdRef = useRef<number | null>(chatId);
  activeChatIdRef.current = chatId;

  /** 从 timeline 末位事件派生 Orb 阶段 */
  const orbStage = useMemo<OrbStage | null>(() => {
    if (!isSending) return null;
    if (timeline.length === 0) return "working";
    const last = timeline[timeline.length - 1];
    switch (last.type) {
      case "thinking":
      case "thinking_indicator":
        return "solving";
      case "tool":
        return "searching";
      case "approval":
        return "listening";
      case "text":
        return "composing";
      default:
        return "working";
    }
  }, [isSending, timeline]);

  // 同步全局流式状态：侧边栏/头部按 chatId 读取加载阶段
  useEffect(() => {
    if (chatId == null) return;
    useStreamStore.getState().setStream(chatId, orbStage);
    return () => {
      // 仅当该 chatId 不在发送中时清除指示器（后台流仍在运行时保持）
      const s = useStreamStore.getState().getSession(chatId);
      if (!s.isSending) {
        useStreamStore.getState().setStream(chatId, null);
      }
    };
  }, [chatId, orbStage]);

  /** 重置指定 chatId 的流状态（操作全局 store + 清理 refs） */
  const resetStreaming = useCallback((targetChatId: number) => {
    const refs = store.getRefs(targetChatId);
    refs.toolIndex.clear();
    refs.taskIndex.clear();
    refs.thinkingBuffer = "";
    if (refs.thinkingRaf != null) {
      cancelAnimationFrame(refs.thinkingRaf);
      refs.thinkingRaf = null;
    }
    refs.firstText = true;
    if (refs.agentStateTimer) {
      clearTimeout(refs.agentStateTimer);
      refs.agentStateTimer = null;
    }
    store.resetSession(targetChatId);
    // 同步清除侧边栏加载指示器（后台会话出错时页面 effect 不会触发）
    store.setStream(targetChatId, null);
  }, [store]);

  /** 用户手动停止生成：abort 当前 chatId 的 SSE 连接 */
  const stop = useCallback(() => {
    if (chatId == null) return;
    const refs = store.getRefs(chatId);
    refs.abortController?.abort();
    refs.abortController = null;
    store.updateSession(chatId, () => ({ isSending: false }));
  }, [chatId, store]);

  /** 用户批准/拒绝待审批命令 */
  const resolveApproval = useCallback(
    async (approvalId: string, action: "approve" | "deny", toolCallId?: string) => {
      if (!chatId) return;
      // 重复点击保护：检查当前状态是否已处理
      const session = store.getSession(chatId);
      const existing = session.timeline.find(
        (s) => s.type === "approval" && s.approval.approval_id === approvalId
      );
      if (existing?.type === "approval" && existing.approval.resolvedAction) return;
      const resolvedAction = action === "approve" ? "approved" : "rejected";
      // 乐观 UI：立即将卡片置为只读状态
      store.updateSession(chatId, (prev) => ({
        timeline: prev.timeline.map((s) => {
          if (s.type === "approval" && s.approval.approval_id === approvalId) {
            return { ...s, approval: { ...s.approval, resolvedAction } };
          }
          return s;
        }),
      }));
      try {
        const body = toolCallId
          ? { tool_call_id: toolCallId, decision: resolvedAction }
          : { approval_id: approvalId, action };
        await apiPost(`/api/chat/${chatId}/approve`, body);
      } catch (err) {
        console.error("Failed to resolve approval:", err);
        // 失败回退
        store.updateSession(chatId, (prev) => ({
          timeline: prev.timeline.map((s) => {
            if (s.type === "approval" && s.approval.approval_id === approvalId) {
              return { ...s, approval: { ...s.approval, resolvedAction: undefined } };
            }
            return s;
          }),
        }));
      }
    },
    [chatId, store]
  );

  /** 用户对 ask_user_choice 抉择卡做反馈。
   *  - selected：选中的预设选项下标
   *  - customText：用户输入的自定义想法（与 selected 二选一）
   *  - skip：true 表示"跳过"，后端按"采纳推荐项"处理（custom_text="(用户跳过)"）
   *  - timeout：true 表示超时自动采纳，仅前端使用，不发请求（后端自己处理超时）
   */
  const resolveChoice = useCallback(
    async (
      choiceId: string,
      options: { selected?: number; customText?: string; skip?: boolean; timeout?: boolean } = {}
    ) => {
      if (!chatId) return;
      const session = store.getSession(chatId);
      const existing = session.timeline.find(
        (s) => s.type === "user_choice" && s.choice.choice_id === choiceId
      );
      if (existing?.type === "user_choice" && existing.choice.resolvedAction) return;

      // 内部超时：仅前端标记 resolvedAction=true，不发请求（后端会自行采纳推荐项）
      if (options.timeout) {
        store.updateSession(chatId, (prev) => ({
          timeline: prev.timeline.map((s) => {
            if (s.type === "user_choice" && s.choice.choice_id === choiceId) {
              return { ...s, choice: { ...s.choice, resolvedAction: { kind: "timeout" as const } } };
            }
            return s;
          }),
        }));
        return;
      }

      // 跳过语义：custom_text="(用户跳过)" 标记
      const customText = options.skip
        ? "(用户跳过)"
        : (options.customText || "").trim() || undefined;

      const resolvedAction: { kind: "selected"; selected: number } | { kind: "skipped" } =
        options.skip
          ? { kind: "skipped" as const }
          : { kind: "selected" as const, selected: options.selected ?? 0 };

      // 乐观 UI：立即将卡片置为只读状态
      store.updateSession(chatId, (prev) => ({
        timeline: prev.timeline.map((s) => {
          if (s.type === "user_choice" && s.choice.choice_id === choiceId) {
            return { ...s, choice: { ...s.choice, resolvedAction } };
          }
          return s;
        }),
      }));

      try {
        await apiPost(`/api/chat/${chatId}/choice`, {
          choice_id: choiceId,
          selected: options.skip ? null : options.selected ?? null,
          custom_text: customText || null,
        });
      } catch (err) {
        console.error("Failed to resolve choice:", err);
        // 失败回退
        store.updateSession(chatId, (prev) => ({
          timeline: prev.timeline.map((s) => {
            if (s.type === "user_choice" && s.choice.choice_id === choiceId) {
              return { ...s, choice: { ...s.choice, resolvedAction: undefined } };
            }
            return s;
          }),
        }));
      }
    },
    [chatId, store]
  );

  const sendStream = useCallback(
    async (content: string, options: SendStreamOptions = {}) => {
      if (!chatId) throw new Error("No chat selected");
      const targetChatId = chatId; // 捕获发送时的 chatId，后续所有操作都使用此值
      const startedAt = Date.now(); // 任务开始时刻：用于完成通知与用时展示

      // “用户离开”判定（系统通知触发条件）：切到其他会话/离开聊天页（全局活跃会话追踪，
      // 不受组件卸载后 ref 冻结影响）、窗口最小化/隐藏、或焦点在其他应用——任一成立即弹通知；
      // 用户正在查看该会话时界面已有反馈，不重复弹。
      const isUserAway = (): boolean =>
        useStreamStore.getState().activeChatId !== targetChatId ||
        (typeof document !== "undefined" &&
          (document.visibilityState !== "visible" || !document.hasFocus()));
      const { modelId, personalityLevel, reasoningEffort, permissionMode, appendUserMessage = true, buildContent, attachments } = options;

      const refs = store.getRefs(targetChatId);

      // 如果该会话已有进行中的流，先中断（同会话重复发送防御，非跨会话）
      refs.abortController?.abort();
      refs.abortController = null;

      // 设置发送状态 + 重置流状态
      store.updateSession(targetChatId, () => ({
        isSending: true,
        timeline: [],
        tasks: [],
        tokenUsage: null,
        streamingError: null,
        currentAgentState: null,
        reasoningActive: false,
      }));
      refs.toolIndex.clear();
      refs.taskIndex.clear();
      refs.thinkingBuffer = "";
      refs.firstText = true;
      if (refs.thinkingRaf != null) {
        cancelAnimationFrame(refs.thinkingRaf);
        refs.thinkingRaf = null;
      }
      if (refs.agentStateTimer) {
        clearTimeout(refs.agentStateTimer);
        refs.agentStateTimer = null;
      }

      // 乐观更新：先追加用户消息到本地列表（仅当目标会话是当前活跃会话时）
      if (appendUserMessage && activeChatIdRef.current === targetChatId) {
        const tempUserMsg: Message = {
          id: Date.now(),
          chat_id: targetChatId,
          role: "user",
          content,
          attachments: attachments?.map((a) => ({ name: a.name, path: a.path ?? undefined, mime: a.mime, kind: a.kind, size: a.size })),
          created_at: new Date().toISOString(),
        };
        appendMessage(tempUserMsg);
      }

      const finalContent = buildContent ? await buildContent(content) : content;

      // 立即注入"正在思考..."占位符
      store.updateSession(targetChatId, () => ({ reasoningActive: true }));
      refs.firstText = true;
      const indicatorId = `think-indicator-${Date.now()}`;
      store.updateSession(targetChatId, () => ({
        timeline: [{ id: indicatorId, type: "thinking_indicator" as const, content: "" }],
      }));

      // rAF 批处理 — 思考文本增量写入 buffer，由 rAF 统一 flush 到 timeline
      const flushThinkingBuffer = () => {
        refs.thinkingRaf = null;
        const delta = refs.thinkingBuffer;
        if (delta === "") return;
        refs.thinkingBuffer = "";
        store.updateSession(targetChatId, (prev) => {
          const next = prev.timeline.slice();
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i].type === "thinking_indicator") {
              const seg = next[i] as ThinkingIndicatorEvent;
              next[i] = { ...seg, content: seg.content + delta };
              return { timeline: next };
            }
          }
          return { timeline: [...next, { id: `think-${Date.now()}`, type: "thinking_indicator" as const, content: delta }] };
        });
      };

      const scheduleThinkingFlush = () => {
        if (refs.thinkingRaf != null) return;
        refs.thinkingRaf = requestAnimationFrame(flushThinkingBuffer);
      };

      // 流结束：持久化 AI 消息（仅当目标会话是当前活跃会话时追加到本地列表）
      const appendAssistant = (final: string, toolCalls: ToolCall[], finalThinking: string) => {
        // 在清空 timeline 前快照：转换为与后端 Message.timeline 一致的事件格式，
        // 随乐观消息写入，使流结束瞬间即按时序渲染（工具卡片不上浮），refetch 落地后无缝衔接
        const prevTimeline = store.getSession(targetChatId)?.timeline ?? [];
        const timelineEvents = prevTimeline.flatMap((seg) => {
          switch (seg.type) {
            case "thinking":
            case "thinking_indicator":
              return seg.content ? [{ type: "thinking", content: seg.content }] : [];
            case "tool": {
              const tc = seg.toolCall;
              const evts: TimelineEvent[] = [{
                type: "tool_start",
                tool_call_id: tc.tool_call_id,
                tool: tc.tool,
                input: tc.input ?? tc.arguments ?? {},
              }];
              if (tc.status === "success" || tc.status === "failed") {
                evts.push({
                  type: "tool_result",
                  tool_call_id: tc.tool_call_id,
                  tool: tc.tool,
                  success: tc.success,
                  result: tc.result,
                  duration_ms: tc.duration_ms,
                  error: tc.error,
                });
              }
              return evts;
            }
            case "text":
              return [{ type: "text", content: seg.content }];
            default:
              return [];
          }
        });

        store.updateSession(targetChatId, () => ({
          timeline: [],
          streamingError: null,
          reasoningActive: false,
          currentAgentState: null,
          isSending: false,
        }));
        refs.toolIndex.clear();
        refs.taskIndex.clear();
        refs.thinkingBuffer = "";
        if (refs.thinkingRaf != null) {
          cancelAnimationFrame(refs.thinkingRaf);
          refs.thinkingRaf = null;
        }
        refs.firstText = true;
        if (refs.agentStateTimer) {
          clearTimeout(refs.agentStateTimer);
          refs.agentStateTimer = null;
        }
        // 后台完成时侧边栏加载指示器无人清理（页面 effect 仅在当前会话生效）→ 主动清除，
        // 修复“后台任务完成后侧边栏一直转圈，点进去才恢复”
        store.setStream(targetChatId, null);

        // 仅当目标会话是当前活跃会话时追加 AI 消息到本地列表
        if (activeChatIdRef.current === targetChatId) {
          const aiMsg: Message = {
            id: Date.now(),
            chat_id: targetChatId,
            role: "assistant",
            content: final,
            thinking: finalThinking || undefined,
            tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
            timeline: timelineEvents.length > 0 ? timelineEvents : undefined,
            created_at: new Date().toISOString(),
          };
          appendMessage(aiMsg);
          // 后台静默同步真实 ID
          refetch().catch(() => { /* 静默失败 */ });
        }
        // 如果目标会话不是当前活跃会话，AI 消息已由后端持久化，
        // 用户切回该会话时 useMessages 会自动 fetchMessages 获取最新消息

        // 长任务完成通知：用户离开（切会话/离开页面/最小化/切应用）时弹通知，正文附用时
        if (isUserAway()) {
          const preview = final.slice(0, 80) + (final.length > 80 ? "..." : "");
          const elapsed = formatDuration(Date.now() - startedAt);
          showDesktopNotification("任务完成", `${preview || "AI 回复已完成"} · 用时 ${elapsed}`);
        }
      };

      try {
        const controller = new AbortController();
        refs.abortController = controller;
        await sendMessageStream(
          finalContent,
          modelId || FALLBACK_MODEL_ID,
          // onChunk（text）
          (chunk) => {
            if (refs.firstText) {
              refs.firstText = false;
              store.updateSession(targetChatId, () => ({ reasoningActive: false }));
              if (refs.thinkingRaf != null) {
                cancelAnimationFrame(refs.thinkingRaf);
                refs.thinkingRaf = null;
              }
              const remaining = refs.thinkingBuffer;
              refs.thinkingBuffer = "";
              store.updateSession(targetChatId, (prev) => {
                const filtered = prev.timeline.filter((s) => s.type !== "thinking_indicator");
                if (remaining) {
                  return { timeline: [...filtered, { id: `thinking-${Date.now()}`, type: "thinking" as const, content: remaining }] };
                }
                return { timeline: filtered };
              });
            }
            store.updateSession(targetChatId, (prev) => {
              const last = prev.timeline[prev.timeline.length - 1];
              if (last && last.type === "text") {
                const next = prev.timeline.slice();
                next[next.length - 1] = { ...last, content: last.content + chunk };
                return { timeline: next };
              }
              return { timeline: [...prev.timeline, { id: `text-${Date.now()}-${Math.random()}`, type: "text" as const, content: chunk }] };
            });
          },
          // onFinish: 兜底清理。正常流程中 onComplete(appendAssistant) 已先执行完毕，
          // 此处仅做防御性重置：若 isSending 仍为 true，说明 onComplete 未正常执行，走完整清理。
          // 执行顺序契约：sendMessageStream 保证 onComplete → onFinish 顺序调用。
          () => {
            const session = store.getSession(targetChatId);
            if (!session.isSending) return; // onComplete 已清理，跳过
            store.updateSession(targetChatId, () => ({
              timeline: [],
              isSending: false,
              reasoningActive: false,
              currentAgentState: null,
            }));
            refs.toolIndex.clear();
            refs.taskIndex.clear();
            refs.thinkingBuffer = "";
            if (refs.thinkingRaf != null) {
              cancelAnimationFrame(refs.thinkingRaf);
              refs.thinkingRaf = null;
            }
            refs.firstText = true;
            if (refs.agentStateTimer) {
              clearTimeout(refs.agentStateTimer);
              refs.agentStateTimer = null;
            }
            store.setStream(targetChatId, null);
          },
          // onError
          (error) => {
            resetStreaming(targetChatId);
            store.updateSession(targetChatId, () => ({
              isSending: false,
              streamingError: error,
            }));
          },
          personalityLevel,
          reasoningEffort,
          // onThinking
          (thinking) => {
            refs.thinkingBuffer += thinking;
            scheduleThinkingFlush();
          },
          // onToolStart
          (toolStart) => {
            store.updateSession(targetChatId, (prev) => {
              const name = toolStart.tool || "tool";
              const key = toolStart.tool_call_id || `${name}_${prev.timeline.length}`;
              const segment: RuntimeEvent = {
                id: key,
                type: "tool",
                toolCallId: key,
                toolCall: {
                  tool: toolStart.tool,
                  name: toolStart.tool,
                  input: toolStart.input ?? {},
                  arguments: toolStart.input ?? {},
                  status: "running",
                  tool_call_id: toolStart.tool_call_id,
                },
              };
              refs.toolIndex.set(key, prev.timeline.length);
              return { timeline: [...prev.timeline, segment] };
            });
          },
          // onToolApproval
          (approval) => {
            store.updateSession(targetChatId, (prev) => {
              if (prev.timeline.some((s) => s.type === "approval" && s.approval.approval_id === approval.approval_id)) {
                return {};
              }
              return { timeline: [...prev.timeline, { id: `approval-${approval.approval_id}`, type: "approval" as const, approval }] };
            });
            // 审批请求通知（仅新审批时触发，去重逻辑已在上方保证）；
            // 与任务完成通知一致：用户正在查看该会话时界面已有审批卡片，不重复弹系统通知
            if (isUserAway()) {
              showDesktopNotification("需要审批", `工具 ${approval.tool || "未知工具"} 请求执行，请确认`);
            }
          },
          // onUserChoice（ask_user_choice 抉择卡）
          (choice) => {
            store.updateSession(targetChatId, (prev) => {
              if (prev.timeline.some((s) => s.type === "user_choice" && s.choice.choice_id === choice.choice_id)) {
                return {};
              }
              return { timeline: [...prev.timeline, { id: `choice-${choice.choice_id}`, type: "user_choice" as const, choice }] };
            });
            // 抉择请求通知：用户在切窗口/后台时弹系统通知（与审批对齐）
            if (isUserAway()) {
              showDesktopNotification("AI 询问你", choice.question || "AI 提出了一个选择，请查看");
            }
          },
          // onToolOutput
          () => {},
          // onToolResult
          (toolResult) => {
            const id = toolResult.tool_call_id;
            store.updateSession(targetChatId, (prev) => {
              let idx: number | undefined;
              if (id) {
                idx = refs.toolIndex.get(id);
              } else {
                for (let i = prev.timeline.length - 1; i >= 0; i--) {
                  const s = prev.timeline[i];
                  if (s.type === "tool" && (s.toolCall.status === "running" || s.toolCall.status === "pending")) {
                    idx = i;
                    break;
                  }
                }
              }
              if (idx == null || idx >= prev.timeline.length) return {};
              const seg = prev.timeline[idx];
              if (seg.type !== "tool") return {};
              const next = prev.timeline.slice();
              const origId = seg.toolCall.tool_call_id;
              next[idx] = {
                ...seg,
                toolCall: {
                  ...seg.toolCall,
                  tool: toolResult.tool ?? seg.toolCall.tool,
                  name: toolResult.tool ?? seg.toolCall.name,
                  success: toolResult.success,
                  status: toolResult.success ? "success" : "failed",
                  result: toolResult.result,
                  duration_ms: toolResult.duration_ms,
                  error: toolResult.error,
                  tool_call_id: id ?? origId,
                },
              };
              const matchApproval = id ?? origId;
              return {
                timeline: next.filter(
                  (s) =>
                    !(s.type === "approval" && matchApproval && s.approval.tool_call_id === matchApproval) &&
                    !(s.type === "user_choice" && matchApproval && s.choice.tool_call_id === matchApproval)
                ),
              };
            });
          },
          // onToolCallsBatch
          (batch) => {
            store.updateSession(targetChatId, (prev) => {
              let next = prev.timeline;
              for (const c of batch) {
                if (!c.tool_call_id) continue;
                const idx = refs.toolIndex.get(c.tool_call_id);
                if (idx == null || idx >= next.length) continue;
                const seg = next[idx];
                if (seg.type !== "tool") continue;
                if (next === prev.timeline) next = prev.timeline.slice();
                next[idx] = { ...seg, toolCall: { ...seg.toolCall, ...c } };
              }
              const resolvedIds = new Set(batch.filter((c) => c.tool_call_id).map((c) => c.tool_call_id));
              if (resolvedIds.size > 0) {
                next = next.filter(
                  (s) =>
                    !(s.type === "approval" && resolvedIds.has(s.approval.tool_call_id)) &&
                    !(s.type === "user_choice" && resolvedIds.has(s.choice.tool_call_id))
                );
              }
              return { timeline: next };
            });
          },
          // onTaskEvent
          (evt: TaskEvent) => {
            const node = evt.task;
            if (evt.type === "task_started" || evt.type === "task_skipped") {
              const status = evt.type === "task_started" ? "running" : "skipped";
              store.updateSession(targetChatId, (prev) => {
                const existingIdx = refs.taskIndex.get(node.task_id);
                if (existingIdx != null && existingIdx < prev.tasks.length && prev.tasks[existingIdx].task_id === node.task_id) {
                  const next = prev.tasks.slice();
                  next[existingIdx] = { ...prev.tasks[existingIdx], ...node, status };
                  return { tasks: next };
                }
                refs.taskIndex.set(node.task_id, prev.tasks.length);
                return { tasks: [...prev.tasks, { ...node, status }] };
              });
            } else {
              store.updateSession(targetChatId, (prev) => {
                const idx = refs.taskIndex.get(node.task_id);
                if (idx == null || idx >= prev.tasks.length || prev.tasks[idx].task_id !== node.task_id) {
                  const fallback = prev.tasks.findIndex((t) => t.task_id === node.task_id);
                  if (fallback < 0) return {};
                  const next = prev.tasks.slice();
                  next[fallback] = {
                    ...prev.tasks[fallback],
                    ...node,
                    status: evt.type === "task_completed" ? "completed" : "failed",
                    error: evt.type === "task_failed" ? node.error : undefined,
                  };
                  return { tasks: next };
                }
                const next = prev.tasks.slice();
                next[idx] = {
                  ...prev.tasks[idx],
                  ...node,
                  status: evt.type === "task_completed" ? "completed" : "failed",
                  error: evt.type === "task_failed" ? node.error : undefined,
                };
                return { tasks: next };
              });
              // Phase 3 T3/T8: 任务完成/失败通知（仅用户离开时触发）
              if (isUserAway()) {
                if (evt.type === "task_completed") {
                  showDesktopNotification("任务完成", node.action || "子任务已完成");
                } else if (evt.type === "task_failed") {
                  showDesktopNotification("任务失败", node.error || node.action || "子任务执行失败");
                }
              }
            }
          },
          // onTokenUsage
          (usage: TokenUsageEvent) => {
            store.updateSession(targetChatId, () => ({ tokenUsage: usage }));
          },
          // onAgentStateUpdate
          (evt: AgentStateUpdateEvent) => {
            if (refs.agentStateTimer) {
              clearTimeout(refs.agentStateTimer);
              refs.agentStateTimer = null;
            }
            store.updateSession(targetChatId, () => ({ currentAgentState: evt }));
            if (evt.status === "completed" || evt.status === "error") {
              refs.agentStateTimer = setTimeout(() => {
                refs.agentStateTimer = null;
                store.updateSession(targetChatId, () => ({ currentAgentState: null }));
              }, 1500);
            }
          },
          // onComplete
          appendAssistant,
          // 附件
          attachments,
          // 权限模式
          permissionMode,
          // 中断信号
          controller.signal
        );
      } catch (err) {
        // 主动中断（用户点击停止）不算错误：静默清理
        if (refs.abortController && err instanceof DOMException && err.name === "AbortError") {
          refs.abortController = null;
          resetStreaming(targetChatId);
          store.updateSession(targetChatId, () => ({ isSending: false }));
          return;
        }
        const msg = err instanceof Error ? err.message : String(err);
        resetStreaming(targetChatId);
        store.updateSession(targetChatId, () => ({
          isSending: false,
          streamingError: msg,
        }));
        // 流式错误通知：与任务完成通知一致，仅用户离开时弹（在场时界面已有错误卡片）
        if (isUserAway()) {
          showDesktopNotification("任务出错", msg.slice(0, 100));
        }
      }
    },
    [chatId, sendMessageStream, appendMessage, refetch, resetStreaming, store]
  );

  return {
    isSending,
    timeline,
    tasks,
    tokenUsage,
    setTokenUsage: (usage: TokenUsageEvent | null) => {
      if (chatId != null) store.updateSession(chatId, () => ({ tokenUsage: usage }));
    },
    currentAgentState,
    reasoningActive,
    orbStage,
    streamingError,
    sendStream,
    resolveApproval,
    resolveChoice,
    stop,
  };
}
