"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const COPPER = "#B87333";
const BRASS = "#D4AF37";
const SMOKE = "#2C2C2C";

/** Theme: Steampunk — 黄铜边框 + 齿轮转动 + 铆钉，维多利亚机械浪漫 */
export function SteampunkTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.35 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        padding: "30px 28px",
        background: `linear-gradient(145deg, ${SMOKE}, #3a2f22)`,
        border: `3px solid ${COPPER}`,
        borderRadius: 10,
        boxShadow: `0 0 30px rgba(184,115,51,0.25), inset 0 0 60px rgba(0,0,0,0.5)`,
        fontFamily: "var(--font-geist-sans), 'IM Fell English', serif",
        textAlign: "center",
        color: "#f0d9a8",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 齿轮装饰（一大一小咬合旋转） */}
      <div style={{ position: "absolute", top: 16, right: 18, display: "flex", alignItems: "center", gap: 10, opacity: 0.85 }}>
        <div style={{ position: "relative", width: 44, height: 44, animation: animated ? "spinSlow 6s linear infinite" : undefined }}>
          {[0, 45, 90, 135].map((deg) => (
            <span key={deg} style={{ position: "absolute", top: "50%", left: "50%", width: 20, height: 9, background: BRASS, borderRadius: 2, transform: `translate(-50%, -50%) rotate(${deg}deg)`, transformOrigin: "center" }} />
          ))}
          <span style={{ position: "absolute", top: "50%", left: "50%", width: 20, height: 20, borderRadius: "50%", background: BRASS, transform: "translate(-50%, -50%)" }} />
        </div>
        <div style={{ position: "relative", width: 30, height: 30, animation: animated ? "spinSlow 4s linear infinite reverse" : undefined }}>
          <span style={{ position: "absolute", top: "50%", left: "50%", width: 24, height: 7, background: COPPER, borderRadius: 2, transform: "translate(-50%, -50%)", boxShadow: "0 0 6px rgba(212,175,55,0.6)" }} />
          <span style={{ position: "absolute", top: "50%", left: "50%", width: 14, height: 14, borderRadius: "50%", background: COPPER, transform: "translate(-50%, -50%)" }} />
        </div>
      </div>

      <div style={{ fontSize: 40, fontWeight: 700, letterSpacing: "0.06em", textShadow: "0 2px 8px rgba(0,0,0,0.6)" }}>{title}</div>

      {/* 黄铜分割线 */}
      <div style={{ height: 2, width: "60%", margin: "14px auto", background: `linear-gradient(90deg, transparent, ${BRASS}, transparent)`, boxShadow: `0 0 8px ${BRASS}` }} />

      {welcome && <div style={{ fontSize: 16, color: "#e6c887", fontStyle: "italic" }}>{welcome}</div>}
      {subtext && <div style={{ fontSize: 13, marginTop: 8, color: "#b09a6f" }}>{subtext}</div>}

      {/* 压力表式进度条 */}
      <div style={{ marginTop: 16, height: 16, border: `2px solid ${COPPER}`, borderRadius: 8, overflow: "hidden", background: "#1c1610" }}>
        <div style={{ height: "100%", background: `repeating-linear-gradient(90deg, ${BRASS} 0 12px, ${COPPER} 12px 16px)`, animation: animated ? "progressFill 1.6s ease-out forwards" : undefined }} />
      </div>

      {animated && (
        <div style={{ marginTop: 12, fontSize: 12, color: "#a8906a", letterSpacing: "0.2em" }}>
          <span>PRESSURIZING</span>
          <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: "50%", background: BRASS, marginLeft: 8, verticalAlign: "middle", animation: "glowPulse 1.2s ease-in-out infinite" }} />
        </div>
      )}
    </motion.div>
  );
}
