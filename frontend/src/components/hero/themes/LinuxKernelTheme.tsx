"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";
import { TypewriterLine } from "../shared";

const GREEN = "#a3e635";
const WHITE = "#e8e6e3";
const DIM = "#6b7a52";

const BOOT_LINES: { text: string; delay: number }[] = [
  { text: "Linux version 6.12.6-mfk (gcc-13.2.0)", delay: 150 },
  { text: "Command line: ROOT=/dev/mfk_core AGENT=auto", delay: 700 },
  { text: "[ OK ] Mounted /dev/mfk_core", delay: 1200 },
  { text: "[ OK ] Reached target MfkAgent.AI Runtime", delay: 1700 },
];

/** Linux Kernel — 内核启动日志 + 发光标题（轻量：几行日志，无完整动画） */
export function LinuxKernelTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
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
      {/* 左上角内核日志小终端 */}
      <div style={{
        borderRadius: 8,
        border: "1px solid rgba(163, 230, 53, 0.25)",
        background: "rgba(10, 14, 8, 0.9)",
        padding: "10px 14px",
        fontSize: 11,
        lineHeight: 1.8,
        color: DIM,
        width: "fit-content",
        marginBottom: 18,
      }}>
        {BOOT_LINES.map((line, i) => (
          <TypewriterLine key={i} text={line.text} delay={line.delay} speed={10} color={DIM} block={false} />
        ))}
        {animated && (
          <span style={{ display: "inline-block", width: 8, height: 12, background: GREEN, verticalAlign: "text-bottom", animation: "heroCursor 1s steps(1) infinite" }} />
        )}
      </div>

      {/* 中央大标题：白字 + 黄绿辉光 */}
      <motion.h1
        initial={{ opacity: 0, letterSpacing: "0.4em" }}
        animate={{ opacity: 1, letterSpacing: "0.06em" }}
        transition={{ duration: 0.9, delay: 0.4, ease: "easeOut" }}
        style={{
          margin: 0,
          fontSize: 44,
          fontWeight: 800,
          color: WHITE,
          textShadow: `0 0 12px ${GREEN}, 0 0 40px rgba(163, 230, 53, 0.45)`,
        }}
      >
        {title.toUpperCase()}
      </motion.h1>

      {welcome && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 1.1 }}
          style={{ margin: "10px 0 0 0", fontSize: 14, color: GREEN }}
        >
          {welcome}
        </motion.p>
      )}
      {subtext && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 1.4 }}
          style={{ margin: "4px 0 0 0", fontSize: 12, color: DIM }}
        >
          {subtext}
        </motion.p>
      )}
    </motion.div>
  );
}
