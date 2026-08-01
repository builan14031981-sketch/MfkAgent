"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const BLUE = "#B3E5FC";
const PEACH = "#FFCCBC";
const MINT = "#B2DFDB";

/** Theme: Claymorphism — 黏土质感，大圆角 + 内外双层阴影 + 马卡龙色 */
export function ClaymorphismTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  const clay = (bg: string) => ({
    background: bg,
    borderRadius: 24,
    boxShadow:
      "8px 8px 16px rgba(163,177,198,0.5), -8px -8px 16px rgba(255,255,255,0.9), inset 2px 2px 4px rgba(255,255,255,0.8)",
  });

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        padding: "26px",
        background: "linear-gradient(145deg, #fff7e8, #ffe3d1)",
        borderRadius: 30,
        fontFamily: "var(--font-geist-sans), 'Nunito', sans-serif",
        textAlign: "center",
      }}
    >
      <div style={{ ...clay(MINT), padding: "22px 24px" }}>
        <div style={{ fontSize: 40, fontWeight: 800, color: "#4a7c6f", letterSpacing: "0.01em" }}>{title}</div>
        {welcome && <div style={{ fontSize: 17, marginTop: 10, color: "#5d9c8c", fontWeight: 600 }}>{welcome}</div>}
        {subtext && <div style={{ fontSize: 13, marginTop: 6, color: "#7fb3a5" }}>{subtext}</div>}
      </div>

      <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 18 }}>
        {[PEACH, BLUE, MINT].map((c, i) => (
          <div
            key={i}
            style={{
              ...clay(c),
              width: 74,
              height: 74,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 24,
              color: "rgba(0,0,0,0.35)",
              animation: animated ? `heroParticleFloat ${3 + i * 0.4}s ease-in-out infinite` : undefined,
              animationDelay: `${i * 0.6}s`,
            }}
          >
            {["♥", "✦", "●"][i]}
          </div>
        ))}
      </div>
    </motion.div>
  );
}
