"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";

const TITLE_COLORS = ["#0071e3", "#5b8cff", "#8b5cf6", "#c084fc"];

interface Particle {
  left: number;
  top: number;
  size: number;
  delay: number;
  duration: number;
  opacity: number;
  hue: number;
}

/** 确定性种子 PRNG（纯函数，满足渲染纯度要求，粒子位置稳定可复现） */
function mulberry32(seed: number) {
  return function () {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Theme 3: AI Awakening — 电影字幕感 + 逐字渐显 + 粒子背景 */
export function AIAwakeningTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  // 粒子一次性生成（性能优先：固定数量、纯 CSS 动画、确定性种子）
  const particles = useMemo<Particle[]>(() => {
    const rand = mulberry32(20260801);
    const list: Particle[] = [];
    for (let i = 0; i < 28; i++) {
      list.push({
        left: rand() * 100,
        top: rand() * 100,
        size: 2 + rand() * 3,
        delay: rand() * 6,
        duration: 6 + rand() * 8,
        opacity: 0.25 + rand() * 0.45,
        hue: rand() < 0.5 ? 217 : 265,
      });
    }
    return list;
  }, []);

  const letters = title.split("");

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      style={{ position: "relative", width: "100%", maxWidth: "680px", margin: "0 auto", textAlign: "center" }}
    >
      {/* 粒子背景 */}
      {animated && (
        <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
          {particles.map((p, i) => (
            <span
              key={i}
              style={{
                position: "absolute",
                left: `${p.left}%`,
                top: `${p.top}%`,
                width: p.size,
                height: p.size,
                borderRadius: "50%",
                background: `hsl(${p.hue}, 90%, 65%)`,
                opacity: p.opacity,
                boxShadow: `0 0 ${p.size * 3}px hsl(${p.hue}, 90%, 65%)`,
                animation: "heroParticleFloat 10s ease-in-out infinite",
                animationDelay: `${p.delay}s`,
                animationDuration: `${p.duration}s`,
              }}
            />
          ))}
        </div>
      )}

      {/* 电影字幕：逐字母渐显上浮 */}
      <div style={{ marginBottom: 16, minHeight: 64 }}>
        {letters.map((letter, i) => (
          <motion.span
            key={`${letter}-${i}`}
            initial={{ opacity: 0, y: 14, filter: "blur(6px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            transition={{ duration: 0.5, delay: 0.15 + i * 0.06, ease: "easeOut" }}
            style={{
              display: "inline-block",
              fontSize: 48,
              fontWeight: 800,
              letterSpacing: "0.02em",
              color: TITLE_COLORS[i % TITLE_COLORS.length],
              background: `linear-gradient(180deg, ${TITLE_COLORS[i % TITLE_COLORS.length]} 0%, ${TITLE_COLORS[(i + 1) % TITLE_COLORS.length]} 100%)`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            {letter}
          </motion.span>
        ))}
      </div>

      {/* 字幕式欢迎语 */}
      {welcome && (
        <motion.p
          initial={{ opacity: 0, letterSpacing: "0.6em" }}
          animate={{ opacity: 1, letterSpacing: "0.3em" }}
          transition={{ duration: 1.2, delay: 0.6 + letters.length * 0.06 }}
          style={{
            margin: 0,
            fontSize: 14,
            fontWeight: 600,
            textTransform: "uppercase",
            color: "var(--text-level-3)",
          }}
        >
          {welcome}
        </motion.p>
      )}
      {subtext && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 1.1 + letters.length * 0.06 }}
          style={{
            margin: "8px 0 0 0",
            fontSize: 12,
            color: "var(--text-level-4)",
          }}
        >
          {subtext}
        </motion.p>
      )}

      {/* 底部循环字幕 */}
      {animated && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.6, 0.6, 0] }}
          transition={{ duration: 3.5, delay: 1.5 + letters.length * 0.06 }}
          style={{
            margin: "18px 0 0 0",
            fontSize: 11,
            letterSpacing: "0.45em",
            textTransform: "uppercase",
            color: "var(--color-primary)",
          }}
        >
          Awakening Intelligence
        </motion.p>
      )}
    </motion.div>
  );
}
