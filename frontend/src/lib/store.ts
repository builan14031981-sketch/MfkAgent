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

export const useSettingsStore = create<SettingsState>((set, get) => ({
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
      await get().fetchSettings();
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
      await get().fetchSettings();
    } catch (err) {
      console.error("Failed to update settings:", err);
    }
  },
}));
