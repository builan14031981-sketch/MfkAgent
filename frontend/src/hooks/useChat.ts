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

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

const API_BASE = "http://127.0.0.1:8001";

export function useChat(projectId?: number | null, page: number = 1, limit: number = 50) {
  const [chats, setChats] = useState<Chat[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchChats = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({ page: String(page), limit: String(limit) });
      if (projectId) params.append("project_id", String(projectId));
      const res = await fetch(`${API_BASE}/api/chat?${params}`);
      if (!res.ok) throw new Error("Failed to fetch chats");
      const data: PaginatedResponse<Chat> = await res.json();
      setChats(data.items);
      setTotal(data.total);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [projectId, page, limit]);

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

  async function updateChat(id: number, updates: { title?: string; agent_id?: string }) {
    const res = await fetch(`${API_BASE}/api/chat/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    if (!res.ok) throw new Error("Failed to update chat");
    await fetchChats();
  }

  async function deleteChat(id: number) {
    const res = await fetch(`${API_BASE}/api/chat/${id}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete chat");
    await fetchChats();
  }

  return { chats, total, loading, error, createChat, updateChat, deleteChat, refetch: fetchChats };
}
