/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";

export interface FileContent {
  path: string;
  content: string;
  size: number;
  encoding: string;
}

const API_BASE = "http://127.0.0.1:8001";

export function useFileContent(projectId: number | null, filePath: string) {
  const [fileContent, setFileContent] = useState<FileContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchContent = useCallback(async () => {
    if (!projectId || !filePath) return;
    try {
      setLoading(true);
      const params = new URLSearchParams({ path: filePath });
      const res = await fetch(`${API_BASE}/api/projects/${projectId}/file?${params}`);
      if (!res.ok) throw new Error("Failed to fetch file content");
      const data = await res.json();
      setFileContent(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [projectId, filePath]);

  useEffect(() => {
    fetchContent();
  }, [fetchContent]);

  return { fileContent, loading, error, refetch: fetchContent };
}
