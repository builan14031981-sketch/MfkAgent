"use client";

import { memo, useMemo } from "react";
import { Minimize2, Loader2 } from "lucide-react";
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

/** 环形进度圈 SVG 参数（2026-08-12 缩小：外径 20px/环宽 3px，中心孔 10px，减少空洞感） */
const RING_RADIUS = 8;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS; // ≈ 50.3
const RING_SIZE = 20; // SVG viewBox 尺寸
const RING_STROKE_WIDTH = 3;

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
    <div title={label} style={{ display: "flex", alignItems: "center", flexShrink: 0, cursor: "default" }}>
      <svg
        width={RING_SIZE}
        height={RING_SIZE}
        viewBox={`0 0 ${RING_SIZE} ${RING_SIZE}`}
        style={{ transform: "rotate(-90deg)" }}
      >
        {/* 背景轨道：必须与承载面（主内容区背景 --bg-level-2）有区分。
            2026-08-12 修复：原用 --bg-level-2，但 header 背景 transparent、环直接浮在主背景上，同色即隐形（用户报「全透明」）→ 改用 --border-primary */}
        <circle
          cx={cx}
          cy={cy}
          r={RING_RADIUS}
          fill="none"
          stroke="var(--border-primary)"
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
 * - 2026-08-12 极简化：仅一个 20px 环形进度圈，文字仅在 hover tooltip 展示（无感设计）
 * - 颜色随水位变化：< 30% 绿色；30%-40% 橙色；> 40% 红色
 * - 水位 >= 40% 时环右侧出现紧凑「压缩会话」按钮（保留功能可达性）
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
        : "var(--color-primary)";

  const label = `${t("chat.context.dashboard")}: ${formatTokens(usage.total_tokens)} / ${formatTokens(usage.model_max_tokens)} (${ratio}%)`;
  const showWarning = ratio >= WARNING_THRESHOLD;

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: "6px",
    }}>
      {/* 环形进度圈：hover 显示完整文案，默认态无文字 */}
      <RingProgress ratio={ratio} color={color} label={label} />
      {/* 上下文字数：已用 / 上限（11px 次级色，数字等宽防刷新抖动） */}
      <span
        style={{
          fontSize: "11px",
          color: "var(--text-level-3)",
          whiteSpace: "nowrap",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {formatTokens(usage.total_tokens)} / {formatTokens(usage.model_max_tokens)}
      </span>

      {/* 40% 水位预警：紧凑压缩按钮贴身环右侧（G6-B 压缩逻辑） */}
      {showWarning && (
        <button
          onClick={onCompress}
          disabled={isCompressing}
          title={label}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            padding: "3px 8px",
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
      )}
    </div>
  );
});
