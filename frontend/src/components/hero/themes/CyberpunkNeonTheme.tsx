"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const BG = "#0D0208";
const PINK = "#FF00FF";
const CYAN = "#00F0FF";
const PURPLE = "#7B2FFF";

/** Theme: Cyberpunk Neon — 霓虹发光文字 + 暗角 + 扫描线，夜之城气质 */
export function CyberpunkNeonTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  const glow = (c: string) => `${c} 0 0 12px, ${c} 0 0 28px, ${c} 0 0 48px`;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        padding: "30px 28px",
        borderRadius: 4,
        background: BG,
        backgroundImage: "radial-gradient(circle at 20% 0%, rgba(123,47,255,0.25), transparent 60%), radial-gradient(circle at 85% 100%, rgba(0,240,255,0.2), transparent 55%)",
        border: `1px solid ${PURPLE}`,
        boxShadow: `0 0 24px rgba(255,0,255,0.15), inset 0 0 60px rgba(0,0,0,0.6)`,
        position: "relative",
        overflow: "hidden",
        fontFamily: "var(--font-geist-mono), 'Share Tech Mono', monospace",
        textAlign: "center",
      }}
    >
      {/* 顶部霓虹线 */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, transparent, ${PINK}, ${CYAN}, transparent)`, opacity: 0.8 }} />

      <div style={{ fontSize: 42, fontWeight: 800, letterSpacing: "0.1em", color: "#fff", textShadow: glow(PINK), textTransform: "uppercase" }}>
        {title}
      </div>

      {welcome && (
        <div style={{ fontSize: 17, marginTop: 14, color: CYAN, textShadow: glow(CYAN) }}>{welcome}</div>
      )}
      {subtext && (
        <div style={{ fontSize: 13, marginTop: 8, color: "#9c8fd0", textShadow: "0 0 8px rgba(123,47,255,0.8)", opacity: 0.9 }}>
          {subtext}
        </div>
      )}

      {/* 能量槽进度条 */}
      <div style={{ marginTop: 18, height: 8, border: `1px solid ${CYAN}`, boxShadow: `0 0 8px ${CYAN}`, padding: 2 }}>
        <div style={{ height: "100%", background: `linear-gradient(90deg, ${PINK}, ${CYAN})`, boxShadow: `0 0 10px ${CYAN}`, animation: animated ? "progressFill 1.4s ease-out forwards" : undefined }} />
      </div>

      {animated && (
        <div style={{ marginTop: 14, display: "flex", justifyContent: "center", gap: 4, color: CYAN, fontSize: 13, textShadow: glow(CYAN) }}>
          <span>SYS.LINK</span>
          <span style={{ display: "inline-block", width: 10, height: 15, background: CYAN, boxShadow: `0 0 8px ${CYAN}`, animation: "heroCursor 1s steps(1) infinite" }} />
        </div>
      )}
    </motion.div>
  );
}
