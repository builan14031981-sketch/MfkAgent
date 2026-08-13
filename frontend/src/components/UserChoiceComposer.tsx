"use client";

import { useState, useEffect } from "react";
import { Check, HelpCircle, Star, SkipForward } from "lucide-react";
import { useStreamStore } from "@/lib/streamStore";
import { useTranslation } from "@/hooks/useTranslation";
import type { UserChoiceRequest } from "@/types/runtime";
import { apiPost } from "@/lib/api";

/**
 * 内联抉择框（V3）：无感替换输入组合框。
 *
 * 设计意图（对齐产品"无感、不打断"铁律）：
 *  - 当 AI 提出抉择（ask_user_choice）时，输入框区域整体变成一个"选择框"，
 *    因为此刻用户不需要打字发新消息，输入端让位给选择交互。
 *  - 选择框一定比输入框更高（要容纳选项列表 + 自定义输入），占住输入框位置。
 *  - 用户点选项 / 输入自定义想法 / 跳过，选完即恢复输入框。
 *  - 对话记录里保留一条只读记录（由 MessageList 的 UserChoiceCard 呈现历史态）。
 *
 * 不再使用全屏 Modal（V2 的 createPortal + 遮罩 + blur 太"焦点式"）。
 *
 * V3.1：全套减档，目标高度 ≈ 当前 1/2；选项等高（minHeight）等间距（gap 5px）。
 */
