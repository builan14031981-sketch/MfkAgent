"use client";

import { TerminalSquare, Package, X, Maximize2, Minimize2 } from "lucide-react";
import { useDockStore, DOCK_TAB_ORDER, type DockTabId } from "@/lib/dockStore";
import { useTranslation } from "@/hooks/useTranslation";
import { TerminalPanel } from "./TerminalPanel";
import { ArtifactsPanel } from "./ArtifactsPanel";

interface DockPanelProps {
  cwd?: string | null;
}

/**
 * 右侧面板（浏览器式标签页）。
 * - 单一面板，顶部标签栏：终端 / 产出物，选中哪个就显示哪个内容（互斥不并排）
 * - 每个标签自带 X：关闭该标签；全部关闭则整个面板收起
 * - 非激活标签保持挂载（终端后台运行），仅激活标签执行尺寸同步
 */
export function DockPanel({ cwd }: DockPanelProps) {
  const { t } = useTranslation();
  const isOpen = useDockStore((s) => s.isOpen);
  const isFullscreen = useDockStore((s) => s.isFullscreen);
  const activeTab = useDockStore((s) => s.activeTab);
  const tabs = useDockStore((s) => s.tabs);
  const setActiveTab = useDockStore((s) => s.setActiveTab);
  const closeTab = useDockStore((s) => s.closeTab);
  const toggleFullscreen = useDockStore((s) => s.toggleFullscreen);
  const close = useDockStore((s) => s.close);

  if (!isOpen) return null;

  const openTabs = DOCK_TAB_ORDER.filter((id) => tabs[id]);

  const tabLabel = (id: DockTabId) => (id === "terminal" ? t("terminal.title") : t("artifact.title"));
  const tabIcon = (id: DockTabId, active: boolean) =>
    id === "terminal" ? (
      <TerminalSquare style={{ width: 13, height: 13, color: active ? "var(--color-primary)" : "var(--text-level-4)" }} />
    ) : (
      <Package style={{ width: 13, height: 13, color: active ? "var(--color-primary)" : "var(--text-level-4)" }} />
    );

  return (
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
      {/* 浏览器式标签栏 */}
      <div
        style={{
          display: "flex",
          alignItems: "stretch",
          flexShrink: 0,
          minHeight: 34,
          background: "var(--bg-level-3)",
          borderBottom: "1px solid var(--border-primary)",
        }}
      >
        {openTabs.map((id) => {
          const active = id === activeTab;
          return (
            <div
              key={id}
              role="tab"
              aria-selected={active}
              onClick={() => setActiveTab(id)}
              title={tabLabel(id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "0 6px 0 10px",
                cursor: "pointer",
                userSelect: "none",
                whiteSpace: "nowrap",
                background: active ? "var(--bg-level-2)" : "transparent",
                color: active ? "var(--text-level-1)" : "var(--text-level-3)",
                borderTop: `2px solid ${active ? "var(--color-primary)" : "transparent"}`,
                borderRight: "1px solid var(--border-primary)",
              }}
            >
              {tabIcon(id, active)}
              <span style={{ fontSize: 12, fontWeight: active ? 600 : 500 }}>{tabLabel(id)}</span>
              {/* 每个标签自带 X：关闭该标签 */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  closeTab(id);
                }}
                title={t("common.close")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 16,
                  height: 16,
                  padding: 0,
                  border: "none",
                  borderRadius: "var(--radius-sm)",
                  background: "transparent",
                  cursor: "pointer",
                  color: "var(--text-level-4)",
                  transition: "background 0.15s, color 0.15s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--bg-level-4)";
                  e.currentTarget.style.color = "var(--color-error)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "var(--text-level-4)";
                }}
              >
                <X style={{ width: 11, height: 11 }} />
              </button>
            </div>
          );
        })}

        {/* 面板级操作：全屏 / 关闭整个面板 */}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 2, padding: "0 6px" }}>
          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? t("common.exitFullscreen") : t("common.fullscreen")}
            style={panelBtnStyle}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-4)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
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
            style={panelBtnStyle}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-4)";
              e.currentTarget.style.color = "var(--color-error)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--text-level-3)";
            }}
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
      </div>
    </div>
  );
}

const panelBtnStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: 24,
  height: 22,
  borderRadius: "var(--radius-sm)",
  border: "none",
  background: "transparent",
  cursor: "pointer",
  color: "var(--text-level-3)",
  padding: 0,
  outline: "none",
  transition: "background 0.15s, color 0.15s",
};
