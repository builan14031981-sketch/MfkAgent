"use client";

import { useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { useSettings } from "@/hooks/useSettings";

interface ThemeProviderProps {
  children: React.ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const { theme } = useAppStore();

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

export function FontProvider({ children }: FontProviderProps) {
  const { settings } = useSettings();

  useEffect(() => {
    if (!settings?.font_family) return;

    // 字体 CDN 映射
    const fontCDN: Record<string, string> = {
      "source-han-sans": "https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap",
      "lxgw-wenkai": "https://cdn.jsdelivr.net/npm/lxgw-wenkai-webfont@1.7.0/style.css",
      "ibm-plex-sans": "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;700&display=swap",
    };

    // 字体映射
    const fontFamilyMap: Record<string, string> = {
      "system": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      "source-han-sans": "'Source Han Sans SC', 'Noto Sans SC', sans-serif",
      "lxgw-wenkai": "'LXGW WenKai', cursive",
      "ibm-plex-sans": "'IBM Plex Sans', sans-serif",
    };

    const root = window.document.documentElement;

    // 如果是系统字体，直接应用
    if (settings.font_family === "system") {
      root.style.setProperty("--font-family", fontFamilyMap["system"]);
      return;
    }

    // 动态加载字体 CDN
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

      // 等待字体加载完成后应用
      link.onload = () => {
        const fontFamily = fontFamilyMap[settings.font_family] || fontFamilyMap["system"];
        root.style.setProperty("--font-family", fontFamily);
      };
    } else {
      // 没有 CDN，直接应用
      const fontFamily = fontFamilyMap[settings.font_family] || fontFamilyMap["system"];
      root.style.setProperty("--font-family", fontFamily);
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
