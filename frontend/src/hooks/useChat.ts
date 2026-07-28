/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";

export interface Chat {
  id: number;
  project_id: number | null;
  agent_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

const API_BASE = "http://127.0.0.1:8001";

export function useChat(projectId?: number | null) {
  const [chats, setChats] = useState<Chat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchChats = useCallback(async () => {
    try {
      setLoading(true);
      const url = projectId
        ? `${API_BASE}/api/chat?project_id=${projectId}`
        : `${API_BASE}/api/chat`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to fetch chats");
      const data = await res.json();
      setChats(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchChats();
  }, [fetchChats]);

  async function createChat(agentId: string, title: string, projectId?: number | null) {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_id: projectId || null,
        agent_id: agentId,
        title: title,
      }),
    });
    if (!res.ok) throw new Error("Failed to create chat");
    const data = await res.json();
    await fetchChats();
    return data;
  }

  async function deleteChat(id: number) {
    const res = await fetch(`${API_BASE}/api/chat/${id}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete chat");
    await fetchChats();
  }

  return { chats, loading, error, createChat, deleteChat, refetch: fetchChats };
}
