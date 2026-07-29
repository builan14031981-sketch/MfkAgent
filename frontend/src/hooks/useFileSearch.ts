import { useState, useEffect, useCallback } from "react";
import { apiGet } from "@/lib/api";

export interface SearchResult {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
}

export function useFileSearch(projectId: number | null, query: string, limit: number = 20) {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(async () => {
    if (!projectId || !query.trim()) {
      setResults([]);
      return;
    }
    try {
      setLoading(true);
      const params = new URLSearchParams({ q: query, limit: String(limit) });
      const data = await apiGet<SearchResult[]>(`/api/projects/${projectId}/search?${params}`);
      setResults(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [projectId, query, limit]);

  useEffect(() => {
    const timer = setTimeout(search, 300);
    return () => clearTimeout(timer);
  }, [search]);

  return { results, loading, error };
}
