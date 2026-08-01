"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const ADD = "+ feat: awaken MfkAgent AI";
const STAT = "+ 6 files changed, 1284 insertions(+), 42 deletions(-)";
const DEL = "- legacy: sleep mode";

const GREEN = "#22c55e";
const RED = "#ef4444";
const GRAY = "#9ca3af";

/** Git Commit — diff/patch 视觉 + 分支徽章（轻量，区别于 Git Developer 完整动画） */
export function GitCommitTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        textAlign: "left",
        fontFamily: "var(--font-geist-mono), ui-monospace, 'Courier New', monospace",
      }}
    >
      {/* diff 块（左右两栏装饰） */}
      <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
        <div style={{ flex: 1, fontSize: 12, lineHeight: 2 }}>
          <motion.div
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.35, delay: 0.15 }}
            style={{ color: RED, background: "rgba(239, 68, 68, 0.08)", borderRadius: 6, padding: "2px 8px", marginBottom: 4 }}
          >
            {DEL}
          </motion.div>
          <motion.div
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.35, delay: 0.45 }}
            style={{ color: GREEN, background: "rgba(34, 197, 94, 0.08)", borderRadius: 6, padding: "2px 8px", marginBottom: 4 }}
          >
            {ADD}
          </motion.div>
          <motion.div
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.35, delay: 0.75 }}
            style={{ color: GRAY, padding: "2px 8px", fontSize: 11 }}
          >
            {STAT}
          </motion.div>
        </div>

        {/* 中央标题 + 分支徽章 */}
        <div style={{ flex: 1.2, minWidth: 0 }}>
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.1 }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "3px 10px",
              borderRadius: 999,
              border: `1px solid ${GREEN}`,
              color: GREEN,
              fontSize: 11,
              marginBottom: 12,
            }}
          >
            <span style={{ width: 8, height: 8, borderRadius: 2, background: GREEN }} />
            feature/awaken
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, delay: 0.3 }}
            style={{
              margin: 0,
              fontSize: 38,
              fontWeight: 800,
              letterSpacing: "-0.02em",
              color: "var(--text-level-1)",
              textShadow: "0 4px 24px rgba(34, 197, 94, 0.25)",
            }}
          >
            {title}
          </motion.h1>
          {welcome && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4, delay: 0.7 }}
              style={{ margin: "10px 0 0 0", fontSize: 13, color: "var(--text-level-3)" }}
            >
              {welcome}
            </motion.p>
          )}
          {animated && (
            <div style={{ marginTop: 10, fontSize: 13, color: GREEN, display: "flex", gap: 6, alignItems: "center" }}>
              <span>$ git status</span>
              <span style={{ display: "inline-block", width: 9, height: 14, background: GREEN, verticalAlign: "text-bottom", animation: "heroCursor 1s steps(1) infinite" }} />
            </div>
          )}
        </div>
      </div>
      {subtext && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 1.1 }}
          style={{ marginTop: 14, fontSize: 11, color: "var(--text-level-4)", fontFamily: "var(--font-family)" }}
        >
          {subtext}
        </motion.div>
      )}
    </motion.div>
  );
}
