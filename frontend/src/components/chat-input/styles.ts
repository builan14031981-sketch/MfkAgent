import type { CSSProperties } from "react";

/** 统一 Toolbar Pill 控件外观：28px 高、12px 字、medium、px-2.5、同背景同箭头 */
export const pillStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "6px",
  height: "28px",
  padding: "0 10px",
  borderRadius: "var(--radius-full)",
  border: "1px solid var(--border-primary)",
  background: "var(--bg-level-3)",
  cursor: "pointer",
  fontSize: "12px",
  fontWeight: 500,
  color: "var(--text-level-2)",
  whiteSpace: "nowrap",
  transition: "all var(--transition-fast)",
  flexShrink: 0,
  outline: "none",
};

export const chevronStyle: CSSProperties = {
  width: "12px",
  height: "12px",
  color: "var(--text-level-4)",
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
