"use client";

import { useEffect, useMemo } from "react";
import { MotionConfig } from "framer-motion";
import { useHeroTheme } from "@/hooks/useHeroTheme";
import { useTranslation } from "@/hooks/useTranslation";
import { StaticTitle } from "./StaticTitle";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { QuoteMenu, QuoteCategory, QuoteItem } from "./QuoteMenu";
import type { QuickAction } from "@/themes/types";

interface HeroStageProps {
  title?: string;
  welcome: string;
  subtext: string;
  quoteCategories?: QuoteCategory[];
  onSelectQuote?: (item: QuoteItem) => void;
  /** 主题内快捷指令点击回调（预填输入框等，由调用方注入） */
  onQuickAction?: (prompt: string) => void;
  /** 当前生效主题 id 变化时上报（供调用方判断是否可交互主题） */
  onThemeChange?: (id: string | undefined) => void;
}

/**
 * 首页启动主题舞台：
 * - 挂载时由 ThemeManager 按设置规则（随机/收藏范围）选择主题并播放
 * - 入口被设置关闭或主题未解析（SSR 首帧）时回退静态标题
 * - enabled 为「动画开关」：关闭动画时主题仍以静态形式展示，可继续切换主题
 * - quickActions：由 home.quickStarts 生成，注入主题组件供可交互主题渲染
 */
export function HeroStage({ title = "MfkAgent", welcome, subtext, quoteCategories, onSelectQuote, onQuickAction, onThemeChange }: HeroStageProps) {
  const { theme, enabled, entryEnabled, setEnabled, setTheme, shuffle, favorites, favoriteThemes, isFavorite, toggleFavorite, themes } = useHeroTheme();
  const { tArray } = useTranslation();

  // 当前生效主题变化时上报（theme 首帧可能为 undefined）
  useEffect(() => {
    onThemeChange?.(theme?.id);
  }, [theme?.id, onThemeChange]);

  // 快捷指令数据源沿用首页现有 home.quickStarts（locale），点击行为统一由调用方决定
  const quickActions = useMemo<QuickAction[]>(
    () => tArray("home.quickStarts").map((prompt, index) => ({ id: `quick-${index}`, prompt })),
    [tArray]
  );
  const handleQuickAction = (action: QuickAction) => {
    onQuickAction?.(action.prompt);
  };

  if (!entryEnabled) {
    return <StaticTitle title={title} welcome={welcome} subtext={subtext} />;
  }

  return (
    <div className="hero-stage" style={{ position: "relative", width: "100%" }}>
      <MotionConfig reducedMotion={enabled ? "never" : "always"}>
        {theme ? (
          <theme.component
            title={title}
            welcome={welcome}
            subtext={subtext}
            animated={enabled}
            quickActions={quickActions}
            onQuickAction={handleQuickAction}
          />
        ) : (
          <StaticTitle title={title} welcome={welcome} subtext={subtext} />
        )}
      </MotionConfig>
      <ThemeSwitcher
        theme={theme}
        themes={themes}
        enabled={enabled}
        setEnabled={setEnabled}
        setTheme={setTheme}
        shuffle={shuffle}
        favorites={favorites}
        favoriteThemes={favoriteThemes}
        isFavorite={isFavorite}
        toggleFavorite={toggleFavorite}
      />
      {quoteCategories && onSelectQuote && (
        <QuoteMenu
          categories={quoteCategories}
          current={{ text: welcome, subtext }}
          onSelect={onSelectQuote}
        />
      )}
    </div>
  );
}
