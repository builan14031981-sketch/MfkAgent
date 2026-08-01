"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const PAPER = "#F5F0E8";
const INK = "#2C2C2C";
const TEA = "#8B6F47";
const MOSS = "#6B7B3A";

/** Theme: Wabi-Sabi — 侘寂：宣纸肌理 + 大量留白 + 手绘分割线，静默克制 */
export function WabiSabiTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        padding: "44px 34px",
        background: PAPER,
        backgroundImage: "radial-gradient(rgba(139,111,71,0.05) 1px, transparent 1px)",
        backgroundSize: "5px 5px",
        borderRadius: 2,
        fontFamily: "var(--font-geist-sans), 'Source Han Serif', 'Noto Serif JP', serif",
        textAlign: "center",
        color: INK,
      }}
    >
      <div style={{ fontSize: 40, fontWeight: 600, letterSpacing: "0.12em", color: INK, lineHeight: 1.3 }}>{title}</div>

      {/* 毛笔笔触分割线（SVG 曲线） */}
      <svg width="120" height="10" viewBox="0 0 120 10" style={{ margin: "18px auto 0", display: "block" }}>
        <path d="M0 6 C 30 2, 60 9, 120 4" fill="none" stroke={TEA} strokeWidth="2" strokeLinecap="round" />
      </svg>

      {welcome && <div style={{ fontSize: 17, marginTop: 16, color: TEA, letterSpacing: "0.08em" }}>{welcome}</div>}
      {subtext && <div style={{ fontSize: 13, marginTop: 10, color: MOSS, lineHeight: 1.9 }}>{subtext}</div>}

      {/* 不对称留白印章 */}
      {animated && (
        <div style={{ marginTop: 22, display: "flex", justifyContent: "center" }}>
          <span style={{ padding: "4px 10px", border: `1.5px solid ${MOSS}`, color: MOSS, fontSize: 11, letterSpacing: "0.2em", borderRadius: 2, opacity: 0.75 }}>
            Mfk
          </span>
        </div>
      )}
    </motion.div>
  );
}
