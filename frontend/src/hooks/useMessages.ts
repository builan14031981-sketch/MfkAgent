/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { API_BASE, apiGet, apiPost, apiDelete } from "@/lib/api";
import type { ToolCall } from "@/components/ToolCallCard";
import type { Attachment, AttachmentKind } from "@/components/FileDropZone";
import { getFileExt } from "@/components/FileDropZone";
import { FALLBACK_MODEL_ID } from "@/lib/modelDefaults";
import type { PermissionMode } from "@/components/chat-input/PermissionSelector";
import type { AgentStateUpdateEvent, TaskEvent, TaskNode, TokenUsageEvent } from "@/types/runtime";

/**
 * 后端 Message.timeline 持久化的时序事件（GET /messages 随消息下发）。
 * 由后端 SSE 录制：thinking/tool_start/tool_result 按真实到达顺序记录，
 * text 目前由后端合并为单个事件追加在末尾（见 backend/app/api/chat.py）。
 */
export interface TimelineEvent {
  type: "thinking" | "text" | "tool_start" | "tool_result" | "tool_approval" | string;
  content?: string;
  tool_call_id?: string;
  tool?: string;
  input?: Record<string, unknown>;
  success?: boolean;
  result?: string;
  duration_ms?: number;
  error?: string;
  file_path?: string;
}

export interface Message {
  id: number;
  chat_id: number;
  role: "user" | "assistant" | "system";
  content: string;
  thinking?: string;
  tool_calls?: ToolCall[];
  /** 时序事件列表：存在时按真实顺序渲染（thinking/tool/text 交错），否则回退三字段固定顺序 */
  timeline?: TimelineEvent[];
  attachments?: Array<{ name: string; path?: string; mime?: string; kind?: string; size?: number }>;
  created_at: string;
}

