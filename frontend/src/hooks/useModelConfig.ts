/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";

export interface ProviderModelConfig {
  id: string;
  name: string;
}

export interface ProviderConfig {
  id: string;
  name: string;
  description?: string;
  free: boolean;
  website?: string;
  api_key_masked: string;
  has_key: boolean;
  api_base: string;
  api_base_override: boolean;
  models: ProviderModelConfig[];
}

export interface CustomModel {
  id: number;
  model_id: string;
  name: string;
  provider: string;
  model_name: string;
  api_base: string;
  api_key_masked: string;
  has_key: boolean;
  max_tokens: number;
  temperature: number;
  enabled: boolean;
}

export interface CustomModelPayload {
  model_id: string;
  name: string;
  provider: string;
  model_name: string;
  api_base: string;
  api_key?: string;
  max_tokens?: number;
  temperature?: number;
  enabled?: boolean;
}

export function useModelConfig() {
  const [configs, setConfigs] = useState<ProviderConfig[]>([]);
  const [customModels, setCustomModels] = useState<CustomModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const [configData, customData] = await Promise.all([
        apiGet<{ configs: ProviderConfig[] }>("/api/models/config"),
        apiGet<CustomModel[]>("/api/models/custom"),
      ]);
      setConfigs(configData.configs);
      setCustomModels(customData);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const saveProviderKey = useCallback(
    async (providerId: string, apiKey?: string, apiBase?: string) => {
      const body: { provider_id: string; api_key?: string; api_base?: string } = { provider_id: providerId };
      if (apiKey !== undefined) body.api_key = apiKey;
      if (apiBase !== undefined) body.api_base = apiBase;
      await apiPost("/api/models/provider-key", body);
      await refresh();
    },
    [refresh]
  );

  const createCustomModel = useCallback(
    async (data: CustomModelPayload) => {
      await apiPost("/api/models/custom", data);
      await refresh();
    },
    [refresh]
  );

  const updateCustomModel = useCallback(
    async (id: number, data: Partial<CustomModelPayload>) => {
      await apiPut(`/api/models/custom/${id}`, data);
      await refresh();
    },
    [refresh]
  );

  const deleteCustomModel = useCallback(
    async (id: number) => {
      await apiDelete(`/api/models/custom/${id}`);
      await refresh();
    },
    [refresh]
  );

  return {
    configs,
    customModels,
    loading,
    error,
    refresh,
    saveProviderKey,
    createCustomModel,
    updateCustomModel,
    deleteCustomModel,
  };
}
