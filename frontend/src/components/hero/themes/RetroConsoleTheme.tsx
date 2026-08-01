"use client";

import { motion } from "framer-motion";
import type { CSSProperties } from "react";
import type { HeroThemeProps } from "@/themes/types";

/* 16-bit 家用机（FC/SFC）启动配色 */
const NES_RED = "#E60012";
const NES_BLUE = "#00A8E8";
const GOLD = "#F8B800";
const GAME_GREEN = "#00D400";
const WHITE = "#FFFFFF";
const DIM = "#3a3f66";

const pixel8: CSSProperties = {
  fontFamily: "var(--font-pixel-8bit), var(--font-pixel-dot), monospace",
  letterSpacing: "0.1em",
  imageRendering: "pixelated",
};

const pixelVT: CSSProperties = {
  fontFamily: "var(--font-pixel-vt), var(--font-pixel-dot), var(--font-noto-sans-sc), monospace",
  letterSpacing: "0.05em",
};

const MENU = ["1P AGENT MODE", "2P PROJECT MODE", "OPTIONS", "QUIT"];

/** Theme: Retro Console — 16-bit 家用机开机选单，像素外框 + 像素标题 + 扫描线 */
export function RetroConsoleTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        padding: "10px",
        background: "#141a33",
        border: "3px solid #2a3160",
        boxShadow: "6px 6px 0 rgba(0,0,0,0.5), 10px 10px 0 rgba(230,0,18,0.25)",
        imageRendering: "pixelated",
        textAlign: "center",
      }}
    >
      {/* CRT 内屏（圆角 + 扫描线 + 暗角） */}
      <div
        style={{
          position: "relative",
          overflow: "hidden",
          borderRadius: 6,
          background: "radial-gradient(ellipse at center, #10142b 0%, #080a18 100%)",
          border: "2px solid #000",
          padding: "22px 26px 24px",
          boxShadow: "inset 0 0 40px rgba(0,0,0,0.85)",
        }}
      >
        {/* 扫描线纹理 */}
        {animated && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              pointerEvents: "none",
              background:
                "repeating-linear-gradient(to bottom, rgba(255,255,255,0.03) 0px, rgba(255,255,255,0.03) 1px, transparent 1px, transparent 3px)",
            }}
          />
        )}

        {/* 顶部状态行 */}
        <div style={{ ...pixelVT, fontSize: 14, color: GOLD, display: "flex", justifyContent: "space-between" }}>
          <span>CONSOLE 16-BIT</span>
          <span style={{ color: animated ? GAME_GREEN : GOLD }}>
            {animated ? "● POWER" : "● READY"}
          </span>
        </div>

        {/* 像素标题：Press Start 2P + 硬投影 */}
        <div
          style={{
            ...pixel8,
            marginTop: 16,
            fontSize: 34,
            lineHeight: 1.3,
            color: WHITE,
            textShadow: `3px 3px 0 ${NES_RED}, 6px 6px 0 rgba(0,0,0,0.6)`,
          }}
        >
          {title}
        </div>

        {welcome && (
          <div style={{ ...pixelVT, marginTop: 12, fontSize: 20, color: GAME_GREEN, textShadow: "2px 2px 0 rgba(0,0,0,0.6)" }}>
            {welcome}
          </div>
        )}
        {subtext && (
          <div style={{ ...pixelVT, marginTop: 6, fontSize: 15, color: NES_BLUE, textShadow: "1px 1px 0 rgba(0,0,0,0.6)" }}>
            {subtext}
          </div>
        )}

        {/* 像素色块精灵排 */}
        <div style={{ display: "flex", gap: 8, justifyContent: "center", marginTop: 16 }}>
          {[NES_RED, GOLD, GAME_GREEN, NES_BLUE, "#FF8C00"].map((c, i) => (
            <span
              key={i}
              style={{
                width: 12,
                height: 12,
                background: c,
                boxShadow: "2px 2px 0 rgba(0,0,0,0.5)",
                display: "inline-block",
              }}
            />
          ))}
        </div>

        {/* 游戏选单（像素边框 + 高亮第一项） */}
        <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 6 }}>
          {MENU.map((m, i) => (
            <div
              key={m}
              style={{
                ...pixelVT,
                fontSize: 15,
                padding: "4px 10px",
                border: i === 0 ? `2px solid ${GOLD}` : "2px solid #2a3160",
                background: i === 0 ? "rgba(248,184,0,0.12)" : "rgba(20,26,51,0.6)",
                color: i === 0 ? GOLD : DIM,
                textAlign: "left",
                boxShadow: i === 0 ? "3px 3px 0 rgba(0,0,0,0.4)" : undefined,
              }}
            >
              <span style={{ display: "inline-block", width: 16 }}>{i === 0 ? "►" : ""}</span>
              {m}
            </div>
          ))}
        </div>

        {/* PRESS START 闪烁 */}
        {animated && (
          <div style={{ ...pixel8, marginTop: 16, fontSize: 14, color: WHITE, animation: "glowPulse 1.6s ease-in-out infinite" }}>
            PRESS START
            <span
              style={{
                display: "inline-block",
                width: 12,
                height: 15,
                background: WHITE,
                marginLeft: 8,
                verticalAlign: "text-bottom",
                animation: "heroCursor 1s steps(1) infinite",
              }}
            />
          </div>
        )}

        {/* 底部 HP 条（一次性填充） */}
        <div style={{ marginTop: 14, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
          <span style={{ ...pixelVT, fontSize: 13, color: GAME_GREEN }}>HP</span>
          <div style={{ width: 180, height: 12, border: "2px solid #2a3160", background: "#000", padding: 1 }}>
            <div
              style={{
                height: "100%",
                background: "repeating-linear-gradient(90deg, #00D400 0px, #00D400 6px, #0a3a0a 6px, #0a3a0a 8px)",
                animation: animated ? "progressFill 1.4s ease-out forwards" : undefined,
              }}
            />
          </div>
        </div>
      </div>
    </motion.div>
  );
}
