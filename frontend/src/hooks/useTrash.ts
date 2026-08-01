/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiDelete } from "@/lib/api";

export interface TrashProject {
  id: number;
  type: "project";
  name: string;
  path: string;
  deleted_at: string | null;
}

export interface TrashChat {
  id: number;
  type: "chat";
  title: string;
  project_id: number | null;
  deleted_at: string | null;
}

export interface TrashData {
  projects: TrashProject[];
  chats: TrashChat[];
}

export function useTrash() {
  const [data, setData] = useState<TrashData>({ projects: [], chats: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      setLoading(true);
      const d = await apiGet<TrashData>("/api/trash");
      setData({ projects: d.projects || [], chats: d.chats || [] });
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  async function restoreProject(id: number) {
    await apiPost(`/api/trash/projects/${id}/restore`, {});
    await refetch();
  }

  async function restoreChat(id: number) {
    await apiPost(`/api/trash/chats/${id}/restore`, {});
    await refetch();
  }

  async function purgeProject(id: number) {
    await apiDelete(`/api/trash/projects/${id}/forever`);
    await refetch();
  }

  async function purgeChat(id: number) {
    await apiDelete(`/api/trash/chats/${id}/forever`);
    await refetch();
  }

  return { data, loading, error, refetch, restoreProject, restoreChat, purgeProject, purgeChat };
}
