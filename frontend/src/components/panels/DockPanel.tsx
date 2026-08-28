"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { TerminalSquare, Package, Globe, Plus, X, Maximize2, Minimize2, Check } from "lucide-react";
import { useDockStore, DOCK_TAB_ORDER, type DockTabId } from "@/lib/dockStore";
import { useTranslation } from "@/hooks/useTranslation";
import { TerminalPanel } from "./TerminalPanel";
import { ArtifactsPanel } from "./ArtifactsPanel";
import { BrowserPanel } from "./BrowserPanel";

interface DockPanelProps {
  cwd?: string | null;
  /** 当前会话 id（供浏览器标签按 chat 隔离会话） */
  chatId?: number | null;
  /** 当前绑定的项目路径（供浏览器面板判断默认页） */
  projectPath?: string | null;
}

/**
 * 右侧面板（浏览器式标签页，样式参数与顶部聊天标签栏 .chrome-tab 完全对齐）。
 * - 默认打开终端；标签栏右侧「+」按钮可开启 产出物 / 浏览器
 * - 已打开标签带 X 可单独关闭；关掉最后一个标签则面板整体收起
 * - 收起/展开由 dockStore 的 close/open 管理：收起不销毁标签组合，展开恢复原样
 */
export function DockPanel({ cwd, chatId, projectPath }: DockPanelProps) {
  const { t } = useTranslation();
  const isOpen = useDockStore((s) => s.isOpen);
  const isFullscreen = useDockStore((s) => s.isFullscreen);
  const activeTab = useDockStore((s) => s.activeTab);
  const tabs = useDockStore((s) => s.tabs);
  const setActiveTab = useDockStore((s) => s.setActiveTab);
  const openTab = useDockStore((s) => s.openTab);
  const closeTab = useDockStore((s) => s.closeTab);
  const toggleFullscreen = useDockStore((s) => s.toggleFullscreen);
  const close = useDockStore((s) => s.close);

  // 「+」小菜单：打开状态 + 定位
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });
  const addBtnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const openTabs = DOCK_TAB_ORDER.filter((id) => tabs[id]);

  // 面板收起时同步收起菜单，避免再展开时残留弹出
  useEffect(() => {
    if (!isOpen) setMenuOpen(false);
  }, [isOpen]);

  // 点击菜单外部关闭
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (
        addBtnRef.current?.contains(e.target as Node) ||
        menuRef.current?.contains(e.target as Node)
      ) {
        return;
      }
      setMenuOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpen]);

  const toggleMenu = () => {
    const rect = addBtnRef.current?.getBoundingClientRect();
    setMenuPos(rect ? { top: rect.bottom + 4, left: rect.left } : { top: 0, left: 0 });
    setMenuOpen((v) => !v);
  };

  // 菜单项：未打开 → 打开并激活；已打开 → 直接切换过去
  const pickTab = (id: DockTabId) => {
    setMenuOpen(false);
    if (!tabs[id]) {
      openTab(id);
    } else {
      setActiveTab(id);
    }
  };

  const tabLabel = (id: DockTabId) =>
    id === "terminal" ? t("terminal.title") : id === "browser" ? t("browser.title") : t("artifact.title");
  const tabIcon = (id: DockTabId, active: boolean) =>
    id === "terminal" ? (
      <TerminalSquare style={{ width: 13, height: 13, color: active ? "var(--color-primary)" : "var(--text-level-4)" }} />
    ) : id === "browser" ? (
      <Globe style={{ width: 13, height: 13, color: active ? "var(--color-primary)" : "var(--text-level-4)" }} />
    ) : (
      <Package style={{ width: 13, height: 13, color: active ? "var(--color-primary)" : "var(--text-level-4)" }} />
    );

  if (!isOpen) return null;

  return (
    <>
      <style>{`
        /* 与顶部聊天标签栏 .chrome-tab 完全同参；类名加 dock- 前缀避免互相干扰 */
        .dock-tab {
          position: relative;
          display: flex;
          align-items: center;
          gap: 6px;
          height: 32px;
          padding: 0 10px 0 12px;
          font-size: 12px;
          cursor: pointer;
          user-select: none;
          white-space: nowrap;
          margin-top: 4px;
          border-top-left-radius: 8px;
          border-top-right-radius: 8px;
          transition: background 0.15s ease, color 0.15s ease;
          box-sizing: border-box;
        }
        .dock-tab--active {
          background: var(--bg-level-2);
          color: var(--text-level-1);
          font-weight: 500;
          z-index: 2;
          border-top: 1px solid var(--border-primary);
          border-left: 1px solid var(--border-primary);
          border-right: 1px solid var(--border-primary);
          border-bottom: none;
        }
        .dock-tab--inactive {
          background: transparent;
          color: var(--text-level-3);
          border: 1px solid transparent;
          border-bottom: none;
        }
        .dock-tab--inactive:hover {
          background: color-mix(in srgb, var(--text-level-1) 5%, transparent);
          color: var(--text-level-2);
          border-radius: 6px 6px 0 0;
        }
        .dock-tab-divider {
          position: absolute;
          right: -1px;
          top: 50%;
          transform: translateY(-50%);
          width: 1px;
          height: 14px;
          background: color-mix(in srgb, var(--border-primary) 70%, transparent);
          pointer-events: none;
          transition: opacity 0.15s ease;
        }
        .dock-tab:hover .dock-tab-divider,
        .dock-tab--active .dock-tab-divider {
          opacity: 0;
        }
        .dock-tab-close {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 16px;
          height: 16px;
          border-radius: 4px;
          border: none;
          background: transparent;
          cursor: pointer;
          color: inherit;
          padding: 0;
          flex-shrink: 0;
          opacity: 0;
          transition: opacity 0.12s ease, background 0.12s ease;
        }
        .dock-tab:hover .dock-tab-close {
          opacity: 0.6;
        }
        .dock-tab--active .dock-tab-close {
          opacity: 0.75;
        }
        .dock-tab-close:hover {
          opacity: 1 !important;
          background: color-mix(in srgb, var(--text-level-1) 12%, transparent);
        }
        .dock-tab-new {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 26px;
          height: 26px;
          border-radius: 6px;
          border: none;
          background: transparent;
          cursor: pointer;
          color: var(--text-level-3);
          flex-shrink: 0;
          margin-top: 4px;
          transition: all 0.15s ease;
        }
        .dock-tab-new:hover {
          background: color-mix(in srgb, var(--text-level-1) 6%, transparent);
          color: var(--text-level-1);
        }
      `}</style>

      <div
        style={{
          position: isFullscreen ? "fixed" : "relative",
          ...(isFullscreen
            ? { inset: 0, width: "100vw", height: "100vh", zIndex: 100 }
            : { width: "var(--dock-width)", flexShrink: 0 }),
          display: "flex",
          flexDirection: "column",
          borderLeft: "1px solid var(--border-primary)",
          background: "var(--bg-level-2)",
          overflow: "hidden",
          animation: "slideInFromRight 0.2s ease-out",
        }}
      >
        {/* 标签栏：高度/间距/圆角与顶部聊天标签栏一致 */}
        <div
          style={{
            position: "relative",
            display: "flex",
            alignItems: "flex-end",
            height: 36,
            flexShrink: 0,
            background: "var(--bg-level-3)",
            borderBottom: "1px solid var(--border-primary)",
            padding: "0 6px",
          }}
        >
          {openTabs.map((id, idx) => {
            const active = id === activeTab;
            const nextIsActive = idx + 1 < openTabs.length ? openTabs[idx + 1] === activeTab : false;
            return (
              <div
                key={id}
                role="tab"
                aria-selected={active}
                onClick={() => setActiveTab(id)}
                title={tabLabel(id)}
                className={`dock-tab ${active ? "dock-tab--active" : "dock-tab--inactive"}`}
              >
                {tabIcon(id, active)}
                <span>{tabLabel(id)}</span>
                {/* 每个标签自带 X：关闭该标签 */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    closeTab(id);
                  }}
                  title={t("common.close")}
                  className="dock-tab-close"
                >
                  <X style={{ width: 11, height: 11 }} />
                </button>
                {!active && !nextIsActive && <div className="dock-tab-divider" />}
              </div>
            );
          })}

          {/* + 加号：弹出小菜单打开 终端 / 产出物 / 浏览器 */}
          <button
            ref={addBtnRef}
            onClick={toggleMenu}
            title="打开 终端 / 产出物 / 浏览器 面板"
            className="dock-tab-new"
          >
            <Plus style={{ width: 15, height: 15 }} />
          </button>

          {/* 面板级操作：全屏 / 收起整个面板 */}
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 2 }}>
            <button
              onClick={toggleFullscreen}
              title={isFullscreen ? t("common.exitFullscreen") : t("common.fullscreen")}
              className="dock-tab-new"
            >
              {isFullscreen ? (
                <Minimize2 style={{ width: 13, height: 13 }} />
              ) : (
                <Maximize2 style={{ width: 13, height: 13 }} />
              )}
            </button>
            <button
              onClick={close}
              title={t("common.close")}
              className="dock-tab-new"
            >
              <X style={{ width: 13, height: 13 }} />
            </button>
          </div>
        </div>

        {/* 内容区：激活标签渲染，非激活标签保持挂载（终端后台运行） */}
        <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div
            style={{
              flex: 1,
              minHeight: 0,
              display: activeTab === "terminal" ? "flex" : "none",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            <TerminalPanel cwd={cwd} />
          </div>
          <div
            style={{
              flex: 1,
              minHeight: 0,
              display: activeTab === "artifacts" ? "flex" : "none",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            <ArtifactsPanel />
          </div>
          <div
            style={{
              flex: 1,
              minHeight: 0,
              display: activeTab === "browser" ? "flex" : "none",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            <BrowserPanel chatId={chatId} projectPath={projectPath} />
          </div>
        </div>
      </div>

      {/* + 小菜单：Portal 挂 body，fixed 定位不受面板裁剪/缩放影响 */}
      {menuOpen &&
        createPortal(
          <div
            ref={menuRef}
            role="menu"
            style={{
              position: "fixed",
              top: menuPos.top,
              left: menuPos.left,
              minWidth: 156,
              padding: 4,
              background: "var(--bg-level-2)",
              border: "1px solid var(--border-primary)",
              borderRadius: "var(--radius-md)",
              boxShadow: "0 8px 24px rgba(0,0,0,0.16)",
              zIndex: 200,
            }}
          >
            {DOCK_TAB_ORDER.map((id) => {
              const opened = tabs[id];
              const active = id === activeTab;
              return (
                <button
                  key={id}
                  role="menuitem"
                  onClick={() => pickTab(id)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    width: "100%",
                    padding: "7px 10px",
                    border: "none",
                    background: "transparent",
                    borderRadius: "var(--radius-sm)",
                    fontSize: 12,
                    color: "var(--text-level-2)",
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "var(--bg-level-3)";
                    e.currentTarget.style.color = "var(--text-level-1)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "var(--text-level-2)";
                  }}
                >
                  {tabIcon(id, active)}
                  <span style={{ flex: 1 }}>{tabLabel(id)}</span>
                  {active ? (
                    <Check style={{ width: 13, height: 13, color: "var(--color-primary)" }} />
                  ) : opened ? (
                    <Check style={{ width: 13, height: 13, color: "var(--text-level-4)" }} />
                  ) : null}
                </button>
              );
            })}
          </div>,
          document.body
        )}
    </>
  );
}