"use client";

import { useMemo } from "react";
import type { Model } from "@/hooks/useModels";
import { useProviderConfig } from "@/hooks/useProviderConfig";

/**
 * useVisibleModels —— 全站统一的"可见模型" hook
 *
 * 2026-08-11 架构优化：区分内置 provider 与自定义模型 provider。
 *
 * 后端 /api/models/models 是权威源，已保证返回的模型都有有效 API Key。
 * 前端只需叠加 UI 层概念：provider 禁用开关 + enabled_models 候选池白名单。
 *
 * 过滤规则：
 *  - 内置 provider 模型：isProviderDisabled + hasProviderKey + enabled_models
 *  - 自定义模型（provider 不在 configs[]）：仅 enabled_models
 *    （自带 API Key，后端已验证；前端 hasProviderKey 不认识其 provider，不能拦截）
 *
 * 兜底：
 *  - settings 尚未加载完 → 返回原始 models
 *  - 过滤后为空 → 返回原始 models（避免首屏空白 / 老用户升级后模型消失）
 */
export function useVisibleModels(models: Model[]): Model[] {
  const providerConfig = useProviderConfig();

  return useMemo(() => {
    const loaded = !providerConfig.loading && providerConfig.settings != null;
    if (!loaded) return models;
    const filtered = models.filter((m) => {
      // 1. Provider 总开关禁用 → 隐藏（内置 + 自定义 均适用）
      if (providerConfig.isProviderDisabled(m.provider)) return false;

      // 2. API Key 检查：仅对内置 provider 生效
      //    自定义模型自带 Key，后端已验证，前端不重复检查
      if (providerConfig.isBuiltinProvider(m.provider)) {
        if (!providerConfig.hasProviderKey(m.provider)) return false;
      }

      // 3. enabled_models 候选池白名单（空列表 = 全可见）
      const providerEnabled = providerConfig.getEnabled(m.provider);
      return providerEnabled.length === 0 || providerEnabled.includes(m.id);
    });
    return filtered.length > 0 ? filtered : models;
  }, [
    models,
    providerConfig.loading,
    providerConfig.settings,
    providerConfig.isProviderDisabled,
    providerConfig.isBuiltinProvider,
    providerConfig.hasProviderKey,
    providerConfig.getEnabled,
  ]);
}
