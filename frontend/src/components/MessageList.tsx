"use client";

import { useRef, useCallback, useEffect, useLayoutEffect, useMemo, memo, useState, type MouseEvent as ReactMouseEvent } from "react";
import { ArrowDown, AlertTriangle, RotateCw, Package, ChevronDown, ChevronRight } from "lucide-react";
import type { Message } from "@/hooks/useMessages";
import { ChatMessage, ThinkingPanel, StreamingThinkingPanel, MemorySavedNotice } from "@/components/ChatMessage";
import { ImageLightbox } from "@/components/ImageLightbox";
import { AgentIcon } from "@/components/AgentIcon";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { ToolCallGroup, groupToolCalls } from "@/components/ToolCallGroup";
import { ToolApprovalCard } from "@/components/ToolApprovalCard";
import { UserChoiceCard } from "@/components/UserChoiceCard";
import type { RuntimeEvent } from "@/types/runtime";
import type { OrbStage } from "@/lib/streamStore";
import { useTranslation } from "@/hooks/useTranslation";

interface MessageListProps {
  messages: Message[];
  /** 运行时事件时间线：按 SSE 真实到达顺序排列 thinking/tool/approval/text（及未来扩展类型） */
  timeline: RuntimeEvent[];
  streamingError?: string | null;
  isStreaming: boolean;
  /** 流式加载阶段：非空时在流式块头部显示 Orb 动画 */
  streamingStage?: OrbStage | null;
  reasoningActive?: boolean;
  currentAgent?: { id: string; name: string } | null;
  onQuote: (content: string) => void;
  onRegenerate: (messageId: number) => void;
  onRetry?: () => void;
  onEdit: (message: Message) => void;
  /** 审批卡片回调（timeline 中的 approval event 使用） */
  onApproveApproval?: (approvalId: string, toolCallId?: string) => void;
  onDenyApproval?: (approvalId: string, toolCallId?: string) => void;
  /** 抉择卡片回调（timeline 中的 user_choice event 使用） */
  onSelectChoice?: (choiceId: string, selected: number) => void;
  onChoiceCustomText?: (choiceId: string, text: string) => void;
  onSkipChoice?: (choiceId: string) => void;
  /** 当前视口对应的用户消息 id 变化时回调（供对话大纲定位/高亮） */
  onActiveUserMessageChange?: (messageId: number | null) => void;
  /** 滚动位置持久化 key（如 `mfk_chat_scroll_${chatId}`）：存当前活跃用户消息 id，进入会话时恢复 */
  scrollPersistenceKey?: string;
}

/** 距离底部阈值：低于该值视为"用户停在底部"，自动吸底 */
const BOTTOM_THRESHOLD = 120;

/** 判断消息是否为压缩摘要节点 */
function isCompressionNode(message: Message): boolean {
  return message.role === "user" && message.content.startsWith("【历史记忆摘要】");
}

/**
 * AI 消息用时 = 自身 created_at − 前一条用户消息 created_at。
 * 两端均为本机时钟（后端本地运行），乐观消息与 refetch 后的历史消息都成立；
 * 找不到前置用户消息或时间非法时返回 undefined（不展示）。
 */
function computeAssistantDuration(message: Message, messages: Message[], idx: number): number | undefined {
  if (message.role !== "assistant" || !message.created_at) return undefined;
  for (let i = idx - 1; i >= 0; i--) {
    const prev = messages[i];
    if (prev.role === "user") {
      if (!prev.created_at) return undefined;
      const diff = new Date(message.created_at).getTime() - new Date(prev.created_at).getTime();
      return Number.isFinite(diff) && diff > 0 ? diff : undefined;
    }
  }
  return undefined;
}

/**
 * 压缩节点卡片：折叠展示历史记忆摘要。
 * - 默认折叠，点击展开查看完整摘要
 * - 图标 + 提示语："已压缩 XX 轮历史对话"
 */
