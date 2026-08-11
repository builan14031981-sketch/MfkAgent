import type { CSSProperties } from "react";

/** 极简 Ghost Pill 控件外观（默认态）：无边框无阴影、透明背景、中低对比度浅灰文字，低调不抢眼 */
export const ghostPillStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "6px",
  height: "28px",
  // 2026-08-11：压紧胶囊内边距，缩小胶囊间视觉空白
  padding: "0 8px",
  borderRadius: "var(--radius-full)",
  border: "1px solid transparent",
  background: "transparent",
  cursor: "pointer",
  fontSize: "12px",
  fontWeight: 400,
  color: "var(--text-level-4)",
  whiteSpace: "nowrap",
  transition: "all 0.2s ease-in-out",
  flexShrink: 0,
  outline: "none",
};

/** Ghost Pill 悬停态：浅灰微背景 + 文字高亮 + 轻阴影 */
export const ghostPillHoverBackground = "var(--bg-level-3)";
export const ghostPillHoverColor = "var(--text-level-2)";
export const ghostPillHoverShadow = "var(--shadow-sm)";

export const chevronStyle: CSSProperties = {
  width: "12px",
  height: "12px",
  color: "inherit",
  opacity: 0.6,
  marginLeft: "4px",
  flexShrink: 0,
};

/** 下拉面板：统一向上弹出（bottom-full mb-1.5）、最高层级 z-[100]、紧凑高密度 */
export const popoverStyle: CSSProperties = {
  position: "absolute",
  bottom: "calc(100% + 6px)",
  left: 0,
  display: "flex",
  flexDirection: "column",
  gap: "2px",
  minWidth: "140px",
  padding: "4px",
  borderRadius: "var(--radius-xl)",
  background: "var(--bg-level-2)",
  border: "1px solid var(--border-primary)",
  boxShadow: "var(--shadow-lg)",
  zIndex: 100,
  animation: "panelOpen 0.15s ease forwards",
  transformOrigin: "bottom left",
};

/** 下拉选项：text-xs、font-medium、px-2.5 py-1.5、leading-tight */
export const popoverItemStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  width: "100%",
  padding: "6px 10px",
  border: "none",
  background: "transparent",
  cursor: "pointer",
  fontSize: "12px",
  fontWeight: 500,
  lineHeight: 1.25,
  whiteSpace: "nowrap",
  color: "var(--text-level-2)",
  borderRadius: "var(--radius-sm)",
  textAlign: "left",
  outline: "none",
};

/** 胶囊按钮展开态 / hover 时的背景色 */
export const pillActiveBackground = "var(--bg-level-4)";
export const pillActiveColor = "var(--color-primary)";

/** 下拉项 hover 背景 */
export const itemHoverBackground = "var(--bg-level-3)";

/** portal 下拉容器（固定定位，随按钮位置出现） */
export interface PortalDropdownStyleOptions {
  bottom: number;
  left: number;
  width?: number;
  maxHeight?: number;
}

export function portalDropdownStyle({ bottom, left, width, maxHeight }: PortalDropdownStyleOptions): CSSProperties {
  return {
    position: "fixed",
    bottom: bottom + 8,
    left,
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    minWidth: "160px",
    width,
    maxHeight,
    overflowY: maxHeight ? "auto" : undefined,
    padding: "6px",
    borderRadius: "var(--radius-xl)",
    background: "var(--bg-level-2)",
    border: "1px solid var(--border-secondary)",
    boxShadow: "var(--shadow-lg)",
    zIndex: 9999,
  };
}
