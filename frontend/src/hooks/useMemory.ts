/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiDelete } from "@/lib/api";
import type { MemoryItem, MemoryScope } from "@/types/memory";

// 保持旧引用兼容：既有 import { MemoryItem } / { MemoryScope } from "@/hooks/useMemory"
export type { MemoryItem, MemoryScope };

/**
 * 极简记忆（memory_items 表）：按 scope 三作用域隔离
 * - global：所有对话可见
 * - agent：当前 Agent 专属（绑定 agentId）
 * - project：当前项目下 Agent 共享（绑定 projectId）
 */
export function useMemory(agentId: string, projectId: number | null = null, scope: MemoryScope = "global") {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMemories = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({ scope });
      if (scope === "agent" && agentId) params.set("agent_id", agentId);
      if (scope === "project" && projectId != null) params.set("project_id", String(projectId));
      const data = await apiGet<MemoryItem[]>(`/api/memories?${params}`);
      setMemories(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [scope, agentId, projectId]);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  async function createMemory(content: string, targetScope: MemoryScope) {
    const trimmed = content.trim();
    if (!trimmed) return;
    await apiPost("/api/memories", {
      scope: targetScope,
      content: trimmed,
      ...(targetScope === "agent" ? { agent_id: agentId } : {}),
      ...(targetScope === "project" && projectId != null ? { project_id: projectId } : {}),
    });
    await fetchMemories();
  }

  async function deleteMemory(id: number) {
    await apiDelete(`/api/memories/${id}`);
    await fetchMemories();
  }

  return { memories, loading, error, createMemory, deleteMemory, refetch: fetchMemories };
}
