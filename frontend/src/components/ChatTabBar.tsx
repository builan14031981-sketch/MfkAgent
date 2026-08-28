"use client";

import React, { useRef, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Plus, X, MessageSquare, Copy, ArrowRightToLine, Ban } from "lucide-react";
import { useTabStore } from "@/lib/tabStore";
import { useStreamStore } from "@/lib/streamStore";
import { AgentIcon } from "@/components/AgentIcon";

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  chatId: number | null;
}

interface ChatTabBarProps {
  onNewChat?: () => void;
}

export function ChatTabBar({ onNewChat }: ChatTabBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);
  const tabs = useTabStore((s) => s.tabs);
  const activeChatId = useTabStore((s) => s.activeChatId);
  const closeTab = useTabStore((s) => s.closeTab);
  const closeOtherTabs = useTabStore((s) => s.closeOtherTabs);
  const closeRightTabs = useTabStore((s) => s.closeRightTabs);
  const streams = useStreamStore((s) => s.streams);

  const scrollRef = useRef<HTMLDivElement>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false,
    x: 0,
    y: 0,
    chatId: null,
  });

  useEffect(() => {
    setMounted(true);
  }, []);

  // 鼠标滚轮横向平滑滚动
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const handleWheel = (e: WheelEvent) => {
      if (e.deltaY !== 0) {
        e.preventDefault();
        el.scrollLeft += e.deltaY;
      }
    };
    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, []);

  // 点击外部关闭右键菜单
  useEffect(() => {
    const handleOutsideClick = () => {
      if (contextMenu.visible) {
        setContextMenu((prev) => ({ ...prev, visible: false }));
      }
    };
    window.addEventListener("click", handleOutsideClick);
    window.addEventListener("contextmenu", handleOutsideClick);
    return () => {
      window.removeEventListener("click", handleOutsideClick);
      window.removeEventListener("contextmenu", handleOutsideClick);
    };
  }, [contextMenu.visible]);

  const handleSelectTab = (chatId: number) => {
    router.push(`/chat/${chatId}`);
  };

  const handleCloseTab = (e: React.MouseEvent, chatId: number) => {
    e.stopPropagation();
    const nextId = closeTab(chatId);
    if (activeChatId === chatId) {
      if (nextId != null) {
        router.push(`/chat/${nextId}`);
      } else {
        router.push("/");
      }
    }
  };

  const handleContextMenu = (e: React.MouseEvent, chatId: number) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      visible: true,
      x: e.clientX,
      y: e.clientY,
      chatId,
    });
  };

  const handleCopyLink = async (chatId: number) => {
    try {
      const url = `${window.location.origin}/chat/${chatId}`;
      await navigator.clipboard.writeText(url);
    } catch {
      // 忽略剪贴板错误
    }
    setContextMenu((prev) => ({ ...prev, visible: false }));
  };

  // 客户端挂载前不渲染，保持与 SSR 初始状态一致
  if (!mounted) {
    return null;
  }

  // 如果没有打开任何标签且当前不在 chat 页面，不渲染
  if (tabs.length === 0 && !pathname.startsWith("/chat/")) {
    return null;
  }

  return (
    <>
      <style>{`
        @keyframes mfk-tab-pulse {
          0%, 100% { transform: scale(1); opacity: 0.7; }
          50% { transform: scale(1.25); opacity: 1; filter: drop-shadow(0 0 3px var(--color-primary, #3b82f6)); }
        }

        /* 标签基础样式 */
        .chrome-tab {
          position: relative;
          display: flex;
          align-items: center;
          gap: 6px;
          height: 32px;
          padding: 0 10px 0 12px;
          font-size: 12px;
          cursor: pointer;
          user-select: none;
          max-width: 190px;
          min-width: 100px;
          margin-top: 4px;
          border-top-left-radius: 8px;
          border-top-right-radius: 8px;
          transition: background 0.15s ease, color 0.15s ease;
          box-sizing: border-box;
        }

        /* 活跃标签：底部无边框，实色背景精准覆盖假底线 */
        .chrome-tab--active {
          background: var(--bg-app, var(--bg-level-1));
          color: var(--text-level-1);
          font-weight: 500;
          z-index: 2;
          /* 顶部与左右边框 */
          border-top: 1px solid var(--border-primary);
          border-left: 1px solid var(--border-primary);
          border-right: 1px solid var(--border-primary);
          border-bottom: none;
        }

        /* 非活跃标签 */
        .chrome-tab--inactive {
          background: transparent;
          color: var(--text-level-3);
          border: 1px solid transparent;
          border-bottom: none;
        }
        .chrome-tab--inactive:hover {
          background: color-mix(in srgb, var(--text-level-1) 5%, transparent);
          color: var(--text-level-2);
          border-radius: 6px 6px 0 0;
        }

        /* 非活跃标签之间的分割线 */
        .chrome-tab-divider {
          position: absolute;
          right: -1px;
          top: 50%;
          transform: translateY(-50%);
          width: 1px;
          height: 14px;
          background: color-mix(in srgb, var(--border-primary) 70%, transparent);
          pointer-events: none;
          transition: opacity 0.15s ease;
        }

        .chrome-tab:hover .chrome-tab-divider,
        .chrome-tab--active .chrome-tab-divider {
          opacity: 0;
        }

        /* 关闭按钮 */
        .chrome-tab-close {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 16px;
          height: 16px;
          border-radius: 4px;
          border: none;
          background: transparent;
          cursor: pointer;
          color: inherit;
          padding: 0;
          flex-shrink: 0;
          opacity: 0;
          transition: opacity 0.12s ease, background 0.12s ease;
        }
        .chrome-tab:hover .chrome-tab-close {
          opacity: 0.6;
        }
        .chrome-tab--active .chrome-tab-close {
          opacity: 0.75;
        }
        .chrome-tab-close:hover {
          opacity: 1 !important;
          background: color-mix(in srgb, var(--text-level-1) 12%, transparent);
        }

        /* 新建标签按钮 */
        .chrome-tab-new {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 26px;
          height: 26px;
          border-radius: 6px;
          border: none;
          background: transparent;
          cursor: pointer;
          color: var(--text-level-3);
          flex-shrink: 0;
          margin-top: 4px;
          transition: all 0.15s ease;
        }
        .chrome-tab-new:hover {
          background: color-mix(in srgb, var(--text-level-1) 6%, transparent);
          color: var(--text-level-1);
        }
      `}</style>

      {/* 浏览器顶栏容器 */}
      <div
        style={{
          position: "relative",
          display: "flex",
          alignItems: "flex-end",
          height: "36px",
          background: "var(--bg-level-2)",
          padding: "0 10px",
          gap: "4px",
          userSelect: "none",
          flexShrink: 0,
          zIndex: 10,
        }}
      >
        {/* 全局底线（放在底层） */}
        <div style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: "1px",
          background: "var(--border-primary)",
          zIndex: 1,
        }} />

        {/* 横向滚动标签容器 */}
        <div
          ref={scrollRef}
          style={{
            display: "flex",
            alignItems: "flex-end",
            overflowX: "auto",
            scrollbarWidth: "none",
            msOverflowStyle: "none",
            flex: 1,
            height: "100%",
            paddingRight: "8px",
            zIndex: 2, // 确保标签容器在底线之上
          }}
        >
          {tabs.map((tab, idx) => {
            const isActive =
              tab.chatId === activeChatId &&
              (pathname === `/chat/${tab.chatId}` || pathname.startsWith(`/chat/${tab.chatId}/`));
            const isStreaming = Boolean(streams[tab.chatId]);
            const nextTab = tabs[idx + 1];
            const nextIsActive =
              nextTab &&
              nextTab.chatId === activeChatId &&
              (pathname === `/chat/${nextTab.chatId}` || pathname.startsWith(`/chat/${nextTab.chatId}/`));

            return (
              <div
                key={tab.chatId}
                onClick={() => handleSelectTab(tab.chatId)}
                onContextMenu={(e) => handleContextMenu(e, tab.chatId)}
                title={tab.title || "对话"}
                className={`chrome-tab ${isActive ? "chrome-tab--active" : "chrome-tab--inactive"}`}
              >
                {/* Agent 图标或通用图标 */}
                {tab.agentId ? (
                  <AgentIcon id={tab.agentId} size={13} style={{ flexShrink: 0 }} />
                ) : (
                  <MessageSquare size={13} style={{ flexShrink: 0, color: "var(--text-level-4)" }} />
                )}

                {/* 标题截断展示 */}
                <span
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    flex: 1,
                    fontSize: "12px",
                    lineHeight: "1.2",
                    letterSpacing: "-0.01em",
                  }}
                >
                  {tab.title || "新对话"}
                </span>

                {/* 后台流式生成状态指示器（呼吸蓝点） */}
                {isStreaming && (
                  <span
                    title="正在生成中..."
                    style={{
                      width: "6px",
                      height: "6px",
                      borderRadius: "50%",
                      background: "var(--color-primary, #3b82f6)",
                      flexShrink: 0,
                      animation: "mfk-tab-pulse 1.4s infinite ease-in-out",
                    }}
                  />
                )}

                {/* 标签关闭按钮 */}
                <button
                  onClick={(e) => handleCloseTab(e, tab.chatId)}
                  title="关闭标签页 (Ctrl+W)"
                  className="chrome-tab-close"
                >
                  <X style={{ width: "11px", height: "11px" }} />
                </button>

                {/* 非活跃标签间的微弱分割线 */}
                {!isActive && !nextIsActive && <div className="chrome-tab-divider" />}
              </div>
            );
          })}
        </div>

        {/* 新建标签页按钮 */}
        {onNewChat && (
          <button
            onClick={onNewChat}
            title="新建对话标签 (Ctrl+N / Ctrl+T)"
            className="chrome-tab-new"
          >
            <Plus style={{ width: "15px", height: "15px" }} />
          </button>
        )}
      </div>

      {/* 右键上下文菜单 */}
      {contextMenu.visible && contextMenu.chatId !== null && (
        <div
          style={{
            position: "fixed",
            left: Math.min(contextMenu.x, window.innerWidth - 170),
            top: Math.min(contextMenu.y, window.innerHeight - 150),
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-primary)",
            borderRadius: "var(--radius-md)",
            padding: "4px",
            boxShadow: "0 6px 20px rgba(0, 0, 0, 0.18)",
            zIndex: 9999,
            minWidth: "150px",
            display: "flex",
            flexDirection: "column",
            gap: "2px",
            backdropFilter: "blur(8px)",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* 关闭当前 */}
          <button
            onClick={() => {
              const cid = contextMenu.chatId!;
              setContextMenu((p) => ({ ...p, visible: false }));
              const nextId = closeTab(cid);
              if (activeChatId === cid) {
                if (nextId != null) router.push(`/chat/${nextId}`);
                else router.push("/");
              }
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 8px",
              borderRadius: "var(--radius-sm)",
              fontSize: "12px",
              color: "var(--text-level-1)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              textAlign: "left",
              width: "100%",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-level-3)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <X size={13} style={{ color: "var(--text-level-3)" }} />
            <span>关闭标签页</span>
          </button>

          {/* 关闭其他 */}
          <button
            onClick={() => {
              const cid = contextMenu.chatId!;
              setContextMenu((p) => ({ ...p, visible: false }));
              closeOtherTabs(cid);
              router.push(`/chat/${cid}`);
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 8px",
              borderRadius: "var(--radius-sm)",
              fontSize: "12px",
              color: "var(--text-level-1)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              textAlign: "left",
              width: "100%",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-level-3)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <Ban size={13} style={{ color: "var(--text-level-3)" }} />
            <span>关闭其他标签页</span>
          </button>

          {/* 关闭右侧 */}
          <button
            onClick={() => {
              const cid = contextMenu.chatId!;
              setContextMenu((p) => ({ ...p, visible: false }));
              const nextId = closeRightTabs(cid);
              if (nextId != null) router.push(`/chat/${nextId}`);
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 8px",
              borderRadius: "var(--radius-sm)",
              fontSize: "12px",
              color: "var(--text-level-1)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              textAlign: "left",
              width: "100%",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-level-3)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <ArrowRightToLine size={13} style={{ color: "var(--text-level-3)" }} />
            <span>关闭右侧标签页</span>
          </button>

          <div style={{ height: "1px", background: "var(--border-primary)", margin: "2px 0" }} />

          {/* 复制链接 */}
          <button
            onClick={() => handleCopyLink(contextMenu.chatId!)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 8px",
              borderRadius: "var(--radius-sm)",
              fontSize: "12px",
              color: "var(--text-level-1)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              textAlign: "left",
              width: "100%",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-level-3)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <Copy size={13} style={{ color: "var(--text-level-3)" }} />
            <span>复制对话链接</span>
          </button>
        </div>
      )}
    </>
  );
}
