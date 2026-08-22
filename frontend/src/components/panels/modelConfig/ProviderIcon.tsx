"use client";

import type { CSSProperties } from "react";
import {
  siDeepseek,
  siGoogle,
  siBaidu,
  siXiaomi,
  siMinimax,
  siQwen,
  siAlibabacloud,
  siMoonshotai,
} from "simple-icons";

/**
 * ProviderIcon —— 厂商品牌图标组件
 *
 * 优先使用 simple-icons 官方 SVG logo（配合品牌色），
 * 未收录的厂商用精致的品牌色圆角方块 + 首字母兜底。
 *
 * 用法：
 *   <ProviderIcon providerId="deepseek" size={20} />
 */

interface SimpleIconDef {
  path: string;
  hex: string;
}

/** simple-icons 官方图标映射（品牌色 + SVG path） */
const SIMPLE_ICONS: Record<string, SimpleIconDef> = {
  deepseek: { path: siDeepseek.path, hex: siDeepseek.hex },
  google: { path: siGoogle.path, hex: siGoogle.hex },
  baidu: { path: siBaidu.path, hex: siBaidu.hex },
  xiaomi: { path: siXiaomi.path, hex: siXiaomi.hex },
  minimax: { path: siMinimax.path, hex: siMinimax.hex },
  qwen: { path: siQwen.path, hex: siQwen.hex },
  alibaba: { path: siAlibabacloud.path, hex: siAlibabacloud.hex },
  moonshot: { path: siMoonshotai.path, hex: siMoonshotai.hex },
  wenxin: { path: siBaidu.path, hex: siBaidu.hex }, // 百度文心复用百度 logo
  mimo: { path: siXiaomi.path, hex: siXiaomi.hex }, // 小米 MiMo 复用小米 logo
};

/** 兜底样式：品牌色 + 首字母（精致圆角方块） */
const FALLBACK_STYLES: Record<string, { bg: string; label: string }> = {
  openai: { bg: "#10A37F", label: "O" },
  anthropic: { bg: "#D97757", label: "A" },
  doubao: { bg: "#3370FF", label: "豆" },
  hunyuan: { bg: "#0052D9", label: "混" },
  openrouter: { bg: "#FF7000", label: "OR" },
  glm: { bg: "#1E88E5", label: "智" },
  zhipu: { bg: "#1E88E5", label: "智" },
  spark: { bg: "#003DA6", label: "讯" },
  iflytek: { bg: "#003DA6", label: "讯" },
  siliconflow: { bg: "#00B3A0", label: "硅" },
  freellmapi: { bg: "#6B7280", label: "F" },
};

const DEFAULT_FALLBACK = { bg: "#6B7280", label: "?" };

export interface ProviderIconProps {
  /** 厂商 ID（如 "deepseek"、"qwen"、"glm"） */
  providerId: string;
  /** 图标尺寸（px），默认 20 */
  size?: number;
  /** 自定义样式 */
  style?: CSSProperties;
}

export function ProviderIcon({ providerId, size = 20, style }: ProviderIconProps) {
  // 优先用 simple-icons 官方 SVG
  const icon = SIMPLE_ICONS[providerId];
  if (icon) {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: `${size}px`,
          height: `${size}px`,
          borderRadius: "6px",
          background: `#${icon.hex}`,
          flexShrink: 0,
          ...style,
        }}
        title={providerId}
      >
        <svg
          width={size * 0.6}
          height={size * 0.6}
          viewBox="0 0 24 24"
          fill="#FFFFFF"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path d={icon.path} />
        </svg>
      </span>
    );
  }

  // 兜底：品牌色 + 首字母
  const fb = FALLBACK_STYLES[providerId] || DEFAULT_FALLBACK;
  const fontSize = Math.max(8, Math.floor(size * 0.45));

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: `${size}px`,
        height: `${size}px`,
        borderRadius: "6px",
        background: fb.bg,
        color: "#FFFFFF",
        fontSize: `${fontSize}px`,
        fontWeight: 700,
        fontFamily: "system-ui, -apple-system, sans-serif",
        lineHeight: 1,
        flexShrink: 0,
        userSelect: "none",
        ...style,
      }}
      title={providerId}
    >
      {fb.label}
    </span>
  );
}
