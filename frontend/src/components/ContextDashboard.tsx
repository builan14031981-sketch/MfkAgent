"use client";

import { memo, useMemo } from "react";
import { AlertTriangle, Minimize2 } from "lucide-react";
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

interface ContextDashboardProps {
  /** G6-A 最新 token_usage 事件；null 时不渲染仪表盘 */
  usage: TokenUsageEvent | null;
}

/**
 * F-Context 上下文仪表盘：展示当前会话 Token 消耗与上下文水位。
 * - 迷你进度条 + 「上下文: 35k / 128k (27%)」文案
 * - 颜色随水位变化：< 30% 绿色；30%-40% 橙色；> 40% 红色
 * - 水位 >= 40% 时显示「压缩会话」预警按钮（G6-B 阶段接入真实逻辑）
 */
export const ContextDashboard = memo(function ContextDashboard({ usage }: ContextDashboardProps) {
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
      {/* 迷你进度条 + 水位文案 */}
      <div
        title={label}
        style={{ display: "flex", alignItems: "center", gap: "6px" }}
      >
        <span style={{
          width: "64px",
          height: "6px",
          borderRadius: "var(--radius-full)",
          background: "color-mix(in srgb, var(--bg-level-2) 70%, transparent)",
          overflow: "hidden",
          flexShrink: 0,
        }}>
          <span style={{
            display: "block",
            width: `${ratio}%`,
            height: "100%",
            borderRadius: "var(--radius-full)",
            background: color,
            transition: "width 0.3s ease, background 0.3s ease",
          }} />
        </span>
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
            onClick={() => console.log("Trigger Compression")}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: "3px 10px",
              borderRadius: "var(--radius-full)",
              border: "1px solid color-mix(in srgb, var(--color-error) 45%, transparent)",
              background: "color-mix(in srgb, var(--color-error) 10%, var(--bg-level-3))",
              color: "var(--color-error)",
              cursor: "pointer",
              fontSize: "11px",
              fontWeight: 600,
              lineHeight: 1,
              whiteSpace: "nowrap",
              transition: "background 0.2s ease",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "color-mix(in srgb, var(--color-error) 20%, var(--bg-level-3))"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "color-mix(in srgb, var(--color-error) 10%, var(--bg-level-3))"; }}
          >
            <Minimize2 style={{ width: "12px", height: "12px", flexShrink: 0 }} />
            {t("chat.context.compress")}
          </button>
        </>
      )}
    </div>
  );
});
