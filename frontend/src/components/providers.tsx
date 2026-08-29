"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { MotionConfig } from "framer-motion";
import { useSettingsStore } from "@/lib/store";
import {
  resolveVisualTheme,
  applyThemeToDocument,
  writeThemeCache,
  type VisualTheme,
  OFFICIAL_THEME_IDS,
} from "@/lib/theme";

/**
 * V2 视觉主题体系（2026-08-13 整理）：
 *   官方主题：
 *   studio-graphite —— Studio 石墨（Notion 式近黑强调，默认）
 *   terminal        —— Developer Terminal，开发者高密度
 *   实验主题（原官方降级 + 探索）：
 *   obsidian / studio / titanium / paper / midnight / mono / warm-minimal / aurora
 *   已移除：studio-lavender / studio-spectrum（归档 _backup/theme-regroup-20260813）
 * 应用方式：html[data-theme] 驱动 tokens.css 中的 --mf-* Token，
 * 同时维持 .dark/.light 类兼容存量样式。
 * 2026-08-11：解析/名单/缓存逻辑抽至 @/lib/theme（修重启闪黑 FOUC），此处重导出保持兼容。
 */
export type { VisualTheme };
export { OFFICIAL_THEME_IDS };

interface ThemeProviderProps {
  children: React.ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const { settings } = useSettingsStore();
  const theme = resolveVisualTheme(settings);

  useEffect(() => {
    // 设置未到达前不得应用主题：resolveVisualTheme(null)=studio-graphite 会把
    // layout 内联守卫首帧应用的缓存主题（如浅色）覆盖回黑色，造成黑闪。
    // 首帧主题由守卫脚本负责，Provider 只在设置到达后接管。
    if (!settings) return;
    // data-theme 驱动 V2 Token；同步维护 .dark/.light 类兼容存量样式；
    // 并写首帧缓存，下次启动由 layout 内联脚本首帧前应用
    applyThemeToDocument(theme);
    writeThemeCache(theme);
  }, [theme, settings]);

  return <>{children}</>;
}

interface FontProviderProps {
  children: React.ReactNode;
}

// 字体映射：source-han-sans / ibm-plex-sans 引用本地自托管字体的
// CSS 变量（globals.css :root，@font-face 来自 fontsource 包），零网络依赖；
// 霞鹜文楷无本地托管，保留 CDN
export const FONT_FAMILY_MAP: Record<string, string> = {
  "system": "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei UI', 'Noto Sans CJK SC', sans-serif",
  "source-han-sans": "var(--font-noto-sans-sc), 'PingFang SC', 'Microsoft YaHei UI', sans-serif",
  "lxgw-wenkai": "'LXGW WenKai', 'PingFang SC', 'Microsoft YaHei UI', cursive",
  "ibm-plex-sans": "var(--font-ibm-plex-sans), 'PingFang SC', 'Microsoft YaHei UI', sans-serif",
};

// 字体 CDN 映射：本地字体可用时不会用到，仅作极端场景兜底
const fontCDN: Record<string, string> = {
  "source-han-sans": "https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&display=swap",
  "lxgw-wenkai": "https://cdn.jsdelivr.net/npm/lxgw-wenkai-webfont@1.7.0/style.css",
  "ibm-plex-sans": "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;700&display=swap",
};

// 字体可用性检测用的 family 名（fontsource 包注册的 @font-face family；
// 2026-08-11 字体本地化：next/font/google → fontsource，可变字体名带 Variable 后缀）
const FONT_CHECK_NAME: Record<string, string> = {
  "source-han-sans": "Noto Sans SC Variable",
  "lxgw-wenkai": "LXGW WenKai",
  "ibm-plex-sans": "IBM Plex Sans Variable",
};

export function FontProvider({ children }: FontProviderProps) {
  const { settings, fetchSettings } = useSettingsStore();

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  useEffect(() => {
    if (!settings?.font_family) return;

    const root = window.document.documentElement;
    const fontFamily = FONT_FAMILY_MAP[settings.font_family] || FONT_FAMILY_MAP["system"];

    // 立即应用字体，不依赖 CDN 加载
    root.style.setProperty("--font-family", fontFamily);

    if (settings.font_family === "system") return;

    const key = settings.font_family;
    const cdn = fontCDN[key];
    const checkName = FONT_CHECK_NAME[key];
    // 本地自托管 @font-face 缺失时回退 CDN（正常情况 fontsource CSS 始终在，检测通过）；
    // 打包版/dev 均为纯本地零请求
    const missingLocal = checkName ? !document.fonts?.check(`16px "${checkName}"`) : true;
    const existingLink = document.getElementById("font-cdn");

    if (cdn && missingLocal) {
      if (existingLink && existingLink.getAttribute("href") !== cdn) existingLink.remove();
      if (!document.getElementById("font-cdn")) {
        const link = document.createElement("link");
        link.id = "font-cdn";
        link.rel = "stylesheet";
        link.href = cdn;
        document.head.appendChild(link);
      }
    } else if (existingLink) {
      // 本地字体可用：清理旧选项残留的 CDN link
      existingLink.remove();
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
  const router = useRouter();

  // 监听 Electron 主进程通知点击 → 客户端路由导航，避免 loadURL 硬导航白屏
  useEffect(() => {
    if (typeof window !== "undefined" && window.electronAPI?.onNavigateToChat) {
      window.electronAPI.onNavigateToChat((chatId) => {
        router.push(`/chat/${chatId}`);
      });
    }
  }, [router]);

  return (
    <MotionConfig reducedMotion="user">
      <ThemeProvider>
        <AccentProvider>
          <FontProvider>{children}</FontProvider>
        </AccentProvider>
      </ThemeProvider>
    </MotionConfig>
  );
}
