"use client";

import { useState, useEffect, useCallback } from "react";
import { getHeroTheme, pickRandomHeroTheme, nextHeroTheme, HERO_THEMES } from "@/themes/registry";
import type { HeroTheme } from "@/themes/types";
import { useSettingsStore } from "@/lib/store";

const STORAGE_THEME = "mfk_hero_theme";
const STORAGE_ENABLED = "mfk_hero_theme_enabled";
const STORAGE_FAVORITES = "mfk_hero_favorites";

/** 收藏位上限 */
export const MAX_FAVORITES = 5;
/** 默认收藏（保证开箱即有快速切换入口） */
const DEFAULT_FAVORITES = ["cyber-terminal", "8bit-boot", "ai-awakening"];

/** 会话级决策标志：每次应用启动只随机一次；手动选择/手动随机后不再被启动随机覆盖 */
let sessionDecided = false;

function readFavorites(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_FAVORITES);
    if (raw !== null) {
      const parsed: unknown = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed
          .filter((id): id is string => typeof id === "string" && !!getHeroTheme(id))
          .slice(0, MAX_FAVORITES);
      }
    }
  } catch {
    /* ignore */
  }
  // 首次使用：播种默认收藏
  return DEFAULT_FAVORITES.filter((id) => !!getHeroTheme(id));
}

function persistFavorites(favorites: string[]) {
  try {
    localStorage.setItem(STORAGE_FAVORITES, JSON.stringify(favorites));
  } catch {
    /* ignore */
  }
}

/**
 * ThemeManager：
 * - 每次应用启动从「设置指定范围」中随机选择一个启动主题（默认全部主题）
 * - 用户手动选择后，本会话内不再被启动随机覆盖
 * - 收藏机制：首页快速切换只展示收藏主题（上限 MAX_FAVORITES）
 * - 可随时关闭动画 / 通过设置关闭整个入口
 * - 偏好持久化到 localStorage，规则控制走 Settings（后端）
 */
export function useHeroTheme() {
  const { settings } = useSettingsStore();
  const [theme, setThemeState] = useState<HeroTheme | undefined>(undefined);
  const [enabled, setEnabledState] = useState(true);
  const [favorites, setFavoritesState] = useState<string[]>([]);

  /** 是否启用首页主题入口（设置：hero_entry，默认开启） */
  const entryEnabled = settings?.hero_entry !== "0";
  /** 是否开启启动随机（设置：hero_random，默认开启） */
  const randomEnabled = settings?.hero_random !== "0";
  /** 随机范围（设置：hero_random_scope，默认全部） */
  const randomScope = settings?.hero_random_scope === "favorites" ? "favorites" : "all";

  const persistTheme = useCallback((id: string) => {
    try {
      localStorage.setItem(STORAGE_THEME, id);
    } catch {
      /* ignore */
    }
  }, []);

  // 挂载时决策：等待设置就绪后按规则执行（随机范围 / 是否随机）；
  // 设置接口加载失败时 1.2s 兜底，按默认规则（随机全部）出主题
  useEffect(() => {
    if (sessionDecided) return;

    const decide = (randomOn: boolean, scope: "all" | "favorites") => {
      let savedId: string | null = null;
      let savedEnabled = true;
      let favs: string[] = [];
      try {
        savedId = localStorage.getItem(STORAGE_THEME);
        savedEnabled = localStorage.getItem(STORAGE_ENABLED) !== "0";
        favs = readFavorites();
      } catch {
        /* ignore */
      }
      setEnabledState(savedEnabled);
      setFavoritesState(favs);

      let chosen: HeroTheme | undefined;
      if (randomOn) {
        const pool =
          scope === "favorites" && favs.length > 0
            ? HERO_THEMES.filter((t) => favs.includes(t.id))
            : HERO_THEMES;
        chosen = pickRandomHeroTheme(pool);
      } else {
        chosen = getHeroTheme(savedId) ?? getHeroTheme(favs[0]) ?? HERO_THEMES[0];
      }
      if (chosen) {
        sessionDecided = true;
        setThemeState(chosen);
        persistTheme(chosen.id);
      }
    };

    if (settings !== null) {
      decide(randomEnabled, randomScope);
      return;
    }
    const t = setTimeout(() => decide(true, "all"), 1200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings]);

  const setTheme = useCallback((id: string) => {
    const next = getHeroTheme(id);
    if (!next) return;
    sessionDecided = true;
    setThemeState(next);
    persistTheme(next.id);
  }, [persistTheme]);

  const cycleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next = nextHeroTheme(prev);
      persistTheme(next.id);
      return next;
    });
  }, [persistTheme]);

  /** 立即随机一次（首页快捷随机，范围跟随设置） */
  const shuffle = useCallback(() => {
    const pool =
      randomScope === "favorites" && favorites.length > 0
        ? HERO_THEMES.filter((t) => favorites.includes(t.id))
        : HERO_THEMES;
    const next = pickRandomHeroTheme(pool);
    sessionDecided = true;
    setThemeState(next);
    persistTheme(next.id);
  }, [favorites, randomScope, persistTheme]);

  const setEnabled = useCallback((value: boolean) => {
    setEnabledState(value);
    try {
      localStorage.setItem(STORAGE_ENABLED, value ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, []);

  const isFavorite = useCallback((id: string) => favorites.includes(id), [favorites]);

  const toggleFavorite = useCallback((id: string) => {
    setFavoritesState((prev) => {
      const has = prev.includes(id);
      let next: string[];
      if (has) {
        next = prev.filter((f) => f !== id);
      } else if (prev.length >= MAX_FAVORITES) {
        // 收藏位已满：挤出最旧收藏
        next = [...prev.slice(1), id];
      } else {
        next = [...prev, id];
      }
      persistFavorites(next);
      return next;
    });
  }, []);

  const favoriteThemes = HERO_THEMES.filter((t) => favorites.includes(t.id));

  return {
    theme,
    enabled,
    entryEnabled,
    favorites,
    favoriteThemes,
    isFavorite,
    toggleFavorite,
    setEnabled,
    setTheme,
    cycleTheme,
    shuffle,
    themes: HERO_THEMES,
  };
}
