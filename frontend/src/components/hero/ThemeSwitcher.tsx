"use client";

import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
import { Palette, X, Check, Power, Star, ArrowLeft, ChevronDown, Shuffle, Layers } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { THEME_CATEGORIES } from "@/themes/registry";
import { MAX_FAVORITES } from "@/hooks/useHeroTheme";
import type { HeroTheme } from "@/themes/types";

interface ThemeSwitcherProps {
  theme: HeroTheme | undefined;
  themes: HeroTheme[];
  enabled: boolean;
  setEnabled: (value: boolean) => void;
  setTheme: (id: string) => void;
  shuffle: () => void;
  favorites: string[];
  favoriteThemes: HeroTheme[];
  isFavorite: (id: string) => boolean;
  toggleFavorite: (id: string) => void;
}

interface PanelPos {
  top?: number;
  bottom?: number;
  right: number;
  maxHeight: number;
}

/**
 * 首页主题快速切换器：
 * - 快捷区：只展示收藏主题（上限 5），一键切换
 * - 「查看更多」→ 完整主题列表（分类分组、可折叠、紧凑高密度，支撑 20+ 主题）
 * - 定位：自适应上/下展开 + maxHeight 内部滚动 + Portal 挂 body，
 *   入口附近空间不足时自动翻转方向，杜绝内容被遮挡/截断
 */
