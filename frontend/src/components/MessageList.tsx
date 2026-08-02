"use client";

import { useRef, useCallback, useEffect, useLayoutEffect, useMemo, memo } from "react";
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
  /** 当前视口对应的用户消息 id 变化时回调（供对话大纲定位/高亮） */
  onActiveUserMessageChange?: (messageId: number | null) => void;
  /** 滚动位置持久化 key（如 `mfk_chat_scroll_${chatId}`）：存当前活跃用户消息 id，进入会话时恢复 */
  scrollPersistenceKey?: string;
}

/** 距离底部阈值：低于该值视为"用户停在底部"，自动吸底 */
const BOTTOM_THRESHOLD = 120;

/**
 * 消息列表 + 智能吸底滚动：
 * - 用户停在底部时用 rAF 平滑吸底，禁止剧烈抖动
 * - 用户向上浏览历史时暂停吸底，右下角浮现 [↓ 回最新]
 *
 * memo：滚动/流式期间 active 追踪的 state 更新在父级（page）发生，
 * 若此处每帧重渲染会全量重跑 400 条消息的 Markdown 树导致卡顿，
 * memo 确保父级 re-render 时消息树跳过。
 */
export const MessageList = memo(function MessageList({ messages, streamingContent, streamingToolCalls, isStreaming, currentAgent, onQuote, onRegenerate, onEdit, onActiveUserMessageChange, scrollPersistenceKey }: MessageListProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const prevStreamingRef = useRef(isStreaming);
  const lastActiveRef = useRef<number | null>(null);
  const restoredRef = useRef(false);
  const jumpButtonRef = useRef<HTMLButtonElement>(null);

  // 空状态：渲染期派生，避免 effect 中 setState
  const isEmptyState = messages.length === 0 && !streamingContent;

  const userMessageIds = useMemo(
    () => messages.filter((m) => m.role === "user").map((m) => m.id),
    [messages]
  );

  // 滚动位置持久化：提交 active 时写入 localStorage（退出/切换会话时即时 flush）
  const persistPosition = useCallback(() => {
    if (!scrollPersistenceKey || lastActiveRef.current == null) return;
    try {
      localStorage.setItem(scrollPersistenceKey, String(lastActiveRef.current));
    } catch {
      /* 忽略存储异常 */
    }
  }, [scrollPersistenceKey]);

  // active 提交：滚动停止 300ms 后才对外更新（高亮/持久化）。
  // 关键：滚动期间零 DOM 修改，避免「大纲高亮 patch → 布局 dirty → 下一帧
  // getBoundingClientRect 强制全树重排」的卡顿闭环。
  const submitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const commitActive = useCallback(() => {
    submitTimerRef.current = null;
    const active = lastActiveRef.current;
    if (active != null) {
      onActiveUserMessageChange?.(active);
      persistPosition();
    }
  }, [onActiveUserMessageChange, persistPosition]);

  const scheduleCommit = useCallback(() => {
    if (submitTimerRef.current) clearTimeout(submitTimerRef.current);
    submitTimerRef.current = setTimeout(() => commitActive(), 300);
  }, [commitActive]);

  // 计算当前视口对应的用户消息：二分找第一条位于容器视口顶部的 user 消息；滚到底则取最后一条
  // 二分前提：消息 DOM 顺序与 userMessageIds 一致，getBoundingClientRect().top 单调递增
  // 注意：此处只更新 lastActiveRef（读缓存布局），不触发任何 setState / DOM 修改
  const computeActiveUserMessage = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    const containerTop = container.getBoundingClientRect().top;
    let lo = 0;
    let hi = userMessageIds.length - 1;
    let active: number | null = null;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      const el = container.querySelector<HTMLElement>(`[id="msg-${userMessageIds[mid]}"]`);
      const top = el ? el.getBoundingClientRect().top : Infinity;
      if (top >= containerTop) {
        active = userMessageIds[mid];
        hi = mid - 1;
      } else {
        lo = mid + 1;
      }
    }
    if (active === null && userMessageIds.length > 0) {
      active = userMessageIds[userMessageIds.length - 1];
    }
    if (active !== lastActiveRef.current) {
      lastActiveRef.current = active;
      scheduleCommit();
    }
  }, [userMessageIds, scheduleCommit]);

  // rAF 节流：scroll 高频触发时每帧最多计算一次，避免平滑滚动期间反复同步布局
  const activeRafRef = useRef<number | null>(null);
  const scheduleComputeActive = useCallback(() => {
    if (activeRafRef.current != null) return;
    activeRafRef.current = requestAnimationFrame(() => {
      activeRafRef.current = null;
      computeActiveUserMessage();
    });
  }, [computeActiveUserMessage]);

  // 会话切换 / 卸载时：重置恢复标记并立即保存当前位置（flush 待提交的 active）
  useEffect(() => {
    restoredRef.current = false;
    return () => {
      if (activeRafRef.current != null) cancelAnimationFrame(activeRafRef.current);
      if (submitTimerRef.current) clearTimeout(submitTimerRef.current);
      commitActive();
    };
  }, [scrollPersistenceKey, commitActive]);

  // 恢复：消息首次可用后定位到上次浏览位置（非底部，禁用吸底）
  useEffect(() => {
    if (restoredRef.current || !scrollPersistenceKey) return;
    if (messages.length === 0) return;
    let saved: string | null = null;
    try {
      saved = localStorage.getItem(scrollPersistenceKey);
    } catch {
      /* 忽略 */
    }
    if (saved) {
      const id = Number(saved);
      const el = document.getElementById(`msg-${id}`);
      if (el) {
        el.scrollIntoView({ behavior: "auto", block: "center" });
        isNearBottomRef.current = false;
        restoredRef.current = true;
      }
    }
  }, [messages, scrollPersistenceKey]);

  // 挂载 / 消息增删时重算一次（滚动时由 handleScroll 驱动），挂载时立即提交一次 active
  useEffect(() => {
    computeActiveUserMessage();
    commitActive();
    return () => {
      if (activeRafRef.current != null) cancelAnimationFrame(activeRafRef.current);
    };
  }, [computeActiveUserMessage, commitActive]);

  // 跳转按钮显隐：直接操作原生 DOM（opacity/pointer-events/transform），
  // 全部为合成器属性不触发重排，且完全绕开 React state → 滚动中显隐零重渲染
  const updateJumpButton = useCallback((show: boolean) => {
    const btn = jumpButtonRef.current;
    if (!btn) return;
    btn.style.opacity = show ? "1" : "0";
    btn.style.pointerEvents = show ? "auto" : "none";
    btn.style.transform = show ? "translateY(0)" : "translateY(10px)";
  }, []);

  // 判断是否靠近底部
  const updateNearBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    const near = distance <= BOTTOM_THRESHOLD;
    isNearBottomRef.current = near;
    updateJumpButton(!near);
  }, [updateJumpButton]);

  // 滚动事件监听：暂停吸底判定 + 追踪当前活跃用户消息（rAF 节流）
  const handleScroll = useCallback(() => {
    updateNearBottom();
    scheduleComputeActive();
  }, [updateNearBottom, scheduleComputeActive]);

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
    updateJumpButton(false);
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [updateJumpButton]);

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
              <div key={message.id} id={`msg-${message.id}`} style={{ marginBottom: "20px" }}>
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

      {/* 悬浮回最新按钮：常驻 DOM，显隐由 updateJumpButton 直操（初始隐藏）。
          注意：style 中不写动态属性，避免 React 重渲染时覆盖手动设置的 DOM 值 */}
      <button
        ref={jumpButtonRef}
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
          opacity: "0",
          pointerEvents: "none",
          transform: "translateY(10px)",
          transition: "opacity 0.3s ease, transform 0.3s ease",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--color-primary)"; e.currentTarget.style.color = "var(--color-primary)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-primary)"; e.currentTarget.style.color = "var(--text-level-2)"; }}
      >
        <ArrowDown style={{ width: "13px", height: "13px" }} />
        {t("chat.jumpToLatest")}
      </button>
    </div>
  );
});
