/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiDelete } from "@/lib/api";

export interface Memory {
  id: number;
  agent_id: string;
  user_id: string;
  key: string;
  value: string;
  memory_type: string;
  created_at: string;
  updated_at: string;
}

export function useMemory(agentId: string) {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMemories = useCallback(async () => {
    if (!agentId) return;
    try {
      setLoading(true);
      const data = await apiGet<Memory[]>(`/api/memory/${agentId}`);
      setMemories(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  async function createMemory(key: string, value: string, memoryType: string = "preference") {
    await apiPost("/api/memory", {
      agent_id: agentId,
      key,
      value,
      memory_type: memoryType,
    });
    await fetchMemories();
  }

  async function deleteMemory(id: number) {
    await apiDelete(`/api/memory/${id}`);
    await fetchMemories();
  }

  return { memories, loading, error, createMemory, deleteMemory, refetch: fetchMemories };
}
