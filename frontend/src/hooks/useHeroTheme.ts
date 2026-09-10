"use client";

import { useState, useCallback } from "react";
import { HERO_THEMES } from "@/themes/registry";
import type { HeroTheme } from "@/themes/types";

const APPLE_THEME = HERO_THEMES[0];

/**
 * useHeroTheme:
 * 已收敛锁定为 Apple Minimal 极简主题，隐藏其他所有主题及切换交互。
 */
export function useHeroTheme() {
  const [theme] = useState<HeroTheme>(APPLE_THEME);
  const [enabled, setEnabledState] = useState(true);
  const [favorites] = useState<string[]>([APPLE_THEME.id]);

  const setEnabled = useCallback((val: boolean) => {
    setEnabledState(val);
  }, []);

  const setTheme = useCallback((_themeOrId: string | HeroTheme) => {
    // 强制锁定 Apple 主题，不再切换至其他主题
  }, []);

  const shuffle = useCallback(() => {
    // 锁定 Apple 主题，不再随机
  }, []);

  const toggleFavorite = useCallback((_id: string) => {
    // 锁定状态，无需收藏操作
  }, []);

  return {
    theme,
    enabled,
    entryEnabled: true,
    setEnabled,
    setTheme,
    shuffle,
    favorites,
    favoriteThemes: [APPLE_THEME],
    isFavorite: () => true,
    toggleFavorite,
    themes: [APPLE_THEME],
  };
}
