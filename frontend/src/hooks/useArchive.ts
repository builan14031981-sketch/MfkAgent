/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiDelete } from "@/lib/api";

export interface ArchiveItem {
  type: "project" | "chat";
  id: number;
  name: string;
  project_id?: number | null;
  archived_at?: string | null;
  archive_path?: string | null;
}

export interface ArchiveData {
  items: ArchiveItem[];
  archive_dir: string;
}

export function useArchive() {
  const [data, setData] = useState<ArchiveData>({ items: [], archive_dir: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      setLoading(true);
      const d = await apiGet<ArchiveData>("/api/archive");
      setData({ items: d.items || [], archive_dir: d.archive_dir || "" });
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
    await apiPost(`/api/archive/project/${id}/restore`, {});
    await refetch();
  }

  async function restoreChat(id: number) {
    await apiPost(`/api/archive/chat/${id}/restore`, {});
    await refetch();
  }

  async function purgeProject(id: number) {
    await apiDelete(`/api/archive/project/${id}`);
    await refetch();
  }

  async function purgeChat(id: number) {
    await apiDelete(`/api/archive/chat/${id}`);
    await refetch();
  }

  return { data, loading, error, refetch, restoreProject, restoreChat, purgeProject, purgeChat };
}
