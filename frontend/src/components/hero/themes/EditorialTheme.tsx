"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const INK = "#111";
const RED = "#C62828";
const GRAY = "#666";

/** Theme: Editorial — 独立杂志排版：大衬线标题 + 留白 + 朱砂红引言 */
export function EditorialTheme({ title, welcome, subtext }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        padding: "36px 32px",
        background: "#fff",
        borderTop: `3px solid ${INK}`,
        borderBottom: `1px solid ${INK}`,
        fontFamily: "var(--font-geist-sans), 'Playfair Display', Georgia, serif",
        textAlign: "left",
        color: INK,
      }}
    >
      {/* 页眉式刊头 */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, fontSize: 11, letterSpacing: "0.18em", color: GRAY, textTransform: "uppercase", borderBottom: "1px solid #ddd", paddingBottom: 8 }}>
        <span>MfkAgent</span>
        <span style={{ flex: 1 }} />
        <span>Vol.1 · AI</span>
      </div>

      <div style={{ fontSize: 42, fontWeight: 800, lineHeight: 1.12, marginTop: 18, letterSpacing: "-0.02em" }}>{title}</div>

      {welcome && (
        <blockquote
          style={{
            margin: "16px 0 0",
            paddingLeft: 14,
            borderLeft: `3px solid ${RED}`,
            fontStyle: "italic",
            fontSize: 17,
            color: "#333",
          }}
        >
          {welcome}
        </blockquote>
      )}

      {subtext && (
        <div style={{ marginTop: 12, fontSize: 14, color: GRAY, lineHeight: 1.8, fontFamily: "var(--font-geist-sans), 'Source Sans Pro', sans-serif" }}>
          {subtext}
        </div>
      )}

      {/* 页脚式元信息 */}
      <div style={{ display: "flex", gap: 16, marginTop: 20, fontSize: 11, color: RED, letterSpacing: "0.12em", textTransform: "uppercase" }}>
        <span>● 思考型助手</span>
        <span>⟶ 继续阅读</span>
      </div>
    </motion.div>
  );
}
