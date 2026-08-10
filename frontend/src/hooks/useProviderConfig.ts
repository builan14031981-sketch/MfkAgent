"use client";
/**
 * useProviderConfig —— Provider 配置状态收敛层（状态重构核心）
 *
 * 设计目标：
 * 1. 收拢所有 api_key_*、vision_api_key 的读写/清除/明文判定逻辑，消灭"状态幽灵"。
 * 2. enabled_models 以**后端 settings 表为唯一权威源**（Single Source of Truth），
 *    废除 localStorage 双写污染，彻底修复清空 Key 后界面状态残留 Bug。
 * 3. 暴露统一 loading/error，供 SettingsPanel 统管加载态。
 *
 * 不变性契约：
 * - clearProviderKey 必须保证"后端 purge 关联数据 + 前端 enabled_models 清空"原子可见，
 *   调用方无需再手动补一刀 setEnabled([])。
 * - hasProviderKey 统一脱敏判定：脱敏值非空（含 ****）即视为已配置。
 *
 * API 契约：禁止修改任何后端 URL/Payload，本 Hook 仅封装现有端点调用。
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import { useSettingsStore } from "@/lib/store";
import { triggerModelsRefresh } from "@/hooks/useModels";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";

// ──── 类型定义（与 useModelConfig 保持兼容，禁止破坏后端契约） ────

export interface ProviderModelConfig {
  id: string;
  name: string;
}

export interface RemoteModelInfo {
  /** 上游模型 ID */
  id: string;
  /** 上下文窗口大小（token 数），null 表示无法推测 */
  context_window: number | null;
}

export interface ProviderConfig {
  id: string;
  name: string;
  description?: string;
  free: boolean;
  website?: string;
  /** 后端明文下发：完整 API Key（本地化工具，用户可随时查看）；空串表示未配置 */
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
  /** 后端明文下发：完整 API Key */
  api_key_masked: string;
  has_key: boolean;
  max_tokens: number;
  temperature: number;
  enabled: boolean;
  supports_vision: boolean;
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
  supports_vision?: boolean;
}

// ──── 连通性测试类型（与后端 /api/models/test-connection 契约对齐）────
/**
 * 连通性测试请求。
 * - provider_id: provider 唯一 ID（必填，用于回退读取存量 Key 与默认端点）
 * - api_key / api_base / model_id: 可选，传入输入框实时草稿值；
 *   为 undefined 时后端走三层回退读取系统已存值（BYOK 不落库即可验证）。
 *
 * 注意：调用方必须传入输入框中的实时草稿值（Draft State），
 * 而非 Store 中已保存的值，以支持"无需保存即可验证"的体验。
 */
export interface TestConnectionRequest {
  provider_id: string;
  api_key?: string;
  api_base?: string;
  model_id?: string;
}

/** 连通性测试响应。后端对常见错误也返回 200 + {ok:false, detail}，便于前端统一展示。 */
export interface TestConnectionResponse {
  ok: boolean;
  latency_ms: number;
  detail: string;
  method?: string;
}

// ──── enabled_models 存储约定 ────
/**
 * enabled_models 的 settings key。
 * 值为 JSON 字符串：{ providerId: [modelId, ...] }。
 * 后端 settings 表为**唯一权威源**，localStorage 不再参与写入。
 */
export const ENABLED_MODELS_KEY = "enabled_models";

/** provider_disabled 的 settings key。值为 JSON 字符串：{ providerId: true } 表示禁用。 */
export const PROVIDER_DISABLED_KEY = "provider_disabled";

/** 按 provider 分组的已启用模型映射 */
export type EnabledModelsMap = Record<string, string[]>;

/** provider 禁用映射：{ providerId: true } 表示该 provider 被禁用 */
export type ProviderDisabledMap = Record<string, boolean>;

export interface UseProviderConfigResult {
  // ── 数据 ──
  configs: ProviderConfig[];
  customModels: CustomModel[];
  /** 全量 enabled_models 映射（来自 settings 唯一权威源） */
  enabledMap: EnabledModelsMap;
  /** provider 禁用状态映射（来自 settings 唯一权威源） */
  disabledMap: ProviderDisabledMap;
  loading: boolean;
  error: string | null;

