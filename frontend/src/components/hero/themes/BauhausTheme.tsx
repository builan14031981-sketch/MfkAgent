"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const RED = "#E3000F";
const BLUE = "#0038EC";
const YELLOW = "#FED200";

/** Theme: Bauhaus — 三原色几何 + 大留白，理性秩序现代主义 */
export function BauhausTheme({ title, welcome, subtext }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        padding: "34px 30px",
        background: "#fff",
        border: "2px solid #000",
        position: "relative",
        fontFamily: "var(--font-geist-sans), 'Helvetica Neue', Helvetica, sans-serif",
        textAlign: "left",
        color: "#000",
      }}
    >
      {/* 三原色几何装饰：红圆 + 蓝方块 + 黄三角 */}
      <div style={{ position: "absolute", top: 18, right: 20, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 26, height: 26, borderRadius: "50%", background: RED, display: "inline-block" }} />
        <span style={{ width: 26, height: 26, background: BLUE, display: "inline-block", transform: "rotate(45deg)" }} />
        <span style={{ width: 0, height: 0, borderLeft: "16px solid transparent", borderRight: "16px solid transparent", borderBottom: "26px solid " + YELLOW, display: "inline-block" }} />
      </div>

      <div style={{ fontSize: 46, fontWeight: 900, letterSpacing: "-0.03em", lineHeight: 1.05 }}>
        {title.split(" ").map((word, i, arr) => (
          <span key={i}>
            <span style={{ color: i % 2 === 0 ? "#000" : BLUE }}>{word}</span>
            {i < arr.length - 1 && " "}
          </span>
        ))}
      </div>

      {welcome && (
        <div style={{ fontSize: 18, marginTop: 16, fontWeight: 500, borderTop: `4px solid ${RED}`, paddingTop: 12, display: "inline-block" }}>{welcome}</div>
      )}
      {subtext && <div style={{ fontSize: 13, marginTop: 8, color: "#555", lineHeight: 1.6 }}>{subtext}</div>}

      {/* 数学化间距分隔线 */}
      <div style={{ display: "flex", gap: 6, marginTop: 20 }}>
        <span style={{ flex: 1, height: 6, background: YELLOW }} />
        <span style={{ flex: 2, height: 6, background: "#000" }} />
        <span style={{ flex: 1, height: 6, background: BLUE }} />
      </div>
    </motion.div>
  );
}
