"use client";

import { useState, useEffect, useCallback } from "react";
import { Check, HelpCircle, Star, SkipForward, Loader2, AlertCircle } from "lucide-react";
import { useStreamStore } from "@/lib/streamStore";
import { useTranslation } from "@/hooks/useTranslation";
import type { UserChoiceRequest } from "@/types/runtime";
import { apiPost } from "@/lib/api";

/**
 * 内联抉择框（V4）：高视觉权重的决策卡片。
 *
 * 设计原则：
 *  - 这是需要用户做决策的交互，视觉权重必须高于普通消息气泡
 *  - 顶部主色强调条 + 深背景 + 强阴影，一眼区分"需要你操作"
 *  - 选项卡片化，选中态/推荐态有明显视觉差距
 *  - 两步选择（点选→确认），但确认按钮始终有引导文案
 *  - 自定义输入作为替代路径，放在确认按钮上方
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
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 进入/切换 choice 时清空
  useEffect(() => {
    setCustomText("");
    setSelectedIdx(null);
    setError(null);
  }, [choice.choice_id]);

  const submitChoice = useCallback(async (params: {
    selected?: number | null;
    customText?: string | null;
    skip?: boolean;
  }) => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    const text = params.skip
      ? "(用户跳过)"
      : (params.customText ?? "").trim() || null;
    try {
      await apiPost(`/api/chat/${chatId}/choice`, {
        choice_id: choice.choice_id,
        selected: params.skip ? null : params.selected ?? null,
        custom_text: text,
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
      setError("提交失败，请重试");
    } finally {
      setSubmitting(false);
    }
  }, [submitting, chatId, choice.choice_id]);

  const handleSelect = (idx: number) => {
    if (submitting) return;
    setSelectedIdx((prev) => (prev === idx ? null : idx));
    setError(null);
  };

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

  // 键盘导航：↑↓ 切换选项，Enter 确认
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIdx((prev) => {
        if (prev == null) return 0;
        return (prev + 1) % choice.options.length;
      });
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIdx((prev) => {
        if (prev == null) return choice.options.length - 1;
        return (prev - 1 + choice.options.length) % choice.options.length;
      });
    } else if (e.key === "Enter" && !customText) {
      e.preventDefault();
      if (selectedIdx != null) handleConfirm();
    }
  };

  const hasSelection = selectedIdx != null;
  const hasCustomText = customText.trim().length > 0;

  return (
    <div
      role="radiogroup"
      aria-label={t("chat.choiceTitle")}
      onKeyDown={handleKeyDown}
      style={{
        width: "100%",
        maxWidth: "1400px",
        margin: "0 auto",
        padding: "0 24px 4px 24px",
        animation: "fadeIn 0.25s ease-out",
      }}
    >
      <div
        style={{
          position: "relative",
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          padding: "14px 16px 12px 16px",
          borderRadius: "var(--radius-2xl)",
          background: "var(--bg-level-2)",
          border: "2px solid color-mix(in srgb, var(--color-primary) 25%, var(--border-primary))",
          boxShadow: "0 12px 40px rgba(0,0,0,0.12)",
          overflow: "hidden",
        }}
      >
        {/* 顶部主色强调条 */}
        <div style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: "3px",
          background: "linear-gradient(90deg, var(--color-primary), color-mix(in srgb, var(--color-primary) 50%, transparent))",
        }} />

        {/* 标题行 */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", paddingTop: "2px" }}>
          <div style={{
            flexShrink: 0,
            width: "26px",
            height: "26px",
            borderRadius: "var(--radius-md)",
            background: "color-mix(in srgb, var(--color-primary) 15%, var(--bg-level-2))",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}>
            <HelpCircle style={{ width: "16px", height: "16px", color: "var(--color-primary)" }} />
          </div>
          <span style={{
            flex: 1,
            fontSize: "14px",
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
              padding: "4px 10px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: "transparent",
              color: "var(--text-level-3)",
              cursor: submitting ? "not-allowed" : "pointer",
              fontSize: "11.5px",
              fontWeight: 500,
              transition: "background 0.15s ease, color 0.15s ease, border-color 0.15s ease",
            }}
            onMouseEnter={(e) => {
              if (submitting) return;
              e.currentTarget.style.background = "var(--bg-level-3)";
              e.currentTarget.style.color = "var(--text-level-1)";
              e.currentTarget.style.borderColor = "var(--color-primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--text-level-3)";
              e.currentTarget.style.borderColor = "var(--border-primary)";
            }}
          >
            <SkipForward style={{ width: "13px", height: "13px" }} />
            {t("chat.choiceSkip")}
          </button>
        </div>

        {/* 分隔线 */}
        <div style={{ height: "1px", background: "var(--border-primary)", opacity: 0.6 }} />

        {/* 问题正文 */}
        <p style={{
          margin: 0,
          fontSize: "13px",
          lineHeight: 1.55,
          color: "var(--text-level-1)",
          fontWeight: 500,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}>
          {choice.question}
        </p>

        {/* 错误提示 */}
        {error && (
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "6px 10px",
            borderRadius: "var(--radius-md)",
            background: "color-mix(in srgb, #ef4444 10%, transparent)",
            color: "#ef4444",
            fontSize: "12px",
            fontWeight: 500,
          }}>
            <AlertCircle style={{ width: "14px", height: "14px", flexShrink: 0 }} />
            {error}
          </div>
        )}

        {/* 选项列表 */}
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          {choice.options.map((opt, idx) => {
            const isRecommended = choice.recommended === idx;
            const isSelected = selectedIdx === idx;
            return (
              <button
                key={idx}
                role="radio"
                aria-checked={isSelected}
                disabled={submitting}
                onClick={() => handleSelect(idx)}
                style={{
                  position: "relative",
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "10px 14px",
                  minHeight: "52px",
                  borderRadius: "var(--radius-lg)",
                  border: "2px solid",
                  borderColor: isSelected
                    ? "var(--color-primary)"
                    : isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 45%, var(--border-primary))"
                    : "var(--border-primary)",
                  background: isSelected
                    ? "color-mix(in srgb, var(--color-primary) 12%, var(--bg-level-2))"
                    : isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 7%, var(--bg-level-2))"
                    : "var(--bg-level-3)",
                  boxShadow: isSelected
                    ? "0 4px 16px color-mix(in srgb, var(--color-primary) 20%, transparent), inset 3px 0 0 var(--color-primary)"
                    : isRecommended
                    ? "inset 3px 0 0 color-mix(in srgb, var(--color-primary) 50%, transparent)"
                    : "none",
                  cursor: submitting ? "not-allowed" : "pointer",
                  textAlign: "left",
                  font: "inherit",
                  color: "var(--text-level-1)",
                  transition: "background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease, transform 0.1s ease",
                }}
                onMouseEnter={(e) => {
                  if (submitting || isSelected) return;
                  e.currentTarget.style.background = isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 12%, var(--bg-level-2))"
                    : "var(--bg-level-2)";
                  e.currentTarget.style.borderColor = "color-mix(in srgb, var(--color-primary) 60%, var(--border-primary))";
                  e.currentTarget.style.transform = "translateY(-1px)";
                }}
                onMouseLeave={(e) => {
                  if (submitting || isSelected) return;
                  e.currentTarget.style.background = isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 7%, var(--bg-level-2))"
                    : "var(--bg-level-3)";
                  e.currentTarget.style.borderColor = isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 45%, var(--border-primary))"
                    : "var(--border-primary)";
                  e.currentTarget.style.transform = "translateY(0)";
                }}
              >
                {/* 单选圆圈 */}
                <span style={{
                  flexShrink: 0,
                  width: "18px",
                  height: "18px",
                  borderRadius: "var(--radius-full)",
                  border: "2px solid",
                  borderColor: isSelected
                    ? "var(--color-primary)"
                    : isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 55%, var(--border-primary))"
                    : "var(--text-level-4)",
                  background: isSelected ? "var(--color-primary)" : "transparent",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#fff",
                  transition: "all 0.15s ease",
                }}>
                  {isSelected && <Check style={{ width: "11px", height: "11px" }} />}
                </span>

                {/* 文本内容 */}
                <span style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  gap: "3px",
                  minWidth: 0,
                }}>
                  <span style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    fontSize: "13.5px",
                    fontWeight: isRecommended ? 600 : 500,
                    lineHeight: 1.35,
                    color: "var(--text-level-1)",
                  }}>
                    {opt.label}
                    {isRecommended && (
                      <span
                        className="pulse-badge"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "3px",
                          padding: "1px 8px",
                          borderRadius: "var(--radius-xs)",
                          fontSize: "10px",
                          fontWeight: 700,
                          color: "var(--color-primary)",
                          background: "color-mix(in srgb, var(--color-primary) 14%, transparent)",
                          lineHeight: "16px",
                          letterSpacing: "0.3px",
                          animation: "pulse3times 1.6s ease-in-out 3",
                        }}
                      >
                        <Star style={{ width: "9px", height: "9px" }} fill="currentColor" />
                        {t("chat.choiceRecommended")}
                      </span>
                    )}
                  </span>
                  {opt.description && (
                    <span style={{
                      fontSize: "12px",
                      lineHeight: 1.4,
                      color: "var(--text-level-3)",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}>
                      {opt.description}
                    </span>
                  )}
                </span>
              </button>
            );
          })}
        </div>

        {/* 自定义输入（在确认按钮上方） */}
        {choice.allow_custom && (
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              fontSize: "11.5px",
              color: "var(--text-level-3)",
              fontWeight: 500,
            }}>
              <span style={{ flex: 1, height: "1px", background: "var(--border-primary)" }} />
              <span>或者输入你的想法</span>
              <span style={{ flex: 1, height: "1px", background: "var(--border-primary)" }} />
            </div>
            <textarea
              value={customText}
              onChange={(e) => { setCustomText(e.target.value); setError(null); }}
              placeholder={t("chat.choiceCustomPlaceholder")}
              rows={1}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleCustomSubmit();
                }
              }}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--radius-md)",
                border: "1.5px solid var(--border-primary)",
                background: "var(--bg-level-3)",
                color: "var(--text-level-1)",
                fontSize: "13px",
                lineHeight: 1.4,
                fontFamily: "inherit",
                resize: "none",
                outline: "none",
                boxSizing: "border-box",
                transition: "border-color 0.15s ease, box-shadow 0.15s ease",
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = "var(--color-primary)";
                e.currentTarget.style.boxShadow = "0 0 0 3px color-mix(in srgb, var(--color-primary) 12%, transparent)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = "var(--border-primary)";
                e.currentTarget.style.boxShadow = "none";
              }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                disabled={!hasCustomText || submitting}
                onClick={handleCustomSubmit}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  padding: "6px 16px",
                  borderRadius: "var(--radius-md)",
                  border: "1.5px solid",
                  borderColor: hasCustomText && !submitting
                    ? "var(--color-primary)"
                    : "var(--border-primary)",
                  background: hasCustomText && !submitting
                    ? "var(--color-primary)"
                    : "var(--bg-level-3)",
                  color: hasCustomText && !submitting
                    ? "var(--text-on-primary, #fff)"
                    : "var(--text-level-4)",
                  cursor: hasCustomText && !submitting ? "pointer" : "not-allowed",
                  fontSize: "12px",
                  fontWeight: 600,
                  transition: "background 0.15s ease, color 0.15s ease, border-color 0.15s ease",
                }}
              >
                {submitting ? <Loader2 style={{ width: "13px", height: "13px", animation: "spin 0.8s linear infinite" }} /> : <Check style={{ width: "13px", height: "13px" }} />}
                {t("chat.choiceSubmitCustom")}
              </button>
            </div>
          </div>
        )}

        {/* 确认按钮 */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginTop: "2px" }}>
          <button
            disabled={!hasSelection || submitting}
            onClick={handleConfirm}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "8px 22px",
              borderRadius: "var(--radius-md)",
              border: "2px solid",
              borderColor: hasSelection && !submitting
                ? "var(--color-primary)"
                : "var(--border-primary)",
              background: hasSelection && !submitting
                ? "var(--color-primary)"
                : "var(--bg-level-3)",
              color: hasSelection && !submitting
                ? "var(--text-on-primary, #fff)"
                : "var(--text-level-4)",
              cursor: hasSelection && !submitting ? "pointer" : "not-allowed",
              fontSize: "13px",
              fontWeight: 600,
              transition: "background 0.15s ease, color 0.15s ease, border-color 0.15s ease, transform 0.1s ease",
            }}
            onMouseDown={(e) => {
              if (hasSelection && !submitting) e.currentTarget.style.transform = "scale(0.97)";
            }}
            onMouseUp={(e) => {
              e.currentTarget.style.transform = "scale(1)";
            }}
          >
            {submitting ? (
              <Loader2 style={{ width: "14px", height: "14px", animation: "spin 0.8s linear infinite" }} />
            ) : (
              <Check style={{ width: "14px", height: "14px" }} />
            )}
            {hasSelection ? t("chat.choiceConfirm") : "请先选择一项"}
          </button>
          {!hasSelection && !submitting && (
            <span style={{ fontSize: "11.5px", color: "var(--text-level-4)" }}>
              ↑↓ 切换 · Enter 确认
            </span>
          )}
        </div>
      </div>

      <p style={{
        textAlign: "center",
        fontSize: "11px",
        lineHeight: 1.2,
        color: "var(--text-level-3)",
        margin: 0,
        paddingTop: "4px",
        pointerEvents: "none",
      }}>{t("chat.choiceHint")}</p>
    </div>
  );
}
