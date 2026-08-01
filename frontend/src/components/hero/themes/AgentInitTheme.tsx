"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const MODULES = [
  { name: "agent.core", ms: "12ms" },
  { name: "memory.embed", ms: "8ms" },
  { name: "neural.link", ms: "3ms" },
  { name: "personality.map", ms: "5ms" },
];

/** Agent Init — Agent 初始化清单 + 进度条（微动画） */
export function AgentInitTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      style={{
        width: "100%",
        maxWidth: "560px",
        margin: "0 auto",
        textAlign: "left",
        fontFamily: "var(--font-geist-mono), ui-monospace, 'Courier New', monospace",
      }}
    >
      {/* 模块清单 */}
      <div style={{ marginBottom: 14 }}>
        {MODULES.map((mod, i) => (
          <motion.div
            key={mod.name}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, delay: 0.15 + i * 0.12 }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "3px 0",
              fontSize: 12,
              color: "var(--text-level-2)",
            }}
          >
            <span style={{ color: "var(--text-level-4)" }}>[{String(i + 1).padStart(2, "0")}]</span>
            <span style={{ color: "var(--text-level-3)" }}>{mod.name}</span>
            <span style={{ marginLeft: "auto", color: "#34d399" }}>✓ {mod.ms}</span>
          </motion.div>
        ))}
      </div>

      {/* 进度条 */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-level-4)", marginBottom: 5 }}>
          <span>initializing agent</span>
          <span>100%</span>
        </div>
        <div style={{ height: 6, borderRadius: 999, background: "var(--bg-level-4)", overflow: "hidden" }}>
          <div
            style={{
              height: "100%",
              borderRadius: 999,
              background: "linear-gradient(90deg, #34d399, var(--color-primary))",
              animation: animated ? "progressFill 0.9s ease 0.7s forwards" : undefined,
              width: animated ? 0 : "100%",
            }}
          />
        </div>
      </div>

      {/* 标题 */}
      <motion.h1
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.55 }}
        style={{
          margin: 0,
          fontSize: 40,
          fontWeight: 800,
          letterSpacing: "-0.01em",
          color: "var(--text-level-1)",
          background: "linear-gradient(90deg, #34d399, var(--color-primary))",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}
      >
        {title}
      </motion.h1>
      {welcome && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 1 }}
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
