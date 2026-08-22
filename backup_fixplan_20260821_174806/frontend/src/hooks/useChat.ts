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
  model: string | null;
  personality_level: number;
  context_files: string[];
  mode: "build" | "plan" | "roundtable";
  permission_mode?: "safe" | "standard" | "autonomous";
  is_archived?: boolean;
  archived_at?: string | null;
  roundtable_config?: {
    agent_ids?: string[];
    max_rounds?: number;
    need_summary?: boolean;
    moderator_id?: string | null;
    strategy?: string;
  } | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

// 跨实例同步事件：任一实例变更 chats 后广播，所有实例（Sidebar / Chat 页 / 首页）立即重新拉取
export const CHATS_CHANGED_EVENT = "mfk-chats-changed";

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

  // 监听其他实例的变更事件，实时同步（新建会话 / 置顶 / 取消置顶 / 删除 / 重命名等）
  useEffect(() => {
    const handler = () => {
      fetchChats();
    };
    window.addEventListener(CHATS_CHANGED_EVENT, handler);
    return () => window.removeEventListener(CHATS_CHANGED_EVENT, handler);
  }, [fetchChats]);

  // 变更成功后刷新本实例并向所有实例广播
  const refreshAndBroadcast = useCallback(async () => {
    await fetchChats();
    window.dispatchEvent(new Event(CHATS_CHANGED_EVENT));
  }, [fetchChats]);

  // 创建 Chat：人格由后端从 Agent 快照生成，前端不传 personality_level
  async function createChat(
    agentId: string,
    title: string,
    projectId?: number | null,
    model?: string | null,
    contextFiles?: string[],
    mode?: "build" | "plan" | "roundtable",
    permissionMode?: "safe" | "standard" | "autonomous",
    roundtableConfig?: Chat["roundtable_config"]
  ) {
    const data = await apiPost<Chat>("/api/chat", {
      project_id: projectId || null,
      agent_id: agentId,
      title: title,
      model: model || null,
      context_files: contextFiles || [],
      mode: mode || "build",
      permission_mode: permissionMode || "standard",
      roundtable_config: roundtableConfig || null,
    });
    await refreshAndBroadcast();
    return data;
  }

  async function updateChat(id: number, updates: { title?: string; agent_id?: string; is_pinned?: boolean; model?: string; personality_level?: number; project_id?: number | null; unbind_project?: boolean; mode?: "build" | "plan"; permission_mode?: "safe" | "standard" | "autonomous" }) {
    await apiPatch(`/api/chat/${id}`, updates);
    await refreshAndBroadcast();
  }

  async function deleteChat(id: number) {
    await apiDelete(`/api/chat/${id}`);
    await refreshAndBroadcast();
  }

  async function pinChat(id: number, pinned: boolean) {
    await apiPatch(`/api/chat/${id}`, { is_pinned: pinned });
    await refreshAndBroadcast();
  }

  async function archiveChat(id: number) {
    await apiPost(`/api/archive/chats/${id}`, {});
    await refreshAndBroadcast();
  }

  return { chats, total, loading, error, createChat, updateChat, deleteChat, pinChat, archiveChat, refetch: fetchChats };
}