function CompressionNodeCard({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(false);
  const summary = content.replace("【历史记忆摘要】\n", "").trim();

  // 估算压缩轮数：从摘要中提取信息
  const roundCount = useMemo(() => {
    const lines = summary.split("\n").filter(Boolean);
    return lines.length;
  }, [summary]);

  return (
    <div style={{
      marginBottom: "20px",
      display: "flex",
      justifyContent: "center",
    }}>
      <div style={{
        maxWidth: "600px",
        width: "100%",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--border-primary)",
        background: "var(--bg-level-3)",
        overflow: "hidden",
      }}>
        <button
          onClick={() => setExpanded((v) => !v)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            width: "100%",
            padding: "10px 14px",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            fontSize: "13px",
            color: "var(--text-level-2)",
            textAlign: "left",
          }}
        >
          <Package style={{ width: "16px", height: "16px", color: "var(--color-primary)", flexShrink: 0 }} />
          <span style={{ flex: 1, fontWeight: 500 }}>
            已压缩 {roundCount} 轮历史对话
          </span>
          {expanded ? (
            <ChevronDown style={{ width: "14px", height: "14px", color: "var(--text-level-4)", flexShrink: 0 }} />
          ) : (
            <ChevronRight style={{ width: "14px", height: "14px", color: "var(--text-level-4)", flexShrink: 0 }} />
          )}
        </button>
        {expanded && (
          <div style={{
            padding: "0 14px 12px 38px",
            fontSize: "12px",
            lineHeight: "1.6",
            color: "var(--text-level-3)",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}>
            {summary}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * 消息列表 + 智能吸底滚动：
 * - 用户停在底部时用 rAF 平滑吸底，禁止剧烈抖动
 * - 用户向上浏览历史时暂停吸底，右下角浮现 [↓ 回最新]
 *
 * memo：滚动/流式期间 active 追踪的 state 更新在父级（page）发生，
 * 若此处每帧重渲染会全量重跑 400 条消息的 Markdown 树导致卡顿，
 * memo 确保父级 re-render 时消息树跳过。
 */
export const MessageList = memo(function MessageList({ messages, timeline, streamingError, isStreaming, reasoningActive, currentAgent, onQuote, onRegenerate, onRetry, onEdit, onApproveApproval, onDenyApproval, onSelectChoice, onChoiceCustomText, onSkipChoice, onActiveUserMessageChange, scrollPersistenceKey }: MessageListProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const lastActiveRef = useRef<number | null>(null);
  const restoredRef = useRef(false);
  const jumpButtonRef = useRef<HTMLButtonElement>(null);

  // ──── 图片预览 Lightbox 状态（全局唯一实例） ────
  const [lightboxState, setLightboxState] = useState<{ urls: string[]; index: number } | null>(null);
  const handleImageClick = useCallback((urls: string[], index: number) => {
    setLightboxState({ urls, index });
  }, []);
  const handleLightboxClose = useCallback(() => setLightboxState(null), []);

  // 空状态：渲染期派生，避免 effect 中 setState
  const isEmptyState = messages.length === 0 && timeline.length === 0;

  const userMessageIds = useMemo(
    () => messages.filter((m) => m.role === "user").map((m) => m.id),
    [messages]
  );

  // ---- 用户消息浮动焦点锚（V3 单锚点：全列表零 sticky） ----
  // 已滚出滚动区顶部视线的用户消息 id 集合；锚点 = 其中位置最深的一条，
  // 由唯一的浮动焦点条呈现。滚回原位（行重新可见）→ 锚点解除 → 焦点条消失。
  const stuckUserIdsRef = useRef<Set<number>>(new Set());
  const [focusAnchorId, setFocusAnchorId] = useState<number | null>(null);

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
  }, [messages, timeline, streamingError, isEmptyState, updateNearBottom, scrollToBottom]);

  // 监听发送状态或流式开始（false -> true）：强制重置吸底锁并滚动到底部
  const isActive = isStreaming;
  const prevActiveRef = useRef(isActive);

  useEffect(() => {
    const wasActive = prevActiveRef.current;
    prevActiveRef.current = isActive;

    if (isActive && !wasActive) {
      // 用户刚点击发送或开始流式 -> 强行重置吸底意图
      isNearBottomRef.current = true;
      updateJumpButton(false);

      const raf = requestAnimationFrame(() => {
        const el = containerRef.current;
        if (el) el.scrollTop = el.scrollHeight;
      });
      return () => cancelAnimationFrame(raf);
    }
  }, [isActive, updateJumpButton]);

  // 用户主动滚回最新
  const jumpToLatest = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    isNearBottomRef.current = true;
    updateJumpButton(false);
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [updateJumpButton]);

  // 锚点观测：判定法只用于"是否已滚出顶部"（!isIntersecting && top < rootTop），
  // 浮动元素本身不做 sticky，不存在释放边界/多锚交接问题。
  // 压缩摘要节点不是真实气泡，不参与锚点。
  const anchorableIds = useMemo(
    () => messages.filter((m) => m.role === "user" && !isCompressionNode(m)).map((m) => m.id),
    [messages]
  );

  useEffect(() => {
    const root = containerRef.current;
    if (!root || anchorableIds.length === 0) return;
    stuckUserIdsRef.current.clear();
    const io = new IntersectionObserver(
      (entries) => {
        const rootTop = root.getBoundingClientRect().top;
        for (const entry of entries) {
          const id = Number((entry.target as HTMLElement).id.replace(/^msg-/, ""));
          if (!Number.isFinite(id)) continue;
          const stuck = !entry.isIntersecting && entry.boundingClientRect.top < rootTop;
          if (stuck) stuckUserIdsRef.current.add(id);
          else stuckUserIdsRef.current.delete(id);
        }
        let anchor: number | null = null;
        for (let i = anchorableIds.length - 1; i >= 0; i--) {
          if (stuckUserIdsRef.current.has(anchorableIds[i])) {
            anchor = anchorableIds[i];
            break;
          }
        }
        setFocusAnchorId((prev) => (prev === anchor ? prev : anchor));
      },
      { root, rootMargin: "-1px 0px 0px 0px", threshold: 0 }
    );
    anchorableIds.forEach((id) => {
      const el = document.getElementById(`msg-${id}`);
      if (el) io.observe(el);
    });
    return () => io.disconnect();
  }, [anchorableIds]);

  const focusAnchorMessage = useMemo(
    () => (focusAnchorId == null ? null : messages.find((m) => m.id === focusAnchorId) ?? null),
    [focusAnchorId, messages]
  );

  // 溢出检测：锚点切换时量一次，超出两行才打 data-overflow（CSS 只对长消息挂底部渐变，
  // 短消息文字完整无 mask）。滚动期间零开销。
  const focusChipRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = focusChipRef.current;
    if (!el) return;
    if (el.scrollHeight > el.clientHeight) el.dataset.overflow = "true";
    else delete el.dataset.overflow;
  }, [focusAnchorMessage]);

  // 双击焦点条回弹：平滑滚回锚点消息原位（reduced-motion 时瞬跳）
  const handleFocusDoubleClick = useCallback((e: ReactMouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    const root = containerRef.current;
    if (!root || focusAnchorId == null) return;
    const row = document.getElementById(`msg-${focusAnchorId}`);
    if (!row) return;
    const delta = row.getBoundingClientRect().top - root.getBoundingClientRect().top - 6;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    root.scrollBy({ top: delta, behavior: reduce ? "auto" : "smooth" });
  }, [focusAnchorId]);

  // 流式 timeline：连续工具段合并为组（中间无 text/thinking/memory 则归一组），渲染层计算
  const toolBlocks = useMemo(
    () =>
      groupToolCalls(timeline, (s) => (s.type === "tool" ? s.toolCall : undefined)),
    [timeline]
  );

  return (
    <>
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
            {messages.map((message, idx) => (
              <div key={message.id} id={`msg-${message.id}`} style={{ marginBottom: "8px" }}>
                {isCompressionNode(message) ? (
                  <CompressionNodeCard content={message.content} />
                ) : (
                  <ChatMessage
                    message={message}
                    currentAgent={currentAgent}
                    durationMs={computeAssistantDuration(message, messages, idx)}
                    onQuote={onQuote}
                    onRegenerate={onRegenerate}
                    onEdit={onEdit}
                    onImageClick={handleImageClick}
                  />
                )}
              </div>
            ))}
            {timeline.length > 0 && (
              <div style={{ marginBottom: "12px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                  {/* 2026-08-12：去除流式期间 AgentOrb 动画，思考状态由思考面板 Loader2 唯一表达，避免双动画 */}
                  {currentAgent ? (
                    <AgentIcon id={currentAgent.id} size={16} style={{ color: "var(--text-level-3)" }} />
                  ) : null}
                  <span style={{ fontSize: "13px", fontWeight: 500, lineHeight: 1.25, color: "var(--text-level-3)" }}>
                    {currentAgent?.name || "AI"}
                  </span>
                </div>
                {toolBlocks.map((block) => {
                  // 工具段：按组渲染（流式中单行头 / 完成后摘要组头，可展开）
                  if (block.kind === "tool") {
                    return (
                      <ToolCallGroup
                        key={`toolgroup-${block.tools[0]?.tool_call_id ?? block.tools.length}`}
                        tools={block.tools}
                        streaming={block.streaming}
                      />
                    );
                  }
                  const seg = block.seg;
                  switch (seg.type) {
                    case "thinking":
                      return <ThinkingPanel key={seg.id} thinking={seg.content} />;
                    case "thinking_indicator":
                      return <StreamingThinkingPanel key={seg.id} content={seg.content} isActive={reasoningActive ?? false} />;
                    case "approval":
                      return (
                        <div key={seg.id} style={{ marginTop: "8px" }}>
                          <ToolApprovalCard
                            approval={seg.approval}
                            onApprove={(id) => onApproveApproval?.(id, seg.approval.tool_call_id)}
                            onDeny={(id) => onDenyApproval?.(id, seg.approval.tool_call_id)}
                          />
                        </div>
                      );
                    case "user_choice":
                      return (
                        <div key={seg.id} style={{ marginTop: "8px" }}>
                          <UserChoiceCard
                            choice={seg.choice}
                            onSelect={onSelectChoice}
                            onCustomText={onChoiceCustomText}
                            onSkip={onSkipChoice}
                          />
                        </div>
                      );
                    case "text":
                      return <MarkdownRenderer key={seg.id} content={seg.content} />;
                    case "memory_saved":
                      return (
                        <div key={seg.id} style={{ marginBottom: "8px" }}>
                          <MemorySavedNotice count={seg.count} items={seg.items} />
                        </div>
                      );
                    // task_* 事件不进入 timeline 渲染（由独立 tasks 状态 + TaskProgressCard 处理）
                    case "task_started":
                    case "task_completed":
                    case "task_failed":
                    case "task_skipped":
                      return null;
                    // 工具段已由 toolBlocks 分组提前消费（见 ToolCallGroup），此分支仅为保留类型收窄
                    // （否则 default 分支中 seg 会包含无 title/content 的 ToolEvent 导致类型报错），运行时不会命中。
                    case "tool":
                      return null;
                    // 未来扩展事件（verification / sub_agent / vision / memory）：
                    // 以通用占位块呈现，字段就绪后可替换为专用组件
                    default:
                      return (
                        <div key={seg.id} style={{ marginBottom: "8px" }}>
                          <div style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                            padding: "6px 12px",
                            borderRadius: "var(--radius-md)",
                            background: "var(--bg-level-3)",
                            border: "1px solid var(--border-primary)",
                            fontSize: "12px",
                            color: "var(--text-level-3)",
                          }}>
                            <span style={{
                              flexShrink: 0,
                              padding: "0 6px",
                              borderRadius: "var(--radius-xs)",
                              fontSize: "10px",
                              fontWeight: 600,
                              lineHeight: "16px",
                              fontFamily: "var(--font-geist-mono), var(--font-family)",
                              color: "var(--text-level-3)",
                              background: "color-mix(in srgb, var(--bg-level-2) 60%, transparent)",
                              border: "1px solid var(--border-primary)",
                            }}>{seg.type}</span>
                            <span style={{
                              flex: 1,
                              minWidth: 0,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}>{seg.title || seg.content || seg.type}</span>
                          </div>
                        </div>
                      );
                  }
                })}
              </div>
            )}
            {/* 多 Agent 任务进度卡片已移至输入框上方（TaskProgressCard 在 page.tsx 中渲染） */}
            {streamingError && (
              <div style={{
                marginBottom: "16px",
                maxWidth: "800px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--color-error)",
                background: "color-mix(in srgb, var(--color-error) 8%, var(--bg-level-3))",
                padding: "12px 14px",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                  <AlertTriangle style={{ width: "16px", height: "16px", color: "var(--color-error)", flexShrink: 0 }} />
                  <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--color-error)", lineHeight: 1.3 }}>
                    {t("chat.streamErrorTitle")}
                  </span>
                </div>
                <p style={{
                  margin: 0,
                  fontSize: "12px",
                  lineHeight: 1.6,
                  color: "var(--text-level-2)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}>{streamingError}</p>
                {onRetry && (
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "12px" }}>
                    <button
                      onClick={onRetry}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        padding: "7px 16px",
                        borderRadius: "var(--radius-md)",
                        border: "none",
                        background: "var(--color-primary)",
                        color: "var(--text-on-primary)",
                        cursor: "pointer",
                        fontSize: "13px",
                        fontWeight: 500,
                        transition: "background 0.2s ease",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-primary-hover)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "var(--color-primary)")}
                    >
                      <RotateCw style={{ width: "13px", height: "13px" }} />
                      {t("chat.streamRetry")}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 浮动焦点条：当前锚点用户消息的唯一浮层（V3 单锚点）。
          外层 absolute 横跨全宽，内层复用 800px 居中列 + 24px 内边距，
          保证焦点条右缘在任何窗口宽度下都与用户气泡右缘对齐。
          无锚点时整块不渲染；切换会话瞬间旧锚失效由判空兑底。 */}
      {focusAnchorMessage && (
        <div
          style={{
            position: "absolute",
            top: "6px",
            left: 0,
            right: 0,
            zIndex: 60,
            pointerEvents: "none",
          }}
        >
          <div style={{ maxWidth: "800px", margin: "0 auto", padding: "0 24px", display: "flex", justifyContent: "flex-end" }}>
            <div
              ref={focusChipRef}
              className="mf-focus-chip"
              onDoubleClick={handleFocusDoubleClick}
              title={t("chat.stuckHint")}
              style={{ pointerEvents: "auto" }}
            >
              {focusAnchorMessage.content || "\u00A0"}
            </div>
          </div>
        </div>
      )}

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
    {/* 图片预览 Lightbox（全局唯一实例） */}
    {lightboxState && (
      <ImageLightbox
        urls={lightboxState.urls}
        initialIndex={lightboxState.index}
        onClose={handleLightboxClose}
      />
    )}
  </>
  );
});
