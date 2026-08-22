"use client";

import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { PanelLeftOpen } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { CommandPalette } from "./CommandPalette";
import { SettingsPanel } from "./panels/SettingsPanel";
import { DockPanel } from "./panels/DockPanel";
import { useDockStore, hydrateDockUI, DOCK_MIN, DOCK_MAX, DOCK_DEFAULT } from "@/lib/dockStore";
import { useTabStore } from "@/lib/tabStore";
import { ChatTabBar } from "./ChatTabBar";
import { useChat } from "@/hooks/useChat";
import { useProjects } from "@/hooks/useProjects";

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
// 2026-08-14：右侧面板（终端/产出物标签式）宽度实时落库键
const DOCK_WIDTH_STORAGE_KEY = "mfk_dock_width_css";

function clampWidth(w: number, min: number, max: number): number {
  return Math.min(Math.max(w, min), max);
}

export function AppLayout({ children }: AppLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // 挂载后读回收起态（不放在 useState 初始化器里，避免 SSR hydration mismatch）
  useEffect(() => {
    try {
      setSidebarCollapsed(window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1");
    } catch { /* localStorage 不可用时保持展开 */ }
    // 2026-08-14：恢复右侧面板 UI 状态（width / isOpen / isFullscreen / activeTab / tabs）
    hydrateDockUI();
  }, []);

  // 全局 Cmd+K / Ctrl+K 打开命令面板
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // 面板：Ctrl+` 打开/关闭"终端"标签
  const toggleTab = useDockStore((s) => s.toggleTab);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "`") {
        e.preventDefault();
        toggleTab("terminal");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [toggleTab]);

  // ── Ctrl+滚轮 内容缩放（V4 2026-08-19）──
  // 对标豆包：框架固定，只缩放内容（侧边栏内容、消息列表、输入框）。
  // 通过 CSS 变量 --app-content-zoom 控制，globals.css 中给指定容器加 zoom。
  // 步长5%，范围0.75~1.5，持久化到 localStorage。
  const ZOOM_KEY = "mfk_app_zoom";
  const ZOOM_MIN = 0.75;
  const ZOOM_MAX = 1.5;
  const ZOOM_STEP = 0.05;

  useEffect(() => {
    // 恢复上次缩放比例
    let zoom = 1;
    try {
      const saved = parseFloat(window.localStorage.getItem(ZOOM_KEY) || "");
      if (Number.isFinite(saved)) zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, saved));
    } catch { /* localStorage 不可用则用默认 1 */ }
    document.documentElement.style.setProperty("--app-content-zoom", String(zoom));

    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
      zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, +(zoom + delta).toFixed(2)));
      document.documentElement.style.setProperty("--app-content-zoom", String(zoom));
      try { window.localStorage.setItem(ZOOM_KEY, String(zoom)); } catch { /* noop */ }
    };
    // passive:false 才能 preventDefault 阻止浏览器默认的 Ctrl+滚轮缩放
    window.addEventListener("wheel", onWheel, { passive: false });
    return () => window.removeEventListener("wheel", onWheel);
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

  // 终端 cwd：取当前会话关联项目的本地路径，无则回退 null（后端用主目录）
  const { chats, createChat } = useChat();
  const { projects } = useProjects(1, 100);

  // ── 多会话标签栏状态与快捷键 ──
  const activeChatId = useTabStore((s) => s.activeChatId);
  const closeTab = useTabStore((s) => s.closeTab);
  const cycleTab = useTabStore((s) => s.cycleTab);
  const cleanStaleTabs = useTabStore((s) => s.cleanStaleTabs);

  // 自动激活当前路由会话
  useEffect(() => {
    if (currentChatId != null) {
      useTabStore.getState().setActiveTab(currentChatId);
    }
  }, [currentChatId]);

  // 会话列表加载后自动清理已删除的脏标签
  useEffect(() => {
    if (chats.length > 0) {
      cleanStaleTabs(new Set(chats.map((c) => c.id)));
    }
  }, [chats, cleanStaleTabs]);

  // 全局新建会话（继承当前活跃会话的 Agent 与项目上下文）
  const handleGlobalNewChat = useCallback(async () => {
    let agentId = "general";
    let projectId: number | null = null;
    if (currentChatId != null) {
      const currentChat = chats.find((c) => c.id === currentChatId);
      if (currentChat) {
        agentId = currentChat.agent_id || "general";
        projectId = currentChat.project_id ?? null;
      }
    }
    try {
      const chat = await createChat(
        agentId,
        "新对话",
        projectId,
        null,
        [],
        "build",
        "standard"
      );
      router.push(`/chat/${chat.id}`);
    } catch (err) {
      console.error("Failed to create new chat tab:", err);
      router.push("/");
    }
  }, [currentChatId, chats, createChat, router]);

  // 全局标签快捷键（Ctrl+T/N 新建，Ctrl+W 关闭，Ctrl+Tab 切换，Alt+1~9 直达）
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const isInput =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);

      // 1. 新建标签：Ctrl+T / Ctrl+N (Mac: Cmd+T / Cmd+N)
      if (
        (e.ctrlKey || e.metaKey) &&
        (e.key === "t" || e.key === "T" || e.key === "n" || e.key === "N")
      ) {
        e.preventDefault();
        handleGlobalNewChat();
        return;
      }

      // 2. 关闭当前标签：Ctrl+W / Cmd+W / Alt+W
      if (
        ((e.ctrlKey || e.metaKey) && (e.key === "w" || e.key === "W")) ||
        (e.altKey && (e.key === "w" || e.key === "W"))
      ) {
        if (!isInput && activeChatId != null) {
          e.preventDefault();
          const nextId = closeTab(activeChatId);
          if (nextId != null) {
            router.push(`/chat/${nextId}`);
          } else {
            router.push("/");
          }
          return;
        }
      }

      // 3. 标签左右轮转：Ctrl+Tab / Ctrl+Shift+Tab
      if ((e.ctrlKey || e.metaKey) && e.key === "Tab") {
        e.preventDefault();
        const direction = e.shiftKey ? -1 : 1;
        const nextId = cycleTab(direction);
        if (nextId != null) {
          router.push(`/chat/${nextId}`);
        }
        return;
      }

      // 4. 数字快捷键直达对应标签：Alt+1 ~ Alt+9
      if (e.altKey && e.key >= "1" && e.key <= "9") {
        const index = parseInt(e.key, 10) - 1;
        const currentTabs = useTabStore.getState().tabs;
        if (index < currentTabs.length) {
          e.preventDefault();
          router.push(`/chat/${currentTabs[index].chatId}`);
          return;
        }
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [activeChatId, closeTab, cycleTab, handleGlobalNewChat, router]);
  const terminalCwd = useMemo(() => {
    if (currentChatId == null) return null;
    const chat = chats.find((c) => c.id === currentChatId);
    if (!chat?.project_id) return null;
    const project = projects.find((p) => p.id === chat.project_id);
    return project?.path ?? null;
  }, [currentChatId, chats, projects]);

  // 当前绑定的项目路径（供浏览器面板判断默认页）
  const currentProjectPath = terminalCwd;


  // ── 侧边栏宽度 ──
  const layoutRef = useRef<HTMLDivElement>(null);
  const sidebarDragRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT);

  // 初始从 localStorage 恢复宽度
  useEffect(() => {
    try {
      const saved = localStorage.getItem(SIDEBAR_STORAGE_KEY);
      if (saved != null) {
        const n = Number(saved);
        if (Number.isFinite(n)) {
          // eslint-disable-next-line react-hooks/set-state-in-effect
          setSidebarWidth(clampWidth(n, SIDEBAR_MIN, SIDEBAR_MAX));
        }
      }
    } catch {
      /* localStorage 不可用则忽略 */
    }
  }, []);

  // 同步 sidebar state → DOM CSS 变量
  useEffect(() => {
    layoutRef.current?.style.setProperty("--sidebar-width", `${sidebarCollapsed ? 0 : sidebarWidth}px`);
  }, [sidebarWidth, sidebarCollapsed]);

  // ── 右侧面板宽度（终端/产出物共用）──
  const dockWidth = useDockStore((s) => s.width);
  const isDockOpen = useDockStore((s) => s.isOpen);
  const isDockFullscreen = useDockStore((s) => s.isFullscreen);
  const setDockWidth = useDockStore((s) => s.setWidth);

  // 右侧面板拖拽调宽（拖拽条在面板左侧：向右拖变窄）
  const dockDragRef = useRef<{ startX: number; startWidth: number; lastX: number } | null>(null);
  const startDockResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startWidth = useDockStore.getState().width;
    dockDragRef.current = { startX: e.clientX, startWidth, lastX: e.clientX };

    document.body.style.userSelect = "none";
    document.body.style.cursor = "ew-resize";

    const onMove = (ev: MouseEvent) => {
      const drag = dockDragRef.current;
      if (!drag) return;
      drag.lastX = ev.clientX;
      // 向右拖 → 面板变窄（delta 负值）；向左拖 → 面板变宽（delta 正值）
      const delta = drag.startX - ev.clientX;
      const next = clampWidth(drag.startWidth + delta, DOCK_MIN, DOCK_MAX);
      layoutRef.current?.style.setProperty("--dock-width", `${next}px`);
    };

    const onUp = () => {
      const drag = dockDragRef.current;
      dockDragRef.current = null;
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      if (drag) {
        // 取拖拽过程中的最终宽度，避免回弹到起始宽度
        const final = clampWidth(drag.startWidth + (drag.startX - drag.lastX), DOCK_MIN, DOCK_MAX);
        setDockWidth(final);
        try {
          localStorage.setItem(DOCK_WIDTH_STORAGE_KEY, final.toString());
        } catch { /* 忽略 */ }
      }
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, [setDockWidth]);

  // 侧边栏拖拽调宽
  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const startWidth = Number(
      getComputedStyle(layoutRef.current!).getPropertyValue("--sidebar-width").replace("px", "") || sidebarWidth
    );
    sidebarDragRef.current = { startX: e.clientX, startWidth };

    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";

    const onMove = (ev: MouseEvent) => {
      const drag = sidebarDragRef.current;
      if (!drag) return;
      const delta = ev.clientX - drag.startX;
      const next = clampWidth(drag.startWidth + delta, SIDEBAR_MIN, SIDEBAR_MAX);
      layoutRef.current?.style.setProperty("--sidebar-width", `${next}px`);
    };

    const onUp = () => {
      const drag = sidebarDragRef.current;
      sidebarDragRef.current = null;
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      if (drag) {
        const final = clampWidth(drag.startWidth, SIDEBAR_MIN, SIDEBAR_MAX);
        setSidebarWidth(final);
        try {
          localStorage.setItem(SIDEBAR_STORAGE_KEY, final.toString());
        } catch { /* 忽略 */ }
      }
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, [sidebarWidth]);

  const resetWidth = useCallback(() => {
    setSidebarWidth(SIDEBAR_DEFAULT);
    layoutRef.current?.style.setProperty("--sidebar-width", `${SIDEBAR_DEFAULT}px`);
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, SIDEBAR_DEFAULT.toString());
    } catch { /* 忽略 */ }
  }, []);

  return (
    <>
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        onSelectChat={(chatId) => router.push(`/chat/${chatId}`)}
        onSelectProject={(projectId) => router.push(`/projects/${projectId}/files`)}
        onNewChat={() => router.push("/")}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />
      <div
        ref={layoutRef}
      style={{
        display: "flex",
        height: "100vh",
        background: "var(--bg-level-2)",
        position: "relative",
        "--sidebar-width": `${sidebarCollapsed ? 0 : sidebarWidth}px`,
        "--dock-width": isDockOpen && !isDockFullscreen ? `${dockWidth}px` : "0px",
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
        {/* 多标签栏（浏览器式多会话切换） */}
        <ChatTabBar onNewChat={handleGlobalNewChat} />
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0, overflow: "hidden" }}>
          {children}
        </div>
      </main>

      {/* 右侧面板拖拽调宽条：面板打开且非全屏时显示（位于面板左侧） */}
      {isDockOpen && !isDockFullscreen && (
        <div
          onMouseDown={startDockResize}
          style={{
            width: 6,
            height: "100vh",
            cursor: "ew-resize",
            flexShrink: 0,
            touchAction: "none",
            userSelect: "none",
            background: "transparent",
            zIndex: 20,
          }}
        />
      )}

      {/* 右侧面板（浏览器式标签：终端 / 产出物 / 浏览器） */}
      <DockPanel cwd={terminalCwd} chatId={currentChatId} projectPath={currentProjectPath} />

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
      )}</div>
    </>
  );
}





