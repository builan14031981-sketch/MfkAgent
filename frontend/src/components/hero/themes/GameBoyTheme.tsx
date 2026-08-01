"use client";

import { motion } from "framer-motion";
import type { CSSProperties } from "react";
import type { HeroThemeProps } from "@/themes/types";

/* 原版 Game Boy DMG 配色 */
const SHELL_LIGHT = "#C8BFA4";
const SHELL_DARK = "#5A5A5A";
const BEZEL = "#3B4A4F";
const SCREEN_BG = "#8BAC0F"; // GB 亮绿
const SCREEN_INK = "#0F380F"; // GB 墨绿
const SCREEN_MID = "#306230";
const LED_RED = "#E60012";

const gbFont: CSSProperties = {
  fontFamily: "var(--font-pixel-dot), var(--font-pixel-vt), var(--font-noto-sans-sc), monospace",
  letterSpacing: "0.05em",
};

/** Theme: Game Boy — 原版 DMG 掌机外壳，4 色绿屏 + 十字键 + A/B 键 */
export function GameBoyTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.35 }}
      style={{
        width: "100%",
        maxWidth: "520px",
        margin: "0 auto",
        padding: "18px 22px 20px",
        borderRadius: 16,
        background: `linear-gradient(145deg, ${SHELL_LIGHT} 0%, #A89E86 60%, #8E8570 100%)`,
        boxShadow: "6px 8px 0 rgba(0,0,0,0.45), inset 0 2px 0 rgba(255,255,255,0.55)",
        textAlign: "center",
      }}
    >
      {/* 顶部品牌区 */}
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", padding: "0 4px" }}>
        <span
          style={{
            ...gbFont,
            fontSize: 20,
            fontWeight: 700,
            color: SHELL_DARK,
            letterSpacing: "0.18em",
            lineHeight: 1,
          }}
        >
          MfkAgent
        </span>
        <span style={{ ...gbFont, fontSize: 9, color: "#5A5A5A", letterSpacing: "0.12em" }}>
          MICRO-AGENT™
        </span>
      </div>

      {/* 电源指示灯 */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 6px 4px" }}>
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: LED_RED,
            display: "inline-block",
            boxShadow: "0 0 4px rgba(230,0,18,0.8)",
            animation: animated ? "glowPulse 1.8s ease-in-out infinite" : undefined,
          }}
        />
        <span style={{ ...gbFont, fontSize: 8, color: "#5A5A5A", letterSpacing: "0.1em" }}>BATTERY</span>
      </div>

      {/* 屏幕外框（bezel） */}
      <div
        style={{
          background: BEZEL,
          borderRadius: 8,
          padding: "14px 12px 12px",
          boxShadow: "inset 0 2px 4px rgba(0,0,0,0.6)",
        }}
      >
        {/* 屏幕点阵描边 */}
        <div style={{ background: "#2B3438", borderRadius: 4, padding: "10px 8px" }}>
          {/* 绿屏 */}
          <div
            style={{
              background: SCREEN_BG,
              border: `2px solid ${SCREEN_MID}`,
              padding: "16px 14px 18px",
              color: SCREEN_INK,
              borderRadius: 2,
              boxShadow: "inset 0 0 12px rgba(15,56,15,0.35)",
            }}
          >
            {/* 像素网格（模拟 LCD） */}
            <div
              style={{
                background:
                  "repeating-linear-gradient(0deg, transparent 0px, transparent 3px, rgba(15,56,15,0.12) 3px, rgba(15,56,15,0.12) 4px), repeating-linear-gradient(90deg, transparent 0px, transparent 3px, rgba(15,56,15,0.12) 3px, rgba(15,56,15,0.12) 4px)",
              }}
            >
              <div style={{ ...gbFont, fontSize: 26, fontWeight: 700, letterSpacing: "0.1em", lineHeight: 1.3 }}>
                {title}
              </div>
              {welcome && (
                <div style={{ ...gbFont, fontSize: 15, marginTop: 8, lineHeight: 1.5 }}>{welcome}</div>
              )}
              {subtext && (
                <div style={{ ...gbFont, fontSize: 12, marginTop: 6, opacity: 0.75 }}>{subtext}</div>
              )}
            </div>

            {/* 状态行 */}
            <div
              style={{
                ...gbFont,
                fontSize: 10,
                marginTop: 10,
                display: "flex",
                justifyContent: "space-between",
                color: SCREEN_MID,
              }}
            >
              <span>{animated ? "► RUNNING" : "READY"}</span>
              <span>N-LINK</span>
            </div>
          </div>
        </div>

        {/* 屏幕下方文字 */}
        <div
          style={{
            ...gbFont,
            fontSize: 8,
            color: "#8FA6AB",
            letterSpacing: "0.22em",
            marginTop: 6,
            textAlign: "center",
          }}
        >
          DOT MATRIX WITH STEREO SOUND
        </div>
      </div>

      {/* 控制区：十字键 + A/B 键 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 16 }}>
        {/* D-Pad */}
        <div style={{ width: 92, height: 92, position: "relative" }}>
          {/* 十字键背景槽 */}
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              width: 64,
              height: 64,
              transform: "translate(-50%, -50%)",
              borderRadius: 6,
              background: "#3A3A3A",
              boxShadow: "inset 0 2px 4px rgba(0,0,0,0.7)",
            }}
          />
          {/* 垂直杆 */}
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: 40,
              height: 88,
              background: SHELL_DARK,
              borderRadius: 4,
              boxShadow: "2px 2px 0 rgba(0,0,0,0.4)",
            }}
          />
          {/* 水平杆 */}
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: 88,
              height: 40,
              background: SHELL_DARK,
              borderRadius: 4,
              boxShadow: "2px 2px 0 rgba(0,0,0,0.4)",
            }}
          />
          {/* 中心圆点 */}
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: 14,
              height: 14,
              borderRadius: "50%",
              background: "#2E2E2E",
            }}
          />
        </div>

        {/* A/B 键 */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, paddingRight: 6 }}>
          {[
            { label: "B", delay: 0 },
            { label: "A", delay: 0.5 },
          ].map((btn) => (
            <div key={btn.label} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <span
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: "50%",
                  background: "radial-gradient(circle at 35% 30%, #D44A4A, #8E1E2A 70%)",
                  color: "#fff",
                  ...gbFont,
                  fontSize: 12,
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "inset 0 -3px 0 rgba(0,0,0,0.35), 2px 2px 0 rgba(0,0,0,0.4)",
                  animation: animated ? "keyTap 2.4s ease-in-out infinite" : undefined,
                  animationDelay: `${btn.delay}s`,
                }}
              >
                {btn.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 底部铭牌 */}
      <div
        style={{
          ...gbFont,
          fontSize: 9,
          color: "#6B6355",
          letterSpacing: "0.15em",
          marginTop: 14,
        }}
      >
        ← SELECT&nbsp;&nbsp;&nbsp;START →
      </div>
    </motion.div>
  );
}
