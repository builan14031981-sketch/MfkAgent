/**
 * 视觉主题解析与首帧缓存（2026-08-11 从 providers.tsx 抽出）
 *
 * 抽出目的：修复"重启闪黑"FOUC——首帧 CSS（tokens.css :root 默认 obsidian）
 * 先于设置拉取绘制，需在 HTML 解析阶段（next/script beforeInteractive 内联脚本）
 * 读取 localStorage 缓存立即应用上次主题。store.ts 与 providers.tsx 共用本模块，
 * 避免循环依赖与名单双份漂移。
 *
 * 缓存格式（layout.tsx 内联脚本依赖，改动需同步）：
 *   key:   "mfk-visual-theme"
 *   value: JSON { t: 主题id, m: "light" | "dark" }
 *   存解析结果而非原始 settings，内联脚本零逻辑纯应用。
 */

export type VisualTheme =
  | "obsidian"
  | "studio"
  | "terminal"
  | "titanium"
  | "paper"
  | "midnight"
  | "mono"
  | "warm-minimal"
  | "aurora"
  // 2026-08-11 配色调研：Studio 强调色 A/B/C 对比样张，验收后选定写回 studio 再移除
  | "studio-graphite"
  | "studio-lavender"
  | "studio-spectrum";

export const VALID_THEMES: readonly VisualTheme[] = [
  "obsidian",
  "studio",
  "terminal",
  "titanium",
  "paper",
  "midnight",
  "mono",
  "warm-minimal",
  "aurora",
  "studio-graphite",
  "studio-lavender",
  "studio-spectrum",
];

/** 官方主题 id 集合（非官方即实验主题） */
export const OFFICIAL_THEME_IDS: ReadonlySet<string> = new Set(["obsidian", "studio", "terminal"]);

/** 浅色基调主题：用于 .dark/.light 兼容类判定 */
export const LIGHT_BASED_THEMES: ReadonlySet<string> = new Set(["studio", "titanium", "paper", "warm-minimal", "studio-graphite", "studio-lavender", "studio-spectrum"]);

/** 从设置中解析视觉主题：visual_theme 优先；存量 theme=light 迁移到 studio，其余回落默认 obsidian */
export function resolveVisualTheme(settings: Record<string, string> | null): VisualTheme {
  const raw = settings?.visual_theme;
  if (raw && (VALID_THEMES as readonly string[]).includes(raw)) return raw as VisualTheme;
  if (!raw && settings?.theme === "light") return "studio";
  return "obsidian";
}

export function themeMode(theme: string): "light" | "dark" {
  return LIGHT_BASED_THEMES.has(theme) ? "light" : "dark";
}

const THEME_CACHE_KEY = "mfk-visual-theme";

/** 设置到达/变更后写入首帧缓存（解析结果），供下次启动内联脚本首帧前应用 */
export function writeThemeCache(theme: VisualTheme): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(THEME_CACHE_KEY, JSON.stringify({ t: theme, m: themeMode(theme) }));
  } catch {
    /* 隐私模式等 localStorage 不可用场景：静默降级为无缓存（首帧回默认主题） */
  }
}

/** 应用主题到 documentElement：data-theme 驱动 V2 Token，同步维护 .dark/.light 兼容类 */
export function applyThemeToDocument(theme: string): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.setAttribute("data-theme", theme);
  root.classList.remove("light", "dark");
  root.classList.add(themeMode(theme));
}
