"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const DOTS = [0, 1, 2];

/** Future OS — 未来操作系统：渐变背景 + 玻璃卡片 + 发光标题 + 状态点（轻量） */
export function FutureOsTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      style={{
        width: "100%",
        maxWidth: "620px",
        margin: "0 auto",
        textAlign: "center",
        fontFamily: "var(--font-family)",
        borderRadius: 20,
        padding: "34px 26px",
        background:
          "radial-gradient(120% 120% at 20% 0%, rgba(99, 102, 241, 0.5), transparent 55%)," +
          "radial-gradient(120% 120% at 85% 100%, rgba(168, 85, 247, 0.4), transparent 55%)," +
          "linear-gradient(180deg, #101226, #0b0d1a)",
        border: "1px solid rgba(129, 140, 248, 0.25)",
        boxShadow: "0 20px 60px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255,255,255,0.08)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 顶部状态点 */}
      <div style={{ display: "flex", justifyContent: "center", gap: 8, marginBottom: 22 }}>
        {DOTS.map((i) => (
          <span
            key={i}
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: i === 0 ? "#34d399" : i === 1 ? "#818cf8" : "#f472b6",
              animation: animated ? `glowPulse ${2.2 + i * 0.6}s ease ${i * 0.3}s infinite` : undefined,
            }}
          />
        ))}
      </div>

      {/* 标题（玻璃拟态内） */}
      <motion.h1
        initial={{ opacity: 0, letterSpacing: "0.25em" }}
        animate={{ opacity: 1, letterSpacing: "0.02em" }}
        transition={{ duration: 0.9, delay: 0.25 }}
        style={{
          margin: 0,
          fontSize: 46,
          fontWeight: 800,
          color: "#fff",
          textShadow: "0 0 30px rgba(129, 140, 248, 0.6), 0 2px 12px rgba(0, 0, 0, 0.4)",
        }}
      >
        {title}
      </motion.h1>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.7 }}
        style={{
          margin: "18px auto 0",
          width: 240,
          height: 34,
          borderRadius: 999,
          background: "rgba(255, 255, 255, 0.08)",
          border: "1px solid rgba(255, 255, 255, 0.15)",
          backdropFilter: "blur(12px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          fontSize: 12,
          color: "rgba(255, 255, 255, 0.85)",
        }}
      >
        {welcome ? (
          <>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#34d399" }} />
            {welcome}
          </>
        ) : null}
      </motion.div>

      {subtext && (
        <p style={{ margin: "10px 0 0 0", fontSize: 11, color: "rgba(255, 255, 255, 0.5)" }}>{subtext}</p>
      )}

      {/* 底部系统行 */}
      {animated && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 1.1 }}
          style={{ marginTop: 20, fontSize: 10, color: "rgba(255, 255, 255, 0.35)", letterSpacing: "0.2em", textTransform: "uppercase", fontFamily: "var(--font-geist-mono), ui-monospace, monospace" }}
        >
          os.v2.5.1 · uptime ∞ · kernel mfk-core
        </motion.div>
      )}
    </motion.div>
  );
}
