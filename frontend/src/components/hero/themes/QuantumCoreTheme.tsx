"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const RINGS = [
  { size: 240, duration: 9, direction: 1, color: "rgba(192, 132, 252, 0.55)" },
  { size: 176, duration: 7, direction: -1, color: "rgba(129, 140, 248, 0.5)" },
  { size: 116, duration: 5, direction: 1, color: "rgba(232, 121, 249, 0.6)" },
];

/** Quantum Core — 量子光环旋转 + 中心标题（微动画） */
export function QuantumCoreTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
      style={{
        width: "100%",
        maxWidth: "620px",
        margin: "0 auto",
        textAlign: "center",
        position: "relative",
        padding: "10px 0",
        fontFamily: "var(--font-family)",
      }}
    >
      {/* 量子光环 */}
      <div style={{ position: "relative", width: 240, height: 240, margin: "0 auto 6px" }}>
        {RINGS.map((ring, i) => (
          <div
            key={i}
            style={{
              position: "absolute",
              top: (240 - ring.size) / 2,
              left: (240 - ring.size) / 2,
              width: ring.size,
              height: ring.size,
              borderRadius: "50%",
              border: `1px solid ${ring.color}`,
              boxShadow: `0 0 18px ${ring.color}, inset 0 0 18px ${ring.color}`,
              animation: animated ? `spinSlow ${ring.duration}s linear ${ring.direction > 0 ? "normal" : "reverse"} infinite` : undefined,
            }}
          />
        ))}
        {/* 轨道上的光子点 */}
        {animated && (
          <div style={{
            position: "absolute",
            top: 8,
            left: "50%",
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: "#e879f9",
            boxShadow: "0 0 12px #e879f9",
            animation: "spinSlow 5s linear infinite",
          }} />
        )}
        <div style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 13,
          color: "rgba(192, 132, 252, 0.8)",
          letterSpacing: "0.2em",
          textTransform: "uppercase",
          fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
        }}>
          Q-BIT 8
        </div>
      </div>

      <motion.h1
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.3 }}
        style={{
          margin: 0,
          fontSize: 44,
          fontWeight: 800,
          letterSpacing: "-0.01em",
          color: "#fff",
          background: "linear-gradient(120deg, #c4b5fd, #e879f9)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          textShadow: "0 0 40px rgba(192, 132, 252, 0.35)",
        }}
      >
        {title}
      </motion.h1>
      {welcome && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.6 }}
          style={{ margin: "10px 0 0 0", fontSize: 13, color: "var(--text-level-3)" }}
        >
          {welcome}
        </motion.p>
      )}
      {subtext && (
        <p style={{ margin: "4px 0 0 0", fontSize: 12, color: "var(--text-level-4)" }}>{subtext}</p>
      )}
    </motion.div>
  );
}
