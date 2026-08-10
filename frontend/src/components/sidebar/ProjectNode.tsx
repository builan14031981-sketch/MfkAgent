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

/**
 * 项目文件夹节点 + 其下会话列表
 *
 * V77 设计规则（与 ChatRow 对齐）：
 * - 行内图标统一 var(--sidebar-icon-size) = 14px
 * - 小标识（Pin/角标）统一 var(--sidebar-icon-size-sm) = 12px
 * - 行内次级按钮统一 22×22，圆角 radius-sm (8px)
 * - 活动态：背景 --sidebar-active-bg + 文字 --sidebar-active-fg + 2px 左侧指示条
 * - hover 才显形的按钮：默认 opacity 0（不用 color: transparent，避免色相不一致）
 */
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
  const isActive = isActiveProject;

  return (
    <div style={{ marginBottom: "1px" }}>
      {/* 项目文件夹节点 */}
      <div
        onClick={onToggleCollapse}
        onContextMenu={(e) => onContextMenu(e, project.id)}
        onMouseEnter={() => onHoverChange(true)}
        onMouseLeave={() => onHoverChange(false)}
        style={{
          position: "relative",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "var(--sidebar-row-py) var(--sidebar-row-px)",
          borderRadius: "var(--radius-sm)",
          cursor: "pointer",
          background: isActive ? "var(--sidebar-active-bg)" : "transparent",
          transition: "background var(--transition-fast)",
        }}
      >
        {/* 活动项目：2px 左侧指示条（与 ChatRow 对齐） */}
        {isActive && (
          <span
            aria-hidden
            style={{
              position: "absolute",
              left: "4px",
              top: "20%",
              bottom: "20%",
              width: "var(--sidebar-indicator-w)",
              borderRadius: "var(--radius-full)",
              background: "var(--sidebar-active-fg)",
            }}
          />
        )}

        {/* 折叠/展开 Chevron：与小图标档同尺寸 */}
        <span
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "var(--sidebar-icon-size-sm)",
            height: "var(--sidebar-icon-size-sm)",
            flexShrink: 0,
            transition: "transform var(--transition-fast)",
            transform: isCollapsed ? "none" : "rotate(90deg)",
          }}
        >
          <ChevronRight
            style={{
              width: "var(--sidebar-icon-size-sm)",
              height: "var(--sidebar-icon-size-sm)",
              color: "var(--text-level-4)",
            }}
          />
        </span>

        {/* 文件夹图标：行内统一 14px */}
        {isCollapsed ? (
          <Folder
            style={{
              width: "var(--sidebar-icon-size)",
              height: "var(--sidebar-icon-size)",
              color: isActive ? "var(--sidebar-active-fg)" : "var(--text-level-3)",
              flexShrink: 0,
            }}
          />
        ) : (
          <FolderOpen
            style={{
              width: "var(--sidebar-icon-size)",
              height: "var(--sidebar-icon-size)",
              color: isActive ? "var(--sidebar-active-fg)" : "var(--text-level-3)",
              flexShrink: 0,
            }}
          />
        )}

        {/* 项目名：13px / 500 weight / 活动态 primary 色 */}
        <span
          style={{
            flex: 1,
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            fontSize: "13px",
            fontWeight: 500,
            lineHeight: "var(--line-height-normal)",
            color: isActive ? "var(--sidebar-active-fg)" : "var(--text-level-2)",
          }}
        >
          {project.name}
        </span>

        {/* Pin 标识：小图标档 12px */}
        {project.is_pinned && (
          <Pin
            style={{
              width: "var(--sidebar-icon-size-sm)",
              height: "var(--sidebar-icon-size-sm)",
              flexShrink: 0,
              color: "var(--sidebar-active-fg)",
            }}
          />
        )}

        {/* chat 数量角标：12px + tabular-nums（与提示同档） */}
        <span
          style={{
            fontSize: "12px",
            lineHeight: "var(--line-height-normal)",
            color: "var(--text-level-4)",
            flexShrink: 0,
            fontVariantNumeric: "tabular-nums",
            minWidth: "14px",
            textAlign: "right",
          }}
        >
          {chats.length}
        </span>

        {/* 悬停显示 +：快速新建会话（22×22 / 圆角 radius-sm） */}
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
            width: "var(--sidebar-btn-size)",
            height: "var(--sidebar-btn-size)",
            borderRadius: "var(--radius-sm)",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            color: "var(--text-level-3)",
            flexShrink: 0,
            opacity: isHovered ? 1 : 0,
            transition: "opacity var(--transition-fast), background var(--transition-fast), color var(--transition-fast)",
            outline: "none",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--bg-level-3)";
            e.currentTarget.style.color = "var(--sidebar-active-fg)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "var(--text-level-3)";
          }}
        >
          <Plus
            style={{
              width: "var(--sidebar-icon-size-sm)",
              height: "var(--sidebar-icon-size-sm)",
            }}
          />
        </button>

        {/* 悬停显示 ...：更多操作（22×22 / 圆角 radius-sm） */}
        <button
          onClick={(e) => onMoreProject(e, project.id)}
          title={t("sidebar.more")}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "var(--sidebar-btn-size)",
            height: "var(--sidebar-btn-size)",
            borderRadius: "var(--radius-sm)",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            color: "var(--text-level-3)",
            flexShrink: 0,
            opacity: isHovered ? 1 : 0,
            transition: "opacity var(--transition-fast), background var(--transition-fast), color var(--transition-fast)",
            outline: "none",
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
          <MoreHorizontal
            style={{
              width: "var(--sidebar-icon-size)",
              height: "var(--sidebar-icon-size)",
            }}
          />
        </button>
      </div>

      {/* 项目内会话：与 ChatRow 一致的缩进（22px 对齐项目图标起点） */}
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
