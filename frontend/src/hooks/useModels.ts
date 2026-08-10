/* eslint-disable react-hooks/set-state-in-effect */
/**
 * useModels —— 可用模型列表 Hook（最小刷新联动修复）
 *
 * 根因修复：
 * 此前 useModels 使用本地 useState，每个调用方各自独立实例，mount 时 fetch 一次后永不刷新。
 * 导致设置页清除 Provider Key 后，聊天页的模型列表不更新（需刷新页面）。
 *
 * 最小修复方案（不全面 zustand 化，保持本地 state 架构）：
 * - 新增一个极小的 zustand store（refreshTrigger），只存一个计数器。
 * - useModels 内部订阅 refreshTrigger，变化时自动 re-fetch。
 * - 暴露全局 triggerModelsRefresh()，供 useProviderConfig 在 clearProviderKey 成功后调用。
 * - useModels() 接口不变（{ models, loading, error }），首页/聊天页/设置页/ProjectInitModal 零改动。
 *
 * 不变性契约：
 * - models 数据仍是本地 useState，只在 mount 和 trigger 变化时 fetch。
 * - 不新增重复数据源，不新增接口。
 */
import { useState, useEffect, useCallback } from "react";
import { create } from "zustand";
import { apiGet } from "@/lib/api";

export interface Model {
  id: string;
  name: string;
  provider: string;
  max_tokens?: number;
  priority?: number;
}

// ════════════════════════════════════════════════════════════════════
// 最小全局 store：只存一个刷新计数器，供外部触发联动
// models 数据本身仍是本地 useState，不全面 zustand 化
// ════════════════════════════════════════════════════════════════════

interface RefreshTriggerState {
  /** 每次调用 trigger() 时 +1，useModels 订阅变化后 re-fetch */
  tick: number;
  trigger: () => void;
}

const useRefreshTrigger = create<RefreshTriggerState>((set) => ({
  tick: 0,
  trigger: () => set((s) => ({ tick: s.tick + 1 })),
}));

/** 全局触发模型列表刷新（供 useProviderConfig 联动调用） */
export function triggerModelsRefresh() {
  useRefreshTrigger.getState().trigger();
}

// ════════════════════════════════════════════════════════════════════
// useModels Hook：本地 state + 订阅全局 trigger
// ════════════════════════════════════════════════════════════════════

export function useModels() {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 订阅全局刷新触发器
  const tick = useRefreshTrigger((s) => s.tick);

  const fetchModels = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiGet<Model[]>("/api/models/models");
      setModels(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  // mount 时 fetch + tick 变化时 re-fetch
  useEffect(() => {
    fetchModels();
  }, [fetchModels, tick]);

  return { models, loading, error };
}