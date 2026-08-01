"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";
import { TypewriterLine } from "../shared";

const BLUE = "#38bdf8";
const WHITE = "#e8f4ff";
const DIM = "#9cc3e8";

const DOS_LINES: { text: string; delay: number; color?: string }[] = [
  { text: "Microsoft(R) MS-DOS(R) Version 6.22", delay: 250, color: WHITE },
  { text: "(C)Copyright Microsoft Corp 1990-1994.", delay: 850, color: WHITE },
  { text: "", delay: 1250 },
  { text: "C:\\>CD MFKAGENT", delay: 1450, color: BLUE },
  { text: "", delay: 1750 },
  { text: "C:\\MFKAGENT>MFKAGENT.EXE /AI", delay: 1950, color: BLUE },
  { text: "Loading MfkAgent Intelligence Engine...", delay: 2600, color: DIM },
];

/** Theme 5: Retro DOS — 经典 DOS 命令行启动（CGA 蓝底） */
export function RetroDosTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  const [titleDone, setTitleDone] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setTitleDone(true), 3400);
    return () => clearTimeout(t);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        borderRadius: "6px",
        background: "#00008b",
        color: WHITE,
        border: "2px solid #00006b",
        boxShadow: "0 0 32px rgba(0, 0, 139, 0.35)",
        overflow: "hidden",
        fontFamily: "var(--font-geist-mono), ui-monospace, 'Courier New', monospace",
        textAlign: "left",
      }}
    >
      <div style={{ padding: "18px 24px 22px", fontSize: 13, lineHeight: 1.9 }}>
        {DOS_LINES.map((line, i) => (
          <TypewriterLine key={i} text={line.text} delay={line.delay} speed={10} color={line.color} />
        ))}

        {/* DOS 风格标题（蓝底白字 + 方块光标） */}
        {titleDone && (
          <div style={{ marginTop: 12, textAlign: "center" }}>
            <div style={{
              display: "inline-block",
              padding: "4px 20px",
              border: "2px solid #e8f4ff",
              fontSize: 34,
              fontWeight: 800,
              letterSpacing: "0.3em",
              color: WHITE,
              background: "#0000a0",
              textShadow: "2px 2px 0 #000060",
            }}>
              {title.toUpperCase()}
            </div>
          </div>
        )}

        {/* 欢迎语 */}
        {welcome && (
          <div style={{ marginTop: 12, textAlign: "center", fontSize: 13 }}>
            <TypewriterLine text={`C:\\MFKAGENT>WELCOME ${welcome}`} delay={3600} speed={16} color={WHITE} block={false} />
          </div>
        )}
        {subtext && (
          <div style={{ textAlign: "center", fontSize: 12, color: DIM }}>
            <TypewriterLine text={`C:\\MFKAGENT>REM ${subtext}`} delay={4300} speed={14} color={DIM} block={false} />
          </div>
        )}

        {/* 闪烁方块光标 */}
        {animated && (
          <div style={{ marginTop: 10, fontSize: 13, color: WHITE }}>
            <span>C:\MFKAGENT&gt;</span>
            <span style={{ display: "inline-block", width: 11, height: 16, background: WHITE, verticalAlign: "text-bottom", marginLeft: 4, animation: "heroCursor 1s steps(1) infinite" }} />
          </div>
        )}
      </div>
    </motion.div>
  );
}
