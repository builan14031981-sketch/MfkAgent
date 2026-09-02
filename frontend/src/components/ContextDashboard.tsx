"use client";

import { memo, useMemo, useState } from "react";
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

/** 上下文分类中文标签映射（对标 Z code 上下文面板） */
const BREAKDOWN_LABELS: Record<string, string> = {
  system_prompt: "系统提示词",
  tools: "工具定义",
  memory: "记忆",
  messages: "消息",
  reminder: "轮次提醒",
  other: "其他",
};

/** 上下文分类配色（统一中性色，避免花花绿绿） */
const BREAKDOWN_COLORS: Record<string, string> = {
  system_prompt: "var(--text-level-2)",
  tools: "var(--text-level-2)",
  memory: "var(--text-level-2)",
  messages: "var(--text-level-2)",
  reminder: "var(--text-level-2)",
  other: "var(--text-level-2)",
};

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
    <div style={{ display: "flex", alignItems: "center", flexShrink: 0, cursor: "default" }}>
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
  /** 会话级累计：前缀缓存命中 token 总数（平均命中率分子） */
  totalCachedTokens?: number;
  /** 会话级累计：prompt token 总数（平均命中率分母） */
  totalPromptTokens?: number;
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
 * - 2026-09-01 新增：前缀缓存命中率环（青色）、平均缓存命中率、hover 展开上下文分类占比面板（对标 Z code）
 */
