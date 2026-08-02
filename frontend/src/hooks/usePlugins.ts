/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";

export type PluginStatus = "installed" | "active" | "inactive" | "error";

export interface PluginInfo {
  pluginId: string;
  name: string;
  version: string;
  description: string;
  author: string;
  status: PluginStatus;
  config: Record<string, unknown>;
}

export interface PluginCreateInput {
  name: string;
  version?: string;
  description?: string;
  author?: string;
  config?: Record<string, unknown>;
}

/** 插件管理（plugins 表，DB 持久化）：CRUD + 激活/停用 + 配置更新 */
export function usePlugins() {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPlugins = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiGet<{ plugins: PluginInfo[] }>("/api/plugins");
      setPlugins(data.plugins || []);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPlugins();
  }, [fetchPlugins]);

  async function createPlugin(input: PluginCreateInput) {
    await apiPost("/api/plugins", input);
    await fetchPlugins();
  }

  async function setPluginActive(pluginId: string, active: boolean) {
    await apiPost(`/api/plugins/${pluginId}/${active ? "activate" : "deactivate"}`, {});
    await fetchPlugins();
  }

  async function updatePluginConfig(pluginId: string, config: Record<string, unknown>) {
    await apiPut(`/api/plugins/${pluginId}/config`, { config });
    await fetchPlugins();
  }

  async function deletePlugin(pluginId: string) {
    await apiDelete(`/api/plugins/${pluginId}`);
    await fetchPlugins();
  }

  return { plugins, loading, error, createPlugin, setPluginActive, updatePluginConfig, deletePlugin, refetch: fetchPlugins };
}
