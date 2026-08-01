"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const GREEN = "#2ECC71";
const RED = "#FF6B6B";
const BLUE = "#54A0FF";
const YELLOW = "#FECA57";

/** Theme: Pixel RPG — 16-bit 游戏开场，像素字 + 棋盘格 + 色块精灵 */
export function PixelRpgTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  const pixelFont: React.CSSProperties = {
    fontFamily: "var(--font-geist-mono), 'Press Start 2P', monospace",
    textShadow: `3px 3px 0 rgba(0,0,0,0.6)`,
    letterSpacing: "0.08em",
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        padding: "24px 28px 28px",
        borderRadius: 8,
        background: "#1a1f2e",
        backgroundImage:
          "linear-gradient(rgba(84,160,255,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(84,160,255,0.06) 1px, transparent 1px)",
        backgroundSize: "14px 14px",
        border: `4px solid ${GREEN}`,
        boxShadow: `8px 8px 0 rgba(0,0,0,0.45)`,
        imageRendering: "pixelated",
        textAlign: "center",
      }}
    >
      {/* 像素精灵排（固定确定性排列） */}
      <div style={{ display: "flex", gap: 8, justifyContent: "center", marginBottom: 14 }}>
        {[GREEN, RED, BLUE, YELLOW].map((c, i) => (
          <span
            key={i}
            style={{
              width: 14,
              height: 14,
              background: c,
              display: "inline-block",
              boxShadow: "2px 2px 0 rgba(0,0,0,0.5)",
              animation: animated ? "heroParticleFloat 3s ease-in-out infinite" : undefined,
              animationDelay: `${i * 0.4}s`,
            }}
          />
        ))}
      </div>

      <div style={{ fontSize: 40, fontWeight: 800, color: YELLOW, ...pixelFont }}>
        {title}
      </div>

      {welcome && (
        <div style={{ fontSize: 16, color: GREEN, marginTop: 10, ...pixelFont }}>{welcome}</div>
      )}
      {subtext && (
        <div style={{ fontSize: 13, color: BLUE, marginTop: 6, ...pixelFont }}>{subtext}</div>
      )}

      {/* 像素 HP 条 */}
      <div style={{ marginTop: 16, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
        <span style={{ fontSize: 12, color: RED, ...pixelFont }}>HP</span>
        <div style={{ width: 160, height: 12, border: `3px solid ${RED}`, background: "#000", padding: 1 }}>
          <div style={{ height: "100%", background: RED, animation: animated ? "progressFill 1.2s ease-out forwards" : undefined }} />
        </div>
      </div>

      {animated && (
        <div style={{ fontSize: 12, color: "#fff", marginTop: 12, ...pixelFont }}>
          {"> PRESS START"}
          <span style={{ display: "inline-block", width: 10, height: 14, background: "#fff", marginLeft: 6, animation: "heroCursor 1s steps(1) infinite", verticalAlign: "text-bottom" }} />
        </div>
      )}
    </motion.div>
  );
}
