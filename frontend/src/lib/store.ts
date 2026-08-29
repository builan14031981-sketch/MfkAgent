import { create } from "zustand";
import { apiGet, apiFetch } from "./api";
import { resolveVisualTheme, writeThemeCache } from "./theme";

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
      // 2026-08-11：写首帧主题缓存，下次启动内联脚本首帧前应用（修重启闪黑）
      writeThemeCache(resolveVisualTheme(data));
    } catch (err) {
      set({ loading: false });
      console.error("Failed to fetch settings:", err);
    }
  },
  updateSetting: async (key: string, value: string) => {
    try {
      const resp = await apiFetch(`/api/settings/${key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      });
      // 敏感 key（api_key_* / vision_api_key）：后端返回脱敏值，用响应值更新本地状态，
      // 避免本地明文残留 + 保证刷新前后判定一致（非空脱敏值 = 已配置）。
      const isSensitive = key.startsWith("api_key_") || key === "vision_api_key";
      let localValue = value;
      if (isSensitive && resp.ok) {
        try {
          const body = await resp.json();
          if (body && typeof body.value === "string") localValue = body.value;
        } catch {
          /* 解析失败回退到原始值 */
        }
      }
      set((state) => ({
        settings: state.settings ? { ...state.settings, [key]: localValue } : state.settings,
      }));
      // 2026-08-11：同步首帧主题缓存（主题类 key 变更即时生效于下次启动）
      const s1 = get().settings;
      if (s1) writeThemeCache(resolveVisualTheme(s1));
    } catch (err) {
      console.error("Failed to update setting:", err);
      throw err;
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
      // 2026-08-11：同步首帧主题缓存
      const s2 = get().settings;
      if (s2) writeThemeCache(resolveVisualTheme(s2));
    } catch (err) {
      console.error("Failed to update settings:", err);
      throw err;
    }
  },
}));
