"use client";

import { ChevronRight, Folder, FolderOpen, Pin, Plus, MoreHorizontal } from "lucide-react";
import type { Chat } from "@/hooks/useChat";
import type { Project } from "@/hooks/useProjects";
import type { OrbStage } from "@/lib/streamStore";
import { useTranslation } from "@/hooks/useTranslation";
import { ChatRow } from "./ChatRow";

interface ProjectNodeProps {
  project: Project;
  chats: Chat[];
  isCollapsed: boolean;
  isActiveProject: boolean;
  isHovered: boolean;
  onToggleCollapse: () => void;
  onHoverChange: (hovered: boolean) => void;
  onContextMenu: (e: React.MouseEvent, projectId: number) => void;
  onMoreProject: (e: React.MouseEvent, projectId: number) => void;
  onQuickCreateChat: (projectId: number) => void;
  currentChatId?: number | null;
  streams?: Record<number, OrbStage>;
  renamingChatId: number | null;
  renameValue: string;
  onRenameValueChange: (value: string) => void;
  onRenameCommit: () => void;
  onRenameCancel: () => void;
  onChatContextMenu: (e: React.MouseEvent, chatId: number) => void;
  onChatMore: (e: React.MouseEvent, chatId: number) => void;
}

/** 项目文件夹节点 + 其下会话列表 */
export function ProjectNode({
  project,
  chats,
  isCollapsed,
  isActiveProject,
  isHovered,
  onToggleCollapse,
  onHoverChange,
  onContextMenu,
  onMoreProject,
  onQuickCreateChat,
  currentChatId,
  streams,
  renamingChatId,
  renameValue,
  onRenameValueChange,
  onRenameCommit,
  onRenameCancel,
  onChatContextMenu,
  onChatMore,
}: ProjectNodeProps) {
  const { t } = useTranslation();

  return (
    <div style={{ marginBottom: "1px" }}>
      {/* 项目文件夹节点 */}
      <div
        onClick={onToggleCollapse}
        onContextMenu={(e) => onContextMenu(e, project.id)}
        onMouseEnter={() => onHoverChange(true)}
        onMouseLeave={() => onHoverChange(false)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: "5px 8px",
          borderRadius: "var(--radius-sm)",
          cursor: "pointer",
          background: isActiveProject ? "var(--color-primary-lighter)" : "transparent",
          transition: "background var(--transition-fast)",
        }}
      >
        <span style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "14px",
          height: "14px",
          transition: "transform var(--transition-fast)",
          transform: isCollapsed ? "none" : "rotate(90deg)",
        }}>
          <ChevronRight style={{ width: "12px", height: "12px", color: "var(--text-level-4)" }} />
        </span>
        {isCollapsed ? (
          <Folder style={{ width: "13px", height: "13px", color: "var(--text-level-3)", flexShrink: 0 }} />
        ) : (
          <FolderOpen style={{ width: "13px", height: "13px", color: isActiveProject ? "var(--color-primary)" : "var(--text-level-3)", flexShrink: 0 }} />
        )}
        <span style={{
          flex: 1,
          minWidth: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          fontSize: "13px",
          fontWeight: "500",
          color: isActiveProject ? "var(--color-primary)" : "var(--text-level-2)",
        }}>{project.name}</span>
        {project.is_pinned && (
          <Pin style={{ width: "11px", height: "11px", flexShrink: 0, color: "var(--color-primary)" }} />
        )}
        <span style={{
          fontSize: "11px",
          color: "var(--text-level-4)",
          flexShrink: 0,
          fontVariantNumeric: "tabular-nums",
        }}>{chats.length}</span>
        {/* 悬停显示 +：快速新建会话 */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onQuickCreateChat(project.id);
          }}
          title={t("sidebar.newChatInProject")}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "18px",
            height: "18px",
            borderRadius: "var(--radius-xs)",
            border: "none",
            background: isHovered ? "var(--bg-level-3)" : "transparent",
            cursor: "pointer",
            color: isHovered ? "var(--color-primary)" : "transparent",
            opacity: isHovered ? 1 : 0,
            flexShrink: 0,
            transition: "opacity var(--transition-fast), color var(--transition-fast)",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; e.currentTarget.style.color = "var(--color-primary)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "transparent"; }}
        >
          <Plus style={{ width: "12px", height: "12px" }} />
        </button>
        {/* 悬停显示 ...：更多操作（删除项目） */}
        <button
          onClick={(e) => onMoreProject(e, project.id)}
          title={t("sidebar.more")}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "18px",
            height: "18px",
            borderRadius: "var(--radius-xs)",
            border: "none",
            background: isHovered ? "var(--bg-level-3)" : "transparent",
            cursor: "pointer",
            color: isHovered ? "var(--text-level-3)" : "transparent",
            opacity: isHovered ? 1 : 0,
            flexShrink: 0,
            transition: "opacity var(--transition-fast), color var(--transition-fast)",
            outline: "none",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; e.currentTarget.style.color = "var(--text-level-1)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "transparent"; }}
        >
          <MoreHorizontal style={{ width: "13px", height: "13px" }} />
        </button>
      </div>

      {/* 项目内会话 */}
      {!isCollapsed && chats.length > 0 && (
        <div style={{ paddingTop: "1px" }}>
          {chats.map((chat) => (
            <ChatRow
              key={chat.id}
              chat={chat}
              indented
              isActive={chat.id === currentChatId}
              streamingStage={streams?.[chat.id] ?? null}
              isRenaming={renamingChatId === chat.id}
              renameValue={renameValue}
              onRenameValueChange={onRenameValueChange}
              onRenameCommit={onRenameCommit}
              onRenameCancel={onRenameCancel}
              onContextMenu={onChatContextMenu}
              onMore={onChatMore}
            />
          ))}
        </div>
      )}
    </div>
  );
}
