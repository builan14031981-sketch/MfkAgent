"use client";

import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const BLUE = "#4aa3ff";
const WHITE = "#eaf3ff";
const DIM = "rgba(150, 200, 255, 0.55)";

/** Blueprint Engineering — 工程蓝图：网格线 + 标注线 + 描边标题（轻量） */
export function BlueprintEngineeringTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.35 }}
      style={{
        width: "100%",
        maxWidth: "660px",
        margin: "0 auto",
        position: "relative",
        textAlign: "center",
        borderRadius: 14,
        border: `1px solid ${DIM}`,
        background:
          "linear-gradient(rgba(74, 163, 255, 0.06) 1px, transparent 1px)," +
          "linear-gradient(90deg, rgba(74, 163, 255, 0.06) 1px, transparent 1px)," +
          "linear-gradient(180deg, #061a33, #082244)",
        backgroundSize: "22px 22px, 22px 22px, 100% 100%",
        padding: "34px 24px 30px",
        overflow: "hidden",
        fontFamily: "var(--font-geist-mono), ui-monospace, 'Courier New', monospace",
      }}
    >
      {/* 左上角标注 */}
      <div style={{ position: "absolute", top: 12, left: 14, fontSize: 10, color: DIM, textAlign: "left", lineHeight: 1.7 }}>
        <div>PROJECT: MFKAGENT.AI</div>
        <div>REV: 1.0 · SCALE 1:1</div>
      </div>
      {/* 右上角图号 */}
      <div style={{ position: "absolute", top: 12, right: 14, fontSize: 10, color: DIM }}>
        DWG-042
      </div>

      {/* 标题描边 */}
      <motion.h1
        initial={{ opacity: 0, letterSpacing: "0.35em" }}
        animate={{ opacity: 1, letterSpacing: "0.06em" }}
        transition={{ duration: 0.8, delay: 0.25 }}
        style={{
          margin: 0,
          fontSize: 42,
          fontWeight: 700,
          color: WHITE,
          textShadow:
            `-1px -1px 0 ${BLUE}, 1px -1px 0 ${BLUE}, -1px 1px 0 ${BLUE}, 1px 1px 0 ${BLUE},` +
            `0 0 24px rgba(74, 163, 255, 0.45)`,
        }}
      >
        {title.toUpperCase()}
      </motion.h1>

      {/* 标注线 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 0, margin: "10px auto 0", width: 220 }}>
        <span style={{ width: 10, height: 1, background: BLUE }} />
        <span style={{ width: 200, height: 1, background: DIM, position: "relative" }}>
          <span style={{ position: "absolute", top: -3, left: 0, width: 1, height: 7, background: DIM }} />
          <span style={{ position: "absolute", top: -3, right: 0, width: 1, height: 7, background: DIM }} />
        </span>
        <span style={{ width: 10, height: 1, background: BLUE }} />
      </div>
      <div style={{ fontSize: 10, color: DIM, marginTop: 4 }}>
        ├── 42.0mm ── MfkAgent Intelligence Core ── 42.0mm ──┤
      </div>

      {welcome && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.9 }}
          style={{ margin: "16px 0 0 0", fontSize: 13, color: BLUE, fontFamily: "var(--font-family)" }}
        >
          {welcome}
        </motion.p>
      )}
      {subtext && (
        <p style={{ margin: "4px 0 0 0", fontSize: 11, color: DIM, fontFamily: "var(--font-family)" }}>{subtext}</p>
      )}

      {/* 底部十字准星 */}
      {animated && (
        <div style={{ position: "absolute", bottom: 10, right: 14, fontSize: 14, color: DIM, lineHeight: 1 }}>
          +
        </div>
      )}
    </motion.div>
  );
}
