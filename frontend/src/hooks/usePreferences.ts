"use client";

import { useState, useCallback, useMemo } from "react";
import type { Model } from "@/hooks/useModels";
import type { ReasoningEffort } from "@/components/ChatInput";
import { FALLBACK_MODEL_ID } from "@/lib/modelDefaults";

const PREF_MODEL_KEY = "mfk_pref_model";
const PREF_REASONING_KEY = "mfk_pref_reasoning_effort";
// 2026-08-11 改为从 modelDefaults.ts 导入，保留同名别名以最小化下方修改
const DEFAULT_MODEL = FALLBACK_MODEL_ID;

function readLocal(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeLocal(key: string, value: string | null) {
  if (typeof window === "undefined") return;
  try {
    if (value == null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* localStorage 不可用则忽略 */
  }
}

function isReasoningEffort(v: string | null): v is ReasoningEffort {
  return v === "none" || v === "high" || v === "max";
}

export interface UsePreferencesResult {
  /** 三级回落解析后的模型 id：localStorage → settings.default_model → qwen-flash */
  modelId: string;
  /** 三级回落解析后的推理强度：localStorage → settings.default_reasoning_effort → none */
  reasoningEffort: ReasoningEffort;
  /** localStorage 中是否已保存推理强度偏好（供页面决定是否等待 settings 加载） */
  hasLocalReasoning: boolean;
  setModel: (id: string) => void;
  setReasoning: (e: ReasoningEffort) => void;
}

/**
 * 偏好设置三级回落持久化（Phase 1.5）：
 * 模型选择与推理强度统一按 localStorage → /api/settings（后端默认） → 硬编码默认（qwen-flash / none）
 * 的优先级解析；用户手动更改时立即写入 localStorage（最高优先级，下次启动直接命中）。
 */
export function usePreferences(
  models: Model[],
  settings: Record<string, string> | null
): UsePreferencesResult {
  const [prefModel, setPrefModelState] = useState<string | null>(() => readLocal(PREF_MODEL_KEY));
  const [prefReasoning, setPrefReasoningState] = useState<ReasoningEffort | null>(() => {
    const v = readLocal(PREF_REASONING_KEY);
    return isReasoningEffort(v) ? v : null;
  });

  const modelId = useMemo(() => {
    if (prefModel && models.some((m) => m.id === prefModel)) return prefModel;
    const def = settings?.default_model;
    if (def && models.some((m) => m.id === def)) return def;
    return models.some((m) => m.id === DEFAULT_MODEL) ? DEFAULT_MODEL : (models[0]?.id ?? DEFAULT_MODEL);
  }, [prefModel, models, settings?.default_model]);

  const reasoningEffort = useMemo<ReasoningEffort>(() => {
    if (prefReasoning) return prefReasoning;
    const def = settings?.default_reasoning_effort;
    if (def === "high" || def === "max") return def;
    return "none";
  }, [prefReasoning, settings?.default_reasoning_effort]);

  const setModel = useCallback((id: string) => {
    setPrefModelState(id);
    writeLocal(PREF_MODEL_KEY, id);
  }, []);

  const setReasoning = useCallback((e: ReasoningEffort) => {
    setPrefReasoningState(e);
    writeLocal(PREF_REASONING_KEY, e);
  }, []);

  return { modelId, reasoningEffort, hasLocalReasoning: prefReasoning != null, setModel, setReasoning };
}
