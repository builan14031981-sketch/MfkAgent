/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";

export interface Message {
  id: number;
  chat_id: number;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
}

const API_BASE = "http://127.0.0.1:8001";

export function useMessages(chatId: number | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMessages = useCallback(async () => {
    if (!chatId) return;
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/chat/${chatId}/messages`);
      if (!res.ok) throw new Error("Failed to fetch messages");
      const data = await res.json();
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

  async function sendMessage(content: string, model: string = "mimo-v2.5-pro") {
    if (!chatId) throw new Error("No chat selected");
    const res = await fetch(`${API_BASE}/api/chat/${chatId}/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, model }),
    });
    if (!res.ok) throw new Error("Failed to send message");
    const data = await res.json();
    await fetchMessages();
    return data;
  }

  async function sendMessageStream(
    content: string,
    model: string = "mimo-v2.5-pro",
    onChunk: (chunk: string) => void,
    onFinish: () => void,
    onError: (error: string) => void
  ) {
    if (!chatId) throw new Error("No chat selected");

    const response = await fetch(`${API_BASE}/api/chat/${chatId}/send/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, model }),
    });

    if (!response.ok) throw new Error("Failed to send message");

    const reader = response.body?.getReader();
    if (!reader) throw new Error("No reader available");

    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value);
      const lines = text.split("\n");

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6).trim();
          if (data === "[DONE]") {
            onFinish();
            await fetchMessages();
            return;
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.error) {
              onError(parsed.error);
              return;
            }
            if (parsed.content) {
              onChunk(parsed.content);
            }
          } catch {
            // Skip invalid JSON
          }
        }
      }
    }

    onFinish();
    await fetchMessages();
  }

  return { messages, loading, error, sendMessage, sendMessageStream, refetch: fetchMessages };
}
