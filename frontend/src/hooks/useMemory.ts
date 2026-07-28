/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";

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

const API_BASE = "http://127.0.0.1:8001";

export function useMemory(agentId: string) {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMemories = useCallback(async () => {
    if (!agentId) return;
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/memory/${agentId}`);
      if (!res.ok) throw new Error("Failed to fetch memories");
      const data = await res.json();
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
    const res = await fetch(`${API_BASE}/api/memory`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent_id: agentId,
        key,
        value,
        memory_type: memoryType,
      }),
    });
    if (!res.ok) throw new Error("Failed to create memory");
    await fetchMemories();
  }

  async function deleteMemory(id: number) {
    const res = await fetch(`${API_BASE}/api/memory/${id}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete memory");
    await fetchMemories();
  }

  return { memories, loading, error, createMemory, deleteMemory, refetch: fetchMemories };
}
