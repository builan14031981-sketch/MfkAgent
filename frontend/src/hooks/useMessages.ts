/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { API_BASE, apiGet, apiPost, apiDelete } from "@/lib/api";
import type { ToolCall } from "@/components/ToolCallCard";

export interface Message {
  id: number;
  chat_id: number;
  role: "user" | "assistant" | "system";
  content: string;
  thinking?: string;
  tool_calls?: ToolCall[];
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

  async function sendMessage(content: string, model: string = "mimo-v2.5-pro", personalityLevel?: number, reasoningEffort?: "none" | "high" | "max") {
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
    model: string = "mimo-v2.5-pro",
    onChunk: (chunk: string) => void,
    onFinish: () => void,
    onError: (error: string) => void,
    personalityLevel?: number,
    reasoningEffort?: "none" | "high" | "max",
    onThinking?: (thinking: string) => void,
    onToolCall?: (toolCall: ToolCall) => void,
    onToolCallsBatch?: (toolCalls: ToolCall[]) => void,
    onComplete?: (finalContent: string, toolCalls: ToolCall[], finalThinking: string) => void
  ) {
    if (!chatId) throw new Error("No chat selected");

    const response = await fetch(`${API_BASE}/api/chat/${chatId}/send/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, model, personality_level: personalityLevel, reasoning_effort: reasoningEffort }),
    });

    if (!response.ok) throw new Error("Failed to send message");

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
    const accumulatedToolCalls: ToolCall[] = [];

    const flush = () => {
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

        const text = decoder.decode(value);
        const lines = text.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6).trim();
            if (data === "[DONE]") {
              flushNowAndClear();
              onComplete?.(fullContent, accumulatedToolCalls, fullThinking);
              onFinish();
              return;
            }
            try {
              const parsed = JSON.parse(data);
              if (parsed.error) {
                flushNowAndClear();
                onError(parsed.error);
                return;
              }
              if (parsed.thinking) {
                // 思考段增量：立即透传，前端实时渲染"思考中/灰色思考块"
                fullThinking += parsed.thinking;
                onThinking?.(parsed.thinking);
                continue;
              }
              if (parsed.tool_call) {
                // 实时工具执行事件：name 非空即渲染（path 可能为空，如 search_files/run_command/git 工具）
                if (onToolCall && parsed.tool_call.name) {
                  const tc: ToolCall = {
                    name: parsed.tool_call.name,
                    path: parsed.tool_call.path,
                    success: parsed.tool_call.success,
                    arguments: parsed.tool_call.arguments,
                  };
                  onToolCall(tc);
                  accumulatedToolCalls.push(tc);
                }
                continue;
              }
              if (parsed.tool_calls && Array.isArray(parsed.tool_calls)) {
                // 本轮工具调用汇总事件（含完整 result）：一次交给前端补齐卡片结果
                const batch = parsed.tool_calls as ToolCall[];
                onToolCallsBatch?.(batch);
                // 替换为完整汇总数据（含 result）
                accumulatedToolCalls.length = 0;
                accumulatedToolCalls.push(...batch);
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
      onComplete?.(fullContent, accumulatedToolCalls, fullThinking);
      onFinish();
    } finally {
      flushNowAndClear();
    }
  }

  /** 乐观追加消息到本地列表（不触发服务端请求） */
  const appendMessage = useCallback((message: Message) => {
    setMessages((prev) => [...prev, message]);
  }, []);

  return { messages, loading, error, sendMessage, sendMessageStream, deleteMessagesFrom, refetch: fetchMessages, appendMessage };
}
