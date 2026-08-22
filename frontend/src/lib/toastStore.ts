import { create } from "zustand";

/**
 * SettingsToast store —— 设置面板内轻量保存反馈（成功/失败提示条）
 *
 * 设计说明：
 * - 全局单例 store（zustand），设置面板内任意层级组件可直接 showToast()，无需 props 透传。
 * - 只做"已保存 / 失败原因"两类消息；失败原因直接取 ApiError.message（后端 detail 已在 apiFetch 内提取）。
 * - 3 秒自动消失由 SettingsToast 组件内的定时器控制。
 */
interface SettingsToastState {
  message: string | null;
  type: "success" | "error" | null;
  showToast: (message: string, type: "success" | "error") => void;
  hideToast: () => void;
}

export const useSettingsToast = create<SettingsToastState>((set) => ({
  message: null,
  type: null,
  showToast: (message, type) => set({ message, type }),
  hideToast: () => set({ message: null, type: null }),
}));

/** 从任意 err 提取可读消息（ApiError.message 已含后端 detail） */
export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}