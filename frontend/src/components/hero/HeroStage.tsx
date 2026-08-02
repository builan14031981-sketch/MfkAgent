"use client";

import { MotionConfig } from "framer-motion";
import { useHeroTheme } from "@/hooks/useHeroTheme";
import { StaticTitle } from "./StaticTitle";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { QuoteMenu, QuoteCategory, QuoteItem } from "./QuoteMenu";

interface HeroStageProps {
  title?: string;
  welcome: string;
  subtext: string;
  quoteCategories?: QuoteCategory[];
  onSelectQuote?: (item: QuoteItem) => void;
}

/**
 * 首页启动主题舞台：
 * - 挂载时由 ThemeManager 按设置规则（随机/收藏范围）选择主题并播放
 * - 入口被设置关闭或主题未解析（SSR 首帧）时回退静态标题
 * - enabled 为「动画开关」：关闭动画时主题仍以静态形式展示，可继续切换主题
 */
export function HeroStage({ title = "MfkAgent", welcome, subtext, quoteCategories, onSelectQuote }: HeroStageProps) {
  const { theme, enabled, entryEnabled, setEnabled, setTheme, shuffle, favorites, favoriteThemes, isFavorite, toggleFavorite, themes } = useHeroTheme();

  if (!entryEnabled) {
    return <StaticTitle title={title} welcome={welcome} subtext={subtext} />;
  }

  return (
    <div className="hero-stage" style={{ position: "relative", width: "100%" }}>
      <MotionConfig reducedMotion={enabled ? "never" : "always"}>
        {theme ? (
          <theme.component title={title} welcome={welcome} subtext={subtext} animated={enabled} />
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
