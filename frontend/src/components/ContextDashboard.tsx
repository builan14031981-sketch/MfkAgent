"use client";

import { memo, useMemo } from "react";
import { AlertTriangle, Minimize2, Loader2 } from "lucide-react";
import type { TokenUsageEvent } from "@/types/runtime";
import { useTranslation } from "@/hooks/useTranslation";

const WARNING_THRESHOLD = 40;

/** 将 token 数格式化为紧凑展示（>= 1000 → k 单位） */
function formatTokens(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return "0";
  if (n >= 1000) {
    const k = n / 1000;
    return `${k >= 100 ? Math.round(k) : Math.round(k * 10) / 10}k`;
  }
  return String(n);
}

/** 环形进度圈 SVG 参数 */
const RING_RADIUS = 16;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS; // ≈ 100.5
const RING_SIZE = 40; // SVG viewBox 尺寸
const RING_STROKE_WIDTH = 3.5;

interface RingProgressProps {
  ratio: number; // 0-100
  color: string;
  label: string;
}

/** SVG 环形进度圈 */
const RingProgress = memo(function RingProgress({ ratio, color, label }: RingProgressProps) {
  const offset = RING_CIRCUMFERENCE * (1 - ratio / 100);
  const cx = RING_SIZE / 2;
  const cy = RING_SIZE / 2;

  return (
    <div title={label} style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
      <svg
        width={RING_SIZE}
        height={RING_SIZE}
        viewBox={`0 0 ${RING_SIZE} ${RING_SIZE}`}
        style={{ transform: "rotate(-90deg)" }}
      >
        {/* 背景轨道 */}
        <circle
          cx={cx}
          cy={cy}
          r={RING_RADIUS}
          fill="none"
          stroke="var(--bg-level-2)"
          strokeWidth={RING_STROKE_WIDTH}
        />
        {/* 进度弧 */}
        <circle
          cx={cx}
          cy={cy}
          r={RING_RADIUS}
          fill="none"
          stroke={color}
          strokeWidth={RING_STROKE_WIDTH}
          strokeLinecap="round"
          strokeDasharray={RING_CIRCUMFERENCE}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.4s ease, stroke 0.3s ease" }}
        />
      </svg>
    </div>
  );
});

interface ContextDashboardProps {
  /** G6-A 最新 token_usage 事件；null 时不渲染仪表盘 */
  usage: TokenUsageEvent | null;
  /** 压缩回调：点击「压缩会话」按钮时触发 */
  onCompress?: () => void;
  /** 压缩是否进行中 */
  isCompressing?: boolean;
}

/**
 * F-Context 上下文仪表盘：展示当前会话 Token 消耗与上下文水位。
 * - SVG 环形进度圈 + 中心百分比数字
 * - 颜色随水位变化：< 30% 绿色；30%-40% 橙色；> 40% 红色
 * - 水位 >= 40% 时显示「压缩会话」预警按钮（G6-B 阶段接入真实逻辑）
 */
export const ContextDashboard = memo(function ContextDashboard({ usage, onCompress, isCompressing = false }: ContextDashboardProps) {
  const { t } = useTranslation();

  const ratio = useMemo(() => {
    if (!usage || !usage.model_max_tokens) return null;
    const pct =
      usage.watermark_percentage != null
        ? usage.watermark_percentage
        : Math.round((usage.total_tokens / usage.model_max_tokens) * 100);
    return Math.min(100, Math.max(0, pct));
  }, [usage]);

  if (!usage || ratio == null) return null;

  const color =
    ratio >= WARNING_THRESHOLD
      ? "var(--color-error)"
      : ratio >= 30
        ? "var(--color-warning)"
        : "var(--color-success)";

  const label = `${t("chat.context.dashboard")}: ${formatTokens(usage.total_tokens)} / ${formatTokens(usage.model_max_tokens)} (${ratio}%)`;
  const showWarning = ratio >= WARNING_THRESHOLD;

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: "8px",
      padding: "4px 8px",
      borderRadius: "var(--radius-full)",
      background: "var(--bg-level-3)",
    }}>
      {/* 环形进度圈 + 文案 */}
      <div style={{ display: "flex", alignItems: "center", gap: "7px" }}>
        <RingProgress ratio={ratio} color={color} label={label} />
        <span style={{
          fontSize: "11px",
          lineHeight: 1,
          color: "var(--text-level-3)",
          fontVariantNumeric: "tabular-nums",
          whiteSpace: "nowrap",
        }}>{label}</span>
      </div>

      {/* 40% 水位预警：仅提示 + 压缩按钮（G6-B 阶段实现真实压缩逻辑） */}
      {showWarning && (
        <>
          <span style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            fontSize: "11px",
            fontWeight: 600,
            lineHeight: 1,
            color: "var(--color-error)",
            whiteSpace: "nowrap",
          }}>
            <AlertTriangle style={{ width: "12px", height: "12px", flexShrink: 0 }} />
            {t("chat.context.warning", { pct: String(ratio) })}
          </span>
          <button
            onClick={onCompress}
            disabled={isCompressing}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: "3px 10px",
              borderRadius: "var(--radius-full)",
              border: "1px solid color-mix(in srgb, var(--color-error) 45%, transparent)",
              background: isCompressing
                ? "color-mix(in srgb, var(--color-error) 20%, var(--bg-level-3))"
                : "color-mix(in srgb, var(--color-error) 10%, var(--bg-level-3))",
              color: "var(--color-error)",
              cursor: isCompressing ? "not-allowed" : "pointer",
              fontSize: "11px",
              fontWeight: 600,
              lineHeight: 1,
              whiteSpace: "nowrap",
              transition: "background 0.2s ease",
              opacity: isCompressing ? 0.7 : 1,
            }}
            onMouseEnter={(e) => {
              if (isCompressing) return;
              e.currentTarget.style.background = "color-mix(in srgb, var(--color-error) 20%, var(--bg-level-3))";
            }}
            onMouseLeave={(e) => {
              if (isCompressing) return;
              e.currentTarget.style.background = "color-mix(in srgb, var(--color-error) 10%, var(--bg-level-3))";
            }}
          >
            {isCompressing ? (
              <Loader2 style={{ width: "12px", height: "12px", flexShrink: 0, animation: "spin 1s linear infinite" }} />
            ) : (
              <Minimize2 style={{ width: "12px", height: "12px", flexShrink: 0 }} />
            )}
            {isCompressing ? t("chat.context.compressing") : t("chat.context.compress")}
          </button>
        </>
      )}
    </div>
  );
});
