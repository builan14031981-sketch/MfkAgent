"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const GREEN = "#a8f0a8";
const GREEN_DIM = "#3d6b3d";

/** CRT Monitor — 老式显示器外壳 + 荧光屏 + 扫描线（轻量装饰） */
export function CrtMonitorTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.35 }}
      style={{
        width: "100%",
        maxWidth: "600px",
        margin: "0 auto",
        fontFamily: "var(--font-geist-mono), ui-monospace, 'Courier New', monospace",
      }}
    >
      {/* 显示器外壳 */}
      <div style={{
        borderRadius: 20,
        padding: 14,
        background: "linear-gradient(180deg, #3a3a3e, #2a2a2e)",
        boxShadow: "0 12px 40px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255,255,255,0.15)",
      }}>
        {/* 荧光屏 */}
        <div style={{
          position: "relative",
          borderRadius: 10,
          background: "#020604",
          padding: "26px 20px 22px",
          overflow: "hidden",
          textAlign: "center",
        }}>
          <h1 style={{
            margin: 0,
            fontSize: 40,
            fontWeight: 800,
            letterSpacing: "0.08em",
            color: GREEN,
            textShadow: `0 0 10px ${GREEN}, 0 0 34px rgba(168, 240, 168, 0.6), 0 0 2px ${GREEN}`,
          }}>
            {title.toUpperCase()}
          </h1>
          {welcome && (
            <p style={{ margin: "12px 0 0 0", fontSize: 13, color: GREEN_DIM }}>{welcome}</p>
          )}
          {subtext && (
            <p style={{ margin: "4px 0 0 0", fontSize: 11, color: GREEN_DIM }}>{subtext}</p>
          )}
          {animated && (
            <div style={{ marginTop: 12, fontSize: 12, color: GREEN }}>
              CH-01 <span style={{ display: "inline-block", width: 9, height: 13, background: GREEN, verticalAlign: "text-bottom", marginLeft: 4, animation: "heroCursor 1s steps(1) infinite" }} />
            </div>
          )}

          {/* 扫描线 + 闪烁 */}
          <div style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            background: "repeating-linear-gradient(0deg, rgba(0,0,0,0.28) 0px, rgba(0,0,0,0.28) 1px, transparent 1px, transparent 3px)",
          }} />
          {animated && (
            <>
              <div style={{
                position: "absolute",
                inset: 0,
                pointerEvents: "none",
                background: "linear-gradient(180deg, transparent, rgba(168,240,168,0.06), transparent)",
                height: "40%",
                animation: "heroScanline 6s linear infinite",
              }} />
              <div style={{
                position: "absolute",
                inset: 0,
                pointerEvents: "none",
                background: "rgba(200, 255, 200, 0.03)",
                animation: "heroFlicker 5s infinite",
              }} />
            </>
          )}

          {/* 电源灯 */}
          <div style={{ position: "absolute", bottom: 8, right: 12, display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#34d399", boxShadow: "0 0 6px #34d399", animation: animated ? "glowPulse 2.4s ease infinite" : undefined }} />
            <span style={{ fontSize: 9, color: GREEN_DIM }}>PWR</span>
          </div>
        </div>
      </div>

      {/* 底座旋钮 */}
      <div style={{ display: "flex", justifyContent: "center", gap: 18, paddingTop: 12 }}>
        {[0, 1].map((i) => (
          <div key={i} style={{
            width: 20,
            height: 20,
            borderRadius: "50%",
            background: "radial-gradient(circle at 35% 30%, #555, #2a2a2e)",
            boxShadow: "0 2px 4px rgba(0,0,0,0.4)",
            position: "relative",
          }}>
            <span style={{
              position: "absolute",
              top: 4,
              left: "50%",
              width: 2,
              height: 5,
              background: "#c8c8cc",
              borderRadius: 1,
            }} />
          </div>
        ))}
      </div>
    </motion.div>
  );
}
