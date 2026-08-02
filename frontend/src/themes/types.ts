import type { ComponentType } from "react";

/** 主题内可交互快捷指令（点击触发动作） */
export interface QuickAction {
  id: string;
  /** 展示名（即填入输入框的 prompt） */
  prompt: string;
}

/**
 * Hero 主题通用 Props：
 * 每个主题组件独立实现「MfkAgent 标题 + 欢迎语 + 副文本」的电影开场渲染。
 */
export interface HeroThemeProps {
  title: string;
  welcome: string;
  subtext: string;
  animated: boolean;
  /** 可选：可交互快捷指令。主题组件自行决定是否渲染（接入交互的主题使用） */
  quickActions?: QuickAction[];
  /** 可选：点击某个快捷指令的回调（由 HeroStage 统一注入，主题不关心业务） */
  onQuickAction?: (action: QuickAction) => void;
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