export function useMessages(chatId: number | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** 乐观临时消息 id 阈值：page 用 Date.now() 生成临时 id（约 1.7e12），DB 自增 id 远小于此 */
  const TEMP_ID_THRESHOLD = 1_000_000_000_000;

  const fetchMessages = useCallback(async () => {
    if (!chatId) return;
    try {
      setLoading(true);
      const data = await apiGet<Message[]>(`/api/chat/${chatId}/messages`);
      // 合并语义：服务端返回非空 → 整体覆盖（加载历史 / 流结束 refetch 均如此）。
      // 服务端返回空但本地存在"乐观临时消息"（如首页新建会话时 autoSend 先乐观追加、
      // 而 GET /messages 先于 POST /send/stream 的 db.commit 完成，读到空表）→ 保留本地
      // 乐观消息，避免覆盖导致新建会话首屏一片空白（连用户消息都不显示）。
      setMessages((prev) => {
        if (data.length > 0) return data;
        const optimistic = prev.filter((m) => m.id >= TEMP_ID_THRESHOLD);
        return optimistic.length > 0 ? optimistic : data;
      });
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [chatId]);

  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  async function sendMessage(content: string, model: string = FALLBACK_MODEL_ID, personalityLevel?: number, reasoningEffort?: "none" | "high" | "max") {
    if (!chatId) throw new Error("No chat selected");
    const data = await apiPost(`/api/chat/${chatId}/send`, { content, model, personality_level: personalityLevel, reasoning_effort: reasoningEffort });
    await fetchMessages();
    return data;
  }

  /** 删除该消息及其之后的所有历史（重生成 / 编辑） */
  async function deleteMessagesFrom(messageId: number) {
    if (!chatId) throw new Error("No chat selected");
    await apiDelete(`/api/chat/${chatId}/messages/${messageId}`);
    await fetchMessages();
  }

  async function sendMessageStream(
    content: string,
    model: string = FALLBACK_MODEL_ID,
    onChunk: (chunk: string) => void,
    onFinish: () => void,
    onError: (error: string) => void,
    personalityLevel?: number,
    reasoningEffort?: "none" | "high" | "max",
    onThinking?: (thinking: string) => void,
    onToolStart?: (evt: { tool_call_id: string; tool: string; input: Record<string, unknown> }) => void,
    onToolApproval?: (evt: { approval_id: string; tool_call_id: string; tool: string; command: string; risk_level: string; risk_reason: string; chat_id?: number }) => void,
    onToolOutput?: (evt: { tool_call_id: string; delta: string }) => void,
    onToolResult?: (evt: { tool_call_id?: string; tool?: string; success?: boolean; result?: string; duration_ms?: number; error?: string; file_path?: string }) => void,
    onToolCallsBatch?: (toolCalls: ToolCall[]) => void,
    onTaskEvent?: (evt: TaskEvent) => void,
    onTokenUsage?: (evt: TokenUsageEvent) => void,
    onAgentStateUpdate?: (evt: AgentStateUpdateEvent) => void,
    onComplete?: (finalContent: string, toolCalls: ToolCall[], finalThinking: string) => void,
    attachments?: Attachment[],
    permissionMode?: PermissionMode,
    signal?: AbortSignal
  ) {
    if (!chatId) throw new Error("No chat selected");

    const body = {
      content,
      model,
      personality_level: personalityLevel,
      reasoning_effort: reasoningEffort,
      permission_mode: permissionMode,
      attachments: attachments?.map((a) => ({ name: a.name, path: a.path, mime: a.mime, kind: a.kind, size: a.size })) ?? [],
    };
    console.log("[sendMessageStream] 请求体 attachments:", JSON.stringify(body.attachments));
    console.log("[sendMessageStream] 请求体 content 前200字符:", body.content.substring(0, 200));

    const response = await fetch(`${API_BASE}/api/chat/${chatId}/send/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });

    if (!response.ok) {
      let detail = `Failed to send message (HTTP ${response.status})`;
      try {
        const body = await response.text();
        if (body) {
          const parsed = JSON.parse(body);
          if (parsed && typeof parsed.error === "string") detail = parsed.error;
          else if (parsed && typeof parsed.detail === "string") detail = parsed.detail;
        }
      } catch {
        /* 读 body 失败则保留默认信息 */
      }
      throw new Error(detail);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error("No reader available");

    const decoder = new TextDecoder();

    // ---- SSE 平滑缓冲：累积增量文本，以 30ms 节流批量交付给 React，消除打字卡顿 ----
    const THROTTLE_MS = 30;
    let buffer = "";
    let timer: ReturnType<typeof setTimeout> | null = null;

    // 流式过程中累积完整内容 + tool_calls（用于 onComplete 一次性交付）
    let fullContent = "";
    let fullThinking = "";
    const toolCallMap = new Map<string, ToolCall>();

    const flush = () => {
      // Phase 1.5：信号已中断（会话切换/卸载）→ 丢弃残余 buffer，不再投递
      if (signal?.aborted) {
        buffer = "";
        return;
      }
      if (buffer === "") return;
      const chunk = buffer;
      buffer = "";
      onChunk(chunk);
    };

    const scheduleFlush = () => {
      if (timer) return;
      timer = setTimeout(() => {
        timer = null;
        flush();
      }, THROTTLE_MS);
    };

    const flushNowAndClear = () => {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      flush();
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Phase 1.5：外部信号中断（会话切换/卸载）→ 立即静默退出，不再投递残余 chunk
        if (signal?.aborted) {
          buffer = "";
          if (timer) {
            clearTimeout(timer);
            timer = null;
          }
          return;
        }

        const text = decoder.decode(value);
        const lines = text.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6).trim();
            if (data === "[DONE]") {
              flushNowAndClear();
              onComplete?.(fullContent, Array.from(toolCallMap.values()), fullThinking);
              onFinish();
              return;
            }
            try {
              const parsed = JSON.parse(data);

              if (parsed && typeof parsed === "object" && parsed.type) {
                // ---- v2 统一信封：按 type 分发 ----
                switch (parsed.type) {
                  case "text": {
                    fullContent += parsed.content ?? "";
                    buffer += parsed.content ?? "";
                    scheduleFlush();
                    break;
                  }
                  case "thinking": {
                    const th = parsed.content ?? "";
                    fullThinking += th;
                    onThinking?.(th);
                    break;
                  }
                  case "tool_start": {
                    onToolStart?.(parsed);
                    toolCallMap.set(parsed.tool_call_id, {
                      tool: parsed.tool,
                      name: parsed.tool,
                      input: parsed.input ?? {},
                      arguments: parsed.input ?? {},
                      status: "running",
                      tool_call_id: parsed.tool_call_id,
                    });
                    break;
                  }
                  case "tool_approval": {
                    onToolApproval?.(parsed);
                    break;
                  }
                  case "tool_output": {
                    onToolOutput?.(parsed);
                    break;
                  }
                  case "tool_result": {
                    onToolResult?.(parsed);
                    const prev = toolCallMap.get(parsed.tool_call_id) ?? {};
                    toolCallMap.set(parsed.tool_call_id, {
                      ...prev,
                      tool: parsed.tool ?? prev.tool,
                      name: parsed.tool ?? prev.tool,
                      success: parsed.success,
                      status: parsed.success ? "success" : "failed",
                      result: parsed.result,
                      duration_ms: parsed.duration_ms,
                      error: parsed.error,
                      tool_call_id: parsed.tool_call_id,
                      file_path: parsed.file_path,
                    });
                    break;
                  }
                  case "tool_calls": {
                    // 本轮工具调用汇总（含完整 result）：一次补齐，供 onComplete 持久化
                    const calls: ToolCall[] = Array.isArray(parsed.calls) ? parsed.calls : [];
                    onToolCallsBatch?.(calls);
                    for (const c of calls) {
                      if (c.tool_call_id) toolCallMap.set(c.tool_call_id, c);
                    }
                    break;
                  }
                  case "task_started":
                  case "task_completed":
                  case "task_failed":
                  case "task_skipped": {
                    // 多 Agent 任务协同事件：解析 payload 并组装 TaskNode 后分发
                    const task: TaskNode = {
                      task_id: parsed.task_id,
                      action: parsed.action ?? "",
                      status: parsed.status ?? (parsed.type === "task_started" ? "running" : parsed.type === "task_completed" ? "completed" : "failed"),
                      assigned_agent: parsed.assigned_agent ?? "unknown",
                      error: parsed.error,
                      started_at: parsed.started_at,
                      ended_at: parsed.ended_at,
                    };
                    onTaskEvent?.({
                      id: task.task_id,
                      type: parsed.type,
                      task,
                    });
                    break;
                  }
                  case "token_usage": {
                    // G6-A：每轮 LLM 思考结束后的精确 Token 消耗与上下文水位
                    onTokenUsage?.({
                      id: parsed.id ?? `token-usage-${Date.now()}`,
                      type: "token_usage",
                      prompt_tokens: parsed.prompt_tokens ?? 0,
                      completion_tokens: parsed.completion_tokens ?? 0,
                      total_tokens: parsed.total_tokens ?? 0,
                      model_max_tokens: parsed.model_max_tokens ?? 0,
                      watermark_percentage: parsed.watermark_percentage ?? 0,
                    });
                    break;
                  }
                  case "agent_state_update": {
                    // Agent 状态流转事件：驱动动态状态名片（AgentStatusCard）
                    onAgentStateUpdate?.({
                      id: parsed.id ?? `agent-state-${Date.now()}`,
                      type: "agent_state_update",
                      agent_role: parsed.agent_role ?? "",
                      status: parsed.status ?? "working",
                      action_detail: parsed.action_detail ?? "",
                      task_progress: parsed.task_progress ?? "",
                    });
                    break;
                  }
                  case "error": {
                    flushNowAndClear();
                    onError(parsed.message ?? "Unknown error");
                    return;
                  }
                  case "finish":
                  default:
                    break;
                }
                continue;
              }

              // ---- legacy 兜底（旧后端协议）----
              if (parsed.error) {
                flushNowAndClear();
                onError(parsed.error);
                return;
              }
              if (parsed.thinking) {
                fullThinking += parsed.thinking;
                onThinking?.(parsed.thinking);
                continue;
              }
              if (parsed.tool_call) {
                // 旧单事件终态：兼容映射为 tool_result
                const tc: ToolCall = {
                  ...parsed.tool_call,
                  status: parsed.tool_call.success ? "success" : "failed",
                };
                const id = tc.tool_call_id;
                if (id) toolCallMap.set(id, tc);
                onToolResult?.(tc);
                continue;
              }
              if (parsed.tool_calls && Array.isArray(parsed.tool_calls)) {
                const batch = parsed.tool_calls as ToolCall[];
                onToolCallsBatch?.(batch);
                for (const c of batch) {
                  if (c.tool_call_id) toolCallMap.set(c.tool_call_id, c);
                }
                continue;
              }
              if (parsed.content) {
                fullContent += parsed.content;
                buffer += parsed.content;
                scheduleFlush();
              }
            } catch {
              // Skip invalid JSON
            }
          }
        }
      }

      flushNowAndClear();
      if (signal?.aborted) return;
      onComplete?.(fullContent, Array.from(toolCallMap.values()), fullThinking);
      onFinish();
    } finally {
      flushNowAndClear();
    }
  }

  /** 乐观追加消息到本地列表（不触发服务端请求） */
  const appendMessage = useCallback((message: Message) => {
    setMessages((prev) => [...prev, message]);
  }, []);

  return { messages, setMessages, loading, error, sendMessage, sendMessageStream, deleteMessagesFrom, refetch: fetchMessages, appendMessage };
}

/**
 * 上传项目外文件到 Chat 绑定项目的 .mfkagent/uploads/ 目录。
 * 后端返回相对 project_path 的路径，供 context_builder 安全读取。
 * 要求 Chat 已绑定项目（否则后端返回 400）。
 */
export async function uploadAttachment(chatId: number, file: File): Promise<Attachment | null> {
  const formData = new FormData();
  formData.append("file", file);
  try {
    const response = await fetch(`${API_BASE}/api/chat/${chatId}/upload`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) return null;
    const data = await response.json();
    return {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
      name: data.name,
      path: data.path,
      mime: data.mime || "application/octet-stream",
      size: data.size || 0,
      kind: (data.kind as AttachmentKind) || "text",
      ext: getFileExt(data.name || "unknown"),
    };
  } catch (err) {
    console.error("uploadAttachment failed:", err);
    return null;
  }
}
