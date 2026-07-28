/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";

export interface FileEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
}

const API_BASE = "http://127.0.0.1:8001";

export function useProjectFiles(projectId: number | null, subpath: string = "") {
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchFiles = useCallback(async () => {
    if (!projectId) return;
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (subpath) params.append("subpath", subpath);
      const res = await fetch(`${API_BASE}/api/projects/${projectId}/files?${params}`);
      if (!res.ok) throw new Error("Failed to fetch files");
      const data = await res.json();
      setFiles(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [projectId, subpath]);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  return { files, loading, error, refetch: fetchFiles };
}
