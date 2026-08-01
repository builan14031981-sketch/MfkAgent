"use client";

import { motion } from "framer-motion";
import { Star, GitFork, Bug, Heart, Code2 } from "lucide-react";
import type { HeroThemeProps } from "@/themes/types";

const BADGES = [
  { icon: Star, text: "1.2k stars", color: "#f59e0b" },
  { icon: GitFork, text: "342 forks", color: "#38bdf8" },
  { icon: Bug, text: "12 open issues", color: "#f87171" },
];

/** Open Source — 开源徽章 + 品牌标题（轻量） */
export function OpenSourceTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        textAlign: "center",
        fontFamily: "var(--font-family)",
      }}
    >
      {/* 开源徽章行 */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.15 }}
        style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap", marginBottom: 20 }}
      >
        {BADGES.map((badge) => (
          <span
            key={badge.text}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "4px 10px",
              borderRadius: 999,
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-2)",
              fontSize: 12,
              color: "var(--text-level-2)",
            }}
          >
            <badge.icon style={{ width: 13, height: 13, color: badge.color }} />
            {badge.text}
          </span>
        ))}
        <span style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          padding: "4px 10px",
          borderRadius: 999,
          border: "1px solid #6366f1",
          color: "#6366f1",
          background: "rgba(99, 102, 241, 0.08)",
          fontSize: 12,
        }}>
          <Code2 style={{ width: 13, height: 13 }} />
          MIT License
        </span>
      </motion.div>

      {/* 标题 */}
      <motion.h1
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.35 }}
        style={{
          margin: 0,
          fontSize: 46,
          fontWeight: 800,
          letterSpacing: "-0.02em",
          color: "var(--text-level-1)",
        }}
      >
        {title}
      </motion.h1>

      {welcome && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.7 }}
          style={{ margin: "12px 0 0 0", fontSize: 14, color: "var(--text-level-3)" }}
        >
          {welcome}
        </motion.p>
      )}
      {subtext && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.9 }}
          style={{ margin: "6px 0 0 0", fontSize: 12, color: "var(--text-level-4)" }}
        >
          {subtext}
        </motion.p>
      )}

      {/* 底部贡献者心形 */}
      {animated && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.7, 0.7, 0] }}
          transition={{ duration: 3, delay: 1.2 }}
          style={{ marginTop: 18, fontSize: 12, color: "var(--text-level-4)", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}
        >
          built by the community
          <Heart style={{ width: 12, height: 12, color: "#f43f5e", fill: "#f43f5e" }} />
        </motion.div>
      )}
    </motion.div>
  );
}
