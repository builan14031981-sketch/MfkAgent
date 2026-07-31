"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  Settings,
  MessageSquare,
  Trash2,
  Brain,
  Pin,
  PinOff,
  Edit2,
} from "lucide-react";
import { useChat, Chat } from "@/hooks/useChat";
import { useTranslation } from "@/hooks/useTranslation";

interface SidebarProps {
  currentChatId?: number | null;
  onSettingsClick?: () => void;
  onMemoryClick?: () => void;
}

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  chatId: number | null;
}

function getDateGroup(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const chatDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());

  if (chatDate.getTime() === today.getTime()) {
    return "今天";
  } else if (chatDate.getTime() === yesterday.getTime()) {
    return "昨天";
  } else {
    return date.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
  }
}

function groupChatsByDate(chats: Chat[]): Map<string, Chat[]> {
  const groups = new Map<string, Chat[]>();

  for (const chat of chats) {
    const group = getDateGroup(chat.updated_at || chat.created_at);
    if (!groups.has(group)) {
      groups.set(group, []);
    }
    groups.get(group)!.push(chat);
  }

  return groups;
}

export function Sidebar({ currentChatId, onSettingsClick, onMemoryClick }: SidebarProps) {
  const router = useRouter();
  const { t } = useTranslation();
  const { chats, deleteChat, updateChat, pinChat } = useChat();

  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false,
    x: 0,
    y: 0,
    chatId: null,
  });
  const [renamingChatId, setRenamingChatId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const contextMenuRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  const groupedChats = useMemo(() => groupChatsByDate(chats), [chats]);

  // 点击外部关闭右键菜单
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node)) {
        setContextMenu(prev => ({ ...prev, visible: false }));
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // 重命名输入框自动聚焦
  useEffect(() => {
    if (renamingChatId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingChatId]);

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

  const handleDeleteChat = async (id: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await deleteChat(id);
      if (currentChatId === id) {
        router.push("/");
      }
    } catch (err) {
      console.error("Failed to delete chat:", err);
    }
    setContextMenu(prev => ({ ...prev, visible: false }));
  };

  const handleRename = async () => {
    if (!renamingChatId || !renameValue.trim()) {
      setRenamingChatId(null);
      return;
    }
    try {
      await updateChat(renamingChatId, { title: renameValue.trim() });
    } catch (err) {
      console.error("Failed to rename chat:", err);
    }
    setRenamingChatId(null);
  };

  const handlePin = async (chatId: number, pinned: boolean) => {
    try {
      await pinChat(chatId, pinned);
    } catch (err) {
      console.error("Failed to pin chat:", err);
    }
    setContextMenu(prev => ({ ...prev, visible: false }));
  };

  const startRename = (chatId: number, currentTitle: string) => {
    setRenamingChatId(chatId);
    setRenameValue(currentTitle);
    setContextMenu(prev => ({ ...prev, visible: false }));
  };

  // 排序：置顶的聊天在前（使用后端返回的 is_pinned 字段）
  const sortedGroupedChats = useMemo(() => {
    const sorted = new Map<string, Chat[]>();
    for (const [group, chats] of groupedChats) {
      sorted.set(group, [...chats].sort((a, b) => {
        const aPinned = a.is_pinned ? -1 : 0;
        const bPinned = b.is_pinned ? -1 : 0;
        return aPinned - bPinned;
      }));
    }
    return sorted;
  }, [groupedChats]);

  return (
    <aside style={{
      width: "260px",
      height: "100%",
      display: "flex",
      flexDirection: "column",
      borderRight: "1px solid var(--border-primary)",
      background: "var(--bg-level-1)",
      flexShrink: 0,
      position: "relative",
    }}>
      {/* 新建任务 */}
      <div style={{ padding: "16px" }}>
        <button
          onClick={() => router.push("/")}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "10px 16px",
            borderRadius: "var(--radius-md)",
            border: "none",
            background: "var(--bg-level-3)",
            cursor: "pointer",
            fontSize: "14px",
            color: "var(--text-level-1)",
            transition: "all 0.6s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--bg-level-4)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "var(--bg-level-3)";
          }}
          onMouseDown={(e) => {
            e.currentTarget.style.transform = "scale(0.98)";
          }}
          onMouseUp={(e) => {
            e.currentTarget.style.transform = "scale(1)";
          }}
        >
          <Plus style={{ width: "16px", height: "16px" }} />
          <span>{t("sidebar.newTask")}</span>
        </button>
      </div>

      {/* 聊天列表 */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: "0 16px 16px 16px",
      }}>
        {chats.length === 0 ? (
          <div style={{
            padding: "12px",
            textAlign: "center",
          }}>
            <p style={{
              fontSize: "13px",
              color: "var(--text-level-3)",
              margin: 0,
            }}>{t("sidebar.noChats")}</p>
            <p style={{
              fontSize: "12px",
              color: "var(--text-level-4)",
              margin: "2px 0 0 0",
            }}>{t("sidebar.noChatsDesc")}</p>
          </div>
        ) : (
          Array.from(sortedGroupedChats.entries()).map(([dateGroup, groupChats]) => (
            <div key={dateGroup} style={{ marginBottom: "8px" }}>
              <p style={{
                padding: "8px 12px 4px",
                marginBottom: "2px",
                fontSize: "12px",
                fontWeight: "600",
                color: "var(--text-level-4)",
              }}>{dateGroup}</p>
              {groupChats.map((chat) => {
                const isPinned = chat.is_pinned;
                const isRenaming = renamingChatId === chat.id;

                return (
                  <div
                    key={chat.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 12px",
                      borderRadius: "var(--radius-sm)",
                      background: chat.id === currentChatId ? "var(--bg-level-3)" : "transparent",
                      cursor: "pointer",
                      marginBottom: "2px",
                      transition: "all 0.6s ease",
                    }}
                    onClick={() => !isRenaming && router.push(`/chat/${chat.id}`)}
                    onContextMenu={(e) => handleContextMenu(e, chat.id)}
                    onMouseEnter={(e) => {
                      if (chat.id !== currentChatId) {
                        e.currentTarget.style.background = "var(--bg-level-3)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (chat.id !== currentChatId) {
                        e.currentTarget.style.background = "transparent";
                      }
                    }}
                    onMouseDown={(e) => {
                      e.currentTarget.style.transform = "scale(0.98)";
                      e.currentTarget.style.background = "var(--bg-level-4)";
                    }}
                    onMouseUp={(e) => {
                      e.currentTarget.style.transform = "scale(1)";
                      e.currentTarget.style.background = chat.id === currentChatId ? "var(--bg-level-3)" : "transparent";
                    }}
                  >
                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      flex: 1,
                      overflow: "hidden",
                    }}>
                      {isPinned && (
                        <Pin style={{ width: "12px", height: "12px", flexShrink: 0, color: "var(--color-primary)" }} />
                      )}
                      <MessageSquare style={{ width: "14px", height: "14px", flexShrink: 0, color: "var(--text-level-3)" }} />
                      {isRenaming ? (
                        <input
                          ref={renameInputRef}
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onBlur={handleRename}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleRename();
                            if (e.key === "Escape") setRenamingChatId(null);
                          }}
                          onClick={(e) => e.stopPropagation()}
                          style={{
                            flex: 1,
                            fontSize: "14px",
                            color: "var(--text-level-2)",
                            background: "var(--bg-level-2)",
                            border: "1px solid var(--color-primary)",
                            borderRadius: "var(--radius-xs)",
                            padding: "2px 6px",
                            outline: "none",
                          }}
                        />
                      ) : (
                        <span style={{
                          fontSize: "14px",
                          color: "var(--text-level-2)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}>{chat.title}</span>
                      )}
                    </div>
                    <button
                      onClick={(e) => handleDeleteChat(chat.id, e)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: "24px",
                        height: "24px",
                        borderRadius: "var(--radius-xs)",
                        border: "none",
                        background: "transparent",
                        cursor: "pointer",
                        color: "var(--text-level-4)",
                        flexShrink: 0,
                        opacity: 0,
                      transition: "all 0.6s ease",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.opacity = "1";
                        e.currentTarget.style.background = "var(--bg-level-4)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.opacity = "0";
                        e.currentTarget.style.background = "transparent";
                      }}
                    >
                      <Trash2 style={{ width: "12px", height: "12px" }} />
                    </button>
                  </div>
                );
              })}
            </div>
          ))
        )}
      </div>

      {/* 右键菜单 */}
      {contextMenu.visible && contextMenu.chatId && (
        <div
          ref={contextMenuRef}
          style={{
            position: "fixed",
            left: contextMenu.x,
            top: contextMenu.y,
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-primary)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-lg)",
            padding: "4px",
            zIndex: 1000,
            minWidth: "160px",
            opacity: 0,
            transform: "scale(0.95)",
            animation: "contextMenuOpen 0.15s ease forwards",
          }}
        >
          <button
            onClick={() => {
              const chat = chats.find(c => c.id === contextMenu.chatId);
              if (chat) startRename(chat.id, chat.title);
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              width: "100%",
              padding: "8px 12px",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "13px",
              color: "var(--text-level-2)",
              borderRadius: "var(--radius-sm)",
              transition: "all 0.6s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
            onMouseDown={(e) => {
              e.currentTarget.style.transform = "scale(0.98)";
              e.currentTarget.style.background = "var(--bg-level-4)";
            }}
            onMouseUp={(e) => {
              e.currentTarget.style.transform = "scale(1)";
              e.currentTarget.style.background = "var(--bg-level-3)";
            }}
          >
            <Edit2 style={{ width: "14px", height: "14px" }} />
            <span>{t("sidebar.rename")}</span>
          </button>
          <button
            onClick={() => {
              const chat = chats.find(c => c.id === contextMenu.chatId);
              if (chat) handlePin(chat.id, !chat.is_pinned);
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              width: "100%",
              padding: "8px 12px",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "13px",
              color: "var(--text-level-2)",
              borderRadius: "var(--radius-sm)",
              transition: "all 0.6s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
            onMouseDown={(e) => {
              e.currentTarget.style.transform = "scale(0.98)";
              e.currentTarget.style.background = "var(--bg-level-4)";
            }}
            onMouseUp={(e) => {
              e.currentTarget.style.transform = "scale(1)";
              e.currentTarget.style.background = "var(--bg-level-3)";
            }}
          >
            {contextMenu.chatId && chats.find(c => c.id === contextMenu.chatId)?.is_pinned ? (
              <>
                <PinOff style={{ width: "14px", height: "14px" }} />
                <span>{t("sidebar.unpin")}</span>
              </>
            ) : (
              <>
                <Pin style={{ width: "14px", height: "14px" }} />
                <span>{t("sidebar.pin")}</span>
              </>
            )}
          </button>
          <div style={{
            height: "1px",
            background: "var(--border-secondary)",
            margin: "4px 0",
          }} />
          <button
            onClick={() => contextMenu.chatId && handleDeleteChat(contextMenu.chatId)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              width: "100%",
              padding: "8px 12px",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "13px",
              color: "var(--color-error)",
              borderRadius: "var(--radius-sm)",
              transition: "all 0.6s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
            onMouseDown={(e) => {
              e.currentTarget.style.transform = "scale(0.98)";
              e.currentTarget.style.background = "var(--bg-level-4)";
            }}
            onMouseUp={(e) => {
              e.currentTarget.style.transform = "scale(1)";
              e.currentTarget.style.background = "var(--bg-level-3)";
            }}
          >
            <Trash2 style={{ width: "14px", height: "14px" }} />
            <span>{t("sidebar.delete")}</span>
          </button>
        </div>
      )}

      {/* 底部按钮 */}
      <div style={{
        padding: "16px",
        borderTop: "1px solid var(--border-primary)",
      }}>
        {onMemoryClick && (
          <button
            onClick={onMemoryClick}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 12px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "14px",
              color: "var(--text-level-3)",
              marginBottom: "4px",
              transition: "all 0.6s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
              e.currentTarget.style.color = "var(--text-level-2)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--text-level-3)";
            }}
          >
            <Brain style={{ width: "16px", height: "16px" }} />
            <span>{t("sidebar.memory")}</span>
          </button>
        )}
        {onSettingsClick && (
          <button
            onClick={onSettingsClick}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 12px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "14px",
              color: "var(--text-level-3)",
              transition: "all 0.6s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
              e.currentTarget.style.color = "var(--text-level-2)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--text-level-3)";
            }}
          >
            <Settings style={{ width: "16px", height: "16px" }} />
            <span>{t("sidebar.settings")}</span>
          </button>
        )}
      </div>
    </aside>
  );
}
