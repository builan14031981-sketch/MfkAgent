"use client";

import { useState, useEffect } from "react";
import type { CSSProperties } from "react";

/** 确定性种子 PRNG（渲染期生成装饰数据用，满足渲染纯度要求） */
export function mulberry32(seed: number) {
  return function () {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * 打字机效果 Hook：
 * - 逐字符推进，速率 speed ms/字符
 * - startDelay 延迟启动（用于脚本化多行输出序列）
 * - 自动清理定时器，卸载即停（性能友好）
 */
export function useTypewriter(text: string, speed = 24, startDelay = 0) {
  const [count, setCount] = useState(0);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!text) {
      const t = setTimeout(() => setDone(true), 0);
      return () => clearTimeout(t);
    }
    let interval: ReturnType<typeof setInterval> | undefined;
    const startTimer = setTimeout(() => {
      setCount(0);
      setDone(false);
      interval = setInterval(() => {
        setCount((c) => {
          if (c >= text.length) {
            if (interval) clearInterval(interval);
            setDone(true);
            return c;
          }
          return c + 1;
        });
      }, speed);
    }, startDelay);

    return () => {
      clearTimeout(startTimer);
      if (interval) clearInterval(interval);
    };
  }, [text, speed, startDelay]);

  return { text: text.slice(0, count), done };
}

interface TypewriterLineProps {
  text: string;
  /** 延迟开始（ms），用于脚本化行序列 */
  delay?: number;
  speed?: number;
  color?: string;
  /** 渲染完成前占位保持行高 */
  block?: boolean;
  style?: CSSProperties;
}

/** 单行打字输出（终端类主题共用），未开始前占位保持布局稳定 */
export function TypewriterLine({ text, delay = 0, speed = 24, color, block = true, style }: TypewriterLineProps) {
  const { text: typed, done } = useTypewriter(text, speed, delay);

  return (
    <div
      style={{
        minHeight: block && !done ? "1.5em" : undefined,
        color,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
        ...style,
      }}
    >
      {typed}
      {!done && <span style={{ display: "inline-block", width: "0.6em", height: "1.1em", verticalAlign: "text-bottom", background: "currentColor", animation: "heroCursor 1s steps(1) infinite" }} />}
    </div>
  );
}
