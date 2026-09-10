import type { HeroTheme, ThemeCategory } from "./types";
import { AppleMinimalTheme } from "@/components/hero/themes/AppleMinimalTheme";

/**
 * Hero 主题分类：已收敛为仅保留经典的 Apple 极简主题。
 */
export const THEME_CATEGORIES: ThemeCategory[] = [
  { id: "classic", label: "Classic" },
];

/**
 * Hero 主题注册表：
 * 已隐藏其他所有杂乱主题，全局仅保留并锁定 Apple Minimal 主题。
 */
export const HERO_THEMES: HeroTheme[] = [
  {
    id: "apple-minimal",
    name: "Apple Minimal",
    category: "classic",
    accent: "#e5e5e5",
    component: AppleMinimalTheme,
  },
];

export function getHeroTheme(id?: string | null): HeroTheme {
  return HERO_THEMES[0];
}

export const INTERACTIVE_HERO_THEME_IDS: ReadonlySet<string> = new Set();

export function pickRandomHeroTheme(): HeroTheme {
  return HERO_THEMES[0];
}

export function nextHeroTheme(): HeroTheme {
  return HERO_THEMES[0];
}
