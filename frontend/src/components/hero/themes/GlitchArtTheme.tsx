"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const CYAN = "#00F0FF";
const MAGENTA = "#FF00FF";

/** Theme: Glitch Art — RGB 三色分离 + 水平撕裂抖动，数字创伤美学 */
export function GlitchArtTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        padding: "30px 28px",
        background: "#0a0a0a",
        borderRadius: 2,
        border: "1px solid rgba(255,255,255,0.15)",
        fontFamily: "var(--font-geist-mono), 'Courier New', monospace",
        textAlign: "center",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* RGB 分离标题 */}
      <div style={{ position: "relative", display: "inline-block" }}>
        <div style={{ fontSize: 44, fontWeight: 800, color: "#fff", letterSpacing: "0.04em", position: "relative", zIndex: 2 }}>
          {title}
        </div>
        {animated && (
          <>
            <div style={{ position: "absolute", top: 0, left: 0, right: 0, fontSize: 44, fontWeight: 800, color: CYAN, zIndex: 1, opacity: 0.7, clipPath: "inset(0 0 55% 0)", animation: "heroGlitchShift 3.2s steps(2) infinite" }}>
              {title}
            </div>
            <div style={{ position: "absolute", top: 0, left: 0, right: 0, fontSize: 44, fontWeight: 800, color: MAGENTA, zIndex: 0, opacity: 0.7, clipPath: "inset(55% 0 0 0)", animation: "heroGlitchShift 3.2s steps(2) infinite reverse" }}>
              {title}
            </div>
          </>
        )}
      </div>

      {welcome && (
        <div style={{ fontSize: 16, marginTop: 14, color: "#e0e0e0", animation: animated ? "heroGlitchShift 4s steps(3) infinite" : undefined }}>{welcome}</div>
      )}
      {subtext && (
        <div style={{ fontSize: 13, marginTop: 6, color: "#888", animation: animated ? "heroGlitchShift 5s steps(2) infinite reverse" : undefined }}>{subtext}</div>
      )}

      {/* 撕裂条纹装饰 */}
      <div style={{ display: "flex", justifyContent: "center", gap: 10, marginTop: 18 }}>
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            style={{
              width: 36,
              height: 8,
              background: i % 2 === 0 ? CYAN : MAGENTA,
              opacity: 0.5,
              clipPath: `polygon(0 25%, 100% 0, 96% 75%, 4% 100%)`,
              animation: animated ? `heroGlitchShift ${2 + i * 0.4}s steps(3) infinite` : undefined,
              animationDelay: `${i * 0.15}s`,
            }}
          />
        ))}
      </div>

      {animated && (
        <div style={{ marginTop: 14, fontSize: 12, color: "#aaa" }}>
          <span>0xFF{'{SIGNAL_CORRUPTED}'}</span>
          <span style={{ display: "inline-block", width: 9, height: 14, background: "#fff", marginLeft: 8, verticalAlign: "text-bottom", animation: "heroCursor 0.8s steps(1) infinite" }} />
        </div>
      )}
    </motion.div>
  );
}
