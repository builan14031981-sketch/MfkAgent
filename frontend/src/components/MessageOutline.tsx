"use client";

import { useState, useRef, useEffect, useCallback, memo } from "react";
import type { Message } from "@/hooks/useMessages";
import { useTranslation } from "@/hooks/useTranslation";

interface MessageOutlineProps {
  messages: Message[];
  /** 当前视口对应的用户消息 id：打开时面板定位到该条目并高亮 */
  activeUserMessageId?: number | null;
  /** 调试/压测用：锁定展开态，忽略 hover */
  forceOpen?: boolean;
}

/** 收起态胶囊宽度 / 展开态面板宽度（px） */
const COLLAPSED_WIDTH = 12;
const EXPANDED_WIDTH = 240;
/** 收起态最多显示的圆点数（最近 N 条） */
const MAX_DOTS = 12;
/** HoverIntent：鼠标离开后延迟收起，边缘抖动时折返即取消，杜绝悬停鬼畜 */
const COLLAPSE_DELAY_MS = 250;

/**
 * 对话大纲悬浮导航：
 * - 收起态：右侧边缘竖排圆点胶囊（垂直居中，最近 N 条）
 * - 展开态：独立面板，标题 + 编号 + 问题预览列表
 * - 点击条目平滑滚动到对应消息并短暂高亮闪烁
 */
/** 条目预览：超长内容截断 */
function preview(content: string) {
  const text = content.replace(/\s+/g, " ").trim();
  return text.length > 34 ? `${text.slice(0, 34)}…` : text;
}

interface OutlineItemProps {
  msg: Message;
  index: number;
  isActive: boolean;
  onJump: (id: number) => void;
}

/** 条目行：memo 化，仅 isActive/内容变化时重渲染，长列表跳转时避免整列重建 */
const OutlineItem = memo(function OutlineItem({ msg, index, isActive, onJump }: OutlineItemProps) {
  return (
    <button
      data-outline-id={msg.id}
      onClick={() => onJump(msg.id)}
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "6px",
        width: "100%",
        padding: "6px",
        borderRadius: "var(--radius-md)",
        border: "none",
        background: isActive ? "var(--color-primary-lighter)" : "transparent",
        cursor: "pointer",
        textAlign: "left",
        fontSize: "13px",
        lineHeight: 1.4,
        color: isActive ? "var(--color-primary)" : "var(--text-level-2)",
        transition: "background 0.2s ease, color 0.2s ease",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "var(--color-primary-lighter)";
        e.currentTarget.style.color = "var(--color-primary)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = isActive ? "var(--color-primary-lighter)" : "transparent";
        e.currentTarget.style.color = isActive ? "var(--color-primary)" : "var(--text-level-2)";
      }}
    >
      <span style={{
        flexShrink: 0,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: "18px",
        height: "18px",
        borderRadius: "var(--radius-full)",
        background: isActive ? "var(--color-primary)" : "var(--bg-level-3)",
        color: isActive ? "#fff" : "var(--text-level-3)",
        fontSize: "12px",
        fontWeight: 600,
        marginTop: "1px",
      }}>
        {index + 1}
      </span>
      <span style={{
        flex: 1,
        minWidth: 0,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}>
        {preview(msg.content)}
      </span>
    </button>
  );
});

