"use client";

import { useEffect, useMemo } from "react";
import { MotionConfig } from "framer-motion";
import { useHeroTheme } from "@/hooks/useHeroTheme";
import { useTranslation } from "@/hooks/useTranslation";
import { AppleMinimalTheme } from "./themes/AppleMinimalTheme";
import { QuoteMenu, QuoteCategory, QuoteItem } from "./QuoteMenu";
import type { QuickAction } from "@/themes/types";

interface HeroStageProps {
  title?: string;
  welcome: string;
  subtext: string;
  quoteCategories?: QuoteCategory[];
  quoteFavorites?: string[];
  onToggleQuoteFavorite?: (catId: string, item: QuoteItem) => void;
  onSelectQuote?: (item: QuoteItem) => void;
  /** 是否渲染台词小组件（builtin 模式才显示；custom/off 隐藏） */
  showQuoteWidget?: boolean;
  /** 主题内快捷指令点击回调（预填输入框等，由调用方注入） */
  onQuickAction?: (prompt: string) => void;
  /** 当前生效主题 id 变化时上报 */
  onThemeChange?: (id: string | undefined) => void;
}

/**
 * 首页启动主题舞台：
 * 已锁定并仅保留 Apple Minimal 极简主题，隐藏所有其他主题与切换器。
 */
export function HeroStage({
  title = "MfkAgent",
  welcome,
  subtext,
  quoteCategories,
  quoteFavorites,
  onToggleQuoteFavorite,
  onSelectQuote,
  showQuoteWidget = true,
  onQuickAction,
  onThemeChange,
}: HeroStageProps) {
  const { enabled } = useHeroTheme();
  const { tArray } = useTranslation();

  useEffect(() => {
    onThemeChange?.("apple-minimal");
  }, [onThemeChange]);

  const quickActions = useMemo<QuickAction[]>(
    () => tArray("home.quickStarts").map((prompt, index) => ({ id: `quick-${index}`, prompt })),
    [tArray]
  );
  const handleQuickAction = (action: QuickAction) => {
    onQuickAction?.(action.prompt);
  };

  return (
    <div className="hero-stage" style={{ position: "relative", width: "100%" }}>
      <MotionConfig reducedMotion={enabled ? "never" : "always"}>
        <AppleMinimalTheme
          title={title}
          welcome={welcome}
          subtext={subtext}
          animated={enabled}
          quickActions={quickActions}
          onQuickAction={handleQuickAction}
        />
      </MotionConfig>
      {quoteCategories && onSelectQuote && showQuoteWidget && (
        <QuoteMenu
          categories={quoteCategories}
          current={{ text: welcome, subtext }}
          favorites={quoteFavorites}
          onToggleFavorite={onToggleQuoteFavorite}
          onSelect={onSelectQuote}
        />
      )}
    </div>
  );
}
