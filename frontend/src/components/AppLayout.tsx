"use client";

import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { SettingsPanel } from "./panels/SettingsPanel";

interface AppLayoutProps {
  children: React.ReactNode;
}

/** 侧边栏宽度边界（px） */
const SIDEBAR_MIN = 180;
const SIDEBAR_MAX = 480;
const SIDEBAR_DEFAULT = 260;
const SIDEBAR_STORAGE_KEY = "sidebar_width";

function clampWidth(w: number): number {
  return Math.min(Math.max(w, SIDEBAR_MIN), SIDEBAR_MAX);
}

export function AppLayout({ children }: AppLayoutProps) {
  const pathname = usePathname();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // 从URL解析当前chatId
  const currentChatId = useMemo(() => {
    const match = pathname.match(/^\/chat\/(\d+)\/?$/);
    return match ? Number(match[1]) : null;
  }, [pathname]);

  // 侧边栏宽度：React state 驱动初始渲染，拖拽中仅直改 DOM CSS 变量（零 re-render）
  const layoutRef = useRef<HTMLDivElement>(null);
  const dragStateRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const [width, setWidth] = useState(SIDEBAR_DEFAULT);

  // 初始从 localStorage 恢复宽度
  useEffect(() => {
    try {
      const saved = localStorage.getItem(SIDEBAR_STORAGE_KEY);
      if (saved != null) {
        const n = Number(saved);
        if (Number.isFinite(n)) {
          // eslint-disable-next-line react-hooks/set-state-in-effect
          setWidth(clampWidth(n));
        }
      }
    } catch {
      /* localStorage 不可用则忽略 */
    }
  }, []);

  // 同步 state → DOM CSS 变量（初始恢复与最终收尾时执行）
  useEffect(() => {
    layoutRef.current?.style.setProperty("--sidebar-width", `${width}px`);
  }, [width]);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startWidth = Number(
      getComputedStyle(layoutRef.current!).getPropertyValue("--sidebar-width").replace("px", "") || width
    );
    dragStateRef.current = { startX: e.clientX, startWidth };

    // 拖拽期间防止误选中文本
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";

    const onMove = (ev: MouseEvent) => {
      const drag = dragStateRef.current;
      if (!drag) return;
      const delta = ev.clientX - drag.startX;
      const next = clampWidth(drag.startWidth + delta);
      // 零 re-render：仅直改 DOM CSS 变量
      layoutRef.current?.style.setProperty("--sidebar-width", `${next}px`);
    };

    const onUp = () => {
      const drag = dragStateRef.current;
      dragStateRef.current = null;
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      if (drag) {
        // 唯一收尾：同步 state 并持久化
        const final = clampWidth(drag.startWidth);
        setWidth(final);
        try {
          localStorage.setItem(SIDEBAR_STORAGE_KEY, final.toString());
        } catch {
          /* 忽略 */
        }
      }
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, [width]);

  const resetWidth = useCallback(() => {
    setWidth(SIDEBAR_DEFAULT);
    layoutRef.current?.style.setProperty("--sidebar-width", `${SIDEBAR_DEFAULT}px`);
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, SIDEBAR_DEFAULT.toString());
    } catch {
      /* 忽略 */
    }
  }, []);

  return (
    <div
      ref={layoutRef}
      style={{
        display: "flex",
        height: "100vh",
        background: "var(--bg-level-2)",
        position: "relative",
        "--sidebar-width": `${width}px`,
      } as React.CSSProperties}
    >
      {/* 左侧 Sidebar - 固定存在 */}
      <Sidebar
        currentChatId={currentChatId}
        onSettingsClick={() => setIsSettingsOpen(true)}
      />

      {/* 侧边栏拖拽调宽条：位置跟随 CSS 变量，拖拽中零 setState */}
      <div
        onMouseDown={startResize}
        onDoubleClick={resetWidth}
        style={{
          position: "absolute",
          left: "calc(var(--sidebar-width) - 3px)",
          top: 0,
          width: 6,
          height: "100vh",
          cursor: "col-resize",
          zIndex: 20,
          touchAction: "none",
          userSelect: "none",
        }}
      />

      {/* 面板 - 全局覆盖 */}
      <SettingsPanel isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />

      {/* 右侧主内容区 */}
      <main style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        overflow: "hidden",
        minWidth: 0,
      }}>
        {children}
      </main>
    </div>
  );
}