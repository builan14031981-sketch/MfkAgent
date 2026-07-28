import { useState, useEffect } from "react";

export interface Agent {
  id: string;
  name: string;
  description: string;
  avatar: string;
  system_prompt: string;
}

const API_BASE = "http://127.0.0.1:8001";

export function useAgents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAgents();
  }, []);

  async function fetchAgents() {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/agents`);
      if (!res.ok) throw new Error("Failed to fetch agents");
      const data = await res.json();
      setAgents(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return { agents, loading, error };
}
