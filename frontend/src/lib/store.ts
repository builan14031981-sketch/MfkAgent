import { create } from "zustand";

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
}

const API_BASE = "http://127.0.0.1:8001";

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: null,
  loading: true,
  fetchSettings: async () => {
    try {
      set({ loading: true });
      const res = await fetch(`${API_BASE}/api/settings`);
      if (!res.ok) throw new Error("Failed to fetch settings");
      const data = await res.json();
      set({ settings: data, loading: false });
    } catch (err) {
      set({ loading: false });
      console.error("Failed to fetch settings:", err);
    }
  },
  updateSetting: async (key: string, value: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/settings/${key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      });
      if (!res.ok) throw new Error("Failed to update setting");
      await get().fetchSettings();
    } catch (err) {
      console.error("Failed to update setting:", err);
    }
  },
}));
