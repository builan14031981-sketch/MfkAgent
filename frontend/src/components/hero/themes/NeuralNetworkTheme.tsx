"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

/** 三层神经网络：输入(3) → 隐层(4) → 输出(3) */
const LAYERS = [
  { y: [36, 82, 128], color: "#93c5fd" },
  { y: [26, 62, 98, 134], color: "#c4b5fd" },
  { y: [36, 82, 128], color: "#a78bfa" },
];
const XS = [70, 210, 350];
const TITLE_Y = 148;

/** Neural Network — 神经网络节点连线（静态 SVG + 节点微脉冲，轻量） */
export function NeuralNetworkTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.35 }}
      style={{
        width: "100%",
        maxWidth: "620px",
        margin: "0 auto",
        textAlign: "center",
        fontFamily: "var(--font-family)",
      }}
    >
      <svg viewBox="0 0 420 130" width="100%" height={120} style={{ display: "block", margin: "0 auto" }}>
        {/* 连线 */}
        {[0, 1, 2].map((layer) => layer < 2 && (
          <g key={layer} stroke="rgba(167, 139, 250, 0.35)" strokeWidth="1">
            {LAYERS[layer].y.map((y1) =>
              LAYERS[layer + 1].y.map((y2) => (
                <line key={`${y1}-${y2}`} x1={XS[layer]} y1={y1} x2={XS[layer + 1]} y2={y2} />
              ))
            )}
          </g>
        ))}
        {/* 节点 */}
        {LAYERS.map((layer, li) => layer.y.map((y) => (
          <circle
            key={`${li}-${y}`}
            cx={XS[li]}
            cy={y}
            r="5"
            fill={layer.color}
            style={{ animation: animated ? `glowPulse ${2 + li * 0.7}s ease ${(y % 5) * 0.15}s infinite` : undefined }}
          />
        )))}
      </svg>

      <motion.h1
        initial={{ opacity: 0, letterSpacing: "0.3em" }}
        animate={{ opacity: 1, letterSpacing: "0.05em" }}
        transition={{ duration: 0.8, delay: 0.3 }}
        style={{
          position: "relative",
          margin: "10px 0 0 0",
          fontSize: 42,
          fontWeight: 800,
          color: "var(--text-level-1)",
          background: "linear-gradient(90deg, #93c5fd, #a78bfa)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}
      >
        {title}
      </motion.h1>
      {welcome && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.8 }}
          style={{ margin: "10px 0 0 0", fontSize: 13, color: "var(--text-level-3)" }}
        >
          {welcome}
        </motion.p>
      )}
      {subtext && (
        <p style={{ margin: "4px 0 0 0", fontSize: 12, color: "var(--text-level-4)" }}>{subtext}</p>
      )}
      {animated && (
        <p style={{ margin: "12px 0 0 0", fontSize: 11, color: "#a78bfa", letterSpacing: "0.25em", textTransform: "uppercase" }}>
          layer 3 · 84 parameters · sigmoid
        </p>
      )}
    </motion.div>
  );
}
