"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

/** Apple Minimal — 极简大标题 + 微渐显（无装饰，跟随亮暗主题） */
export function AppleMinimalTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
      style={{
        width: "100%",
        maxWidth: "720px",
        margin: "0 auto",
        textAlign: "center",
        padding: "16px 0",
        fontFamily: "var(--font-family)",
      }}
    >
      <motion.h1
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut", delay: 0.15 }}
        style={{
          margin: 0,
          fontSize: 64,
          fontWeight: 700,
          letterSpacing: "-0.03em",
          color: "var(--text-level-1)",
        }}
      >
        {title}
      </motion.h1>

      {welcome && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.7 }}
          style={{
            margin: "14px 0 0 0",
            fontSize: 17,
            color: "var(--text-level-3)",
            letterSpacing: "0.01em",
          }}
        >
          {welcome}
        </motion.p>
      )}
      {subtext && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 1 }}
          style={{ margin: "8px 0 0 0", fontSize: 13, color: "var(--text-level-4)" }}
        >
          {subtext}
        </motion.p>
      )}
      {animated && (
        <motion.div
          initial={{ opacity: 0, scaleX: 0 }}
          animate={{ opacity: 1, scaleX: 1 }}
          transition={{ duration: 0.6, delay: 1.3 }}
          style={{
            width: 48,
            height: 3,
            margin: "22px auto 0",
            borderRadius: 999,
            background: "var(--color-primary)",
          }}
        />
      )}
    </motion.div>
  );
}
