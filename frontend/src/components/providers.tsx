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

    const root = window.document.documentElement;
    const fontMap: Record<string, string> = {
      "system": "var(--font-geist-sans), -apple-system, BlinkMacSystemFont, sans-serif",
      "noto-sans-sc": "var(--font-noto-sans-sc), sans-serif",
      "lxgw-wenkai": "var(--font-lxgw-wenkai), serif",
      "ibm-plex-sans": "var(--font-ibm-plex-sans), sans-serif",
    };

    const fontFamily = fontMap[settings.font_family] || fontMap["system"];
    root.style.setProperty("--font-family", fontFamily);
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
