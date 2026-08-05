"use client";

import { useRef, useEffect } from "react";
import { Edit2, Pin, PinOff, Trash2 } from "lucide-react";
import type { Chat } from "@/hooks/useChat";
import type { Project } from "@/hooks/useProjects";
import { useTranslation } from "@/hooks/useTranslation";

export interface SidebarContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  chatId: number | null;
  projectId: number | null;
}

interface SidebarContextMenuProps {
  state: SidebarContextMenuState;
  chats: Chat[];
  projects: Project[];
  onRenameChat: (chatId: number) => void;
  onPinChat: (chatId: number) => void;
  onDeleteChat: (chatId: number) => void;
  onPinProject: (projectId: number) => void;
  onDeleteProject: (projectId: number) => void;
  onClose: () => void;
}

/** 右键 / 更多菜单：会话（重命名/置顶/删除）或项目（置顶/删除） */
export function SidebarContextMenu({
  state,
  chats,
  projects,
  onRenameChat,
  onPinChat,
  onDeleteChat,
  onPinProject,
  onDeleteProject,
  onClose,
}: SidebarContextMenuProps) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);

  // 点击外部关闭右键菜单
  useEffect(() => {
    if (!state.visible) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [state.visible, onClose]);

  if (!state.visible) return null;
  const isChat = state.chatId != null;

  const menuItemStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    width: "100%",
    padding: "6px 10px",
    border: "none",
    background: "transparent",
    cursor: "pointer",
    fontSize: "13px",
    color: "var(--text-level-2)",
    borderRadius: "var(--radius-sm)",
  };

  return (
    <div
      ref={ref}
      onMouseDown={(e) => e.stopPropagation()}
      style={{
        position: "fixed",
        left: state.x,
        top: state.y,
        background: "var(--bg-level-2)",
        border: "1px solid var(--border-primary)",
        borderRadius: "var(--radius-md)",
        boxShadow: "var(--shadow-lg)",
        padding: "4px",
        zIndex: 1000,
        minWidth: "160px",
        opacity: 0,
        animation: "contextMenuOpen 0.15s ease forwards",
      }}
    >
      {isChat ? (
        <>
          <button
            onClick={() => {
              if (state.chatId != null) onRenameChat(state.chatId);
            }}
            style={menuItemStyle}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            <Edit2 style={{ width: "14px", height: "14px" }} />
            <span>{t("sidebar.rename")}</span>
          </button>
          <button
            onClick={() => {
              if (state.chatId != null) onPinChat(state.chatId);
            }}
            style={menuItemStyle}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            {state.chatId != null && chats.find((c) => c.id === state.chatId)?.is_pinned ? (
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
            onClick={() => {
              if (state.chatId != null) onDeleteChat(state.chatId);
            }}
            style={{ ...menuItemStyle, color: "var(--color-error)" }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            <Trash2 style={{ width: "14px", height: "14px" }} />
            <span>{t("sidebar.delete")}</span>
          </button>
        </>
      ) : (
        <>
          <button
            onClick={() => {
              if (state.projectId != null) onPinProject(state.projectId);
            }}
            style={menuItemStyle}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            {state.projectId != null && projects.find((p) => p.id === state.projectId)?.is_pinned ? (
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
            onClick={() => {
              if (state.projectId != null) onDeleteProject(state.projectId);
            }}
            style={{ ...menuItemStyle, color: "var(--color-error)" }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            <Trash2 style={{ width: "14px", height: "14px" }} />
            <span>{t("sidebar.delete")}</span>
          </button>
        </>
      )}
    </div>
  );
}
