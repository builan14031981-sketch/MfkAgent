"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const LAVENDER = "#B57EDC";
const CORAL = "#FF7EB3";
const MINT = "#7FCDCD";
const GOLD = "#D4AF37";

/** Theme: Vaporwave — 紫粉渐变天空 + 柱廊剪影 + 金色大字，怀旧未来 */
export function VaporwaveTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        padding: "30px 28px 36px",
        borderRadius: 10,
        background: `linear-gradient(180deg, #3d1d6e 0%, #8e4fb2 45%, ${CORAL} 80%, #ffd9a0 100%)`,
        position: "relative",
        overflow: "hidden",
        fontFamily: "var(--font-geist-sans), 'Playfair Display', serif",
        textAlign: "center",
        color: "#fff",
      }}
    >
      {/* 半透明太阳 */}
      <div style={{ position: "absolute", top: 18, right: 40, width: 64, height: 64, borderRadius: "50%", background: "rgba(255,220,180,0.25)", boxShadow: "0 0 40px rgba(255,180,200,0.5)" }} />

      {/* 柱廊剪影（确定性排列） */}
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, display: "flex", justifyContent: "center", gap: 18, opacity: 0.5 }}>
        {[1, 2, 3, 4, 5].map((w) => (
          <div key={w} style={{ width: 26, height: 90, background: "#241244", borderRadius: "2px 2px 0 0", clipPath: "polygon(0 0, 100% 0, 100% 100%, 0 100%)" }} />
        ))}
      </div>

      <div style={{ position: "relative", zIndex: 1 }}>
        <div style={{ fontSize: 40, fontWeight: 700, color: GOLD, textShadow: "0 2px 20px rgba(212,175,55,0.45)" }}>{title}</div>
        {welcome && <div style={{ fontSize: 18, marginTop: 12, color: "#fff", fontStyle: "italic" }}>{welcome}</div>}
        {subtext && <div style={{ fontSize: 13, marginTop: 8, color: MINT, fontFamily: "var(--font-geist-mono), monospace" }}>{subtext}</div>}

        {animated && (
          <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 16, opacity: 0.8 }}>
            {[CORAL, LAVENDER, MINT].map((c, i) => (
              <span key={i} style={{ width: 8, height: 8, borderRadius: "50%", background: c, animation: "heroParticleFloat 3s ease-in-out infinite", animationDelay: `${i * 0.5}s` }} />
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
