"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";
import { TypewriterLine } from "../shared";

const GREEN = "#00ff9c";
const DIM = "#3d9c75";
const AMBER = "#ffd166";

const BOOT_LINES: { text: string; delay: number; color?: string }[] = [
  { text: "$ ./mfkagent --boot --agent=auto", delay: 300, color: AMBER },
  { text: "> loading kernel modules ....... OK", delay: 1100, color: DIM },
  { text: "> mounting memory banks ........ OK", delay: 1800, color: DIM },
  { text: "> establishing neural links .... OK", delay: 2500, color: DIM },
  { text: "> agent online — consciousness synced", delay: 3200, color: GREEN },
];

/** Theme 1: Cyber Terminal — 黑客终端，打字效果 + 命令输出 */
export function CyberTerminalTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  // 标题打字完成后延迟启动欢迎语
  const [titleDone, setTitleDone] = useState(false);
  const titleLength = title.length;

  useEffect(() => {
    const t = setTimeout(() => setTitleDone(true), 200 + titleLength * 45);
    return () => clearTimeout(t);
  }, [titleLength]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        borderRadius: "12px",
        border: `1px solid ${DIM}`,
        background: "rgba(2, 10, 6, 0.92)",
        boxShadow: `0 0 40px rgba(0, 255, 156, 0.08), inset 0 0 24px rgba(0, 255, 156, 0.04)`,
        overflow: "hidden",
        fontFamily: "var(--font-geist-mono), ui-monospace, 'Courier New', monospace",
        textAlign: "left",
      }}
    >
      {/* 终端标题栏 */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "8px 14px",
        borderBottom: `1px solid ${DIM}`,
        background: "rgba(0, 255, 156, 0.05)",
      }}>
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#ff5f56" }} />
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#ffbd2e" }} />
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#27c93f" }} />
        <span style={{ flex: 1, textAlign: "center", fontSize: 12, color: DIM }}>mfkagent@core — zsh</span>
      </div>

      <div style={{ padding: "20px 22px 24px" }}>
        {/* 大标题：逐字打字 + 绿色发光 */}
        <div style={{ fontSize: 40, fontWeight: 700, letterSpacing: "0.04em", color: GREEN, textShadow: "0 0 18px rgba(0, 255, 156, 0.45)", marginBottom: 6 }}>
          <TypewriterLine text={title} speed={45} color={GREEN} />
        </div>

        {/* 欢迎语（终端 echo 风格） */}
        {welcome && (
          <div style={{ fontSize: 14, color: AMBER, marginBottom: 2, minHeight: "1.5em" }}>
            <TypewriterLine text={`> ${welcome}`} delay={200 + titleLength * 45 + 350} speed={16} color={AMBER} block={false} />
          </div>
        )}
        {subtext && (
          <div style={{ fontSize: 12, color: DIM, marginBottom: 14, minHeight: "1.5em" }}>
            <TypewriterLine text={`> ${subtext}`} delay={200 + titleLength * 45 + 900} speed={14} color={DIM} block={false} />
          </div>
        )}

        {/* 启动命令序列 */}
        <div style={{ fontSize: 13, lineHeight: 1.8 }}>
          {BOOT_LINES.map((line, i) => (
            <TypewriterLine key={i} {...line} />
          ))}
        </div>

        {/* 最终状态行 */}
        {titleDone && (
          <div style={{ fontSize: 13, marginTop: 10, color: GREEN }}>
            <TypewriterLine text="[OK] MFKAGENT READY — awaiting your command" delay={4300} speed={20} color={GREEN} />
          </div>
        )}
        {animated && (
          <div style={{ fontSize: 13, marginTop: 8, color: GREEN, display: "flex", gap: 6, alignItems: "center" }}>
            <span>$</span>
            <span style={{ display: "inline-block", width: 10, height: 15, background: GREEN, animation: "heroCursor 1s steps(1) infinite" }} />
          </div>
        )}
      </div>
    </motion.div>
  );
}
