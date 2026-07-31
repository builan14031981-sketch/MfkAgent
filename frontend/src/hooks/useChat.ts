/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/api";

export interface Chat {
  id: number;
  project_id: number | null;
  agent_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  is_pinned: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

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
      const data = await apiGet<PaginatedResponse<Chat>>(`/api/chat?${params}`);
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
    const data = await apiPost<Chat>("/api/chat", {
      project_id: projectId || null,
      agent_id: agentId,
      title: title,
    });
    await fetchChats();
    return data;
  }

  async function updateChat(id: number, updates: { title?: string; agent_id?: string; is_pinned?: boolean }) {
    await apiPatch(`/api/chat/${id}`, updates);
    await fetchChats();
  }

  async function deleteChat(id: number) {
    await apiDelete(`/api/chat/${id}`);
    await fetchChats();
  }

  async function pinChat(id: number, pinned: boolean) {
    await apiPatch(`/api/chat/${id}`, { is_pinned: pinned });
    await fetchChats();
  }

  return { chats, total, loading, error, createChat, updateChat, deleteChat, pinChat, refetch: fetchChats };
}
