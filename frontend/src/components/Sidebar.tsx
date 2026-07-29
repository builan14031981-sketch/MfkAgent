"use client";

import { useRouter } from "next/navigation";
import {
  Plus,
  Settings,
  MessageSquare,
  Trash2,
  Brain,
} from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useChat } from "@/hooks/useChat";
import { useTranslation } from "@/hooks/useTranslation";

interface SidebarProps {
  currentChatId?: number | null;
  onSettingsClick?: () => void;
  onMemoryClick?: () => void;
}

export function Sidebar({ currentChatId, onSettingsClick, onMemoryClick }: SidebarProps) {
  const router = useRouter();
  const { t } = useTranslation();
  const { agents } = useAgents();
  const { chats, deleteChat } = useChat();

  const handleDeleteChat = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteChat(id);
      if (currentChatId === id) {
        router.push("/");
      }
    } catch (err) {
      console.error("Failed to delete chat:", err);
    }
  };

  return (
    <aside style={{
      width: "260px",
      height: "100%",
      display: "flex",
      flexDirection: "column",
      borderRight: "1px solid var(--border-primary)",
      background: "var(--bg-level-1)",
      flexShrink: 0,
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
        <p style={{
          padding: "0 12px",
          marginBottom: "4px",
          fontSize: "12px",
          fontWeight: "600",
          color: "var(--text-level-4)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          }}>{t("sidebar.chats")}</p>
        {chats.map((chat) => {
          const chatAgent = agents.find((a) => a.id === chat.agent_id);
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
              }}
              onClick={() => router.push(`/chat/${chat.id}`)}
            >
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                flex: 1,
                overflow: "hidden",
              }}>
                {chatAgent ? (
                  <span style={{ fontSize: "14px", flexShrink: 0 }}>{chatAgent.avatar}</span>
                ) : (
                  <MessageSquare style={{ width: "14px", height: "14px", flexShrink: 0 }} />
                )}
                <span style={{
                  fontSize: "14px",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}>{chat.title}</span>
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
                  transition: "opacity 0.2s",
                }}
                onMouseEnter={(e) => e.currentTarget.style.opacity = "1"}
                onMouseLeave={(e) => e.currentTarget.style.opacity = "0"}
              >
                <Trash2 style={{ width: "12px", height: "12px" }} />
              </button>
            </div>
          );
        })}
      </div>

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
