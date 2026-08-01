"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";
import { mulberry32 } from "../shared";

const GREEN = "#00ff41";
const GREEN_DIM = "rgba(0, 255, 65, 0.5)";

interface RainColumn {
  text: string;
  left: number;
  delay: number;
  duration: number;
}

/** Matrix Data — 数字雨背景 + 绿色发光标题（微动画） */
export function MatrixDataTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  // 确定性生成雨列（内容两段重复，配合 -50%→0 无缝循环）
  const columns = useMemo<RainColumn[]>(() => {
    const cols: RainColumn[] = [];
    for (let i = 0; i < 9; i++) {
      const rand = mulberry32(20260101 + i * 131);
      let text = "";
      for (let j = 0; j < 44; j++) {
        text += String(Math.floor(rand() * 10));
      }
      cols.push({
        text: text + text, // 两段，保证循环无缝
        left: 4 + (i * 100) / 9 + rand() * 4,
        delay: rand() * 5,
        duration: 4 + rand() * 5,
      });
    }
    return cols;
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      style={{
        position: "relative",
        width: "100%",
        maxWidth: "680px",
        margin: "0 auto",
        textAlign: "center",
        overflow: "hidden",
        fontFamily: "var(--font-geist-mono), ui-monospace, 'Courier New', monospace",
        padding: "10px 0",
      }}
    >
      {/* 数字雨背景 */}
      {animated && columns.map((col, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            top: 0,
            left: `${col.left}%`,
            height: "100%",
            width: 14,
            overflow: "hidden",
            opacity: 0.6,
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              fontSize: 11,
              lineHeight: 1.35,
              color: GREEN,
              whiteSpace: "nowrap",
              animation: `matrixFall ${col.duration}s linear ${col.delay}s infinite`,
            }}
          >
            {col.text}
          </div>
        </div>
      ))}

      <h1 style={{
        position: "relative",
        margin: 0,
        fontSize: 46,
        fontWeight: 800,
        letterSpacing: "0.1em",
        color: GREEN,
        textShadow: `0 0 12px ${GREEN}, 0 0 44px rgba(0, 255, 65, 0.55)`,
      }}>
        {title.toUpperCase()}
      </h1>
      {welcome && (
        <p style={{ position: "relative", margin: "12px 0 0 0", fontSize: 13, color: GREEN_DIM }}>{welcome}</p>
      )}
      {subtext && (
        <p style={{ position: "relative", margin: "4px 0 0 0", fontSize: 12, color: GREEN_DIM }}>{subtext}</p>
      )}
      {animated && (
        <p style={{
          position: "relative",
          margin: "16px 0 0 0",
          fontSize: 11,
          color: GREEN,
          letterSpacing: "0.3em",
          textTransform: "uppercase",
          animation: "glowPulse 2.6s ease infinite",
        }}>
          <span>{`01101101 01100110 01101011`}</span>
        </p>
      )}
    </motion.div>
  );
}
