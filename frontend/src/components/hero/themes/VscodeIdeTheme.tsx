"use client";

import { motion } from "framer-motion";
import { FileCode2, ChevronRight } from "lucide-react";
import type { HeroThemeProps } from "@/themes/types";

const TREE = ["src/", "  agent/core.ts", "  agent/ui.tsx", "  index.ts", "package.json"];

/** VS Code / IDE — 标签栏 + 文件树 + 状态栏（轻量，跟随亮暗主题） */
export function VscodeIdeTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        borderRadius: 10,
        border: "1px solid var(--border-primary)",
        background: "var(--bg-level-3)",
        boxShadow: "var(--shadow-md)",
        overflow: "hidden",
        fontFamily: "var(--font-geist-mono), ui-monospace, 'Courier New', monospace",
      }}
    >
      {/* 标签栏 */}
      <div style={{ display: "flex", alignItems: "center", padding: "6px 8px", borderBottom: "1px solid var(--border-primary)", background: "var(--bg-level-2)" }}>
        <span style={{
          display: "flex", alignItems: "center", gap: 6, padding: "3px 10px", borderRadius: "6px 6px 0 0",
          background: "var(--bg-level-3)", fontSize: 11, color: "var(--text-level-2)",
        }}>
          <FileCode2 style={{ width: 12, height: 12, color: "var(--color-primary)" }} />
          mfkagent.ts
        </span>
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 10, color: "var(--text-level-4)", paddingRight: 6 }}>agent — main</span>
      </div>

      {/* 主体：文件树 + 标题 */}
      <div style={{ display: "flex", minHeight: 150 }}>
        {/* 文件树 */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.15 }}
          style={{
            width: 150,
            flexShrink: 0,
            padding: "10px 8px",
            borderRight: "1px solid var(--border-primary)",
            fontSize: 11,
            lineHeight: 2,
            color: "var(--text-level-3)",
            whiteSpace: "pre",
          }}
        >
          {TREE.map((line, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 4, color: line.endsWith("/") ? "var(--text-level-2)" : "var(--text-level-3)", fontWeight: line.endsWith("/") ? 600 : 400 }}>
              {!line.endsWith("/") && <ChevronRight style={{ width: 10, height: 10, color: "var(--text-level-4)" }} />}
              {line}
            </div>
          ))}
        </motion.div>

        {/* 中央标题 */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "16px 12px", textAlign: "center" }}>
          <motion.h1
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            style={{
              margin: 0, fontSize: 36, fontWeight: 700, letterSpacing: "-0.02em",
              color: "var(--text-level-1)",
              background: "linear-gradient(90deg, var(--color-primary), #8b5cf6)",
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
              transition={{ duration: 0.4, delay: 0.7 }}
              style={{ margin: "8px 0 0 0", fontSize: 13, color: "var(--text-level-3)" }}
            >
              {welcome}
            </motion.p>
          )}
        </div>
      </div>

      {/* 状态栏 */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "5px 10px", background: "var(--color-primary)", color: "#fff", fontSize: 10.5 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#fff", animation: animated ? "glowPulse 2s ease infinite" : undefined }} />
          ready
        </span>
        <span style={{ opacity: 0.85 }}>AGENT:auto</span>
        <span style={{ flex: 1 }} />
        <span style={{ opacity: 0.85 }}>UTF-8</span>
        <span style={{ opacity: 0.85 }}>Ln 1, Col 1</span>
      </div>
      {subtext && (
        <div style={{ fontSize: 10.5, color: "var(--text-level-4)", padding: "3px 10px", textAlign: "right" }}>
          {subtext}
        </div>
      )}
    </motion.div>
  );
}
