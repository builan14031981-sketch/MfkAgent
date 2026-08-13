/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import type { MemoryItem, MemoryScope } from "@/types/memory";

// 保持旧引用兼容：既有 import { MemoryItem } / { MemoryScope } from "@/hooks/useMemory"
export type { MemoryItem, MemoryScope };

/**
 * 极简记忆（memory_items 表）：按 scope 三作用域隔离
 * - global：所有对话可见
 * - agent：当前 Agent 专属（绑定 agentId）
 * - project：当前项目下 Agent 共享（绑定 projectId）
 */
export function useMemory(
  agentId: string,
  projectId: number | null = null,
  scope: MemoryScope = "global",
  search: string = "",
) {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const buildParams = useCallback(() => {
    const params = new URLSearchParams({ scope });
    if (scope === "agent" && agentId) params.set("agent_id", agentId);
    if (scope === "project" && projectId != null) params.set("project_id", String(projectId));
    if (search.trim()) params.set("q", search.trim());
    return params;
  }, [scope, agentId, projectId, search]);

  const fetchMemories = useCallback(async () => {
    try {
      setLoading(true);
      const params = buildParams();
      const data = await apiGet<MemoryItem[]>(`/api/memories?${params}`);
      setMemories(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

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

  async function updateMemory(id: number, patch: { content?: string; memory_type?: string; confidence?: number }) {
    await apiPut(`/api/memories/${id}`, patch);
    await fetchMemories();
  }

  async function deleteMemory(id: number) {
    await apiDelete(`/api/memories/${id}`);
    await fetchMemories();
  }

  async function deleteMemories(ids: number[]) {
    for (const id of ids) {
      await apiDelete(`/api/memories/${id}`);
    }
    await fetchMemories();
  }

  return {
    memories,
    loading,
    error,
    createMemory,
    updateMemory,
    deleteMemory,
    deleteMemories,
    refetch: fetchMemories,
  };
}
