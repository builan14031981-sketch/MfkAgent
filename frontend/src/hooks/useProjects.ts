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

  async function createProject(name: string, path: string) {
    const data = await apiPost<Project>("/api/projects", { name, path });
    await fetchProjects();
    return data;
  }

  async function deleteProject(id: number) {
    await apiDelete(`/api/projects/${id}`);
    await fetchProjects();
  }

  async function pinProject(id: number, pinned: boolean) {
    await apiPatch(`/api/projects/${id}`, { is_pinned: pinned });
    await fetchProjects();
  }

  return { projects, total, loading, error, createProject, deleteProject, pinProject, refetch: fetchProjects };
}
