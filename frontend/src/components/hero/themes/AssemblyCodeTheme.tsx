"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const CODE = [
  "; mfk_awaken.asm",
  "section .text",
  "  mov   eax, 0x7",
  "  call  mfk_awaken",
  "  jmp   main_loop",
  "section .data",
  "  msg  db 'MfkAgent', 0",
];

const RED = "#f87171";
const GREEN = "#a3e635";
const BLUE = "#7dd3fc";

/** Assembly Code — 汇编代码装饰 + 等宽大标题（轻量） */
export function AssemblyCodeTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      style={{
        width: "100%",
        maxWidth: "680px",
        margin: "0 auto",
        display: "flex",
        alignItems: "center",
        gap: 28,
        fontFamily: "var(--font-geist-mono), ui-monospace, 'Courier New', monospace",
      }}
    >
      {/* 左侧：代码列装饰 */}
      <motion.pre
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        style={{
          margin: 0,
          fontSize: 11,
          lineHeight: 1.9,
          color: BLUE,
          background: "rgba(0, 0, 0, 0.25)",
          borderLeft: `3px solid ${RED}`,
          padding: "10px 14px",
          borderRadius: 6,
          flexShrink: 0,
          whiteSpace: "pre",
        }}
      >
        {CODE.join("\n")}
      </motion.pre>

      {/* 右侧：标题 */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <motion.h1
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.35 }}
          style={{
            margin: 0,
            fontSize: 40,
            fontWeight: 800,
            color: "var(--text-level-1)",
            fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
            textShadow: `3px 3px 0 ${RED}, 6px 6px 0 rgba(248, 113, 113, 0.25)`,
          }}
        >
          {title.toUpperCase()}
        </motion.h1>
        {welcome && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.8 }}
            style={{ margin: "12px 0 0 0", fontSize: 13, color: GREEN }}
          >
            {welcome}
          </motion.p>
        )}
        {subtext && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 1 }}
            style={{ margin: "4px 0 0 0", fontSize: 12, color: "var(--text-level-4)" }}
          >
            ; {subtext}
          </motion.p>
        )}
        {animated && (
          <div style={{ marginTop: 10, color: GREEN, fontSize: 13 }}>
            <span>0x0040:</span>
            <span style={{ display: "inline-block", width: 9, height: 14, background: GREEN, verticalAlign: "text-bottom", marginLeft: 6, animation: "heroCursor 1s steps(1) infinite" }} />
          </div>
        )}
      </div>
    </motion.div>
  );
}
