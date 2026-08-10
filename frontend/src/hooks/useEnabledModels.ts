"use client";
/**
 * useEnabledModels —— enabled_models 管理薄包装（状态重构后）
 *
 * ⚠️ 状态重构说明：
 * 本 Hook 现已**完全委托**给 useProviderConfig，不再持有任何独立状态。
 * - **废除 localStorage 双写**：后端 settings 表为唯一权威源（Single Source of Truth）。
 * - 彻底修复清空 Key 后界面状态残留 Bug（此前 localStorage 污染导致 UI 残留旧模型）。
 * - 保留本 Hook 仅为向后兼容已有引用，新代码请直接使用 useProviderConfig。
 *
 * @deprecated 新代码请直接使用 useProviderConfig（含 provider key/base/enabled_models 完整收敛）。
 */
import { useProviderConfig, ENABLED_MODELS_KEY } from "./useProviderConfig";

/** 兼容旧引用：enabled_models 存储 key */
export { ENABLED_MODELS_KEY };

/** 按 provider 分组的已启用模型映射：{ providerId: [modelId, ...] } */
export type EnabledModelsMap = Record<string, string[]>;

export interface UseEnabledModelsResult {
  /** 全量已启用映射（按 provider 分组，来自 settings 唯一权威源） */
  enabledMap: EnabledModelsMap;
  /** 是否已从后端加载完成 */
  loaded: boolean;
  /** 判断某 provider 下某 modelId 是否已启用 */
  isEnabled: (providerId: string, modelId: string) => boolean;
  /** 获取某 provider 下已启用的模型 id 列表 */
  getEnabled: (providerId: string) => string[];
  /** 启用某 provider 下的某模型（已存在则幂等） */
  addModel: (providerId: string, modelId: string) => Promise<void>;
  /** 移除某 provider 下的某模型（不存在则幂等） */
  removeModel: (providerId: string, modelId: string) => Promise<void>;
  /** 批量设置某 provider 下的已启用模型列表（整体覆盖） */
  setEnabled: (providerId: string, modelIds: string[]) => Promise<void>;
  /** 判断全局是否至少启用了一个模型 */
  hasAny: () => boolean;
}

/**
 * 已启用模型管理 Hook（薄包装，委托 useProviderConfig）。
 *
 * 状态重构后：后端 settings 表为唯一权威源，localStorage 不再参与写入。
 */
export function useEnabledModels(): UseEnabledModelsResult {
  const providerConfig = useProviderConfig();

  // loaded 等价于 settings 已加载且 provider configs 已加载
  const loaded = !providerConfig.loading && providerConfig.settings != null;

  return {
    enabledMap: providerConfig.enabledMap,
    loaded,
    isEnabled: providerConfig.isEnabled,
    getEnabled: providerConfig.getEnabled,
    addModel: providerConfig.addModel,
    removeModel: providerConfig.removeModel,
    setEnabled: providerConfig.setEnabled,
    hasAny: providerConfig.hasAnyEnabled,
  };
}
