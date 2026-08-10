"use client";

import { useEffect, useRef } from "react";

export interface VoiceOrb2DProps {
  /** 是否处于录音/说话状态（true=波浪微幅变形；false=静态呼吸） */
  isActive: boolean;
  /** 是否正在转写（true=加载脉冲态） */
  isTranscribing?: boolean;
  /** 点击回调（由父组件决定开始/停止录音） */
  onClick?: () => void;
  /** 透传样式（位置/布局由父组件控制） */
  style?: React.CSSProperties;
  /** 无障碍标题 */
  title?: string;
  /** 是否禁用 */
  disabled?: boolean;
}

/** 逻辑尺寸（px） */
const SIZE = 28;
/** 球体基础半径（px），预留 ≤3px 振幅空间不超出画布 */
const BASE_R = 9;
/** 录音波纹振幅上限（px），严格锁定 2~3px，极为柔和 */
const WAVE_AMP = 2.5;
/** 呼吸最大缩放（极淡，0.96 ↔ 1.0） */
const IDLE_BREATH = 0.04;

/**
 * 2D 轻量语音小球（Canvas 2D 渲染，28×28）。
 *
 * 视觉规格：
 * - Idle：径向渐变静态小球 + 极淡呼吸动画（缩放 0.96↔1.0，周期 ~2.8s）。
 * - 录音/说话：边缘波浪微幅变形，振幅严格 2~3px，双正弦叠加营造柔和起伏。
 * - 转写中：呼吸加快 + 轻微脉冲，提示后台处理。
 *
 * 渲染采用 devicePixelRatio 缩放保证高清；rAF 驱动动画，组件卸载自动清理。
 */
export function VoiceOrb2D({
  isActive,
  isTranscribing = false,
  onClick,
  style,
  title,
  disabled = false,
}: VoiceOrb2DProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const startTsRef = useRef<number>(0);
  // 用 ref 承载最新 props，避免每帧重建 rAF 闭包
  const stateRef = useRef({ isActive, isTranscribing });
  stateRef.current = { isActive, isTranscribing };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2.5));
    canvas.width = Math.round(SIZE * dpr);
    canvas.height = Math.round(SIZE * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    startTsRef.current = performance.now();

    const draw = (now: number) => {
      const t = (now - startTsRef.current) / 1000; // 秒
      const { isActive: rec, isTranscribing: trans } = stateRef.current;
      const cx = SIZE / 2;
      const cy = SIZE / 2;

      ctx.clearRect(0, 0, SIZE, SIZE);

      // ── 状态派生参数 ──
      // 呼吸缩放：idle 极淡 2.8s；transcribing 加快到 1.1s 并加深幅度
      const breathPeriod = trans ? 1.1 : 2.8;
      const breathAmp = trans ? 0.06 : IDLE_BREATH;
      const breath = 1 - breathAmp * (0.5 - 0.5 * Math.cos((2 * Math.PI * t) / breathPeriod));

      // 主色（沿用主题变量，回退到硬编码保证可见）
      const primary = readCssVar("--color-primary", "#4f8cff");
      const primaryHover = readCssVar("--color-primary-hover", primary);
      const baseR = BASE_R;

      // ── 描边路径（idle=圆；recording=波浪圆）──
      ctx.beginPath();
      const steps = 96;
      if (rec) {
        // 双正弦叠加波浪，振幅严格锁定 WAVE_AMP
        const omega = 3.2; // 角速度
        for (let i = 0; i <= steps; i++) {
          const a = (i / steps) * Math.PI * 2;
          const wave =
            Math.sin(5 * a + omega * t) * 0.5 +
            Math.sin(7 * a - omega * t * 0.8) * 0.5;
          const r = (baseR * breath) + WAVE_AMP * wave;
          const x = cx + r * Math.cos(a);
          const y = cy + r * Math.sin(a);
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
      } else {
        // 静态圆（含呼吸缩放）
        const r = baseR * breath;
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
      }
      ctx.closePath();

      // ── 径向渐变填充 ──
      const grad = ctx.createRadialGradient(
        cx - baseR * 0.35,
        cy - baseR * 0.35,
        baseR * 0.1,
        cx,
        cy,
        baseR * 1.15,
      );
      if (rec || trans) {
        grad.addColorStop(0, lighten(primaryHover, 0.25));
        grad.addColorStop(0.6, primaryHover);
        grad.addColorStop(1, primary);
      } else {
        grad.addColorStop(0, lighten(primary, 0.2));
        grad.addColorStop(0.65, primary);
        grad.addColorStop(1, darken(primary, 0.12));
      }
      ctx.fillStyle = grad;
      ctx.fill();

      // ── 高光点（增加精致立体感）──
      ctx.beginPath();
      ctx.arc(cx - baseR * 0.35, cy - baseR * 0.4, baseR * 0.28, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255,255,255,0.35)";
      ctx.fill();

      // ── 录音中：外圈柔光晕（极淡，提示活跃态）──
      if (rec) {
        const halo = 0.5 + 0.5 * Math.sin(2 * Math.PI * t / 1.4);
        ctx.beginPath();
        ctx.arc(cx, cy, baseR + 2 + halo * 1.5, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(79,140,255,${0.12 + halo * 0.12})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, []);

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
      style={{
        width: `${SIZE}px`,
        height: `${SIZE}px`,
        padding: 0,
        border: "none",
        background: "transparent",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.4 : 1,
        outline: "none",
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transition: "opacity 0.2s ease",
        ...style,
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          width: `${SIZE}px`,
          height: `${SIZE}px`,
          display: "block",
          pointerEvents: "none",
        }}
      />
    </button>
  );
}

/** 读取 CSS 变量值，失败回退默认值 */
function readCssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  try {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  } catch {
    return fallback;
  }
}

/** 颜色加亮（支持 #hex / rgb()），factor 0~1 */
function lighten(color: string, factor: number): string {
  return shift(color, factor);
}

/** 颜色加深，factor 0~1 */
function darken(color: string, factor: number): string {
  return shift(color, -factor);
}

/** 通用明度偏移：正数加亮、负数加深 */
function shift(color: string, factor: number): string {
  const rgb = parseColor(color);
  if (!rgb) return color;
  const f = Math.max(-1, Math.min(1, factor));
  const apply = (c: number) => {
    if (f >= 0) return Math.round(c + (255 - c) * f);
    return Math.round(c * (1 + f));
  };
  return `rgb(${apply(rgb.r)}, ${apply(rgb.g)}, ${apply(rgb.b)})`;
}

/** 解析 #hex / rgb() 为 {r,g,b}，失败返回 null */
function parseColor(color: string): { r: number; g: number; b: number } | null {
  const s = (color || "").trim();
  // #hex
  const hexMatch = s.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hexMatch) {
    let h = hexMatch[1];
    if (h.length === 3) {
      h = h.split("").map((c) => c + c).join("");
    }
    const num = parseInt(h, 16);
    return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
  }
  // rgb()
  const rgbMatch = s.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
  if (rgbMatch) {
    return {
      r: parseInt(rgbMatch[1], 10),
      g: parseInt(rgbMatch[2], 10),
      b: parseInt(rgbMatch[3], 10),
    };
  }
  return null;
}
