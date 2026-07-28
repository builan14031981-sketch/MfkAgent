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

  async function sendMessage(content: string) {
    if (!chatId) throw new Error("No chat selected");
    const res = await fetch(`${API_BASE}/api/chat/${chatId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: "user", content }),
    });
    if (!res.ok) throw new Error("Failed to send message");
    const data = await res.json();
    await fetchMessages();
    return data;
  }

  async function getAIReply(model: string = "mimo-v2.5-pro") {
    if (!chatId) throw new Error("No chat selected");
    const res = await fetch(`${API_BASE}/api/models/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        messages: messages.map((m) => ({ role: m.role, content: m.content })),
      }),
    });
    if (!res.ok) throw new Error("Failed to get AI reply");
    const data = await res.json();
    await fetchMessages();
    return data;
  }

  return { messages, loading, error, sendMessage, getAIReply, refetch: fetchMessages };
}
