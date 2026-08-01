import type { ComponentType } from "react";

/**
 * Hero 主题通用 Props：
 * 每个主题组件独立实现「MfkAgent 标题 + 欢迎语 + 副文本」的电影开场渲染。
 */
export interface HeroThemeProps {
  title: string;
  welcome: string;
  subtext: string;
  animated: boolean;
}

export interface HeroTheme {
  id: string;
  /** 显示名（专有名词，保持英文） */
  name: string;
  /** 分类 id（用于完整列表分组，见 THEME_CATEGORIES） */
  category: string;
  /** 主题强调色（用于切换器高亮等） */
  accent: string;
  component: ComponentType<HeroThemeProps>;
}

export interface ThemeCategory {
  id: string;
  /** 分类显示名（回退标签，界面优先走 locales） */
  label: string;
}