export const ContextDashboard = memo(function ContextDashboard({ usage, totalCachedTokens = 0, totalPromptTokens = 0, onCompress, isCompressing = false }: ContextDashboardProps) {
  const { t } = useTranslation();
  const [showBreakdown, setShowBreakdown] = useState(false);

  const ratio = useMemo(() => {
    if (!usage || !usage.model_max_tokens) return 0;
    const pct =
      usage.watermark_percentage != null
        ? usage.watermark_percentage
        : Math.round((usage.total_tokens / usage.model_max_tokens) * 100);
    return Math.min(100, Math.max(0, pct));
  }, [usage]);

  // 工单E：前缀缓存命中率环（cached_tokens / prompt_tokens）
  const hitRatio = useMemo(() => {
    if (!usage || !usage.cached_tokens || !usage.prompt_tokens) return null;
    const pct = Math.round((usage.cached_tokens / usage.prompt_tokens) * 100);
    return Math.min(100, Math.max(0, pct));
  }, [usage]);

  // 平均缓存命中率（会话级累计：totalCached / totalPrompt）
  const avgHitRatio = useMemo(() => {
    if (totalPromptTokens <= 0) return null;
    const pct = Math.round((totalCachedTokens / totalPromptTokens) * 100);
    return Math.min(100, Math.max(0, pct));
  }, [totalCachedTokens, totalPromptTokens]);

  // 上下文分类占比（仅当 context_breakdown 存在且有数据时计算）
  const breakdownItems = useMemo(() => {
    if (!usage?.context_breakdown) return [];
    const entries = Object.entries(usage.context_breakdown)
      .filter(([, v]) => v > 0)
      .sort((a, b) => b[1] - a[1]);
    const total = entries.reduce((sum, [, v]) => sum + v, 0);
    if (total <= 0) return [];
    return entries.map(([key, value]) => ({
      key,
      label: BREAKDOWN_LABELS[key] || key,
      color: BREAKDOWN_COLORS[key] || "#9ca3af",
      tokens: value,
      percent: Math.round((value / total) * 100),
    }));
  }, [usage?.context_breakdown]);

  const color =
    ratio >= WARNING_THRESHOLD
      ? "var(--color-error)"
      : ratio >= 30
        ? "var(--color-warning)"
        : "var(--color-primary)";

  // 缓存命中率来源标注：api=网关真实返回；estimated=稳定前缀估算（网关不返回缓存字段时的 fallback）
  const cacheSourceLabel = usage?.cache_source === "estimated"
    ? "（前缀复用率估算）"
    : usage?.cache_source === "api"
      ? ""
      : "";

  const label = usage
    ? `${t("chat.context.dashboard")}: ${formatTokens(usage.total_tokens)} / ${formatTokens(usage.model_max_tokens)} (${ratio}%)${hitRatio != null ? ` | 本轮缓存命中 ${formatTokens(usage.cached_tokens!)} / ${formatTokens(usage.prompt_tokens)} (${hitRatio}%)${cacheSourceLabel}` : ""}${avgHitRatio != null ? ` | 平均缓存命中率 ${avgHitRatio}%` : ""}`
    : `${t("chat.context.dashboard")}: 发送消息后显示 (${ratio}%)`;
  const cacheLabel = usage
    ? `本轮前缀缓存命中: ${formatTokens(usage.cached_tokens!)} / ${formatTokens(usage.prompt_tokens)} prompt tokens (${hitRatio}%)${cacheSourceLabel}${avgHitRatio != null ? ` | 会话平均: ${avgHitRatio}% (${formatTokens(totalCachedTokens)} / ${formatTokens(totalPromptTokens)})` : ""}`
    : `本轮前缀缓存命中: 发送消息后显示`;
  const showWarning = ratio >= WARNING_THRESHOLD;
  const hasBreakdown = breakdownItems.length > 0;

  return (
    <div
      style={{ position: "relative", display: "flex", alignItems: "center" }}
      onMouseEnter={() => hasBreakdown && setShowBreakdown(true)}
      onMouseLeave={() => setShowBreakdown(false)}
    >
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
          {usage ? `${formatTokens(usage.total_tokens)} / ${formatTokens(usage.model_max_tokens)}` : "-- / --"}
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

      {/* hover 展开：上下文分类占比面板（对标 Z code 上下文容量面板） */}
      {showBreakdown && hasBreakdown && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            right: 0,
            zIndex: 1000,
            minWidth: "200px",
            padding: "8px 10px",
            borderRadius: "var(--radius-md)",
            background: "var(--bg-level-4)",
            border: "1px solid var(--border-primary)",
            boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
            fontSize: "12px",
            color: "var(--text-level-1)",
            pointerEvents: "none",
          }}
        >
          {/* 标题行：仅 token 数/上限/百分比，右对齐 */}
          <div style={{
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            marginBottom: "6px",
          }}>
            <span style={{ color: "var(--text-level-2)", fontVariantNumeric: "tabular-nums", fontSize: "11px" }}>
              {usage ? `${formatTokens(usage.total_tokens)} / ${formatTokens(usage.model_max_tokens)} (${ratio}%)` : `-- / -- (${ratio}%)`}
            </span>
          </div>

          {/* 分类占比列表 */}
          <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
            {breakdownItems.map((item) => (
              <div key={item.key} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                {/* 分类名 */}
                <span style={{
                  width: "56px",
                  color: "var(--text-level-3)",
                  flexShrink: 0,
                  fontSize: "11px",
                }}>
                  {item.label}
                </span>
                {/* 占比进度条 */}
                <div style={{
                  flex: 1,
                  height: "4px",
                  background: "var(--bg-level-2)",
                  borderRadius: "2px",
                  overflow: "hidden",
                }}>
                  <div style={{
                    width: `${item.percent}%`,
                    height: "100%",
                    background: item.color,
                    borderRadius: "2px",
                    transition: "width 0.3s ease",
                  }} />
                </div>
                {/* 百分比 */}
                <span style={{
                  width: "36px",
                  textAlign: "right",
                  color: "var(--text-level-2)",
                  fontVariantNumeric: "tabular-nums",
                  fontSize: "11px",
                  flexShrink: 0,
                }}>
                  {item.percent}%
                </span>
              </div>
            ))}
          </div>

          {/* 底部：平均缓存命中率（仅当有数据时显示） */}
          {avgHitRatio != null && (
            <div style={{
              marginTop: "6px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}>
              <span style={{ color: "var(--text-level-3)", fontSize: "11px" }}>平均缓存命中率</span>
              <span style={{
                color: "var(--text-level-1)",
                fontWeight: 600,
                fontVariantNumeric: "tabular-nums",
                fontSize: "11px",
              }}>
                {avgHitRatio}%
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
});
