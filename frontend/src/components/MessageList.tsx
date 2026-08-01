"use client";

import { useRef, useCallback, useEffect, useLayoutEffect, useState } from "react";
import { ArrowDown } from "lucide-react";
import type { Message } from "@/hooks/useMessages";
import { ChatMessage } from "@/components/ChatMessage";
import { AgentIcon } from "@/components/AgentIcon";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { ToolCallCardList } from "@/components/ToolCallCard";
import type { ToolCall } from "@/components/ToolCallCard";
import { useTranslation } from "@/hooks/useTranslation";

interface MessageListProps {
  messages: Message[];
  streamingContent: string;
  streamingToolCalls?: ToolCall[];
  isStreaming: boolean;
  currentAgent?: { id: string; name: string } | null;
  onQuote: (content: string) => void;
  onRegenerate: (messageId: number) => void;
  onEdit: (message: Message) => void;
}

/** 距离底部阈值：低于该值视为"用户停在底部"，自动吸底 */
const BOTTOM_THRESHOLD = 120;

/**
 * 消息列表 + 智能吸底滚动：
 * - 用户停在底部时用 rAF 平滑吸底，禁止剧烈抖动
 * - 用户向上浏览历史时暂停吸底，右下角浮现 [↓ 回最新]
 */
export function MessageList({ messages, streamingContent, streamingToolCalls, isStreaming, currentAgent, onQuote, onRegenerate, onEdit }: MessageListProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const prevStreamingRef = useRef(isStreaming);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);

  // 空状态：渲染期派生，避免 effect 中 setState
  const isEmptyState = messages.length === 0 && !streamingContent;

  // 判断是否靠近底部
  const updateNearBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    const near = distance <= BOTTOM_THRESHOLD;
    isNearBottomRef.current = near;
    setShowJumpToLatest(!near);
  }, []);

  // 滚动事件监听：暂停吸底判定
  const handleScroll = useCallback(() => {
    updateNearBottom();
  }, [updateNearBottom]);

  // 智能吸底：仅在靠近底部时跟随
  const scrollToBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el || !isNearBottomRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, []);

  // 内容变化（消息 / 流式文本 / 空状态）时吸底
  useEffect(() => {
    updateNearBottom();
    const raf = requestAnimationFrame(() => {
      scrollToBottom();
    });
    return () => cancelAnimationFrame(raf);
  }, [messages, streamingContent, isEmptyState, updateNearBottom, scrollToBottom]);

  // 流式结束瞬间（streaming → idle）强制吸底，防止 Markdown 全量重绘导致跳回顶部
  useLayoutEffect(() => {
    const prev = prevStreamingRef.current;
    prevStreamingRef.current = isStreaming;
    if (prev && !isStreaming) {
      // 等一帧让 Markdown 渲染完，再锁死滚动锚点到最新
      const raf = requestAnimationFrame(() => {
        const el = containerRef.current;
        if (!el || !isNearBottomRef.current) return;
        el.scrollTop = el.scrollHeight;
      });
      return () => cancelAnimationFrame(raf);
    }
  }, [isStreaming]);

  // 用户主动滚回最新
  const jumpToLatest = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    isNearBottomRef.current = true;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    setShowJumpToLatest(false);
  }, []);

  return (
    <div style={{ position: "relative", flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px 24px 8px 24px",
        }}
      >
        {isEmptyState ? (
          <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            color: "var(--text-level-3)",
          }}>
            {currentAgent && (
              <AgentIcon id={currentAgent.id} size={48} strokeWidth={1.5} style={{ marginBottom: "16px", color: "var(--text-level-4)" }} />
            )}
            <p style={{ fontSize: "16px", margin: 0, lineHeight: 1.3 }}>{t("chat.startConversation")}</p>
            <p style={{ fontSize: "13px", margin: "4px 0 0 0", color: "var(--text-level-4)", lineHeight: 1.3 }}>
              {t("chat.startConversationDesc", { name: currentAgent?.name || "AI" })}
            </p>
          </div>
        ) : (
          <div style={{ maxWidth: "800px", margin: "0 auto" }}>
            {messages.map((message) => (
              <div key={message.id} style={{ marginBottom: "20px" }}>
                <ChatMessage
                  message={message}
                  currentAgent={currentAgent}
                  onQuote={onQuote}
                  onRegenerate={onRegenerate}
                  onEdit={onEdit}
                />
              </div>
            ))}
            {streamingToolCalls && streamingToolCalls.length > 0 && (
              <div style={{ marginBottom: "12px" }}>
                <ToolCallCardList toolCalls={streamingToolCalls} />
              </div>
            )}
            {streamingContent && (
              <div style={{ marginBottom: "20px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                  {currentAgent && <AgentIcon id={currentAgent.id} size={16} style={{ color: "var(--text-level-3)" }} />}
                  <span style={{ fontSize: "13px", fontWeight: 500, lineHeight: 1.25, color: "var(--text-level-3)" }}>
                    {currentAgent?.name || "AI"}
                  </span>
                </div>
                <MarkdownRenderer content={streamingContent} />
              </div>
            )}
          </div>
        )}
      </div>

      {/* 悬浮回最新按钮 */}
      {showJumpToLatest && (
        <button
          onClick={jumpToLatest}
          style={{
            position: "absolute",
            right: "24px",
            bottom: "16px",
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "6px 12px",
            borderRadius: "var(--radius-full)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-2)",
            boxShadow: "var(--shadow-md)",
            cursor: "pointer",
            fontSize: "12px",
            fontWeight: 500,
            lineHeight: 1.25,
            color: "var(--text-level-2)",
            zIndex: 50,
            outline: "none",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--color-primary)"; e.currentTarget.style.color = "var(--color-primary)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-primary)"; e.currentTarget.style.color = "var(--text-level-2)"; }}
        >
          <ArrowDown style={{ width: "13px", height: "13px" }} />
          {t("chat.jumpToLatest")}
        </button>
      )}
    </div>
  );
}