export function UserChoiceComposer({
  choice,
  chatId,
}: {
  choice: UserChoiceRequest;
  chatId: number;
}) {
  const { t } = useTranslation();
  const [customText, setCustomText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // 当前选中的选项下标（点击仅选中，不提交；需按「确认」才提交）
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  // 进入/切换 choice 时清空输入框与选中
  useEffect(() => {
    setCustomText("");
    setSelectedIdx(null);
  }, [choice.choice_id]);

  /** 提交到后端 + 乐观标记已解决（弹窗恢复输入框，无需等待 SSE tool_result） */
  const submitChoice = async (params: {
    selected?: number | null;
    customText?: string | null;
    skip?: boolean;
  }) => {
    if (submitting) return;
    setSubmitting(true);
    const customText = params.skip
      ? "(用户跳过)"
      : (params.customText ?? "").trim() || null;
    try {
      await apiPost(`/api/chat/${chatId}/choice`, {
        choice_id: choice.choice_id,
        selected: params.skip ? null : params.selected ?? null,
        custom_text: customText,
      });
      const resolvedAction: UserChoiceRequest["resolvedAction"] = params.skip
        ? { kind: "skipped" }
        : { kind: "selected", selected: params.selected ?? 0 };
      useStreamStore.getState().updateSession(chatId, (prev) => ({
        timeline: prev.timeline.map((s) =>
          s.type === "user_choice" && s.choice.choice_id === choice.choice_id
            ? { ...s, choice: { ...s.choice, resolvedAction } }
            : s
        ),
      }));
    } catch (err) {
      console.error("UserChoiceComposer submit failed:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSelect = (idx: number) => setSelectedIdx((prev) => (prev === idx ? null : idx));
  const handleConfirm = () => {
    if (selectedIdx == null) return;
    submitChoice({ selected: selectedIdx });
  };
  const handleCustomSubmit = () => {
    const text = customText.trim();
    if (!text) return;
    submitChoice({ selected: null, customText: text });
  };
  const handleSkip = () => submitChoice({ skip: true });

  return (
    <div
      role="group"
      aria-label={t("chat.choiceTitle")}
      style={{
        width: "100%",
        maxWidth: "768px",
        margin: "0 auto",
        padding: "8px 16px",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          padding: "10px 12px",
          borderRadius: "var(--radius-2xl)",
          background: "var(--bg-level-2)",
          border: "1.5px solid color-mix(in srgb, var(--color-primary) 40%, var(--border-primary))",
          boxShadow: "0 8px 32px rgba(0,0,0,0.06)",
        }}
      >
        {/* 标题行：图标 + 标题 + 跳过按钮 */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div style={{
            flexShrink: 0,
            width: "20px",
            height: "20px",
            borderRadius: "var(--radius-md)",
            background: "color-mix(in srgb, var(--color-primary) 12%, var(--bg-level-3))",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}>
            <HelpCircle style={{ width: "14px", height: "14px", color: "var(--color-primary)" }} />
          </div>
          <span style={{
            flex: 1,
            fontSize: "12.5px",
            fontWeight: 700,
            color: "var(--text-level-1)",
            lineHeight: 1.3,
          }}>
            {t("chat.choiceTitle")}
          </span>
          <button
            onClick={handleSkip}
            disabled={submitting}
            title={t("chat.choiceSkip")}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: "3px 9px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: "transparent",
              color: "var(--text-level-3)",
              cursor: submitting ? "not-allowed" : "pointer",
              fontSize: "11px",
              fontWeight: 500,
              transition: "background 0.15s ease, color 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
              e.currentTarget.style.color = "var(--text-level-1)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--text-level-3)";
            }}
          >
            <SkipForward style={{ width: "12px", height: "12px" }} />
            {t("chat.choiceSkip")}
          </button>
        </div>

        {/* 问题正文 */}
        <p style={{
          margin: 0,
          fontSize: "12.5px",
          lineHeight: 1.5,
          color: "var(--text-level-1)",
          fontWeight: 500,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}>
          {choice.question}
        </p>

        {/* 选项列表（等高 minHeight + 等间距 gap 5px） */}
        <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
          {choice.options.map((opt, idx) => {
            const isRecommended = choice.recommended === idx;
            const isSelected = selectedIdx === idx;
            return (
              <button
                key={idx}
                disabled={submitting}
                onClick={() => handleSelect(idx)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  padding: "6px 10px",
                  minHeight: "38px",
                  borderRadius: "var(--radius-md)",
                  border: "1.5px solid",
                  borderColor: isSelected
                    ? "var(--color-primary)"
                    : isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 40%, var(--border-primary))"
                    : "var(--border-primary)",
                  background: isSelected
                    ? "color-mix(in srgb, var(--color-primary) 10%, var(--bg-level-3))"
                    : isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 6%, var(--bg-level-3))"
                    : "var(--bg-level-3)",
                  cursor: submitting ? "not-allowed" : "pointer",
                  textAlign: "left",
                  font: "inherit",
                  color: "var(--text-level-1)",
                  transition: "background 0.15s ease, border-color 0.15s ease, transform 0.1s ease",
                }}
                onMouseEnter={(e) => {
                  if (submitting) return;
                  if (isSelected) return;
                  e.currentTarget.style.background = isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 10%, var(--bg-level-3))"
                    : "var(--bg-level-2)";
                  e.currentTarget.style.borderColor = "color-mix(in srgb, var(--color-primary) 55%, var(--border-primary))";
                }}
                onMouseLeave={(e) => {
                  if (submitting) return;
                  if (isSelected) return;
                  e.currentTarget.style.background = isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 6%, var(--bg-level-3))"
                    : "var(--bg-level-3)";
                  e.currentTarget.style.borderColor = isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 40%, var(--border-primary))"
                    : "var(--border-primary)";
                }}
                onMouseDown={(e) => {
                  if (!submitting) e.currentTarget.style.transform = "scale(0.99)";
                }}
                onMouseUp={(e) => {
                  e.currentTarget.style.transform = "scale(1)";
                }}
              >
                <span style={{
                  flexShrink: 0,
                  width: "16px",
                  height: "16px",
                  borderRadius: "var(--radius-full)",
                  border: "1.5px solid",
                  borderColor: isSelected
                    ? "var(--color-primary)"
                    : isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 50%, var(--border-primary))"
                    : "var(--text-level-4)",
                  background: isSelected ? "var(--color-primary)" : "transparent",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#fff",
                }}>
                  {isSelected && <Check style={{ width: "10px", height: "10px" }} />}
                </span>
                <span style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  gap: "2px",
                  minWidth: 0,
                }}>
                  <span style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    fontSize: "12.5px",
                    fontWeight: isRecommended ? 600 : 500,
                    lineHeight: 1.3,
                    color: "var(--text-level-1)",
                  }}>
                    {opt.label}
                    {isRecommended && (
                      <span style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "2px",
                        padding: "0px 6px",
                        borderRadius: "var(--radius-xs)",
                        fontSize: "9px",
                        fontWeight: 700,
                        color: "var(--color-primary)",
                        background: "color-mix(in srgb, var(--color-primary) 14%, transparent)",
                        lineHeight: "14px",
                        textTransform: "uppercase",
                        letterSpacing: "0.3px",
                      }}>
                        <Star style={{ width: "8px", height: "8px" }} fill="currentColor" />
                        {t("chat.choiceRecommended")}
                      </span>
                    )}
                  </span>
                  {opt.description && (
                    <span style={{
                      fontSize: "11.5px",
                      lineHeight: 1.3,
                      color: "var(--text-level-3)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}>
                      {opt.description}
                    </span>
                  )}
                </span>
              </button>
            );
          })}
        </div>

        {/* 确认按钮：点击选项仅选中，需按「确认」才提交 */}
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1px" }}>
          <button
            disabled={selectedIdx == null || submitting}
            onClick={handleConfirm}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "5px",
              padding: "5px 14px",
              borderRadius: "var(--radius-md)",
              border: "1.5px solid",
              borderColor: selectedIdx != null && !submitting
                ? "var(--color-primary)"
                : "var(--border-primary)",
              background: selectedIdx != null && !submitting
                ? "var(--color-primary)"
                : "var(--bg-level-3)",
              color: selectedIdx != null && !submitting
                ? "var(--text-on-primary, #fff)"
                : "var(--text-level-4)",
              cursor: selectedIdx != null && !submitting ? "pointer" : "not-allowed",
              fontSize: "11.5px",
              fontWeight: 600,
              transition: "background 0.15s ease, color 0.15s ease, border-color 0.15s ease",
            }}
          >
            <Check style={{ width: "12px", height: "12px" }} />
            {t("chat.choiceConfirm")}
          </button>
        </div>

        {/* 自定义输入框（仅 allow_custom=true 时显示，压成一行） */}
        {choice.allow_custom && (
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <textarea
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              placeholder={t("chat.choiceCustomPlaceholder")}
              rows={1}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleCustomSubmit();
                }
              }}
              style={{
                width: "100%",
                padding: "6px 10px",
                borderRadius: "var(--radius-md)",
                border: "1.5px solid var(--border-primary)",
                background: "var(--bg-level-3)",
                color: "var(--text-level-1)",
                fontSize: "12.5px",
                lineHeight: 1.4,
                fontFamily: "inherit",
                resize: "none",
                outline: "none",
                boxSizing: "border-box",
                transition: "border-color 0.15s ease",
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = "var(--color-primary)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = "var(--border-primary)";
              }}
            />
            <button
              disabled={!customText.trim() || submitting}
              onClick={handleCustomSubmit}
              style={{
                alignSelf: "flex-end",
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
                padding: "5px 12px",
                borderRadius: "var(--radius-md)",
                border: "1.5px solid",
                borderColor: customText.trim() && !submitting
                  ? "var(--color-primary)"
                  : "var(--border-primary)",
                background: customText.trim() && !submitting
                  ? "var(--color-primary)"
                  : "var(--bg-level-3)",
                color: customText.trim() && !submitting
                  ? "var(--text-on-primary, #fff)"
                  : "var(--text-level-4)",
                cursor: customText.trim() && !submitting ? "pointer" : "not-allowed",
                fontSize: "11.5px",
                fontWeight: 600,
                transition: "background 0.15s ease, color 0.15s ease, border-color 0.15s ease",
              }}
            >
              <Check style={{ width: "12px", height: "12px" }} />
              {t("chat.choiceSubmitCustom")}
            </button>
          </div>
        )}
      </div>

      <p style={{
        textAlign: "center",
        fontSize: "10px",
        lineHeight: 1,
        color: "var(--text-level-4)",
        margin: 0,
        paddingTop: "2px",
        pointerEvents: "none",
      }}>{t("chat.choiceHint")}</p>
    </div>
  );
}
