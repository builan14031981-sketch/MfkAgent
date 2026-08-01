"use client";

import { motion } from "framer-motion";
import type { CSSProperties } from "react";
import type { HeroThemeProps } from "@/themes/types";

/* Windows 95 / 98 原生配色 */
const DESKTOP_TEAL = "#008080";
const WINDOW_GRAY = "#C0C0C0";
const TITLEBAR_DARK = "#000080";
const TITLEBAR_LIGHT = "#1084D0";
const WHITE = "#FFFFFF";
const BLACK = "#000000";
const SHADOW_GRAY = "#808080";

/* Win9x bevel 3D 边框：上/左亮、下/右暗 */
const bevelOut: CSSProperties = {
  borderTop: "2px solid #FFFFFF",
  borderLeft: "2px solid #FFFFFF",
  borderBottom: "2px solid #404040",
  borderRight: "2px solid #404040",
};

const bevelIn: CSSProperties = {
  borderTop: "2px solid #404040",
  borderLeft: "2px solid #404040",
  borderBottom: "2px solid #FFFFFF",
  borderRight: "2px solid #FFFFFF",
};

const sysFont: CSSProperties = {
  fontFamily: "var(--font-ibm-plex-sans), 'MS Sans Serif', 'Tahoma', 'Segoe UI', sans-serif",
  fontSize: 13,
};

/** Theme: Win9x Desktop — Windows 95/98 桌面窗口 + 任务栏 + 开始按钮 */
export function Win9xDesktopTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        background: DESKTOP_TEAL,
        padding: "14px",
        boxShadow: "0 0 0 3px #006060, 8px 8px 0 rgba(0,0,0,0.35)",
        textAlign: "left",
      }}
    >
      {/* 主窗口 */}
      <div style={{ background: WINDOW_GRAY, ...bevelOut }}>
        {/* 标题栏 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 5px",
            background: `linear-gradient(90deg, ${TITLEBAR_DARK} 0%, ${TITLEBAR_LIGHT} 100%)`,
            color: WHITE,
            fontWeight: 700,
          }}
        >
          <span style={{ ...sysFont, fontSize: 13, flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            MfkAgent - {title}
          </span>
          {/* 最小化 / 最大化 / 关闭 */}
          {["─", "□", "✕"].map((glyph, i) => (
            <span
              key={i}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 18,
                height: 17,
                background: WINDOW_GRAY,
                color: BLACK,
                fontSize: 11,
                fontWeight: 400,
                ...bevelOut,
              }}
            >
              {glyph}
            </span>
          ))}
        </div>

        {/* 窗口内容区（内凹 bevel） */}
        <div style={{ margin: "6px", padding: "18px 22px 20px", background: "#FFFFFF", ...bevelIn, textAlign: "center" }}>
          <div
            style={{
              ...sysFont,
              fontSize: 34,
              fontWeight: 700,
              letterSpacing: "-0.01em",
              color: BLACK,
              lineHeight: 1.2,
            }}
          >
            {title}
          </div>

          {welcome && (
            <div style={{ ...sysFont, fontSize: 16, marginTop: 10, color: BLACK }}>{welcome}</div>
          )}
          {subtext && (
            <div style={{ ...sysFont, fontSize: 12, marginTop: 6, color: SHADOW_GRAY }}>{subtext}</div>
          )}

          {/* 仿「确定/取消」按钮（凸起 bevel，按下凹陷） */}
          {animated && (
            <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 14 }}>
              <button
                style={{
                  ...sysFont,
                  fontSize: 12,
                  padding: "4px 18px",
                  background: WINDOW_GRAY,
                  color: BLACK,
                  cursor: "pointer",
                  ...bevelOut,
                }}
              >
                确定
              </button>
              <button
                style={{
                  ...sysFont,
                  fontSize: 12,
                  padding: "4px 18px",
                  background: WINDOW_GRAY,
                  color: BLACK,
                  cursor: "pointer",
                  ...bevelOut,
                }}
              >
                取消
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 任务栏 + 开始按钮 */}
      <div
        style={{
          marginTop: 8,
          display: "flex",
          alignItems: "center",
          gap: 8,
          background: WINDOW_GRAY,
          padding: "3px 5px",
          ...bevelOut,
        }}
      >
        <button
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            background: WINDOW_GRAY,
            color: BLACK,
            cursor: "pointer",
            fontWeight: 700,
            padding: "2px 10px 2px 4px",
            ...bevelOut,
          }}
        >
          <span style={{ width: 16, height: 16, background: `linear-gradient(135deg, ${TITLEBAR_LIGHT}, ${TITLEBAR_DARK})`, display: "inline-block" }} />
          <span style={{ ...sysFont, fontSize: 13 }}>开始</span>
        </button>

        {/* 已启动程序占位 */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, flex: 1, minWidth: 0 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              background: "#D4D0C8",
              color: BLACK,
              fontSize: 12,
              padding: "2px 10px",
              maxWidth: "60%",
              ...bevelIn,
            }}
          >
            <span style={{ width: 14, height: 14, background: "#00D400", display: "inline-block", boxShadow: "1px 1px 0 rgba(0,0,0,0.4)" }} />
            <span style={{ ...sysFont, fontSize: 12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              MfkAgent
            </span>
          </div>
        </div>

        {/* 时钟（静态占位，避免 SSR/客户端时间不一致） */}
        <div style={{ ...sysFont, fontSize: 12, color: BLACK, borderLeft: "1px solid #808080", paddingLeft: 8 }}>
          09:41
        </div>
      </div>
    </motion.div>
  );
}
