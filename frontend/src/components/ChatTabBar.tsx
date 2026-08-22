"use client";

import React, { useRef, useEffect, useState, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Plus, X, MessageSquare, Copy, ArrowRightToLine, Ban } from "lucide-react";
import { useTabStore, ChatTabItem } from "@/lib/tabStore";
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

  // 客户端挂载前不渲染，保持与 SSR 的初始状态一致，彻底消除水合不匹配
  if (!mounted) {
    return null;
  }

  // 如果没有打开任何标签且当前不在 chat 页面，不强行占位
  if (tabs.length === 0 && !pathname.startsWith("/chat/")) {
    return null;
  }

  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          height: "36px",
          background: "var(--bg-level-1)",
          borderBottom: "1px solid var(--border-primary)",
          padding: "0 8px 0 4px",
          gap: "4px",
          userSelect: "none",
          flexShrink: 0,
          position: "relative",
          zIndex: 10,
        }}
      >
        {/* 可滚动标签栏容器 */}
        <div
          ref={scrollRef}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "3px",
            overflowX: "auto",
            scrollbarWidth: "none",
            msOverflowStyle: "none",
            flex: 1,
            height: "100%",
            padding: "3px 0",
          }}
        >
          {tabs.map((tab) => {
            const isActive = tab.chatId === activeChatId && pathname.includes(String(tab.chatId));
            const isStreaming = Boolean(streams[tab.chatId]);

            return (
              <div
                key={tab.chatId}
                onClick={() => handleSelectTab(tab.chatId)}
                onContextMenu={(e) => handleContextMenu(e, tab.chatId)}
                title={tab.title || "对话"}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "0 8px 0 10px",
                  height: "28px",
                  borderRadius: "var(--radius-sm)",
                  background: isActive ? "var(--bg-level-3)" : "transparent",
                  color: isActive ? "var(--text-level-1)" : "var(--text-level-3)",
                  fontSize: "12px",
                  fontWeight: isActive ? 500 : 400,
                  cursor: "pointer",
                  maxWidth: "180px",
                  minWidth: "85px",
                  position: "relative",
                  boxShadow: isActive ? "0 1px 2px rgba(0, 0, 0, 0.05)" : "none",
                  transition: "background 0.15s ease, color 0.15s ease",
                  border: isActive ? "1px solid var(--border-subtle, transparent)" : "1px solid transparent",
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = "var(--bg-level-2)";
                    e.currentTarget.style.color = "var(--text-level-2)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "var(--text-level-3)";
                  }
                }}
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
                      animation: "mfk-tab-pulse 1.5s infinite ease-in-out",
                    }}
                  />
                )}

                {/* 标签关闭按钮 */}
                <button
                  onClick={(e) => handleCloseTab(e, tab.chatId)}
                  title="关闭标签页 (Ctrl+W)"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: "16px",
                    height: "16px",
                    borderRadius: "var(--radius-sm)",
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    color: "inherit",
                    opacity: isActive ? 0.8 : 0.4,
                    padding: 0,
                    flexShrink: 0,
                    transition: "opacity 0.15s ease, background 0.15s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.opacity = "1";
                    e.currentTarget.style.background = "var(--bg-level-4)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.opacity = isActive ? "0.8" : "0.4";
                    e.currentTarget.style.background = "transparent";
                  }}
                >
                  <X style={{ width: "11px", height: "11px" }} />
                </button>
              </div>
            );
          })}
        </div>

        {/* 新建标签页按钮 */}
        {onNewChat && (
          <button
            onClick={onNewChat}
            title="新建标签页 (Ctrl+T / Ctrl+N)"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "24px",
              height: "24px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              color: "var(--text-level-3)",
              transition: "all 0.15s ease",
              flexShrink: 0,
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
            boxShadow: "0 6px 16px rgba(0, 0, 0, 0.15)",
            zIndex: 9999,
            minWidth: "150px",
            display: "flex",
            flexDirection: "column",
            gap: "2px",
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
            className="sb-btn--ghost"
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
            className="sb-btn--ghost"
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
            className="sb-btn--ghost"
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
          >
            <ArrowRightToLine size={13} style={{ color: "var(--text-level-3)" }} />
            <span>关闭右侧标签页</span>
          </button>

          <div style={{ height: "1px", background: "var(--border-primary)", margin: "2px 0" }} />

          {/* 复制链接 */}
          <button
            onClick={() => handleCopyLink(contextMenu.chatId!)}
            className="sb-btn--ghost"
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
          >
            <Copy size={13} style={{ color: "var(--text-level-3)" }} />
            <span>复制对话链接</span>
          </button>
        </div>
      )}
    </>
  );
}
