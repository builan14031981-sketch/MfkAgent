"use client";

import type { OrbStage } from "@/lib/streamStore";
import { useTranslation } from "@/hooks/useTranslation";

interface AgentOrbProps {
  /** 加载阶段；null 时不渲染（未在流式） */
  stage: OrbStage | null;
  /** 直径（px）；默认 20 行内，头像场景可用 64 */
  size?: number;
  /** 可选覆盖 title 文案 */
  title?: string;
}

/**
 * Agent 流式加载指示器（V2 Quiet 版）。
 *
 * 设计原则：系统状态反馈，而非 AI 玩具表演——
 * 单色环形 spinner（灰阶轨道 + accent 弧段），无发光、无粒子、无彩色。
 * 阶段文案（aria-label/title）随 stage 走 i18n，语义保留。
 * stage 为 null 时返回 null。
 */
export function AgentOrb({ stage, size = 20, title }: AgentOrbProps) {
  const { t } = useTranslation();
  if (!stage) return null;

  const label =
    title ||
    (stage === "working"
      ? t("chat.orb.working")
      : stage === "solving"
        ? t("chat.orb.solving")
        : stage === "searching"
          ? t("chat.orb.searching")
          : stage === "listening"
            ? t("chat.orb.listening")
            : t("chat.orb.composing"));

  // 描边随尺寸微调：小尺寸 1.5px，大尺寸（头像级）2px
  const borderWidth = size >= 40 ? 2 : 1.5;

  return (
    <span
      role="status"
      aria-label={label}
      title={label}
      className="mf-spinner"
      style={{ width: size, height: size, borderWidth }}
    />
  );
}
