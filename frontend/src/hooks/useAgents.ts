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

// 跨实例同步事件：任一实例变更 agents 后广播，所有实例立即重新拉取
export const AGENTS_CHANGED_EVENT = "mfk-agents-changed";

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

  // 监听其他实例的变更事件，实时同步
  useEffect(() => {
    const handler = () => {
      fetchAgents();
    };
    window.addEventListener(AGENTS_CHANGED_EVENT, handler);
    return () => window.removeEventListener(AGENTS_CHANGED_EVENT, handler);
  }, [fetchAgents]);

  // 变更成功后刷新本实例并向所有实例广播
  const refreshAndBroadcast = useCallback(async () => {
    await fetchAgents();
    window.dispatchEvent(new Event(AGENTS_CHANGED_EVENT));
  }, [fetchAgents]);

  async function updateAgent(id: string, updates: Partial<Agent>) {
    await apiPatch(`/api/agents/${id}`, updates);
    await refreshAndBroadcast();
  }

  return { agents, loading, error, updateAgent };
}