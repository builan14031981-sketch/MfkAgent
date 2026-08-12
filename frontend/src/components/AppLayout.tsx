"use client";

import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { usePathname } from "next/navigation";
import { PanelLeftOpen } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { SettingsPanel } from "./panels/SettingsPanel";
import { UserChoiceModal } from "./UserChoiceModal";

interface AppLayoutProps {
  children: React.ReactNode;
}

/** 侧边栏宽度边界（px） */
const SIDEBAR_MIN = 180;
const SIDEBAR_MAX = 480;
const SIDEBAR_DEFAULT = 260;
const SIDEBAR_STORAGE_KEY = "sidebar_width";
// 2026-08-11：侧边栏收起/展开态持久化（此前纯内存，刷新即丢）
const SIDEBAR_COLLAPSED_KEY = "mfk_sidebar_collapsed";

function clampWidth(w: number): number {
  return Math.min(Math.max(w, SIDEBAR_MIN), SIDEBAR_MAX);
}

export function AppLayout({ children }: AppLayoutProps) {
  const pathname = usePathname();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // 挂载后读回收起态（不放在 useState 初始化器里，避免 SSR hydration mismatch）
  useEffect(() => {
    try {
      setSidebarCollapsed(window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1");
    } catch { /* localStorage 不可用时保持展开 */ }
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try { window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, next ? "1" : "0"); } catch { /* noop */ }
      return next;
    });
  }, []);

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
        "--sidebar-width": `${sidebarCollapsed ? 0 : width}px`,
      } as React.CSSProperties}
    >
      {/* 左侧 Sidebar */}
      <Sidebar
        currentChatId={currentChatId}
        onSettingsClick={() => setIsSettingsOpen(true)}
        collapsed={sidebarCollapsed}
        onToggleSidebar={toggleSidebar}
      />

      {/* 侧边栏拖拽调宽条：收起时隐藏 */}
      {!sidebarCollapsed && (
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
      )}

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

      {/* 收起后浮动展开按钮：玻璃质感，左侧边缘居中 */}
      {sidebarCollapsed && (
        <button
          onClick={toggleSidebar}
          style={{
            position: "absolute",
            left: 8,
            top: "50%",
            transform: "translateY(-50%)",
            width: 32,
            height: 32,
            borderRadius: "50%",
            border: "1px solid var(--border-primary)",
            background: "color-mix(in srgb, var(--bg-level-2) 80%, transparent)",
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
            boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            color: "var(--text-level-3)",
            zIndex: 30,
            transition: "all 0.2s ease",
            animation: "fadeInRight 0.3s ease-out",
            padding: 0,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--bg-level-2)";
            e.currentTarget.style.color = "var(--color-primary)";
            e.currentTarget.style.transform = "translateY(-50%) scale(1.1)";
            e.currentTarget.style.boxShadow = "0 4px 16px rgba(0,0,0,0.12)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "color-mix(in srgb, var(--bg-level-2) 80%, transparent)";
            e.currentTarget.style.color = "var(--text-level-3)";
            e.currentTarget.style.transform = "translateY(-50%) scale(1)";
            e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.08)";
          }}
          title="展开侧边栏"
        >
          <PanelLeftOpen size={16} />
        </button>
      )}
    </div>
  );
}