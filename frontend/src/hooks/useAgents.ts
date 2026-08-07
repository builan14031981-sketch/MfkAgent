/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPatch } from "@/lib/api";

export interface Agent {
  id: string;
  name: string;
  description: string;
  avatar: string;
  system_prompt: string;
  identity: string;
  capabilities: string[];
  status: string;
}

export function useAgents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiGet<Agent[]>("/api/agents");
      setAgents(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  async function updateAgent(id: string, updates: Partial<Agent>) {
    await apiPatch(`/api/agents/${id}`, updates);
    await fetchAgents();
  }

  return { agents, loading, error, updateAgent };
}
