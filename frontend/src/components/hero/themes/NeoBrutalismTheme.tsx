"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const YELLOW = "#FFE83C";
const BLACK = "#000";
const WHITE = "#fff";
const PINK = "#FF6EC7";

/** Theme: Neo-Brutalism — 粗黑边框 + 硬阴影 + 撞色，反精致直给 */
export function NeoBrutalismTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  const hardShadow = "6px 6px 0 rgba(0,0,0,1)";

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        padding: "28px",
        background: animated ? YELLOW : WHITE,
        border: `4px solid ${BLACK}`,
        boxShadow: hardShadow,
        fontFamily: "var(--font-geist-sans), 'Space Mono', monospace",
        textAlign: "left",
      }}
    >
      <div
        style={{
          fontSize: 44,
          fontWeight: 900,
          lineHeight: 1.05,
          color: BLACK,
          letterSpacing: "-0.02em",
          textTransform: "uppercase",
        }}
      >
        {title}
      </div>

      {welcome && (
        <div style={{ display: "inline-block", marginTop: 14, padding: "8px 14px", background: PINK, border: `3px solid ${BLACK}`, boxShadow: "4px 4px 0 rgba(0,0,0,1)", fontSize: 16, fontWeight: 700, color: BLACK }}>
          {welcome}
        </div>
      )}

      {subtext && (
        <div style={{ marginTop: 16, fontSize: 13, color: BLACK, borderLeft: `5px solid ${BLACK}`, paddingLeft: 10, lineHeight: 1.6 }}>
          {subtext}
        </div>
      )}

      {/* 装饰：裸露网格线 + 状态标签 */}
      <div style={{ marginTop: 20, display: "flex", gap: 8, flexWrap: "wrap" }}>
        {["AGENT v0.1", "UPTIME ∞", "NO FEAR"].map((tag) => (
          <span key={tag} style={{ padding: "4px 10px", background: BLACK, color: YELLOW, fontSize: 12, fontWeight: 700, border: "2px solid #000" }}>
            {tag}
          </span>
        ))}
      </div>
    </motion.div>
  );
}
