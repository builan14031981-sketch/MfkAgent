"use client";

import { memo, useState, useRef, useCallback, useMemo, useEffect } from "react";
import { Copy, Check, Quote, RefreshCw, Edit2, ChevronDown, ChevronUp, Brain, Loader2, Image } from "lucide-react";
import type { Message } from "@/hooks/useMessages";
import { ToolCallCardList } from "@/components/ToolCallCard";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { AgentIcon } from "@/components/AgentIcon";
import { useTranslation } from "@/hooks/useTranslation";
import { API_BASE } from "@/lib/api";

interface ChatMessageProps {
  message: Message;
  currentAgent?: { id: string; name: string } | null;
  onQuote: (content: string) => void;
  onRegenerate: (messageId: number) => void;
  onEdit: (message: Message) => void;
}

/** 从消息内容中解析 <think>...</think> 思考块（部分模型会在 content 中输出） */
function parseThinkBlock(content: string): { thinking: string | null; body: string } {
  const match = /<think>([\s\S]*?)<\/think>/.exec(content);
  if (!match) return { thinking: null, body: content };
  const thinking = match[1].trim();
  const body = content.slice(0, match.index) + content.slice(match.index + match[0].length);
  return { thinking: thinking || null, body };
}

/** 仅用于渲染展示的文本归一化：去首尾空白、\r\n → \n、连续空行压缩为单个 \n。不改动存储数据 */
function normalizeThinking(text: string): string {
  return text.trim().replace(/\r\n/g, "\n").replace(/\n{2,}/g, "\n");
}

/** 思考过程折叠面板：灰色背景、较小字号、左侧边框。默认收起，收起态 2 行截断预览。
 * persistKey 提供时折叠状态写入 localStorage，重进会话保持一致。 */
export function ThinkingPanel({ thinking, persistKey }: { thinking: string; persistKey?: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(() => {
    if (persistKey) {
      try {
        return window.localStorage.getItem(persistKey) === "1";
      } catch {
        /* localStorage 不可用则忽略 */
      }
    }
    return false;
  });

  const handleToggle = useCallback(() => {
    setOpen((v) => {
      const next = !v;
      if (persistKey) {
        try {
          window.localStorage.setItem(persistKey, next ? "1" : "0");
        } catch {
          /* localStorage 不可用则忽略 */
        }
      }
      return next;
    });
  }, [persistKey]);

  const normalized = useMemo(() => normalizeThinking(thinking), [thinking]);

  return (
    <div style={{
      margin: "0 0 8px 0",
      borderRadius: "var(--radius-sm)",
      background: "var(--bg-level-3)",
      borderLeft: "2px solid var(--text-level-4)",
      padding: "6px 10px",
    }}>
      <button
        onClick={handleToggle}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: 0,
          border: "none",
          background: "transparent",
          cursor: "pointer",
          fontSize: "12px",
          fontWeight: 500,
          color: "var(--text-level-3)",
          outline: "none",
        }}
      >
        <Brain style={{ width: "13px", height: "13px", color: "var(--text-level-4)" }} />
        <span>{t("chat.thinking")}</span>
        {open ? (
          <ChevronUp style={{ width: "12px", height: "12px", color: "var(--text-level-4)" }} />
        ) : (
          <ChevronDown style={{ width: "12px", height: "12px", color: "var(--text-level-4)" }} />
        )}
      </button>
      <div
        style={{
          marginTop: "6px",
          fontSize: "12px",
          lineHeight: 1.6,
          color: "var(--text-level-3)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          ...(open
            ? {}
            : {
                display: "-webkit-box" as React.CSSProperties["display"],
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical" as const,
                overflow: "hidden",
              }),
        }}
      >
        {normalized}
      </div>
    </div>
  );
}

/**
 * Phase 12：流式思考面板 — 高性能实时渲染思考过程。
 * - 使用 useRef + requestAnimationFrame 直接操作 DOM，避免每次 SSE chunk 触发 React 全量重渲染
 * - 默认折叠（仅显示 "正在思考..." 标题行），用户可展开查看详细思考过程
 * - 当 content 为空时显示闪烁动画；有内容时显示实时累积文本
 * - 思考结束（isActive 变为 false）后自动折叠
 */
