/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";

export interface Project {
  id: number;
  name: string;
  path: string;
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

export function useProjects(page: number = 1, limit: number = 50) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({ page: String(page), limit: String(limit) });
      const res = await fetch(`${API_BASE}/api/projects?${params}`);
      if (!res.ok) throw new Error("Failed to fetch projects");
      const data: PaginatedResponse<Project> = await res.json();
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
    const res = await fetch(`${API_BASE}/api/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, path }),
    });
    if (!res.ok) throw new Error("Failed to create project");
    const data = await res.json();
    await fetchProjects();
    return data;
  }

  async function deleteProject(id: number) {
    const res = await fetch(`${API_BASE}/api/projects/${id}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete project");
    await fetchProjects();
  }

  return { projects, total, loading, error, createProject, deleteProject, refetch: fetchProjects };
}
