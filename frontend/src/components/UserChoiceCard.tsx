"use client";

import { useState } from "react";
import { Check, X, HelpCircle, Star, SkipForward } from "lucide-react";
import type { UserChoiceRequest } from "@/types/runtime";
import { useTranslation } from "@/hooks/useTranslation";

interface UserChoiceCardProps {
  choice: UserChoiceRequest;
  /** 可选：内嵌卡片的回调（Phase 2 V2 由顶层 UserChoiceModal 接管主要交互，
   *  此处可省略，省略时点击 = noop。保留回调以兼容历史回放/独立使用场景。） */
  onSelect?: (choiceId: string, selected: number) => void;
  onCustomText?: (choiceId: string, text: string) => void;
  onSkip?: (choiceId: string) => void;
}

/** 抉择卡：ask_user_choice 工具的交互面板。
 *  - 选项列表（推荐项高亮 + ⭐ 标识）
 *  - 自定义输入框（allow_custom=true 时显示）
 *  - "跳过"按钮：用户主动不选，后端按"采纳推荐项"处理
 *  - 已解决时显示只读状态（"已选择"/"已跳过"/"已超时"）
 * 视觉对齐 ToolApprovalCard（同一外框/圆角/边框/字号体系）。
 */
export function UserChoiceCard({ choice, onSelect, onCustomText, onSkip }: UserChoiceCardProps) {
  const { t } = useTranslation();
  const [customText, setCustomText] = useState("");
  const isResolved = choice.resolvedAction != null;
  const resolvedKind = choice.resolvedAction?.kind;
  const selectedIdx = resolvedKind === "selected" ? choice.resolvedAction?.selected : null;
  const handleSelect = (idx: number) => onSelect?.(choice.choice_id, idx);
  const handleSkip = () => onSkip?.(choice.choice_id);
  const handleCustom = (text: string) => onCustomText?.(choice.choice_id, text);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      gap: "10px",
      marginBottom: "8px",
      padding: "12px 14px",
      borderRadius: "var(--radius-md)",
      background: isResolved
        ? "var(--bg-level-3)"
        : "color-mix(in srgb, var(--color-primary) 6%, var(--bg-level-3))",
      border: "2px solid",
      borderColor: isResolved
        ? "var(--border-primary)"
        : "color-mix(in srgb, var(--color-primary) 40%, var(--border-primary))",
      opacity: isResolved ? 0.7 : 1,
      transition: "opacity 0.3s ease, border-color 0.3s ease",
    }}>
      {/* 标题行：图标 + 标题 + 状态徽标 */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <HelpCircle style={{
          width: "14px",
          height: "14px",
          color: isResolved ? "var(--text-level-3)" : "var(--color-primary)",
          flexShrink: 0,
        }} />
        <span style={{
          fontSize: "13px",
          fontWeight: 700,
          color: isResolved ? "var(--text-level-3)" : "var(--text-level-1)",
          lineHeight: 1.25,
          flex: 1,
        }}>
          {t("chat.choiceTitle")}
        </span>
        {isResolved && (
          <span style={{
            flexShrink: 0,
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            padding: "1px 8px",
            borderRadius: "var(--radius-xs)",
            fontSize: "10px",
            fontWeight: 700,
            lineHeight: "18px",
            color: "#fff",
            background: resolvedKind === "skipped" || resolvedKind === "timeout"
              ? "var(--text-level-3)"
              : "var(--color-primary)",
            textTransform: "uppercase",
            letterSpacing: "0.5px",
          }}>
            {resolvedKind === "selected" ? <Check style={{ width: "10px", height: "10px" }} /> : <SkipForward style={{ width: "10px", height: "10px" }} />}
            {resolvedKind === "selected"
              ? t("chat.choiceResolvedSelected")
              : resolvedKind === "skipped"
              ? t("chat.choiceResolvedSkipped")
              : t("chat.choiceResolvedTimeout")}
          </span>
        )}
      </div>

      {/* 问题正文 */}
      <p style={{
        margin: 0,
        fontSize: "13px",
        lineHeight: 1.5,
        color: "var(--text-level-1)",
        fontWeight: 500,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}>
        {choice.question}
      </p>

      {/* 选项列表（已选时禁用） */}
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        {choice.options.map((opt, idx) => {
          const isRecommended = choice.recommended === idx;
          const isThisSelected = selectedIdx === idx;
          return (
            <button
              key={idx}
              disabled={isResolved}
              onClick={() => handleSelect(idx)}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "10px",
                padding: "10px 12px",
                borderRadius: "var(--radius-sm)",
                border: "1.5px solid",
                borderColor: isThisSelected
                  ? "var(--color-primary)"
                  : isRecommended
                  ? "color-mix(in srgb, var(--color-primary) 30%, var(--border-primary))"
                  : "var(--border-primary)",
                background: isThisSelected
                  ? "color-mix(in srgb, var(--color-primary) 10%, var(--bg-level-2))"
                  : isRecommended
                  ? "color-mix(in srgb, var(--color-primary) 4%, var(--bg-level-2))"
                  : "var(--bg-level-2)",
                cursor: isResolved ? "default" : "pointer",
                textAlign: "left",
                font: "inherit",
                color: "var(--text-level-1)",
                transition: "background 0.15s ease, border-color 0.15s ease",
              }}
              onMouseEnter={(e) => {
                if (isResolved) return;
                e.currentTarget.style.background = isThisSelected
                  ? "color-mix(in srgb, var(--color-primary) 14%, var(--bg-level-2))"
                  : "color-mix(in srgb, var(--color-primary) 6%, var(--bg-level-2))";
              }}
              onMouseLeave={(e) => {
                if (isResolved) return;
                e.currentTarget.style.background = isThisSelected
                  ? "color-mix(in srgb, var(--color-primary) 10%, var(--bg-level-2))"
                  : isRecommended
                  ? "color-mix(in srgb, var(--color-primary) 4%, var(--bg-level-2))"
                  : "var(--bg-level-2)";
              }}
            >
              <span style={{
                flexShrink: 0,
                marginTop: "1px",
                width: "18px",
                height: "18px",
                borderRadius: "var(--radius-full)",
                border: "2px solid",
                borderColor: isThisSelected
                  ? "var(--color-primary)"
                  : isRecommended
                  ? "color-mix(in srgb, var(--color-primary) 50%, var(--border-primary))"
                  : "var(--text-level-4)",
                background: isThisSelected ? "var(--color-primary)" : "transparent",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
              }}>
                {isThisSelected && <Check style={{ width: "11px", height: "11px" }} />}
              </span>
              <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: "2px", minWidth: 0 }}>
                <span style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  fontSize: "13px",
                  fontWeight: isRecommended ? 600 : 500,
                  lineHeight: 1.4,
                  color: isThisSelected ? "var(--color-primary)" : "var(--text-level-1)",
                }}>
                  {opt.label}
                  {isRecommended && !isThisSelected && (
                    <span style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "2px",
                      padding: "0 5px",
                      borderRadius: "var(--radius-xs)",
                      fontSize: "10px",
                      fontWeight: 600,
                      color: "var(--color-primary)",
                      background: "color-mix(in srgb, var(--color-primary) 12%, transparent)",
                      lineHeight: "16px",
                    }}>
                      <Star style={{ width: "9px", height: "9px" }} />
                      {t("chat.choiceRecommended")}
                    </span>
                  )}
                </span>
                {opt.description && (
                  <span style={{
                    fontSize: "12px",
                    lineHeight: 1.5,
                    color: "var(--text-level-3)",
                    wordBreak: "break-word",
                  }}>
                    {opt.description}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>

      {/* 自定义输入框（仅在 allow_custom=true 且未解决时显示） */}
      {choice.allow_custom && !isResolved && (
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <textarea
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            placeholder={t("chat.choiceCustomPlaceholder")}
            rows={2}
            style={{
              width: "100%",
              padding: "8px 10px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-2)",
              color: "var(--text-level-1)",
              fontSize: "12px",
              lineHeight: 1.5,
              fontFamily: "inherit",
              resize: "vertical",
              outline: "none",
              boxSizing: "border-box",
            }}
          />
          <button
            disabled={!customText.trim()}
            onClick={() => {
              const text = customText.trim();
              if (text) handleCustom(text);
            }}
            style={{
              alignSelf: "flex-start",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 14px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: customText.trim() ? "var(--bg-level-2)" : "var(--bg-level-2)",
              color: customText.trim() ? "var(--color-primary)" : "var(--text-level-4)",
              cursor: customText.trim() ? "pointer" : "not-allowed",
              fontSize: "12px",
              fontWeight: 600,
              transition: "background 0.15s ease, color 0.15s ease",
            }}
          >
            <Check style={{ width: "12px", height: "12px" }} />
            {t("chat.choiceSubmitCustom")}
          </button>
        </div>
      )}

      {/* 跳过按钮（仅在未解决时显示） */}
      {!isResolved && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "2px" }}>
          <button
            onClick={handleSkip}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "transparent",
              color: "var(--text-level-3)",
              cursor: "pointer",
              fontSize: "12px",
              fontWeight: 500,
              transition: "color 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--text-level-1)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--text-level-3)";
            }}
          >
            <SkipForward style={{ width: "12px", height: "12px" }} />
            {t("chat.choiceSkip")}
          </button>
        </div>
      )}
    </div>
  );
}