export function StreamingThinkingPanel({ content, isActive }: { content: string; isActive: boolean }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const prevLengthRef = useRef(0);
  const rafRef = useRef<number | null>(null);

  // 直接 DOM 写入，绕过 React 渲染管线（高频 SSE 下性能关键）
  useEffect(() => {
    const el = contentRef.current;
    if (!el) return;
    // 仅在内容增长时更新 DOM（避免无意义写入）
    if (content.length <= prevLengthRef.current) return;
    prevLengthRef.current = content.length;

    if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      if (contentRef.current) {
        contentRef.current.textContent = content;
        // 自动滚动到底部
        contentRef.current.scrollTop = contentRef.current.scrollHeight;
      }
    });
    return () => {
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [content]);

  // 思考结束时自动折叠（rAF 异步触发，避免在 effect 内同步 setState）
  useEffect(() => {
    if (!isActive && content) {
      const raf = requestAnimationFrame(() => setOpen(false));
      return () => cancelAnimationFrame(raf);
    }
  }, [isActive, content]);

  const hasContent = content.length > 0;

  return (
    <div style={{
      margin: "0 0 8px 0",
      borderRadius: "var(--radius-sm)",
      background: "var(--bg-level-3)",
      borderLeft: "2px solid var(--text-level-4)",
      padding: "6px 10px",
      transition: "border-color 0.3s ease",
    }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: 0,
          border: "none",
          background: "transparent",
          cursor: "pointer",
          fontSize: "12px",
          fontWeight: 500,
          color: "var(--text-level-3)",
          outline: "none",
          width: "100%",
        }}
      >
        {isActive && !hasContent ? (
          <Loader2 style={{
            width: "13px",
            height: "13px",
            color: "var(--color-primary)",
            animation: "spin 1s linear infinite",
          }} />
        ) : (
          <Brain style={{ width: "13px", height: "13px", color: "var(--text-level-4)" }} />
        )}
        <span style={{ flex: 1, textAlign: "left" }}>
          {isActive && !hasContent ? t("chat.thinking") : hasContent ? t("chat.thinking") : t("chat.thinking")}
        </span>
        {open ? (
          <ChevronUp style={{ width: "12px", height: "12px", color: "var(--text-level-4)", flexShrink: 0 }} />
        ) : (
          <ChevronDown style={{ width: "12px", height: "12px", color: "var(--text-level-4)", flexShrink: 0 }} />
        )}
      </button>
      <div
        ref={contentRef}
        style={{
          marginTop: open ? "6px" : "0",
          fontSize: "12px",
          lineHeight: 1.6,
          color: "var(--text-level-3)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          fontStyle: "italic",
          maxHeight: open ? "300px" : "0",
          overflow: open ? "auto" : "hidden",
          opacity: open ? 1 : 0,
          transition: "max-height 0.2s ease, opacity 0.2s ease, margin-top 0.2s ease",
        }}
      />
      {/* 折叠时显示首行预览 */}
      {!open && hasContent && (
        <div style={{
          fontSize: "12px",
          lineHeight: 1.5,
          color: "var(--text-level-4)",
          fontStyle: "italic",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          marginTop: "2px",
        }}>
          {content.slice(0, 80)}{content.length > 80 ? "..." : ""}
        </div>
      )}
    </div>
  );
}

/** 复制按钮：真实 clipboard + 勾选反馈。
 * hover 常驻：鼠标在按钮上就一直显示勾；移开才启动 1.2s 复位计时，
 * 短暂移回则取消计时继续显示勾，避免"去粘贴/读内容再回来已复位"的丢失感。 */
function CopyButton({ text }: { text: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const resetSoon = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setCopied(false), 1200);
  }, []);

  const cancelReset = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      cancelReset();
    } catch (err) {
      console.error("Copy failed:", err);
    }
  }, [text, cancelReset]);

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  return (
    <button
      onClick={handleCopy}
      onMouseEnter={(e) => {
        cancelReset();
        e.currentTarget.style.opacity = "1";
      }}
      onMouseLeave={(e) => {
        resetSoon();
        e.currentTarget.style.opacity = copied ? "1" : "0.4";
      }}
      title={copied ? t("common.copied") : t("common.copy")}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: "28px",
        height: "28px",
        borderRadius: "var(--radius-sm)",
        border: "none",
        background: copied ? "var(--color-copied)" : "transparent",
        cursor: "pointer",
        color: copied ? "var(--color-copied-text)" : "var(--text-level-4)",
        outline: "none",
        opacity: copied ? 1 : 0.4,
        transition: "opacity 0.2s ease",
      }}
    >
      {copied ? (
        <Check style={{ width: "13px", height: "13px" }} />
      ) : (
        <Copy style={{ width: "13px", height: "13px" }} />
      )}
    </button>
  );
}

/** 消息悬浮操作按钮（图标式） */
function ActionButton({
  onClick,
  title,
  children,
}: {
  onClick: () => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      onMouseEnter={(e) => { e.currentTarget.style.opacity = "1"; }}
      onMouseLeave={(e) => { e.currentTarget.style.opacity = "0.4"; }}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: "28px",
        height: "28px",
        borderRadius: "var(--radius-sm)",
        border: "none",
        background: "transparent",
        cursor: "pointer",
        color: "var(--text-level-4)",
        outline: "none",
        opacity: 0.4,
        transition: "opacity 0.2s ease",
      }}
    >
      {children}
    </button>
  );
}

/**
 * 单条消息：
 * - AI 消息：复制 / 引用 / 重生成（仅 AI，hover 显示）
 * - 用户消息：复制 / 编辑（hover 显示）
 * memo：滚动等高频场景下 MessageList 重渲染时（message/回调引用不变）跳过整条渲染
 */
