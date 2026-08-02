"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";
import { TypewriterLine } from "../shared";

const GREEN = "#00FF00";

const BOOT_LINES: { text: string; delay: number; color?: string }[] = [
  { text: "BIOS v4.2 (MfkAgent Core) ....... OK", delay: 300, color: GREEN },
  { text: "CPU: quantum@2.4GHz ............ OK", delay: 1100, color: GREEN },
  { text: "MEM: 8192TB neural .............. OK", delay: 1900, color: GREEN },
  { text: "TTY: /dev/mfk-agent ............. OK", delay: 2700, color: GREEN },
];

/** Theme: Retro Terminal — 纯黑 + 荧光绿，CRT 扫描线 + 命令行输出 */
export function RetroTerminalTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  const titleLength = title.length;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        padding: "24px 26px 28px",
        background: "#000",
        border: "1px solid rgba(0,255,0,0.4)",
        borderRadius: 6,
        position: "relative",
        overflow: "hidden",
        fontFamily: "var(--font-geist-mono), 'Courier New', monospace",
        textAlign: "left",
        color: GREEN,
        textShadow: "0 0 6px rgba(0,255,0,0.5)",
      }}
    >
      {/* CRT 扫描线 */}
      {animated && (
        <>
          <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 60, background: "linear-gradient(to bottom, transparent, rgba(0,255,0,0.06))", animation: "heroScanline 6s linear infinite", pointerEvents: "none" }} />
          <div style={{ position: "absolute", inset: 0, background: "repeating-linear-gradient(0deg, rgba(0,0,0,0.28) 0 1px, transparent 1px 3px)", pointerEvents: "none" }} />
        </>
      )}

      <div style={{ fontSize: 13, lineHeight: 1.7 }}>
        {BOOT_LINES.map((line, i) => (
          <TypewriterLine key={i} text={line.text} delay={line.delay} speed={14} color={line.color} block={false} animated={animated} />
        ))}
      </div>

      {/* 提示符 + 标题逐字输出 */}
      <div style={{ marginTop: 12, fontSize: 34, fontWeight: 700, letterSpacing: "0.03em" }}>
        <TypewriterLine text={`$ ${title}`} speed={60} color={GREEN} animated={animated} />
      </div>

      {welcome && (
        <div style={{ fontSize: 15, marginTop: 8 }}>
          <TypewriterLine text={`mfk-agent$ ${welcome}`} delay={titleLength * 60 + 500} speed={18} color={GREEN} block={false} animated={animated} />
        </div>
      )}
      {subtext && (
        <div style={{ fontSize: 12, marginTop: 4, opacity: 0.75 }}>
          <TypewriterLine text={`mfk-agent$ ${subtext}`} delay={titleLength * 60 + 1000} speed={14} color={GREEN} block={false} animated={animated} />
        </div>
      )}
    </motion.div>
  );
}
