/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { apiGet } from "@/lib/api";

export interface FileEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
}

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
      const data = await apiGet<FileEntry[]>(`/api/projects/${projectId}/files?${params}`);
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
