/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback, useMemo } from "react";
import { apiGet, apiPatch } from "@/lib/api";
import { useSettingsStore } from "@/lib/store";

export interface Agent {
  id: string;
  name: string;
  description: string;
  avatar: string;
  system_prompt: string;
  identity: string;
  capabilities: string[];
  status: string;
  default_personality_level?: number | null;
  expression_profile?: string | null;
  group?: string;
}

/**
 * Agent 英文名映射（英文模式下显示）。
 * 中文模式显示后端返回的中文名，英文模式显示这里的英文名/拼音。
 * 未配置的 agent 英文模式下保持中文名。
 */
const AGENT_EN_NAMES: Record<string, string> = {
  general: "AnGent",
  pianai: "Pianai",
  spark: "Spark",
};

// 跨实例同步事件：任一实例变更 agents 后广播，所有实例立即重新拉取
export const AGENTS_CHANGED_EVENT = "mfk-agents-changed";

// 跨模块同步事件：其他模块（ProjectInitModal 打开等）触发全局 agents 刷新，
// 供那些不方便调 useAgents() 的场景使用（如 Portal 内的子组件、需主动校验场景）。
export const AGENTS_REFRESH_EVENT = "mfk-agents-refresh";

/** 全局触发 agents 列表刷新（供 ProjectInitModal 等主动调用） */
export function triggerAgentsRefresh() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AGENTS_REFRESH_EVENT));
  }
}

export function useAgents() {
  const [rawAgents, setRawAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const locale = useSettingsStore((s) => s.settings?.language ?? "zh-CN");

  const fetchAgents = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiGet<Agent[]>("/api/agents");
      setRawAgents(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  // 根据当前语言转换 agent 显示名：英文模式下用英文名，中文模式下用后端中文名
  const agents = useMemo(() => {
    if (locale === "en-US") {
      return rawAgents.map((a) => ({
        ...a,
        name: AGENT_EN_NAMES[a.id] ?? a.name,
      }));
    }
    return rawAgents;
  }, [rawAgents, locale]);

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

  // 监听外部触发的全局刷新事件（如 ProjectInitModal 打开时主动调用）
  useEffect(() => {
    const handler = () => {
      fetchAgents();
    };
    window.addEventListener(AGENTS_REFRESH_EVENT, handler);
    return () => window.removeEventListener(AGENTS_REFRESH_EVENT, handler);
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