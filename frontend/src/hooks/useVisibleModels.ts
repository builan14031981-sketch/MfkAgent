"use client";

import { useMemo } from "react";
import type { Model } from "@/hooks/useModels";
import { useProviderConfig } from "@/hooks/useProviderConfig";

/**
 * useVisibleModels —— 全站统一的"可见模型" hook
 *
 * 2026-08-11 抽离：之前 chat/[id]/page.tsx 内联了一段三层漏斗（provider_disabled → has_key → enabled_models），
 * 但只 chat 页用，ProjectInitModal / app/page.tsx / BasicSettingsView 都直接拿 useModels() 的原始 models，
 * 导致用户在 ModelConfigSection 把 qwen-max 移出候选池后，3 个入口仍能选到。
 *
 * 三层漏斗契约（与之前 chat 页行为完全一致）：
 *  1. provider_disabled：供应商总开关关闭 → 隐藏该 provider 下所有模型
 *  2. hasProviderKey：未配置 API Key → 隐藏该 provider 下所有模型
 *  3. enabled_models（per-provider 白名单）：
 *     - 列表为空 → 该 provider 全部可见（兼容"全启用"语义）
 *     - 列表非空 → 仅列表内模型可见
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
      if (providerConfig.isProviderDisabled(m.provider)) return false;
      if (!providerConfig.hasProviderKey(m.provider)) return false;
      const providerEnabled = providerConfig.getEnabled(m.provider);
      return providerEnabled.length === 0 || providerEnabled.includes(m.id);
    });
    return filtered.length > 0 ? filtered : models;
  }, [
    models,
    providerConfig.loading,
    providerConfig.settings,
    providerConfig.isProviderDisabled,
    providerConfig.hasProviderKey,
    providerConfig.getEnabled,
  ]);
}
