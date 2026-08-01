import { create } from "zustand";
import { apiGet, apiFetch } from "./api";

interface AppState {
  theme: "light" | "dark" | "system";
  setTheme: (theme: "light" | "dark" | "system") => void;
}

export const useAppStore = create<AppState>((set) => ({
  theme: "system",
  setTheme: (theme) => set({ theme }),
}));

// 设置状态
interface SettingsState {
  settings: Record<string, string> | null;
  loading: boolean;
  fetchSettings: () => Promise<void>;
  updateSetting: (key: string, value: string) => Promise<void>;
  updateSettings: (updates: Record<string, string>) => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: null,
  loading: true,
  fetchSettings: async () => {
    try {
      set({ loading: true });
      const data = await apiGet<Record<string, string>>("/api/settings");
      set({ settings: data, loading: false });
    } catch (err) {
      set({ loading: false });
      console.error("Failed to fetch settings:", err);
    }
  },
  updateSetting: async (key: string, value: string) => {
    try {
      await apiFetch(`/api/settings/${key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      });
      // 本地乐观合并，避免全量拉取引发的 loading 翻转与整树重渲染
      set((state) => ({
        settings: state.settings ? { ...state.settings, [key]: value } : state.settings,
      }));
    } catch (err) {
      console.error("Failed to update setting:", err);
    }
  },
  updateSettings: async (updates: Record<string, string>) => {
    try {
      await apiFetch(`/api/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings: updates }),
      });
      // 本地乐观合并
      set((state) => ({
        settings: state.settings ? { ...state.settings, ...updates } : state.settings,
      }));
    } catch (err) {
      console.error("Failed to update settings:", err);
    }
  },
}));