  // ── 刷新 ──
  refresh: () => Promise<void>;

  // ── Provider Key 管理 ──
  /** 保存 provider key/base（apiKey 为 undefined 表示不修改；为空串表示清除） */
  saveProviderKey: (providerId: string, apiKey?: string, apiBase?: string) => Promise<void>;
  /** 彻底清除 provider Key：后端 purge 关联数据 + 前端 enabled_models 同步清空 */
  clearProviderKey: (providerId: string) => Promise<void>;

  // ── 自定义模型 CRUD ──
  createCustomModel: (data: CustomModelPayload) => Promise<void>;
  updateCustomModel: (id: number, data: Partial<CustomModelPayload>) => Promise<void>;
  deleteCustomModel: (id: number) => Promise<void>;

  // ── 远程模型拉取 ──
  /** 拉取上游官方模型列表（含上下文窗口元数据）。返回 RemoteModelInfo[]。 */
  fetchRemoteModels: (providerId: string) => Promise<RemoteModelInfo[]>;

  // ── 连通性测试（草稿值优先，未传字段后端回退读取存量）──
  /**
   * 测试 provider 连通性。
   * @param data 草稿值（api_key/api_base/model_id 可选，未传则后端回退）
   * @returns {ok, latency_ms, detail, method?}
   */
  testConnection: (data: TestConnectionRequest) => Promise<TestConnectionResponse>;

  // ── enabled_models 管理（后端 settings 唯一权威源）──
  getEnabled: (providerId: string) => string[];
  isEnabled: (providerId: string, modelId: string) => boolean;
  addModel: (providerId: string, modelId: string) => Promise<void>;
  removeModel: (providerId: string, modelId: string) => Promise<void>;
  setEnabled: (providerId: string, modelIds: string[]) => Promise<void>;
  hasAnyEnabled: () => boolean;

  // ── Provider 启用/禁用（总开关）──
  /** 判断 provider 是否被禁用 */
  isProviderDisabled: (providerId: string) => boolean;
  /** 设置 provider 启用/禁用状态 */
  setProviderDisabled: (providerId: string, disabled: boolean) => Promise<void>;

  // ── Key 判定（统一入口，消灭分散的 hasKey 逻辑）──
  /** 判断 provider 是否已配置 Key（明文非空即视为已配置） */
  hasProviderKey: (providerId: string) => boolean;
  /** 备用识图 Key 是否已配置（vision_api_key 明文非空即视为已配置） */
  hasVisionKey: () => boolean;
  /** settings store 引用（供 VisionConfigSection 等读写 vision_* 字段） */
  settings: Record<string, string> | null;
  updateSetting: (key: string, value: string) => Promise<void>;
}

/**
 * 安全解析 JSON 字符串为 EnabledModelsMap，失败返回 {}
 */
function parseEnabledMap(raw: string | undefined | null): EnabledModelsMap {
  if (!raw) return {};
  try {
    const obj = JSON.parse(raw);
    if (obj && typeof obj === "object" && !Array.isArray(obj)) {
      const result: EnabledModelsMap = {};
      for (const [k, v] of Object.entries(obj)) {
        if (Array.isArray(v)) {
          result[k] = v.filter((x): x is string => typeof x === "string");
        }
      }
      return result;
    }
  } catch {
    /* 忽略损坏的 JSON */
  }
  return {};
}

/**
 * 安全解析 JSON 字符串为 ProviderDisabledMap，失败返回 {}
 */
function parseDisabledMap(raw: string | undefined | null): ProviderDisabledMap {
  if (!raw) return {};
  try {
    const obj = JSON.parse(raw);
    if (obj && typeof obj === "object" && !Array.isArray(obj)) {
      const result: ProviderDisabledMap = {};
      for (const [k, v] of Object.entries(obj)) {
        if (typeof v === "boolean") result[k] = v;
      }
      return result;
    }
  } catch {
    /* 忽略损坏的 JSON */
  }
  return {};
}

