"use client";

import { TerminalSquare, Package, Globe } from "lucide-react";
import { useDockStore, DOCK_TAB_ORDER, type DockTabId } from "@/lib/dockStore";
import { useTranslation } from "@/hooks/useTranslation";

/** 图标条宽度（px） */
const BAR_WIDTH = 36;

/**
 * Dock Activity Bar（右侧窄图标条，参考 VS Code Activity Bar 布局）。
 * - 永远渲染：Dock 收起时也保留入口，保证小白用户对「终端/产出物/浏览器」的发现性
 * - 点击逻辑（关键边界）：
 *   - Dock 收起（isOpen=false）→ openTab(id)：打开面板并激活该标签
 *   - Dock 展开 → toggleTab(id)：关→开+激活 / 开且非当前→切 / 开且当前→收起
 *   - 不能全程用 toggleTab：收起态下 tabs 仍保留上次组合，toggleTab 会误走
 *     closeTab 分支导致「点了没反应」或错误切标签
 * - 激活高亮必须带 isOpen，否则收起时会误显示「图标高亮但面板没开」的撕裂状态
 * - 全屏（isFullscreen）时 DockPanel 以 fixed 覆盖全屏，本条隐藏
 */
export function DockActivityBar() {
  const { t } = useTranslation();
  const isOpen = useDockStore((s) => s.isOpen);
  const isFullscreen = useDockStore((s) => s.isFullscreen);
  const activeTab = useDockStore((s) => s.activeTab);
  const tabs = useDockStore((s) => s.tabs);
  const openTab = useDockStore((s) => s.openTab);
  const toggleTab = useDockStore((s) => s.toggleTab);

  const label = (id: DockTabId) =>
    id === "terminal" ? t("terminal.title") : id === "browser" ? t("browser.title") : t("artifact.title");

  const icon = (id: DockTabId, active: boolean) =>
    id === "terminal" ? (
      <TerminalSquare style={{ width: 16, height: 16, color: active ? "var(--color-primary)" : "var(--text-level-4)" }} />
    ) : id === "browser" ? (
      <Globe style={{ width: 16, height: 16, color: active ? "var(--color-primary)" : "var(--text-level-4)" }} />
    ) : (
      <Package style={{ width: 16, height: 16, color: active ? "var(--color-primary)" : "var(--text-level-4)" }} />
    );

  if (isFullscreen) return null;

  return (
    <div
      style={{
        width: BAR_WIDTH,
        flexShrink: 0,
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 6,
        paddingTop: 8,
        background: "transparent",
        borderLeft: "1px solid var(--border-primary)",
        boxSizing: "border-box",
      }}
    >
      {DOCK_TAB_ORDER.map((id) => {
        const active = isOpen && tabs[id] && activeTab === id;
        return (
          <button
            key={id}
            onClick={() => {
              if (!isOpen) {
                openTab(id);
              } else {
                toggleTab(id);
              }
            }}
            title={label(id)}
            style={{
              position: "relative",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 28,
              height: 28,
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              transition: "background 0.15s ease",
              outline: "none",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "color-mix(in srgb, var(--text-level-1) 6%, transparent)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            {active && (
              <span
                style={{
                  position: "absolute",
                  left: -4,
                  top: "50%",
                  transform: "translateY(-50%)",
                  width: 2,
                  height: 16,
                  borderRadius: 1,
                  background: "var(--color-primary)",
                }}
              />
            )}
            {icon(id, active)}
          </button>
        );
      })}
    </div>
  );
}
