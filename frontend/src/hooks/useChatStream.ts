import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import type { Message, useMessages } from "@/hooks/useMessages";
import type { ToolCall } from "@/components/ToolCallCard";
import type { ReasoningEffort } from "@/components/ChatInput";
import { apiPost } from "@/lib/api";
import { useStreamStore, OrbStage } from "@/lib/streamStore";
import type { RuntimeEvent, ApprovalRequest, TaskNode, TaskEvent, TokenUsageEvent } from "@/types/runtime";

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
  /** 是否乐观追加用户消息到本地列表（重试/重新生成时已有消息，置 false） */
  appendUserMessage?: boolean;
  /** 发送前对消息做变换（如拼接项目文件上下文）；返回原始值则不拼 */
  buildContent?: (content: string) => Promise<string> | string;
}

/**
 * 聊天流式发送统一管线：
 * 收敛 chat 页 handleSend / autoSend / runSendForUser 三份重复的
 * isSending + streaming 状态机 + 乐观消息 + 错误/完成处理的逻辑。
 *
 * Runtime Event 模型：以单一 RuntimeEvent[] 替代原来的四个独立状态桶
 * （streamingContent / streamingThinking / toolCallsMap / pendingApprovals），
 * 使 SSE 到达顺序在写入时即保留，渲染时按真实顺序展示。
 */
