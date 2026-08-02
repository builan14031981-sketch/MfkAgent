"use client";

import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
import { Quote, X, Check, ChevronDown, Shuffle } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";

export interface QuoteItem {
  text: string;
  subtext: string;
}

export interface QuoteCategory {
  id: string;
  name: string;
  count: number;
  items: QuoteItem[];
}

interface QuoteMenuProps {
  categories: QuoteCategory[];
  current: QuoteItem | null;
  onSelect: (item: QuoteItem) => void;
}

interface PanelPos {
  top?: number;
  bottom?: number;
  right: number;
  maxHeight: number;
}

/**
 * 首页欢迎语台词菜单（对标 ThemeSwitcher 交互）：
 * - 6 个文案类目（数字生命 / 世界百大电影 / 江南 / 江南随笔 / 华语歌词 / 外语歌词）
 * - 类目可折叠，点击条目即切换首页欢迎语；随机按钮从全库抽取一句
 * - 定位：自适应上/下展开 + maxHeight 内部滚动 + Portal 挂 body，跟随滚动实时重锚
 */
export function QuoteMenu({ categories, current, onSelect }: QuoteMenuProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<PanelPos | null>(null);

  // 默认展开当前欢迎语所在类目，其余折叠
  const initialCollapsed = useMemo(() => {
    if (!current) return {};
    const map: Record<string, boolean> = {};
    let found = false;
    for (const cat of categories) {
      const isCurrent = cat.items.some((i) => i.text === current.text && i.subtext === current.subtext);
      if (isCurrent) found = true;
      map[cat.id] = !isCurrent;
    }
    return found ? map : {};
  }, [categories, current]);

  const updatePos = useCallback(() => {
    const rect = buttonRef.current?.getBoundingClientRect();
    if (!rect) return;
    const gap = 4;
    const spaceAbove = rect.top - gap;
    const spaceBelow = window.innerHeight - rect.bottom - gap;
    const openUp = spaceBelow < 300 && spaceAbove > spaceBelow;
    const available = (openUp ? spaceAbove : spaceBelow) - gap;
    setPos({
      right: window.innerWidth - rect.right - 4,
      ...(openUp
        ? { bottom: window.innerHeight - rect.top + gap }
        : { top: rect.bottom + gap }),
      maxHeight: Math.max(Math.min(available, 520), 160),
    });
  }, []);

  const openPanel = useCallback(() => {
    updatePos();
    // 每次打开时按当前欢迎语重建折叠状态（默认展开其所在类目）
    setCollapsed(initialCollapsed);
    setOpen(true);
  }, [updatePos, initialCollapsed]);

  const closePanel = useCallback(() => {
    setOpen(false);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closePanel();
    };
    const onResize = () => updatePos();
    const onScroll = () => updatePos();
    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (panelRef.current?.contains(target) || buttonRef.current?.contains(target)) return;
      closePanel();
    };
    window.addEventListener("resize", onResize);
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onMouseDown);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open, updatePos, closePanel]);

  const allItems = useMemo(
    () => categories.flatMap((cat) => cat.items),
    [categories]
  );

  const handleShuffle = useCallback(() => {
    if (allItems.length === 0) return;
    const pick = allItems[Math.floor(Math.random() * allItems.length)];
    onSelect(pick);
  }, [allItems, onSelect]);

  const handlePick = useCallback((item: QuoteItem) => {
    onSelect(item);
    closePanel();
  }, [onSelect, closePanel]);

  const activeFor = useCallback(
    (item: QuoteItem) => current !== null && item.text === current.text && item.subtext === current.subtext,
    [current]
  );

  const buttonVisible = categories.length > 0;

  return (
    <>
      <button
        ref={buttonRef}
        onClick={openPanel}
        title={t("home.hero.switchQuote")}
        style={{
          position: "absolute",
          top: 36,
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
          opacity: buttonVisible ? 1 : 0,
          transition: "all 0.2s ease",
        }}
      >
        <Quote style={{ width: 14, height: 14 }} />
        {t("home.hero.quoteShort")}
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
            overscrollBehavior: "contain",
            zIndex: 9999,
            borderRadius: 12,
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-2)",
            boxShadow: "var(--shadow-lg)",
            padding: 6,
            animation: "scaleIn 0.15s ease",
          }}
          className="no-scrollbar"
        >
          {/* 头部：标题 / 随机 / 关闭 */}
          <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "2px 2px 8px" }}>
            <span style={{ flex: 1, fontSize: 12, fontWeight: 600, color: "var(--text-level-2)", paddingLeft: 4 }}>
              {t("home.hero.quoteMenu")}
            </span>
            <button
              onClick={handleShuffle}
              title={t("home.hero.quoteRandom")}
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

          {/* 类目分组：可折叠 */}
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {categories.map((cat) => {
              const isCollapsed = !!collapsed[cat.id];
              return (
                <div key={cat.id}>
                  <button
                    onClick={() => setCollapsed((prev) => ({ ...prev, [cat.id]: !isCollapsed }))}
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
                    <span style={{ flex: 1 }}>{cat.name}</span>
                    <span>{cat.count}</span>
                  </button>
                  {!isCollapsed && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                      {cat.items.map((item) => {
                        const active = activeFor(item);
                        return (
                          <div
                            key={`${cat.id}:${item.text}`}
                            onClick={() => handlePick(item)}
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
                            <span style={{ flex: 1, fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.text}</span>
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
        </div>,
        document.body
      )}
    </>
  );
}