export function MessageOutline({ messages, activeUserMessageId = null, forceOpen = false }: MessageOutlineProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const isOpen = forceOpen || open;
  const collapseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const positionedRef = useRef(false);

  // 卸载时清理延迟收起定时器
  useEffect(() => {
    return () => {
      if (collapseTimerRef.current) clearTimeout(collapseTimerRef.current);
    };
  }, []);

  // 面板仅在「打开瞬间」定位一次到当前浏览位置；打开期间不跟随 active，
  // 避免用户点击跳转（平滑滚动中 active 阶梯变化）时面板被反复拉回
  useEffect(() => {
    if (isOpen) {
      if (positionedRef.current) return;
      positionedRef.current = true;
      const panel = panelRef.current;
      if (!panel || activeUserMessageId == null) return;
      const item = panel.querySelector(`[data-outline-id="${activeUserMessageId}"]`) as HTMLElement | null;
      if (!item) return;
      panel.scrollTop = item.offsetTop - panel.clientHeight / 2 + item.clientHeight / 2;
    } else {
      positionedRef.current = false;
    }
  }, [isOpen, activeUserMessageId]);

  // HoverIntent：进入立即展开并取消延迟收起；离开延迟 COLLAPSE_DELAY_MS 再收起
  const handleMouseEnter = () => {
    if (collapseTimerRef.current) {
      clearTimeout(collapseTimerRef.current);
      collapseTimerRef.current = null;
    }
    setOpen(true);
  };

  const handleMouseLeave = () => {
    if (collapseTimerRef.current) clearTimeout(collapseTimerRef.current);
    collapseTimerRef.current = setTimeout(() => {
      collapseTimerRef.current = null;
      setOpen(false);
    }, COLLAPSE_DELAY_MS);
  };

  const userMessages = messages.filter((m) => m.role === "user");

  // 高亮闪烁：用 Web Animations API 直接作用于目标消息行，无需改动 MessageList 内部
  const flashTarget = useCallback((id: number) => {
    const el = document.getElementById(`msg-${id}`);
    if (!el) return;
    el.animate(
      [
        { backgroundColor: "rgba(76, 154, 255, 0.16)" },
        { backgroundColor: "rgba(76, 154, 255, 0)" },
      ],
      { duration: 1600, easing: "ease-out" }
    );
  }, []);

  const handleJump = useCallback((id: number) => {
    const el = document.getElementById(`msg-${id}`);
    if (!el) return;

    // 找到滚动容器（overflow 可滚动的祖先）；找不到则回退 scrollIntoView
    let container: HTMLElement | null = el.parentElement;
    while (container && container !== document.body) {
      const overflowY = getComputedStyle(container).overflowY;
      if (overflowY === "auto" || overflowY === "scroll") break;
      container = container.parentElement;
    }

    if (container && container !== document.body) {
      // 只滚动消息容器：scrollIntoView 会同时滚动所有滚动祖先，长距离跳转时
      // 多层 smooth 动画并发易被 Chromium 取消 →「第一下没反应」
      const elRect = el.getBoundingClientRect();
      const conRect = container.getBoundingClientRect();
      const targetTop =
        container.scrollTop + (elRect.top - conRect.top) - conRect.height / 2 + elRect.height / 2;
      const clamped = Math.min(
        Math.max(targetTop, 0),
        container.scrollHeight - container.clientHeight
      );
      const startTop = container.scrollTop;
      container.scrollTo({ top: clamped, behavior: "smooth" });
      // 兜底：若 smooth 动画被布局变化取消（几乎未动且目标仍远），350ms 后瞬时补跳
      setTimeout(() => {
        const cur = container.scrollTop;
        if (Math.abs(cur - startTop) < 4 && Math.abs(cur - clamped) > 8) {
          container.scrollTop = clamped;
        }
      }, 350);
    } else {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    flashTarget(id);
  }, [flashTarget]);

  if (userMessages.length === 0) return null;

  // 收起态只渲染最近 N 个点，避免超长对话撑爆胶囊
  const dots = userMessages.slice(-MAX_DOTS);
  const latestId = userMessages[userMessages.length - 1].id;

  return (
    <div
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      aria-label={t("chat.messageOutline")}
      style={{
        position: "absolute",
        right: "12px",
        top: "50%",
        transform: "translateY(-50%)",
        zIndex: 30,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: isOpen ? "flex-start" : "center",
        boxSizing: "border-box",
        width: isOpen ? `${EXPANDED_WIDTH}px` : `${COLLAPSED_WIDTH}px`,
        maxHeight: "min(60vh, 420px)",
        padding: isOpen ? "10px" : "8px 4px",
        borderRadius: isOpen ? "var(--radius-lg)" : "var(--radius-full)",
        background: isOpen ? "var(--bg-level-2)" : "transparent",
        border: isOpen ? "1px solid var(--border-primary)" : "none",
        boxShadow: isOpen ? "var(--shadow-lg)" : "none",
        overflowY: isOpen ? "auto" : "hidden",
        cursor: isOpen ? "default" : "pointer",
      }}
      ref={panelRef}
    >
      {isOpen ? (
        <>
          <div style={{
            fontSize: "12px",
            fontWeight: 600,
            color: "var(--text-level-3)",
            marginBottom: "8px",
            lineHeight: 1.25,
            alignSelf: "flex-start",
          }}>
            {t("chat.messageOutline")}
          </div>
          {userMessages.map((msg, i) => (
            <OutlineItem
              key={msg.id}
              msg={msg}
              index={i}
              isActive={msg.id === activeUserMessageId}
              onJump={handleJump}
            />
          ))}
        </>
      ) : (
        dots.map((msg) => (
          <span
            key={msg.id}
            style={{
              width: "4px",
              height: "4px",
              margin: "3px 0",
              borderRadius: "var(--radius-full)",
              background: msg.id === latestId ? "var(--color-primary)" : "var(--text-level-3)",
              flexShrink: 0,
            }}
          />
        ))
      )}
    </div>
  );
}
