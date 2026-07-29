/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { apiGet } from "@/lib/api";

export interface FileContent {
  path: string;
  content: string;
  size: number;
  encoding: string;
}

export function useFileContent(projectId: number | null, filePath: string) {
  const [fileContent, setFileContent] = useState<FileContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchContent = useCallback(async () => {
    if (!projectId || !filePath) return;
    try {
      setLoading(true);
      const params = new URLSearchParams({ path: filePath });
      const data = await apiGet<FileContent>(`/api/projects/${projectId}/file?${params}`);
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
