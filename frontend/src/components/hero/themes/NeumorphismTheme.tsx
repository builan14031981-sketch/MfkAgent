"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const BASE = "#E0E5EC";
const SHADOW_DARK = "rgba(163,177,198,0.7)";
const SHADOW_LIGHT = "rgba(255,255,255,0.9)";

/** Theme: Neumorphism — 同色系明暗挤压，凸起标题 + 凹陷输入，极简材质感 */
export function NeumorphismTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  const raised = {
    background: BASE,
    borderRadius: 18,
    boxShadow: `9px 9px 18px ${SHADOW_DARK}, -9px -9px 18px ${SHADOW_LIGHT}`,
  };
  const sunken = {
    background: BASE,
    borderRadius: 12,
    boxShadow: `inset 5px 5px 10px ${SHADOW_DARK}, inset -5px -5px 10px ${SHADOW_LIGHT}`,
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
        padding: "28px",
        background: BASE,
        borderRadius: 26,
        fontFamily: "var(--font-geist-sans), 'Montserrat', sans-serif",
        textAlign: "center",
        color: "#5a6478",
      }}
    >
      <div style={{ ...raised, padding: "24px 26px" }}>
        <div style={{ fontSize: 40, fontWeight: 700, letterSpacing: "0.01em" }}>{title}</div>
        {welcome && <div style={{ fontSize: 16, marginTop: 10, color: "#7a849c", fontWeight: 500 }}>{welcome}</div>}
      </div>

      {subtext && (
        <div style={{ ...sunken, marginTop: 18, padding: "12px 16px", fontSize: 13, lineHeight: 1.7, textAlign: "left" }}>{subtext}</div>
      )}

      {/* 内凹开关（凸起圆球） */}
      {animated && (
        <div style={{ marginTop: 18, display: "flex", justifyContent: "center" }}>
          <div style={{ ...sunken, width: 76, height: 36, borderRadius: 999, position: "relative", display: "flex", alignItems: "center", padding: 0 }}>
            <span
              style={{
                position: "absolute",
                left: 4,
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: BASE,
                boxShadow: `4px 4px 8px ${SHADOW_DARK}, -4px -4px 8px ${SHADOW_LIGHT}`,
                animation: animated ? "glowPulse 2s ease-in-out infinite" : undefined,
              }}
            />
          </div>
        </div>
      )}
    </motion.div>
  );
}