export const ChatMessage = memo(function ChatMessage({ message, currentAgent, onQuote, onRegenerate, onEdit }: ChatMessageProps) {
  const { t } = useTranslation();
  // 优先使用独立的 thinking 字段（流式/后端持久化）；老会话 thinking 内嵌在 content
  // 的 think 标签中时回退用 parseThinkBlock 从正文剥离，保证历史消息仍能展示思考块。
  const { thinking, body } = useMemo(
    () =>
      message.thinking
        ? { thinking: message.thinking, body: message.content }
        : parseThinkBlock(message.content),
    [message.content, message.thinking]
  );

  // 静态操作栏布局（Zero CLS）：固定 marginTop、无 maxHeight/overflow/高度动画。
  // 低调常驻：默认低对比度由按钮自身 opacity:0.4 承担，hover 按钮恢复 1，容器始终可见。
  const actionBarStyle = (alignEnd: boolean): React.CSSProperties => ({
    display: "flex",
    gap: "4px",
    justifyContent: alignEnd ? "flex-end" : "flex-start",
    marginTop: "4px",
  });

  if (message.role === "user") {
    const imageAtts = message.attachments?.filter((a) => a.kind === "image") ?? [];
    if (message.attachments?.length) {
      console.log("[ChatMessage] 渲染用户消息 attachments:", message.id, message.attachments);
    }
    return (
      <div>
        {/* 用户消息：轻量气泡 + 悬浮操作栏（复制 + 编辑） */}
        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "flex-end", gap: "4px" }}>
          <div style={{
            position: "relative",
            maxWidth: "70%",
            borderRadius: "var(--radius-md)",
            background: "var(--color-primary)",
            color: "var(--text-on-primary)",
            fontSize: "14px",
            lineHeight: 1.5,
            overflow: "hidden",
          }}>
            {/* 图片附件 */}
            {imageAtts.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px", padding: "4px" }}>
                {imageAtts.map((att, i) => (
                  <div key={i} style={{
                    position: "relative",
                    width: "120px",
                    height: "120px",
                    borderRadius: "6px",
                    overflow: "hidden",
                    background: "rgba(255,255,255,0.1)",
                  }}>
                    {att.path ? (
                      <img
                        src={`${API_BASE}/api/chat/${message.chat_id}/file?path=${encodeURIComponent(att.path)}`}
                        alt={att.name}
                        style={{
                          width: "100%",
                          height: "100%",
                          objectFit: "cover",
                        }}
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = "none";
                          (e.target as HTMLImageElement).nextElementSibling?.setAttribute("style", "display:flex");
                        }}
                      />
                    ) : null}
                    <div style={{
                      display: att.path ? "none" : "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "100%",
                      height: "100%",
                      color: "rgba(255,255,255,0.5)",
                    }}>
                      <Image style={{ width: "24px", height: "24px" }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
            {/* 文字内容 */}
            {message.content && (
              <div style={{ padding: "8px 14px", paddingTop: imageAtts.length > 0 ? "4px" : "8px", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {message.content}
              </div>
            )}
          </div>
        </div>
        {/* 用户消息悬浮操作栏 */}
        <div style={actionBarStyle(true)}>
          <CopyButton text={message.content} />
          <ActionButton onClick={() => onEdit(message)} title={t("chat.edit")}>
            <Edit2 style={{ width: "13px", height: "13px" }} />
          </ActionButton>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* AI 标识 */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
        {currentAgent && <AgentIcon id={currentAgent.id} size={16} style={{ color: "var(--text-level-3)" }} />}
        <span style={{ fontSize: "13px", fontWeight: 500, lineHeight: 1.25, color: "var(--text-level-3)" }}>
          {currentAgent?.name || "AI"}
        </span>
      </div>
      {/* 文件操作事件卡片 */}
      {message.tool_calls && message.tool_calls.length > 0 && (
        <ToolCallCardList toolCalls={message.tool_calls} />
      )}
      {/* 思考过程（<think> 标签内容）折叠面板 */}
      {thinking && <ThinkingPanel thinking={thinking} persistKey={"mfk_think_" + message.id} />}
      {/* 正文：Markdown 渲染（含代码块折叠） */}
      <MarkdownRenderer content={body} />
      {/* AI 消息悬浮操作栏：复制 / 引用 / 重生成 */}
      <div style={actionBarStyle(false)}>
        <CopyButton text={message.content} />
        <ActionButton onClick={() => onQuote(message.content)} title={t("chat.quote")}>
          <Quote style={{ width: "13px", height: "13px" }} />
        </ActionButton>
        <ActionButton onClick={() => onRegenerate(message.id)} title={t("chat.regenerate")}>
          <RefreshCw style={{ width: "13px", height: "13px" }} />
        </ActionButton>
      </div>
    </div>
  );
});
