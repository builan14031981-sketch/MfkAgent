"use client";

import { useEffect, useState } from "react";
import { HelpCircle } from "lucide-react";
import type { UserChoiceRequest } from "@/types/runtime";
import { useTranslation } from "@/hooks/useTranslation";

interface UserChoiceCardProps {
  choice: UserChoiceRequest;
  /** 兼容保留：V3.2 起此卡仅作为对话流里的极简只读记录，交互统一由底部 UserChoiceComposer 接管 */
  onSelect?: (choiceId: string, selected: number) => void;
  onCustomText?: (choiceId: string, text: string) => void;
  onSkip?: (choiceId: string) => void;
}

/** 抉择记录（V3.2 极简一行版）：
 *  - 交互（选项/自定义/跳过）由底部输入框区域的 UserChoiceComposer 承担，消息流不再重复大卡片
 *  - 待选择时：仅一行提示「AI 正在等你选择…」+ 后端 300s 超时剩余时间倒计时
 *  - 已解决后：一行只读记录「问题摘要 · 已选择/已跳过」
 *  - 倒计时与后端 CHOICE_TIMEOUT=300s 对齐：超时后由后端自动采纳推荐项
 */
const CHOICE_TIMEOUT_MS = 300 * 1000;

function useChoiceCountdown(choice: UserChoiceRequest): number | null {
  const [remaining, setRemaining] = useState<number | null>(null);
  const resolved = choice.resolvedAction != null;
  useEffect(() => {
    if (resolved) return;
    const startedAt = choice.created_at
      ? new Date(choice.created_at).getTime()
      : Date.now();
    const update = () => {
      const left = startedAt + CHOICE_TIMEOUT_MS - Date.now();
      setRemaining(left > 0 ? Math.ceil(left / 1000) : 0);
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [choice.choice_id, resolved, choice.created_at]);
  return remaining;
}

function formatRemaining(sec: number): string {
  if (sec >= 60) return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
  return `${sec}s`;
}

export function UserChoiceCard({ choice }: UserChoiceCardProps) {
  const { t } = useTranslation();
  const remaining = useChoiceCountdown(choice);
  const isResolved = choice.resolvedAction != null;
  const resolvedKind = choice.resolvedAction?.kind;
  const selectedIdx = resolvedKind === "selected" ? choice.resolvedAction?.selected : null;
  const selectedLabel =
    selectedIdx != null ? choice.options[selectedIdx]?.label : null;

  const actionText =
    resolvedKind === "selected"
      ? selectedLabel
        ? `${t("chat.choiceResolvedSelected")}：${selectedLabel}`
        : t("chat.choiceResolvedSelected")
      : resolvedKind === "skipped"
      ? t("chat.choiceResolvedSkipped")
      : t("chat.choiceResolvedTimeout");

  const countdownText =
    remaining != null && remaining <= 30
      ? ` · ${remaining <= 0 ? "即将自动采纳" : `${formatRemaining(remaining)} 后自动采纳`}`
      : "";

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: "7px",
      padding: "6px 10px",
      borderRadius: "var(--radius-md)",
      background: isResolved ? "var(--bg-level-3)" : "var(--bg-level-3)",
      border: "1px solid",
      borderColor: remaining != null && remaining <= 30 && !isResolved
        ? "color-mix(in srgb, var(--color-warning) 55%, var(--border-primary))"
        : "var(--border-primary)",
      color: isResolved ? "var(--text-level-3)" : "var(--text-level-2)",
      fontSize: "11.5px",
      lineHeight: 1.4,
      minHeight: "30px",
    }}>
      <HelpCircle style={{
        width: "13px",
        height: "13px",
        color: isResolved ? "var(--text-level-3)" : "var(--color-primary)",
        flexShrink: 0,
      }} />
      <span style={{
        flex: 1,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}>
        {isResolved
          ? t("chat.choiceResolvedLine", {
              question: choice.question,
              action: actionText,
            })
          : `${t("chat.choiceWaiting")}${countdownText}`}
      </span>
    </div>
  );
}
