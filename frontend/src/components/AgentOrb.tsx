"use client";

import { ThinkingOrb } from "thinking-orbs";
import type { OrbState } from "thinking-orbs";
import type { OrbStage } from "@/lib/streamStore";
import { useTranslation } from "@/hooks/useTranslation";

const STAGE_TO_ORB: Record<OrbStage, OrbState> = {
  working: "working",
  solving: "solving",
  searching: "searching",
  listening: "listening",
  composing: "composing",
};

interface AgentOrbProps {
  /** 加载阶段；null 时不渲染（未在流式） */
  stage: OrbStage | null;
  /** 尺寸预设：64（头像）或 20（行内） */
  size?: 64 | 20;
  /** 可选覆盖 title 文案 */
  title?: string;
}

/**
 * Agent 流式加载动画：封装 thinking-orbs 的 ThinkingOrb，
 * 阶段文案（aria-label/title）随 stage 走 i18n。
 * stage 为 null 时返回 null，避免渲染静态 orb。
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

  return (
    <ThinkingOrb
      state={STAGE_TO_ORB[stage]}
      size={size}
      theme="auto"
      aria-label={label}
      title={label}
    />
  );
}
