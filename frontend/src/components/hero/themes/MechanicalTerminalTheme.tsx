"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";
import { TypewriterLine } from "../shared";

const AMBER = "#ffb454";
const DARK = "#1c1712";
const CREAM = "#efe6d5";
const KEYS = ["M", "F", "K", "A", "G", "E", "N", "T"];

/** Mechanical Terminal — 机械打字机：打字标题 + 键帽敲击动画（轻量） */
export function MechanicalTerminalTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        textAlign: "center",
        fontFamily: "var(--font-geist-mono), ui-monospace, 'Courier New', monospace",
      }}
    >
      {/* 打字机面板 */}
      <div style={{
        borderRadius: 16,
        background: `linear-gradient(180deg, ${DARK}, #241d15)`,
        border: "1px solid #3a2f22",
        boxShadow: "0 10px 32px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255,255,255,0.08)",
        padding: "26px 20px 18px",
      }}>
        <h1 style={{
          margin: 0,
          fontSize: 42,
          fontWeight: 700,
          letterSpacing: "0.06em",
          color: CREAM,
          textShadow: `0 0 14px ${AMBER}, 0 0 40px rgba(255, 180, 84, 0.35)`,
          minHeight: "1.2em",
        }}>
          <TypewriterLine text={title.toUpperCase()} speed={55} color={CREAM} block={false} />
        </h1>

        {welcome && (
          <p style={{ margin: "12px 0 0 0", fontSize: 13, color: AMBER, minHeight: "1.5em" }}>
            <TypewriterLine text={welcome} delay={title.length * 55 + 300} speed={16} color={AMBER} block={false} />
          </p>
        )}

        {/* 键帽行：循环敲击（不同 delay 错开） */}
        <div style={{ display: "flex", gap: 6, justifyContent: "center", marginTop: 22, flexWrap: "wrap" }}>
          {KEYS.map((key, i) => (
            <span
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 30,
                height: 30,
                borderRadius: 6,
                background: `linear-gradient(180deg, ${CREAM}, #cfc4ac)`,
                color: DARK,
                fontSize: 13,
                fontWeight: 600,
                boxShadow: "0 2px 0 rgba(0, 0, 0, 0.45)",
                animation: animated ? `keyTap 1.6s ease ${0.5 + i * 0.18}s infinite` : undefined,
              }}
            >
              {key}
            </span>
          ))}
        </div>
      </div>

      {subtext && (
        <p style={{ margin: "10px 0 0 0", fontSize: 11, color: "var(--text-level-4)" }}>{subtext}</p>
      )}
    </motion.div>
  );
}
