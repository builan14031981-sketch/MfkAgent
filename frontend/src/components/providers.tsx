"use client";

import { useEffect } from "react";
import { useSettingsStore } from "@/lib/store";

/**
 * V2 视觉主题体系：
 *   官方三主题：
 *   obsidian —— Obsidian Dark，专业 AI 工作站（默认）
 *   studio   —— Apple Studio Light，简洁明亮日间
 *   terminal —— Developer Terminal，开发者高密度
 *   实验主题（探索阶段，待验收筛选）：
 *   titanium / paper / midnight / mono / warm-minimal / aurora
 * 应用方式：html[data-theme] 驱动 tokens.css 中的 --mf-* Token，
 * 同时维持 .dark/.light 类兼容存量样式。
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
  | "aurora";

const VALID_THEMES: readonly VisualTheme[] = [
  "obsidian",
  "studio",
  "terminal",
  "titanium",
  "paper",
  "midnight",
  "mono",
  "warm-minimal",
  "aurora",
];

/** 官方主题 id 集合（非官方即实验主题） */
export const OFFICIAL_THEME_IDS: ReadonlySet<string> = new Set(["obsidian", "studio", "terminal"]);

/** 浅色基调主题：用于 .dark/.light 兼容类判定 */
const LIGHT_BASED_THEMES: ReadonlySet<string> = new Set(["studio", "titanium", "paper", "warm-minimal"]);

/** 从设置中解析视觉主题：visual_theme 优先；存量 theme=light 迁移到 studio，其余回落默认 obsidian */
function resolveVisualTheme(settings: Record<string, string> | null): VisualTheme {
  const raw = settings?.visual_theme;
  if (raw && (VALID_THEMES as readonly string[]).includes(raw)) return raw as VisualTheme;
  if (!raw && settings?.theme === "light") return "studio";
  return "obsidian";
}

interface ThemeProviderProps {
  children: React.ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const { settings } = useSettingsStore();
  const theme = resolveVisualTheme(settings);

  useEffect(() => {
    const root = window.document.documentElement;

    // data-theme 驱动 V2 Token；同步维护 .dark/.light 类兼容存量样式
    root.setAttribute("data-theme", theme);
    root.classList.remove("light", "dark");
    root.classList.add(LIGHT_BASED_THEMES.has(theme) ? "light" : "dark");
  }, [theme]);

  return <>{children}</>;
}

interface FontProviderProps {
  children: React.ReactNode;
}

// 字体映射
const fontFamilyMap: Record<string, string> = {
  "system": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  "source-han-sans": "'Source Han Sans SC', 'Noto Sans SC', sans-serif",
  "lxgw-wenkai": "'LXGW WenKai', cursive",
  "ibm-plex-sans": "'IBM Plex Sans', sans-serif",
};

// 字体 CDN 映射
const fontCDN: Record<string, string> = {
  "source-han-sans": "https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap",
  "lxgw-wenkai": "https://cdn.jsdelivr.net/npm/lxgw-wenkai-webfont@1.7.0/style.css",
  "ibm-plex-sans": "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;700&display=swap",
};

export function FontProvider({ children }: FontProviderProps) {
  const { settings, fetchSettings } = useSettingsStore();

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  useEffect(() => {
    if (!settings?.font_family) return;

    const root = window.document.documentElement;
    const fontFamily = fontFamilyMap[settings.font_family] || fontFamilyMap["system"];

    // 立即应用字体，不依赖 CDN 加载
    root.style.setProperty("--font-family", fontFamily);

    // 动态加载字体 CDN（如果需要）
    if (settings.font_family !== "system") {
      const cdn = fontCDN[settings.font_family];
      if (cdn) {
        // 检查是否已加载
        const existingLink = document.getElementById("font-cdn");
        if (existingLink) existingLink.remove();

        const link = document.createElement("link");
        link.id = "font-cdn";
        link.rel = "stylesheet";
        link.href = cdn;
        document.head.appendChild(link);
      }
    }
  }, [settings?.font_family]);

  return <>{children}</>;
}

// V2.0：强调色多选体系已废除（每个视觉主题自带唯一 accent）。
// AccentProvider 仅保留清理职责：移除旧版本可能残留的 accent-* 类，避免污染新主题。
const LEGACY_ACCENT_CLASSES = [
  "accent-teal",
  "accent-amber",
  "accent-violet",
  "accent-rose",
  "accent-graphite",
];

export function AccentProvider({ children }: ThemeProviderProps) {
  useEffect(() => {
    const root = window.document.documentElement;
    for (const cls of LEGACY_ACCENT_CLASSES) {
      root.classList.remove(cls);
    }
  }, []);

  return <>{children}</>;
}

interface ProvidersProps {
  children: React.ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider>
      <AccentProvider>
        <FontProvider>{children}</FontProvider>
      </AccentProvider>
    </ThemeProvider>
  );
}
