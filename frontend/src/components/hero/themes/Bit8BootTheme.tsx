"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";
import { TypewriterLine } from "../shared";

const BIOS_LINES: { text: string; delay: number }[] = [
  { text: "MfkAgent BIOS v1.0.0  (C) 2026 MfkAgent Inc.", delay: 250 },
  { text: "CPU  : MfkCore-9000 @ 3.6GHz", delay: 900 },
  { text: "Memory Test : 65536K OK", delay: 1500 },
  { text: "Detecting IDE Drives ...", delay: 2100 },
  { text: "  IDE Primary Master : MFK-SSD 2048MB", delay: 2700 },
  { text: "  IDE Primary Slave  : CORE-BANK 512MB", delay: 3300 },
  { text: "Loading MfkAgent Kernel ...", delay: 3900 },
];

/** Theme 2: 8-Bit Boot — 老式 BIOS 开机，像素字体 + CRT 扫描线 */
export function Bit8BootTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  const [titleDone, setTitleDone] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setTitleDone(true), 4600);
    return () => clearTimeout(t);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      style={{
        position: "relative",
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        borderRadius: "8px",
        background: "#05070a",
        border: "2px solid #1a2330",
        overflow: "hidden",
        fontFamily: "var(--font-geist-mono), ui-monospace, 'Courier New', monospace",
        textAlign: "left",
        color: "#b8e6b8",
      }}
    >
      <div style={{ padding: "18px 24px 22px", fontSize: 13, lineHeight: 1.9 }}>
        {BIOS_LINES.map((line, i) => (
          <TypewriterLine key={i} text={line.text} delay={line.delay} speed={12} />
        ))}

        {/* 像素风大标题：text-shadow 堆叠模拟像素粗体 */}
        {titleDone && (
          <div style={{
            marginTop: 14,
            fontSize: 44,
            fontWeight: 800,
            letterSpacing: "0.12em",
            color: "#c8ffc8",
            textShadow:
              "2px 0 0 #c8ffc8, -2px 0 0 #c8ffc8, 0 2px 0 #c8ffc8, 0 -2px 0 #c8ffc8, " +
              "2px 2px 0 #c8ffc8, -2px -2px 0 #c8ffc8, 0 0 24px rgba(120, 255, 120, 0.5)",
            fontFamily: "var(--font-geist-mono), ui-monospace, monospace",
            textAlign: "center",
          }}>
            {title.toUpperCase()}
          </div>
        )}

        {/* 欢迎语（BIOS 底部状态行） */}
        {welcome && (
          <div style={{ marginTop: 10, textAlign: "center", fontSize: 13, color: "#7fc97f" }}>
            <TypewriterLine text={`> ${welcome}`} delay={4800} speed={16} color="#7fc97f" block={false} />
          </div>
        )}
        {subtext && (
          <div style={{ textAlign: "center", fontSize: 12, color: "#4a6b4a" }}>
            <TypewriterLine text={`> ${subtext}`} delay={5400} speed={14} color="#4a6b4a" block={false} />
          </div>
        )}

        {animated && (
          <div style={{ marginTop: 10, textAlign: "center", fontSize: 13, color: "#7fc97f" }}>
            <span style={{ display: "inline-block", width: 10, height: 15, background: "#7fc97f", verticalAlign: "text-bottom", animation: "heroCursor 1s steps(1) infinite" }} />
          </div>
        )}
      </div>

      {/* CRT 扫描线 overlay */}
      <div style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        background: "repeating-linear-gradient(0deg, rgba(0,0,0,0.22) 0px, rgba(0,0,0,0.22) 1px, transparent 1px, transparent 3px)",
        animation: animated ? "heroScanline 9s linear infinite" : undefined,
        mixBlendMode: "multiply",
      }} />

      {/* 屏幕轻微闪烁 */}
      {animated && (
        <div style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          background: "rgba(180, 255, 180, 0.03)",
          animation: "heroFlicker 4s infinite",
        }} />
      )}
    </motion.div>
  );
}