export function useProviderConfig(): UseProviderConfigResult {
  const { settings, fetchSettings, updateSetting } = useSettingsStore();

  const [configs, setConfigs] = useState<ProviderConfig[]>([]);
  const [customModels, setCustomModels] = useState<CustomModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── 权威数据拉取：provider 配置 + 自定义模型 ──
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

  // ── enabled_models：只从 settings 唯一权威源派生，不再写 localStorage ──
  const enabledMap = useMemo<EnabledModelsMap>(() => {
    if (!settings) return {};
    return parseEnabledMap(settings[ENABLED_MODELS_KEY]);
  }, [settings]);

  // ── provider_disabled：只从 settings 唯一权威源派生 ──
  const disabledMap = useMemo<ProviderDisabledMap>(() => {
    if (!settings) return {};
    return parseDisabledMap(settings[PROVIDER_DISABLED_KEY]);
  }, [settings]);

  // settings 未加载时主动拉取（保证 enabled_models 权威源可用）
  useEffect(() => {
    if (!settings) fetchSettings();
  }, [settings, fetchSettings]);

  // ── enabled_models 持久化：只写后端 settings 表，不再双写 localStorage ──
  const persistEnabledMap = useCallback(
    async (next: EnabledModelsMap) => {
      try {
        await updateSetting(ENABLED_MODELS_KEY, JSON.stringify(next));
      } catch (err) {
        console.error("Failed to persist enabled_models:", err);
      }
    },
    [updateSetting]
  );

  // ── Provider Key 保存（apiKey 为空串 = 清除，触发后端 _purge_provider_associated）──
  const saveProviderKey = useCallback(
    async (providerId: string, apiKey?: string, apiBase?: string) => {
      const body: { provider_id: string; api_key?: string; api_base?: string } = {
        provider_id: providerId,
      };
      if (apiKey !== undefined) body.api_key = apiKey;
      if (apiBase !== undefined) body.api_base = apiBase;
      await apiPost("/api/models/provider-key", body);
      await refresh();
    },
    [refresh]
  );

  // ── Provider Key 彻底清除（收敛：后端 purge + 前端 enabled_models 清空，原子可见）──
  const clearProviderKey = useCallback(
    async (providerId: string) => {
      // 1. 后端清除 key + api_base + 关联自定义模型（_purge_provider_associated）
      await saveProviderKey(providerId, "");
      // 2. 前端同步清空该 provider 的 enabled_models（settings 唯一权威源）
      //    基于当前 enabledMap 派生 next，避免覆盖其他 provider 的数据
      const next: EnabledModelsMap = { ...enabledMap, [providerId]: [] };
      await persistEnabledMap(next);
      // 3. 联动刷新全局模型列表：清除 Key 后该 Provider 模型不可用，
      //    触发 useModels 所有调用方（聊天页/首页等）re-fetch，实时同步模型选择器。
      triggerModelsRefresh();
    },
    [saveProviderKey, enabledMap, persistEnabledMap]
  );

  // ── 自定义模型 CRUD ──
  // 每次变更后都触发全局模型列表刷新（create/update/delete 会改后端 models 表，
  // 进而影响 /api/models/models 的返回；其他模块如 ProjectInitModal 的 useModels
  // 订阅 triggerModelsRefresh 后会自动 re-fetch，保证数据同步）。
  const createCustomModel = useCallback(
    async (data: CustomModelPayload) => {
      await apiPost("/api/models/custom", data);
      await refresh();
      triggerModelsRefresh();
    },
    [refresh]
  );

  const updateCustomModel = useCallback(
    async (id: number, data: Partial<CustomModelPayload>) => {
      await apiPut(`/api/models/custom/${id}`, data);
      await refresh();
      triggerModelsRefresh();
    },
    [refresh]
  );

  const deleteCustomModel = useCallback(
    async (id: number) => {
      await apiDelete(`/api/models/custom/${id}`);
      await refresh();
      triggerModelsRefresh();
    },
    [refresh]
  );

  // ── 远程模型拉取 ──
  const fetchRemoteModels = useCallback(async (providerId: string): Promise<RemoteModelInfo[]> => {
    const data = await apiPost<{ models: RemoteModelInfo[] }>("/api/models/fetch_remote", {
      provider_id: providerId,
    });
    return data.models || [];
  }, []);

  // ── 连通性测试（草稿值优先；不依赖任何持久化状态，纯函数式调用）──
  // 设计要点：
  //   1. 调用方传入输入框实时草稿值（Draft State），未传字段后端自动回退读取存量 Key。
  //   2. 后端对常见错误（超时/Key无效/连接失败）也返回 200 + {ok:false, detail}，
  //      所以此处仅在 HTTP 层异常时抛出，业务层错误通过返回值传递。
  //   3. 不触发 refresh()，避免污染已保存配置状态（测试用草稿不应落库）。
  const testConnection = useCallback(
    async (data: TestConnectionRequest): Promise<TestConnectionResponse> => {
      return apiPost<TestConnectionResponse>("/api/models/test-connection", data);
    },
    []
  );

  // ── enabled_models 查询 ──
  const getEnabled = useCallback(
    (providerId: string) => enabledMap[providerId] || [],
    [enabledMap]
  );

  const isEnabled = useCallback(
    (providerId: string, modelId: string) =>
      (enabledMap[providerId] || []).includes(modelId),
    [enabledMap]
  );

  // ── enabled_models 增删改（基于 settings 唯一权威源）──
  const addModel = useCallback(
    async (providerId: string, modelId: string) => {
      const id = modelId.trim();
      if (!id) return;
      const cur = enabledMap[providerId] || [];
      if (cur.includes(id)) return; // 幂等
      await persistEnabledMap({ ...enabledMap, [providerId]: [...cur, id] });
    },
    [enabledMap, persistEnabledMap]
  );

  const removeModel = useCallback(
    async (providerId: string, modelId: string) => {
      const cur = enabledMap[providerId] || [];
      if (!cur.includes(modelId)) return; // 幂等
      const next = cur.filter((m) => m !== modelId);
      await persistEnabledMap({ ...enabledMap, [providerId]: next });
    },
    [enabledMap, persistEnabledMap]
  );

  const setEnabled = useCallback(
    async (providerId: string, modelIds: string[]) => {
      // 去重 + 去空 + 保序
      const seen = new Set<string>();
      const clean: string[] = [];
      for (const m of modelIds) {
        const id = m.trim();
        if (!id || seen.has(id)) continue;
        seen.add(id);
        clean.push(id);
      }
      await persistEnabledMap({ ...enabledMap, [providerId]: clean });
    },
    [enabledMap, persistEnabledMap]
  );

  const hasAnyEnabled = useCallback(
    () => Object.values(enabledMap).some((arr) => arr.length > 0),
    [enabledMap]
  );

  // ── Provider 启用/禁用（总开关）──
  const isProviderDisabled = useCallback(
    (providerId: string) => !!disabledMap[providerId],
    [disabledMap]
  );

  const setProviderDisabled = useCallback(
    async (providerId: string, disabled: boolean) => {
      const next = { ...disabledMap };
      if (disabled) {
        next[providerId] = true;
      } else {
        delete next[providerId];
      }
      try {
        await updateSetting(PROVIDER_DISABLED_KEY, JSON.stringify(next));
        // 触发模型列表刷新，使聊天界面实时响应启用/禁用状态变化
        triggerModelsRefresh();
      } catch (err) {
        console.error("Failed to persist provider_disabled:", err);
      }
    },
    [disabledMap, updateSetting]
  );

  // ── Key 判定（统一入口）──
  // 后端明文下发 API Key，非空即代表已配置真实 Key。
  const hasProviderKey = useCallback(
    (providerId: string) => {
      const p = configs.find((c) => c.id === providerId);
      return !!(p && p.has_key);
    },
    [configs]
  );

  const hasVisionKey = useCallback(() => {
    const plainKey = settings?.vision_api_key || "";
    return plainKey !== "";
  }, [settings]);

  return {
    configs,
    customModels,
    enabledMap,
    disabledMap,
    loading,
    error,
    refresh,
    saveProviderKey,
    clearProviderKey,
    createCustomModel,
    updateCustomModel,
    deleteCustomModel,
    fetchRemoteModels,
    testConnection,
    getEnabled,
    isEnabled,
    addModel,
    removeModel,
    setEnabled,
    hasAnyEnabled,
    isProviderDisabled,
    setProviderDisabled,
    hasProviderKey,
    hasVisionKey,
    settings,
    updateSetting,
  };
}