export function useChatStream({
  chatId,
  sendMessageStream,
  appendMessage,
  refetch,
}: UseChatStreamParams) {
  const [isSending, setIsSending] = useState(false);
  const [timeline, setTimeline] = useState<RuntimeEvent[]>([]);
  const [streamingError, setStreamingError] = useState<string | null>(null);
  // 多 Agent 任务协同状态：按 task_started 到达顺序累积，completed/failed 原地更新
  const [tasks, setTasks] = useState<TaskNode[]>([]);
  // G6-A：最新 token_usage 事件（上下文仪表盘数据源）；null 表示暂无数据
  const [tokenUsage, setTokenUsage] = useState<TokenUsageEvent | null>(null);

  // 辅助索引：tool_call_id → timeline 数组下标，用于 tool_result 原地更新
  const toolIndexRef = useRef<Map<string, number>>(new Map());
  // 辅助索引：task_id → tasks 数组下标，用于 task_completed/failed 原地更新
  const taskIndexRef = useRef<Map<string, number>>(new Map());

  /** 从 timeline 末位事件派生 Orb 阶段：thinking→solving、tool→searching、approval→listening、text→composing */
  const orbStage = useMemo<OrbStage | null>(() => {
    if (!isSending) return null;
    if (timeline.length === 0) return "working";
    const last = timeline[timeline.length - 1];
    switch (last.type) {
      case "thinking":
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
      useStreamStore.getState().setStream(chatId, null);
    };
  }, [chatId, orbStage]);

  const resetStreaming = useCallback(() => {
    setTimeline([]);
    setStreamingError(null);
    setTasks([]);
    setTokenUsage(null);
    toolIndexRef.current.clear();
    taskIndexRef.current.clear();
  }, []);

  /** 用户批准/拒绝待审批命令；成功即本地移除卡片（后端随后发射 tool_result 更新工具卡） */
  const resolveApproval = useCallback(
    async (approvalId: string, action: "approve" | "deny") => {
      if (!chatId) return;
      try {
        await apiPost(`/api/chat/${chatId}/tool-approval`, { approval_id: approvalId, action });
      } catch (err) {
        console.error("Failed to resolve approval:", err);
        return;
      }
      setTimeline((prev) => prev.filter((s) => !(s.type === "approval" && s.approval.approval_id === approvalId)));
    },
    [chatId]
  );

  const sendStream = useCallback(
    async (content: string, options: SendStreamOptions = {}) => {
      if (!chatId) throw new Error("No chat selected");
      const { modelId, personalityLevel, reasoningEffort, appendUserMessage = true, buildContent } = options;

      setIsSending(true);
      resetStreaming();

      // 乐观更新：先追加用户消息到本地列表（无需等待服务端）
      if (appendUserMessage) {
        const tempUserMsg: Message = {
          id: Date.now(),
          chat_id: chatId,
          role: "user",
          content,
          created_at: new Date().toISOString(),
        };
        appendMessage(tempUserMsg);
      }

      const finalContent = buildContent ? await buildContent(content) : content;

      // 流结束：onComplete 回调已提供累积的 final/toolCalls/finalThinking，直接持久化
      const appendAssistant = (final: string, toolCalls: ToolCall[], finalThinking: string) => {
        setTimeline([]);
        setTasks([]);
        toolIndexRef.current.clear();
        taskIndexRef.current.clear();
        setStreamingError(null);
        const aiMsg: Message = {
          id: Date.now(),
          chat_id: chatId,
          role: "assistant",
          content: final,
          thinking: finalThinking || undefined,
          tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
          created_at: new Date().toISOString(),
        };
        appendMessage(aiMsg);
        // 后台静默同步真实 ID（不触发 loading，不驱动滚动）
        refetch().catch(() => { /* 静默失败 */ });
      };

      try {
        await sendMessageStream(
          finalContent,
          modelId || "qwen-flash",
          // onChunk（text）：追加到最后一个 text segment，否则新建
          (chunk) => {
            setTimeline((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.type === "text") {
                const next = prev.slice();
                next[next.length - 1] = { ...last, content: last.content + chunk };
                return next;
              }
              return [...prev, { id: `text-${Date.now()}-${Math.random()}`, type: "text" as const, content: chunk }];
            });
          },
          // onFinish
          () => {
            setTimeline([]);
            setTasks([]);
            toolIndexRef.current.clear();
            taskIndexRef.current.clear();
            setIsSending(false);
          },
          // onError
          (error) => {
            resetStreaming();
            setIsSending(false);
            setStreamingError(error);
          },
          personalityLevel,
          reasoningEffort,
          // onThinking：追加到最后一个 thinking segment，否则新建
          (thinking) => {
            setTimeline((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.type === "thinking") {
                const next = prev.slice();
                next[next.length - 1] = { ...last, content: last.content + thinking };
                return next;
              }
              return [...prev, { id: `thinking-${Date.now()}-${Math.random()}`, type: "thinking" as const, content: thinking }];
            });
          },
          // onToolStart：新建 tool segment（running），记录索引
          (toolStart) => {
            setTimeline((prev) => {
              const segment: RuntimeEvent = {
                id: toolStart.tool_call_id,
                type: "tool",
                toolCallId: toolStart.tool_call_id,
                toolCall: {
                  tool: toolStart.tool,
                  name: toolStart.tool,
                  input: toolStart.input ?? {},
                  arguments: toolStart.input ?? {},
                  status: "running",
                  tool_call_id: toolStart.tool_call_id,
                },
              };
              toolIndexRef.current.set(toolStart.tool_call_id, prev.length);
              return [...prev, segment];
            });
          },
          // onToolApproval：新建 approval segment
          (approval) => {
            setTimeline((prev) => {
              if (prev.some((s) => s.type === "approval" && s.approval.approval_id === approval.approval_id)) {
                return prev;
              }
              return [...prev, { id: `approval-${approval.approval_id}`, type: "approval" as const, approval }];
            });
          },
          // onToolOutput：Phase A 后端不发射，占位（长命令流式输出时启用）
          () => {},
          // onToolResult：按 tool_call_id 原地更新 tool segment 终态，移除对应 approval
          (toolResult) => {
            const id = toolResult.tool_call_id;
            if (!id) return;
            setTimeline((prev) => {
              const idx = toolIndexRef.current.get(id);
              if (idx == null || idx >= prev.length) return prev;
              const seg = prev[idx];
              if (seg.type !== "tool") return prev;
              const next = prev.slice();
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
                  tool_call_id: id,
                },
              };
              // 移除该 tool 对应的 approval segment
              return next.filter((s) => !(s.type === "approval" && s.approval.tool_call_id === id));
            });
          },
          // onToolCallsBatch：汇总数据合并补齐（含 result），原地更新对应 tool segment
          (batch) => {
            setTimeline((prev) => {
              let next = prev;
              for (const c of batch) {
                if (!c.tool_call_id) continue;
                const idx = toolIndexRef.current.get(c.tool_call_id);
                if (idx == null || idx >= next.length) continue;
                const seg = next[idx];
                if (seg.type !== "tool") continue;
                if (next === prev) next = prev.slice();
                next[idx] = { ...seg, toolCall: { ...seg.toolCall, ...c } };
              }
              // 移除已完成的 approval
              const resolvedIds = new Set(batch.filter((c) => c.tool_call_id).map((c) => c.tool_call_id));
              if (resolvedIds.size > 0) {
                next = next.filter((s) => !(s.type === "approval" && resolvedIds.has(s.approval.tool_call_id)));
              }
              return next;
            });
          },
          // onTaskEvent：多 Agent 任务协同事件
          // - task_started：新增 running 任务，记录索引
          // - task_skipped：新增/原地更新为 skipped（任务未执行，可能无前置 started）
          // - task_completed/failed：按 task_id 原地更新状态（不移动位置）
          (evt: TaskEvent) => {
            const node = evt.task;
            if (evt.type === "task_started" || evt.type === "task_skipped") {
              const status = evt.type === "task_started" ? "running" : "skipped";
              setTasks((prev) => {
                // 防重：已存在同 task_id 则更新（后端可能重发 / skipped 无前置 started）
                const existingIdx = taskIndexRef.current.get(node.task_id);
                if (existingIdx != null && existingIdx < prev.length && prev[existingIdx].task_id === node.task_id) {
                  const next = prev.slice();
                  next[existingIdx] = { ...prev[existingIdx], ...node, status };
                  return next;
                }
                taskIndexRef.current.set(node.task_id, prev.length);
                return [...prev, { ...node, status }];
              });
            } else {
              // task_completed / task_failed
              setTasks((prev) => {
                const idx = taskIndexRef.current.get(node.task_id);
                if (idx == null || idx >= prev.length || prev[idx].task_id !== node.task_id) {
                  // 索引丢失（如流恢复后）：兜底查找
                  const fallback = prev.findIndex((t) => t.task_id === node.task_id);
                  if (fallback < 0) return prev;
                  const next = prev.slice();
                  next[fallback] = {
                    ...prev[fallback],
                    ...node,
                    status: evt.type === "task_completed" ? "completed" : "failed",
                    error: evt.type === "task_failed" ? node.error : undefined,
                  };
                  return next;
                }
                const next = prev.slice();
                next[idx] = {
                  ...prev[idx],
                  ...node,
                  status: evt.type === "task_completed" ? "completed" : "failed",
                  error: evt.type === "task_failed" ? node.error : undefined,
                };
                return next;
              });
            }
          },
          // onTokenUsage：G6-A 精确 Token 消耗事件，直接覆盖最新水位（仪表盘读数）
          (usage: TokenUsageEvent) => {
            setTokenUsage(usage);
          },
          // onComplete：流结束，降级持久化
          appendAssistant
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        resetStreaming();
        setIsSending(false);
        setStreamingError(msg);
      }
    },
    [chatId, sendMessageStream, appendMessage, refetch, resetStreaming]
  );

  return {
    isSending,
    timeline,
    tasks,
    tokenUsage,
    orbStage,
    streamingError,
    sendStream,
    resolveApproval,
  };
}
