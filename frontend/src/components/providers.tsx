"use client";

import { useEffect } from "react";
import { useSettingsStore } from "@/lib/store";

interface ThemeProviderProps {
  children: React.ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const { settings } = useSettingsStore();
  const theme = (settings?.theme as "light" | "dark" | "system") || "system";

  useEffect(() => {
    const root = window.document.documentElement;

    // 移除旧的主题类
    root.classList.remove("light", "dark");

    if (theme === "system") {
      const systemTheme = window.matchMedia("(prefers-color-scheme: dark)")
        .matches
        ? "dark"
        : "light";
      root.classList.add(systemTheme);
    } else {
      root.classList.add(theme);
    }
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

interface ProvidersProps {
  children: React.ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider>
      <FontProvider>{children}</FontProvider>
    </ThemeProvider>
  );
}
