/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { API_BASE, apiGet, apiPost, apiDelete } from "@/lib/api";
import type { ToolCall } from "@/components/ToolCallCard";

export interface Message {
  id: number;
  chat_id: number;
  role: "user" | "assistant" | "system";
  content: string;
  tool_calls?: ToolCall[];
  created_at: string;
}

export function useMessages(chatId: number | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMessages = useCallback(async () => {
    if (!chatId) return;
    try {
      setLoading(true);
      const data = await apiGet<Message[]>(`/api/chat/${chatId}/messages`);
      setMessages(data);
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

  async function sendMessage(content: string, model: string = "mimo-v2.5-pro", personalityLevel?: number, reasoningEffort?: "none" | "low" | "high") {
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
    reasoningEffort?: "none" | "low" | "high",
    onToolCall?: (toolCall: ToolCall) => void,
    onToolCallsBatch?: (toolCalls: ToolCall[]) => void
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
              onFinish();
              await fetchMessages();
              return;
            }
            try {
              const parsed = JSON.parse(data);
              if (parsed.error) {
                flushNowAndClear();
                onError(parsed.error);
                return;
              }
              if (parsed.tool_call) {
                // 实时工具执行事件：name 非空即渲染（path 可能为空，如 search_files/run_command/git 工具）
                if (onToolCall && parsed.tool_call.name) {
                  onToolCall({
                    name: parsed.tool_call.name,
                    path: parsed.tool_call.path,
                    success: parsed.tool_call.success,
                    arguments: parsed.tool_call.arguments,
                  });
                }
                continue;
              }
              if (parsed.tool_calls && Array.isArray(parsed.tool_calls)) {
                // 本轮工具调用汇总事件（含完整 result）：一次交给前端补齐卡片结果
                onToolCallsBatch?.(parsed.tool_calls as ToolCall[]);
                continue;
              }
              if (parsed.content) {
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
      onFinish();
      await fetchMessages();
    } finally {
      flushNowAndClear();
    }
  }

  return { messages, loading, error, sendMessage, sendMessageStream, deleteMessagesFrom, refetch: fetchMessages };
}
