"use client";

import { useRef, useEffect } from "react";
import { Edit2, Pin, PinOff, Trash2, FolderOpen, Archive, ExternalLink } from "lucide-react";
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
  onOpenInNewTab?: (chatId: number) => void;
  onRenameChat: (chatId: number) => void;
  onPinChat: (chatId: number) => void;
  onArchiveChat: (chatId: number) => void;
  onDeleteChat: (chatId: number) => void;
  onPinProject: (projectId: number) => void;
  onArchiveProject: (projectId: number) => void;
  onDeleteProject: (projectId: number) => void;
  onOpenProjectFolder: (projectId: number) => void;
  onClose: () => void;
}

/** 右键 / 更多菜单：会话（重命名/置顶/归档/删除）或项目（打开/置顶/归档/删除） */
export function SidebarContextMenu({
  state,
  chats,
  projects,
  onOpenInNewTab,
  onRenameChat,
  onPinChat,
  onArchiveChat,
  onDeleteChat,
  onPinProject,
  onArchiveProject,
  onDeleteProject,
  onOpenProjectFolder,
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
    gap: "6px",
    width: "100%",
    padding: "3px 8px",
    border: "none",
    cursor: "pointer",
    fontSize: "12px",
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
        padding: "3px",
        zIndex: 1000,
        minWidth: "130px",
        opacity: 0,
        animation: "contextMenuOpen 0.15s ease forwards",
      }}
    >
      {isChat ? (
        <>
          {onOpenInNewTab && (
            <button
              onClick={() => {
                if (state.chatId != null) onOpenInNewTab(state.chatId);
              }}
              className="ctx-menu-item"
              style={menuItemStyle}
            >
              <ExternalLink style={{ width: "13px", height: "13px" }} />
              <span>在顶部新标签页打开</span>
            </button>
          )}
          <button
            onClick={() => {
              if (state.chatId != null) onRenameChat(state.chatId);
            }}
            className="ctx-menu-item"
            style={menuItemStyle}
          >
            <Edit2 style={{ width: "13px", height: "13px" }} />
            <span>{t("sidebar.rename")}</span>
          </button>
          <button
            onClick={() => {
              if (state.chatId != null) onPinChat(state.chatId);
            }}
            className="ctx-menu-item"
            style={menuItemStyle}
          >
            {state.chatId != null && chats.find((c) => c.id === state.chatId)?.is_pinned ? (
              <>
                <PinOff style={{ width: "13px", height: "13px" }} />
                <span>{t("sidebar.unpin")}</span>
              </>
            ) : (
              <>
                <Pin style={{ width: "13px", height: "13px" }} />
                <span>{t("sidebar.pin")}</span>
              </>
            )}
          </button>
          <button
            onClick={() => {
              if (state.chatId != null) onArchiveChat(state.chatId);
            }}
            className="ctx-menu-item"
            style={menuItemStyle}
          >
            <Archive style={{ width: "13px", height: "13px" }} />
            <span>{t("sidebar.archive")}</span>
          </button>
          <div style={{
            height: "1px",
            background: "var(--border-secondary)",
            margin: "3px 0",
          }} />
          <button
            onClick={() => {
              if (state.chatId != null) onDeleteChat(state.chatId);
            }}
            className="ctx-menu-item"
            style={{ ...menuItemStyle, color: "var(--color-error)" }}
          >
            <Trash2 style={{ width: "13px", height: "13px" }} />
            <span>{t("sidebar.delete")}</span>
          </button>
        </>
      ) : (
        <>
          <button
            onClick={() => {
              if (state.projectId != null) onOpenProjectFolder(state.projectId);
            }}
            className="ctx-menu-item"
            style={menuItemStyle}
          >
            <FolderOpen style={{ width: "13px", height: "13px" }} />
            <span>{t("sidebar.openProjectFolder")}</span>
          </button>
          <div style={{
            height: "1px",
            background: "var(--border-secondary)",
            margin: "3px 0",
          }} />
          <button
            onClick={() => {
              if (state.projectId != null) onPinProject(state.projectId);
            }}
            className="ctx-menu-item"
            style={menuItemStyle}
          >
            {state.projectId != null && projects.find((p) => p.id === state.projectId)?.is_pinned ? (
              <>
                <PinOff style={{ width: "13px", height: "13px" }} />
                <span>{t("sidebar.unpin")}</span>
              </>
            ) : (
              <>
                <Pin style={{ width: "13px", height: "13px" }} />
                <span>{t("sidebar.pin")}</span>
              </>
            )}
          </button>
          <button
            onClick={() => {
              if (state.projectId != null) onArchiveProject(state.projectId);
            }}
            className="ctx-menu-item"
            style={menuItemStyle}
          >
            <Archive style={{ width: "13px", height: "13px" }} />
            <span>{t("sidebar.archive")}</span>
          </button>
          <div style={{
            height: "1px",
            background: "var(--border-secondary)",
            margin: "3px 0",
          }} />
          <button
            onClick={() => {
              if (state.projectId != null) onDeleteProject(state.projectId);
            }}
            className="ctx-menu-item"
            style={{ ...menuItemStyle, color: "var(--color-error)" }}
          >
            <Trash2 style={{ width: "13px", height: "13px" }} />
            <span>{t("sidebar.delete")}</span>
          </button>
        </>
      )}
    </div>
  );
}
