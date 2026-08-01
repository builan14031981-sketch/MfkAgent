"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const RED = "#E81123";
const BLUE = "#00A4EF";
const GREEN = "#7FBA00";
const YELLOW = "#FFB900";
const PURPLE = "#8764B8";

const TILES = [
  { color: RED, label: "TITLE" },
  { color: BLUE, label: "AGENT" },
  { color: GREEN, label: "CORE" },
  { color: YELLOW, label: "SYNC" },
  { color: PURPLE, label: "LINK" },
];

/** Theme: Metro — Windows 8 磁贴，纯平面色块，信息密度高 */
export function MetroTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        padding: "26px 26px 30px",
        background: "#14161c",
        fontFamily: "var(--font-geist-sans), 'Segoe UI', sans-serif",
        textAlign: "left",
      }}
    >
      <div style={{ fontSize: 46, fontWeight: 700, color: "#fff", letterSpacing: "-0.01em", marginBottom: 18 }}>{title}</div>

      {welcome && <div style={{ fontSize: 17, color: YELLOW, fontWeight: 600 }}>{welcome}</div>}
      {subtext && <div style={{ fontSize: 13, color: "#9aa", marginTop: 6 }}>{subtext}</div>}

      {/* 磁贴网格 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginTop: 18 }}>
        {TILES.map((tile, i) => (
          <div
            key={tile.label}
            style={{
              background: tile.color,
              height: i % 2 === 0 ? 72 : 56,
              padding: 8,
              display: "flex",
              alignItems: "flex-end",
              fontSize: 13,
              fontWeight: 600,
              color: "#fff",
              animation: animated ? "glowPulse 3s ease-in-out infinite" : undefined,
              animationDelay: `${i * 0.3}s`,
            }}
          >
            {tile.label}
          </div>
        ))}
      </div>
    </motion.div>
  );
}
