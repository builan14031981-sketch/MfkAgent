/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/api";

export interface Project {
  id: number;
  name: string;
  path: string;
  is_pinned: boolean;
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

// 跨实例同步事件：任一实例变更 projects 后广播，所有实例立即重新拉取
export const PROJECTS_CHANGED_EVENT = "mfk-projects-changed";

export function useProjects(page: number = 1, limit: number = 50) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({ page: String(page), limit: String(limit) });
      const data = await apiGet<PaginatedResponse<Project>>(`/api/projects?${params}`);
      setProjects(data.items);
      setTotal(data.total);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [page, limit]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // 监听其他实例的变更事件，实时同步（新建 / 删除 / 置顶等）
  useEffect(() => {
    const handler = () => {
      fetchProjects();
    };
    window.addEventListener(PROJECTS_CHANGED_EVENT, handler);
    return () => window.removeEventListener(PROJECTS_CHANGED_EVENT, handler);
  }, [fetchProjects]);

  // 变更成功后刷新本实例并向所有实例广播
  const refreshAndBroadcast = useCallback(async () => {
    await fetchProjects();
    window.dispatchEvent(new Event(PROJECTS_CHANGED_EVENT));
  }, [fetchProjects]);

  async function createProject(name: string, path: string) {
    const data = await apiPost<Project>("/api/projects", { name, path });
    await refreshAndBroadcast();
    return data;
  }

  async function deleteProject(id: number) {
    await apiDelete(`/api/projects/${id}`);
    await refreshAndBroadcast();
  }

  async function pinProject(id: number, pinned: boolean) {
    await apiPatch(`/api/projects/${id}`, { is_pinned: pinned });
    await refreshAndBroadcast();
  }

  return { projects, total, loading, error, createProject, deleteProject, pinProject, refetch: fetchProjects };
}