"use client";

import { useHeroTheme } from "@/hooks/useHeroTheme";
import { StaticTitle } from "./StaticTitle";
import { ThemeSwitcher } from "./ThemeSwitcher";

interface HeroStageProps {
  title?: string;
  welcome: string;
  subtext: string;
}

/**
 * 首页启动主题舞台：
 * - 挂载时由 ThemeManager 按设置规则（随机/收藏范围）选择主题并播放
 * - 入口被设置关闭、主题未解析（SSR 首帧）或动画被关闭时回退静态标题
 */
export function HeroStage({ title = "MfkAgent", welcome, subtext }: HeroStageProps) {
  const { theme, enabled, entryEnabled, setEnabled, setTheme, shuffle, favorites, favoriteThemes, isFavorite, toggleFavorite, themes } = useHeroTheme();

  if (!entryEnabled) {
    return <StaticTitle title={title} welcome={welcome} subtext={subtext} />;
  }

  return (
    <div className="hero-stage" style={{ position: "relative", width: "100%" }}>
      {theme && enabled ? (
        <theme.component title={title} welcome={welcome} subtext={subtext} animated />
      ) : (
        <StaticTitle title={title} welcome={welcome} subtext={subtext} />
      )}
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
    </div>
  );
}
