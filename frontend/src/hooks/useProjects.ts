import { useState, useEffect } from "react";

export interface Project {
  id: number;
  name: string;
  path: string;
  created_at: string;
  updated_at: string;
}

const API_BASE = "http://127.0.0.1:8001";

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProjects();
  }, []);

  async function fetchProjects() {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/projects`);
      if (!res.ok) throw new Error("Failed to fetch projects");
      const data = await res.json();
      setProjects(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function createProject(name: string, path: string) {
    try {
      const res = await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, path }),
      });
      if (!res.ok) throw new Error("Failed to create project");
      const data = await res.json();
      await fetchProjects();
      return data;
    } catch (err: any) {
      throw err;
    }
  }

  async function deleteProject(id: number) {
    try {
      const res = await fetch(`${API_BASE}/api/projects/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete project");
      await fetchProjects();
    } catch (err: any) {
      throw err;
    }
  }

  return { projects, loading, error, createProject, deleteProject, refetch: fetchProjects };
}
