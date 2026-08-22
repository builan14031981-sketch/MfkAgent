"use client";

import { useState, useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
import { Check, HelpCircle, Star, SkipForward, X } from "lucide-react";
import { useStreamStore } from "@/lib/streamStore";
import { useTranslation } from "@/hooks/useTranslation";
import type { UserChoiceRequest } from "@/types/runtime";
import { apiPost } from "@/lib/api";

/**
 * Phase 2 抉择弹窗（V2）：
 *  真正的全屏居中 Modal（createPortal + 遮罩），跟 ToolApproval 内嵌卡片分工：
 *   - 弹窗：拦截"必须做出决定才能继续"的高优先级提问（聚焦输入、自动滚动可见）
 *   - 内嵌卡片：保留为"历史态"展示（流结束后可回看，模态关闭后仍留在 timeline）
 *
 *  行为：
 *   - 跟随 activeChatId 切换；非聊天页不弹
 *   - 取"activeChatId 对应 timeline 中最新一条未解决 choice"（resolvedAction==null）
 *   - 已解决 / 新发送时清空 / ESC / 点遮罩 → 关闭
 *   - "跳过"按钮、点遮罩、ESC：调 /api/chat/{id}/choice + selected=null + custom_text="(用户跳过)"
 *   - 选项 / 自定义输入：调同样接口
 *
 *  与 useChatStream.resolveChoice 的关系：
 *   - 该函数内部已做重复点击保护 / 乐观 UI / 失败回退；
 *   - 此处直接调 HTTP 接口（不走 store）以避免双写与回滚冲突。
 */
export function UserChoiceModal() {
  const { t } = useTranslation();
  const activeChatId = useStreamStore((s) => s.activeChatId);
  const session = useStreamStore((s) => (activeChatId != null ? s.sessions[activeChatId] : undefined));
  const [mounted, setMounted] = useState(false);
  const [customText, setCustomText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // 从当前活跃 chat 的 timeline 中找"最新一条未解决 choice"
  const activeChoice = useMemo<UserChoiceRequest | null>(() => {
    if (!session) return null;
    for (let i = session.timeline.length - 1; i >= 0; i--) {
      const seg = session.timeline[i];
      if (seg.type === "user_choice" && seg.choice.resolvedAction == null) {
        return seg.choice;
      }
    }
    return null;
  }, [session]);

  // 切换 choice 时清空输入框
  useEffect(() => {
    setCustomText("");
  }, [activeChoice?.choice_id]);

  // 弹窗打开时锁定背景滚动（避免遮罩下页面仍可滚动）
  useEffect(() => {
    if (!activeChoice) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, [activeChoice?.choice_id]);

  // ESC 键 = 跳过
  useEffect(() => {
    if (!activeChoice) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        handleSkip();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeChoice?.choice_id, activeChatId]);

  /** 提交到后端（轻量实现，不走 useChatStream.resolveChoice 以避免与 store 双写）。
   *  - 成功后在 store 中乐观标记该 choice 为已解决 → 弹窗立即关闭，
   *    无需等待后端 SSE 的 tool_result 才关闭（避免弹窗长时间滞留）。
   *  - 后端随后回推 tool_result 时会将对应 user_choice 从 timeline 移除，两者无冲突。 */
  const submitChoice = async (params: { selected?: number | null; customText?: string | null; skip?: boolean }) => {
    if (!activeChatId || !activeChoice || submitting) return;
    const choiceId = activeChoice.choice_id;
    setSubmitting(true);
    const customText = params.skip
      ? "(用户跳过)"
      : (params.customText ?? "").trim() || null;
    try {
      await apiPost(`/api/chat/${activeChatId}/choice`, {
        choice_id: choiceId,
        selected: params.skip ? null : params.selected ?? null,
        custom_text: customText,
      });
      // 乐观标记已解决：弹窗立即关闭（skip → skipped；自定义/选项 → selected）
      const resolvedAction: UserChoiceRequest["resolvedAction"] = params.skip
        ? { kind: "skipped" }
        : { kind: "selected", selected: params.selected ?? 0 };
      useStreamStore.getState().updateSession(activeChatId, (prev) => ({
        timeline: prev.timeline.map((s) =>
          s.type === "user_choice" && s.choice.choice_id === choiceId
            ? { ...s, choice: { ...s.choice, resolvedAction } }
            : s
        ),
      }));
    } catch (err) {
      console.error("UserChoiceModal submit failed:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSelect = (idx: number) => submitChoice({ selected: idx });
  const handleCustomSubmit = () => {
    const text = customText.trim();
    if (!text) return;
    submitChoice({ selected: null, customText: text });
  };
  const handleSkip = () => submitChoice({ skip: true });

  if (!mounted || !activeChoice) return null;

  const choice = activeChoice;
  const isResolved = choice.resolvedAction != null;
  const showResolvedView = isResolved;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="user-choice-title"
      onClick={(e) => {
        // 点遮罩 = 跳过（仅未解决时）
        if (!isResolved && e.target === e.currentTarget) {
          handleSkip();
        }
      }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        background: "color-mix(in srgb, var(--bg-level-1) 60%, transparent)",
        backdropFilter: "blur(6px)",
        WebkitBackdropFilter: "blur(6px)",
        animation: "fadeIn 0.18s ease-out",
      }}
    >
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(12px) scale(0.98); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>

      <div
        style={{
          width: "100%",
          maxWidth: "520px",
          maxHeight: "calc(100vh - 48px)",
          overflow: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "14px",
          padding: "20px 22px",
          borderRadius: "var(--radius-lg)",
          background: "var(--bg-level-2)",
          border: "1.5px solid color-mix(in srgb, var(--color-primary) 50%, var(--border-primary))",
          boxShadow: "0 20px 60px rgba(0,0,0,0.25), 0 0 0 1px color-mix(in srgb, var(--color-primary) 15%, transparent)",
          animation: "slideUp 0.22s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题行：图标 + 标题 + 关闭按钮（=跳过） */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{
            flexShrink: 0,
            width: "32px",
            height: "32px",
            borderRadius: "var(--radius-md)",
            background: "color-mix(in srgb, var(--color-primary) 12%, var(--bg-level-3))",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}>
            <HelpCircle style={{ width: "18px", height: "18px", color: "var(--color-primary)" }} />
          </div>
          <span
            id="user-choice-title"
            style={{
              flex: 1,
              fontSize: "15px",
              fontWeight: 700,
              color: "var(--text-level-1)",
              lineHeight: 1.3,
            }}
          >
            {t("chat.choiceTitle")}
          </span>
          {!showResolvedView && (
            <button
              onClick={handleSkip}
              title={t("chat.choiceSkip")}
              aria-label={t("chat.choiceSkip")}
              style={{
                flexShrink: 0,
                width: "28px",
                height: "28px",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: "transparent",
                color: "var(--text-level-3)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
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
              <X style={{ width: "16px", height: "16px" }} />
            </button>
          )}
        </div>

        {/* 问题正文 */}
        <p style={{
          margin: 0,
          fontSize: "14px",
          lineHeight: 1.6,
          color: "var(--text-level-1)",
          fontWeight: 500,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}>
          {choice.question}
        </p>

        {/* 选项列表 */}
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {choice.options.map((opt, idx) => {
            const isRecommended = choice.recommended === idx;
            return (
              <button
                key={idx}
                disabled={showResolvedView || submitting}
                onClick={() => handleSelect(idx)}
                autoFocus={idx === 0 && !choice.allow_custom}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "12px",
                  padding: "12px 14px",
                  borderRadius: "var(--radius-md)",
                  border: "1.5px solid",
                  borderColor: isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 40%, var(--border-primary))"
                    : "var(--border-primary)",
                  background: isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 6%, var(--bg-level-3))"
                    : "var(--bg-level-3)",
                  cursor: showResolvedView || submitting ? "not-allowed" : "pointer",
                  textAlign: "left",
                  font: "inherit",
                  color: "var(--text-level-1)",
                  transition: "background 0.15s ease, border-color 0.15s ease, transform 0.1s ease",
                }}
                onMouseEnter={(e) => {
                  if (showResolvedView || submitting) return;
                  e.currentTarget.style.background = isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 10%, var(--bg-level-3))"
                    : "var(--bg-level-2)";
                  e.currentTarget.style.borderColor = "color-mix(in srgb, var(--color-primary) 55%, var(--border-primary))";
                }}
                onMouseLeave={(e) => {
                  if (showResolvedView || submitting) return;
                  e.currentTarget.style.background = isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 6%, var(--bg-level-3))"
                    : "var(--bg-level-3)";
                  e.currentTarget.style.borderColor = isRecommended
                    ? "color-mix(in srgb, var(--color-primary) 40%, var(--border-primary))"
                    : "var(--border-primary)";
                }}
                onMouseDown={(e) => {
                  if (!showResolvedView && !submitting) {
                    e.currentTarget.style.transform = "scale(0.99)";
                  }
                }}
                onMouseUp={(e) => {
                  e.currentTarget.style.transform = "scale(1)";
                }}
              >
                <span style={{
                  flexShrink: 0,
                  marginTop: "2px",
                  width: "20px",
                  height: "20px",
                  borderRadius: "var(--radius-full)",
                  border: "2px solid",
                  borderColor: isRecommended ? "var(--color-primary)" : "var(--text-level-4)",
                  background: "transparent",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}>
                  {isRecommended && (
                    <span style={{
                      width: "10px",
                      height: "10px",
                      borderRadius: "50%",
                      background: "var(--color-primary)",
                    }} />
                  )}
                </span>
                <span style={{ flex: 1, display: "flex", flexDirection: "column", gap: "3px", minWidth: 0 }}>
                  <span style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    fontSize: "14px",
                    fontWeight: isRecommended ? 600 : 500,
                    lineHeight: 1.4,
                    color: "var(--text-level-1)",
                  }}>
                    {opt.label}
                    {isRecommended && (
                      <span style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "3px",
                        padding: "1px 7px",
                        borderRadius: "var(--radius-xs)",
                        fontSize: "10px",
                        fontWeight: 700,
                        color: "var(--color-primary)",
                        background: "color-mix(in srgb, var(--color-primary) 14%, transparent)",
                        lineHeight: "16px",
                        textTransform: "uppercase",
                        letterSpacing: "0.3px",
                      }}>
                        <Star style={{ width: "9px", height: "9px" }} fill="currentColor" />
                        {t("chat.choiceRecommended")}
                      </span>
                    )}
                  </span>
                  {opt.description && (
                    <span style={{
                      fontSize: "12.5px",
                      lineHeight: 1.55,
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
        {choice.allow_custom && !showResolvedView && (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <textarea
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              placeholder={t("chat.choiceCustomPlaceholder")}
              rows={2}
              autoFocus
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: "var(--radius-md)",
                border: "1.5px solid var(--border-primary)",
                background: "var(--bg-level-3)",
                color: "var(--text-level-1)",
                fontSize: "13px",
                lineHeight: 1.5,
                fontFamily: "inherit",
                resize: "vertical",
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
                gap: "6px",
                padding: "7px 16px",
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
                fontSize: "12.5px",
                fontWeight: 600,
                transition: "background 0.15s ease, color 0.15s ease, border-color 0.15s ease",
              }}
            >
              <Check style={{ width: "13px", height: "13px" }} />
              {t("chat.choiceSubmitCustom")}
            </button>
          </div>
        )}

        {/* 底部操作栏：跳过（左侧描述 + 右侧跳过按钮） */}
        {!showResolvedView && (
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
            marginTop: "4px",
            paddingTop: "12px",
            borderTop: "1px solid var(--border-primary)",
          }}>
            <span style={{
              fontSize: "11.5px",
              color: "var(--text-level-4)",
              lineHeight: 1.4,
            }}>
              {t("chat.choiceHint")}
            </span>
            <button
              onClick={handleSkip}
              disabled={submitting}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "7px 14px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-primary)",
                background: "transparent",
                color: "var(--text-level-3)",
                cursor: submitting ? "not-allowed" : "pointer",
                fontSize: "12.5px",
                fontWeight: 500,
                transition: "background 0.15s ease, color 0.15s ease, border-color 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-level-3)";
                e.currentTarget.style.color = "var(--text-level-1)";
                e.currentTarget.style.borderColor = "var(--text-level-3)";
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
        )}
      </div>
    </div>,
    document.body
  );
}