export function ThemeSwitcher({
  theme,
  themes,
  enabled,
  setEnabled,
  setTheme,
  shuffle,
  favorites,
  favoriteThemes,
  isFavorite,
  toggleFavorite,
}: ThemeSwitcherProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [fullView, setFullView] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<PanelPos | null>(null);

  const updatePos = useCallback(() => {
    const rect = buttonRef.current?.getBoundingClientRect();
    if (!rect) return;
    const spaceAbove = rect.top - 8;
    const spaceBelow = window.innerHeight - rect.bottom - 8;
    const openUp = spaceBelow < 260 && spaceAbove > spaceBelow;
    setPos({
      right: window.innerWidth - rect.right - 4,
      ...(openUp
        ? { bottom: window.innerHeight - rect.top + 8 }
        : { top: rect.bottom + 8 }),
      maxHeight: Math.max((openUp ? spaceAbove : spaceBelow) - 8, 160),
    });
  }, []);

  const openPanel = useCallback(() => {
    updatePos();
    setOpen(true);
  }, [updatePos]);

  const closePanel = useCallback(() => {
    setOpen(false);
    setFullView(false);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closePanel();
    };
    const onResize = () => updatePos();
    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (panelRef.current?.contains(target) || buttonRef.current?.contains(target)) return;
      closePanel();
    };
    window.addEventListener("resize", onResize);
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onMouseDown);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onMouseDown);
    };
  }, [open, updatePos, closePanel]);

  // 完整列表按分类分组（保持注册表顺序）
  const grouped = useMemo(() => {
    const groups: { category: string; items: HeroTheme[] }[] = [];
    const known = new Set(THEME_CATEGORIES.map((c) => c.id));
    for (const cat of THEME_CATEGORIES) {
      const items = themes.filter((item) => item.category === cat.id);
      if (items.length > 0) groups.push({ category: cat.id, items });
    }
    const others = themes.filter((item) => !known.has(item.category));
    if (others.length > 0) groups.push({ category: "other", items: others });
    return groups;
  }, [themes]);

  const categoryLabel = (id: string) => t(`home.hero.categories.${id}`);
  // 完整列表入口始终可见：即使全部收藏，也需进入列表管理（取消收藏）
  const showMore = themes.length > 0;

  return (
    <>
      <button
        ref={buttonRef}
        onClick={openPanel}
        title={t("home.hero.switchTheme")}
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 10px",
          borderRadius: "var(--radius-full)",
          border: "1px solid var(--border-primary)",
          background: "var(--bg-level-2)",
          color: "var(--text-level-3)",
          cursor: "pointer",
          fontSize: 12,
          opacity: theme ? 1 : 0,
          transition: "all 0.2s ease",
        }}
      >
        <Palette style={{ width: 14, height: 14 }} />
        {theme ? theme.name : ""}
      </button>

      {open && pos && typeof document !== "undefined" && createPortal(
        <div
          ref={panelRef}
          style={{
            position: "fixed",
            right: pos.right,
            ...(pos.top !== undefined ? { top: pos.top } : { bottom: pos.bottom }),
            width: 272,
            maxHeight: pos.maxHeight,
            overflowY: "auto",
            zIndex: 9999,
            borderRadius: 12,
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-2)",
            boxShadow: "var(--shadow-lg)",
            padding: 6,
            animation: "scaleIn 0.15s ease",
          }}
        >
          {/* 头部：返回 / 标题 / 随机 / 关闭 */}
          <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "2px 2px 8px" }}>
            {fullView && (
              <button
                onClick={() => setFullView(false)}
                title={t("home.hero.back")}
                style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--text-level-3)", padding: 2, display: "flex" }}
              >
                <ArrowLeft style={{ width: 14, height: 14 }} />
              </button>
            )}
            <span style={{ flex: 1, fontSize: 12, fontWeight: 600, color: "var(--text-level-2)", paddingLeft: 4 }}>
              {fullView ? t("home.hero.allThemes") : t("home.hero.title")}
            </span>
            <button
              onClick={() => { shuffle(); }}
              title={t("home.hero.random")}
              style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--text-level-3)", padding: 2, display: "flex" }}
            >
              <Shuffle style={{ width: 14, height: 14 }} />
            </button>
            <button
              onClick={closePanel}
              title={t("common.close")}
              style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--text-level-4)", padding: 2, display: "flex" }}
            >
              <X style={{ width: 14, height: 14 }} />
            </button>
          </div>

          {/* 快捷区：仅收藏主题 */}
          {!fullView && (
            <>
              <div style={{ fontSize: 11, color: "var(--text-level-4)", padding: "0 4px 6px", display: "flex", alignItems: "center", gap: 6 }}>
                <Star style={{ width: 11, height: 11, color: "var(--color-warning)", fill: "var(--color-warning)" }} />
                <span>{t("home.hero.favorites")}</span>
                <span style={{ marginLeft: "auto" }}>{favorites.length}/{MAX_FAVORITES}</span>
              </div>

              {favoriteThemes.length === 0 ? (
                <div style={{ fontSize: 12, color: "var(--text-level-4)", padding: "6px 8px" }}>
                  {t("home.hero.noFavorites")}
                </div>
              ) : (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4, padding: "0 2px" }}>
                  {favoriteThemes.map((item) => {
                    const active = theme?.id === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => setTheme(item.id)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          padding: "4px 9px",
                          borderRadius: 999,
                          border: `1px solid ${active ? "var(--color-primary)" : "var(--border-primary)"}`,
                          background: active ? "var(--color-primary-light)" : "transparent",
                          cursor: "pointer",
                          fontSize: 12,
                          color: active ? "var(--color-primary)" : "var(--text-level-2)",
                          maxWidth: "100%",
                        }}
                      >
                        <span style={{ width: 8, height: 8, borderRadius: 2, background: item.accent, flexShrink: 0 }} />
                        <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.name}</span>
                      </button>
                    );
                  })}
                </div>
              )}

              {showMore && (
                <button
                  onClick={() => { updatePos(); setFullView(true); }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    width: "100%",
                    marginTop: 8,
                    padding: "7px 8px",
                    borderRadius: 8,
                    border: "none",
                    background: "var(--bg-level-1)",
                    cursor: "pointer",
                    fontSize: 12,
                    color: "var(--text-level-3)",
                    textAlign: "left",
                  }}
                >
                  <Layers style={{ width: 13, height: 13 }} />
                  <span style={{ flex: 1 }}>{t("home.hero.seeMore")}</span>
                  <span style={{ fontSize: 11, color: "var(--text-level-4)" }}>{themes.length}</span>
                  <ChevronDown style={{ width: 13, height: 13, transform: "rotate(-90deg)" }} />
                </button>
              )}
            </>
          )}

          {/* 完整列表：分类分组 + 折叠 */}
          {fullView && (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {grouped.map((group) => {
                const isCollapsed = !!collapsed[group.category];
                return (
                  <div key={group.category}>
                    <button
                      onClick={() => setCollapsed((prev) => ({ ...prev, [group.category]: !isCollapsed }))}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        width: "100%",
                        padding: "5px 8px",
                        border: "none",
                        background: "transparent",
                        cursor: "pointer",
                        fontSize: 11,
                        fontWeight: 600,
                        color: "var(--text-level-4)",
                        textAlign: "left",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                      }}
                    >
                      <ChevronDown style={{ width: 12, height: 12, transform: isCollapsed ? "rotate(-90deg)" : "none", transition: "transform 0.15s ease" }} />
                      <span style={{ flex: 1 }}>{categoryLabel(group.category)}</span>
                      <span>{group.items.length}</span>
                    </button>
                    {!isCollapsed && (
                      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                        {group.items.map((item) => {
                          const active = theme?.id === item.id;
                          const fav = isFavorite(item.id);
                          return (
                            <div
                              key={item.id}
                              onClick={() => setTheme(item.id)}
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 8,
                                padding: "6px 8px 6px 26px",
                                borderRadius: 8,
                                cursor: "pointer",
                                background: active ? "var(--color-primary-lighter)" : "transparent",
                                color: active ? "var(--color-primary)" : "var(--text-level-2)",
                              }}
                            >
                              <span style={{ width: 10, height: 10, borderRadius: 3, background: item.accent, flexShrink: 0 }} />
                              <span style={{ flex: 1, fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.name}</span>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  toggleFavorite(item.id);
                                }}
                                title={fav ? t("home.hero.unfavorite") : t("home.hero.favorite")}
                                style={{
                                  border: "none",
                                  background: "transparent",
                                  cursor: "pointer",
                                  padding: 2,
                                  display: "flex",
                                  color: fav ? "var(--color-warning)" : "var(--text-level-4)",
                                  opacity: fav ? 1 : 0.6,
                                }}
                              >
                                <Star style={{ width: 13, height: 13, fill: fav ? "var(--color-warning)" : "none" }} />
                              </button>
                              {active && <Check style={{ width: 13, height: 13, flexShrink: 0 }} />}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* 底部：动画开关 */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 4px 4px", borderTop: "1px solid var(--border-primary)", marginTop: 8 }}>
            <Power style={{ width: 13, height: 13, color: "var(--text-level-4)" }} />
            <span style={{ flex: 1, fontSize: 12, color: "var(--text-level-3)" }}>{t("home.hero.animations")}</span>
            <button
              onClick={() => setEnabled(!enabled)}
              role="switch"
              aria-checked={enabled}
              style={{
                width: 34,
                height: 19,
                borderRadius: 999,
                border: "none",
                background: enabled ? "var(--color-primary)" : "var(--bg-level-4)",
                cursor: "pointer",
                position: "relative",
                transition: "background 0.2s ease",
              }}
            >
              <span style={{
                position: "absolute",
                top: 2,
                left: enabled ? 17 : 2,
                width: 15,
                height: 15,
                borderRadius: "50%",
                background: "#fff",
                transition: "left 0.2s ease",
              }} />
            </button>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
