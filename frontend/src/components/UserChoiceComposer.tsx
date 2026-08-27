"use client";

import { useState, useEffect, useCallback } from "react";
import { Check, HelpCircle, Star, SkipForward, Loader2, AlertCircle } from "lucide-react";
import { useStreamStore } from "@/lib/streamStore";
import { useTranslation } from "@/hooks/useTranslation";
import type { UserChoiceRequest } from "@/types/runtime";
import { apiPost } from "@/lib/api";

interface Props {
  choice: UserChoiceRequest;
  chatId: number;
}

export function UserChoiceComposer({ choice, chatId }: Props) {
  const { t } = useTranslation();
  const [selectedIdx, setSelectedIdx] = useState<number | null>(choice.recommended ?? null);
  const [customText, setCustomText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSelectedIdx(choice.recommended ?? null);
    setCustomText("");
    setSubmitting(false);
    setError(null);
  }, [choice.choice_id, choice.recommended]);

  const submitChoice = useCallback(async (params: { selected?: number | null; customText?: string; skip?: boolean }) => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    const custom = params.skip
      ? "(用户跳过)"
      : (params.customText ?? "").trim() || null;
    try {
      await apiPost(`/api/chat/${chatId}/choice`, {
        choice_id: choice.choice_id,
        selected: params.skip ? null : params.selected ?? null,
        custom_text: custom,
      });
      const resolvedAction: UserChoiceRequest["resolvedAction"] = params.skip
        ? { kind: "skipped" }
        : custom
          ? { kind: "custom", custom_text: custom }
          : { kind: "selected", selected: params.selected ?? 0 };
      useStreamStore.getState().updateSession(chatId, (prev) => ({
        timeline: prev.timeline.map((s) =>
          s.type === "user_choice" && s.choice.choice_id === choice.choice_id
            ? { ...s, choice: { ...s.choice, resolvedAction } }
            : s
        ),
      }));
    } catch (e) {
      console.error("UserChoiceComposer submit failed:", e);
      setError(e instanceof Error ? e.message : String(e));
      setSubmitting(false);
    }
  }, [submitting, chatId, choice.choice_id]);

  const handleSelect = (idx: number) => {
    if (submitting) return;
    setSelectedIdx(idx);
    setCustomText("");
  };

  const handleConfirm = () => {
    if (selectedIdx != null) submitChoice({ selected: selectedIdx });
  };

  const handleCustomSubmit = () => {
    if (customText.trim()) submitChoice({ customText });
  };

  const handleSkip = () => submitChoice({ skip: true });

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

  const hasCustom = choice.allow_custom !== false;

  return (
    <div
      role="radiogroup"
      aria-label={t("chat.choiceTitle")}
      onKeyDown={handleKeyDown}
      style={{
        width: "100%",
        maxWidth: "1400px",
        margin: "0 auto",
        padding: "0 100px 4px 100px",
        animation: "fadeIn 0.25s ease-out",
      }}
    >
      <div
        style={{
          position: "relative",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          padding: "10px 14px 10px 14px",
          borderRadius: "var(--radius-2xl)",
          background: "var(--bg-level-2)",
          border: "2px solid color-mix(in srgb, var(--color-primary) 25%, var(--border-primary))",
          boxShadow: "0 8px 28px rgba(0,0,0,0.10)",
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
        <div style={{ display: "flex", alignItems: "center", gap: "8px", paddingTop: "1px" }}>
          <div style={{
            flexShrink: 0,
            width: "22px",
            height: "22px",
            borderRadius: "var(--radius-md)",
            background: "color-mix(in srgb, var(--color-primary) 15%, var(--bg-level-2))",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}>
            <HelpCircle size={13} style={{ color: "var(--color-primary)" }} />
          </div>
          <span style={{
            fontSize: "13px",
            fontWeight: 700,
            color: "var(--color-primary)",
            letterSpacing: "0.01em",
          }}>
            {t("chat.choiceTitle")}
          </span>
          <span style={{
            marginLeft: "auto",
            fontSize: "10px",
            color: "var(--text-tertiary)",
            background: "var(--bg-level-3)",
            padding: "2px 7px",
            borderRadius: "var(--radius-sm)",
            fontWeight: 500,
          }}>
            {choice.options.length} 项可选
          </span>
        </div>

        {/* 分隔线 */}
        <div style={{ height: "1px", background: "var(--border-subtle)", margin: "2px 0" }} />

        {/* 问题 */}
        <p style={{
          margin: 0,
          fontSize: "12px",
          lineHeight: 1.45,
          color: "var(--text-secondary)",
          fontWeight: 500,
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
            background: "color-mix(in srgb, var(--color-danger) 10%, transparent)",
            border: "1px solid color-mix(in srgb, var(--color-danger) 30%, transparent)",
            color: "var(--color-danger)",
            fontSize: "11px",
          }}>
            <AlertCircle size={13} style={{ flexShrink: 0 }} />
            <span>提交失败：{error}，请重试</span>
          </div>
        )}

        {/* 选项列表 */}
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          {choice.options.map((opt, idx) => {
            const isSelected = selectedIdx === idx;
            const isRecommended = choice.recommended === idx;
            return (
              <button
                key={idx}
                type="button"
                role="radio"
                aria-checked={isSelected}
                onClick={() => handleSelect(idx)}
                disabled={submitting}
                style={{
                  width: "100%",
                  textAlign: "left",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "10px",
                  padding: "10px 12px",
                  minHeight: "54px",
                  borderRadius: "var(--radius-lg)",
                  border: isSelected
                    ? "2px solid var(--color-primary)"
                    : "1px solid var(--border-subtle)",
                  background: isSelected
                    ? "color-mix(in srgb, var(--color-primary) 7%, var(--bg-level-2))"
                    : "var(--bg-level-3)",
                  cursor: submitting ? "not-allowed" : "pointer",
                  transition: "all 0.15s ease",
                  opacity: submitting && !isSelected ? 0.5 : 1,
                  position: "relative",
                }}
              >
                {/* 单选圆圈 */}
                <span style={{
                  flexShrink: 0,
                  width: "16px",
                  height: "16px",
                  borderRadius: "50%",
                  border: isSelected ? "2px solid var(--color-primary)" : "2px solid var(--border-primary)",
                  background: isSelected ? "var(--color-primary)" : "transparent",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginTop: "1px",
                  transition: "all 0.15s ease",
                }}>
                  {isSelected && <Check size={10} style={{ color: "#fff", strokeWidth: 3 }} />}
                </span>

                {/* 文本内容 */}
                <span style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: "2px" }}>
                  <span style={{
                    fontSize: "13px",
                    fontWeight: isSelected ? 700 : 600,
                    color: "var(--text-primary)",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}>
                    {opt.label}
                    {isRecommended && (
                      <span
                        className="pulse-badge"
                        style={{
                          fontSize: "9px",
                          fontWeight: 700,
                          color: "var(--color-primary)",
                          background: "color-mix(in srgb, var(--color-primary) 12%, transparent)",
                          border: "1px solid color-mix(in srgb, var(--color-primary) 30%, transparent)",
                          padding: "1px 5px",
                          borderRadius: "var(--radius-sm)",
                          letterSpacing: "0.02em",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "2px",
                          animation: "pulse3times 1.6s ease-in-out 3",
                        }}
                      >
                        <Star size={8} fill="currentColor" />
                        推荐
                      </span>
                    )}
                  </span>
                  {opt.description && (
                    <span style={{
                      fontSize: "11px",
                      lineHeight: 1.4,
                      color: "var(--text-tertiary)",
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

        {/* 自定义输入 */}
        {hasCustom && (
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <textarea
              value={customText}
              onChange={(e) => {
                setCustomText(e.target.value);
                if (e.target.value.trim()) setSelectedIdx(null);
              }}
              placeholder="或直接输入你的想法…"
              disabled={submitting}
              rows={1}
              style={{
                width: "100%",
                resize: "none",
                padding: "8px 10px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-subtle)",
                background: "var(--bg-level-3)",
                color: "var(--text-primary)",
                fontSize: "12px",
                lineHeight: 1.4,
                outline: "none",
                fontFamily: "inherit",
                transition: "border-color 0.15s ease",
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = "var(--color-primary)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-subtle)"; }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleCustomSubmit();
                }
              }}
            />
            {customText.trim() && (
              <button
                type="button"
                onClick={handleCustomSubmit}
                disabled={submitting}
                style={{
                  alignSelf: "flex-end",
                  padding: "6px 14px",
                  borderRadius: "var(--radius-md)",
                  border: "none",
                  background: "var(--bg-level-4)",
                  color: "var(--text-primary)",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: submitting ? "not-allowed" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "5px",
                }}
              >
                {submitting ? <Loader2 size={12} className="spin" /> : null}
                提交我的想法
              </button>
            )}
          </div>
        )}

        {/* 确认按钮 + 跳过 */}
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={submitting || selectedIdx == null}
            style={{
              flex: 1,
              padding: "9px 16px",
              borderRadius: "var(--radius-lg)",
              border: "none",
              background: selectedIdx != null
                ? "linear-gradient(135deg, var(--color-primary), color-mix(in srgb, var(--color-primary) 70%, #000))"
                : "var(--bg-level-4)",
              color: selectedIdx != null ? "#fff" : "var(--text-tertiary)",
              fontSize: "13px",
              fontWeight: 700,
              cursor: (submitting || selectedIdx == null) ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              transition: "all 0.15s ease",
              boxShadow: selectedIdx != null ? "0 4px 14px color-mix(in srgb, var(--color-primary) 30%, transparent)" : "none",
            }}
          >
            {submitting ? (
              <>
                <Loader2 size={14} className="spin" />
                提交中…
              </>
            ) : (
              <>
                <Check size={15} strokeWidth={2.5} />
                确认选择
              </>
            )}
          </button>
          <button
            type="button"
            onClick={handleSkip}
            disabled={submitting}
            title="跳过，由系统按推荐项继续"
            style={{
              padding: "9px 12px",
              borderRadius: "var(--radius-lg)",
              border: "1px solid var(--border-subtle)",
              background: "var(--bg-level-3)",
              color: "var(--text-tertiary)",
              fontSize: "12px",
              fontWeight: 500,
              cursor: submitting ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              transition: "all 0.15s ease",
            }}
          >
            <SkipForward size={13} />
            跳过
          </button>
        </div>

        {/* 底部提示 */}
        <p style={{
          margin: 0,
          fontSize: "10px",
          color: "var(--text-tertiary)",
          textAlign: "center",
          lineHeight: 1.4,
        }}>
          ↑↓ 切换选项 · Enter 确认 · 也可直接输入想法 · 超时将自动采纳推荐项
        </p>
      </div>
    </div>
  );
}
