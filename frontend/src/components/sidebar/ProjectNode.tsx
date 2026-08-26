"use client";

import { Folder, FolderOpen, Pin, Plus, MoreHorizontal } from "lucide-react";
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
 * - 活动态：背景 --sidebar-active-bg-strong（文件夹级，默认等同会话级，主题可覆盖做层级）+ 文字 --sidebar-active-fg
 * - 左侧 2px 指示条：仅折叠态渲染（展开时由子级 ChatRow 的指示条承担标记，避免父子双杠；2026-08-11 修复）
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
    <div style={{ marginBottom: "2px" }}>
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
          gap: "6px",
          padding: "7px 12px 7px 12px",
          borderRadius: "8px",
          cursor: "pointer",
          background: isActive ? "var(--sidebar-active-bg)" : (isHovered ? "var(--bg-level-4)" : "transparent"),
          boxShadow: isActive ? "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)" : "none",
          transition: "background var(--transition-fast), box-shadow var(--transition-fast)",
        }}
      >
        {isCollapsed ? (
          <Folder
            style={{
              width: "16px",
              height: "16px",
              color: isActive ? "var(--sidebar-active-fg)" : "var(--text-level-3)",
              flexShrink: 0,
            }}
          />
        ) : (
          <FolderOpen
            style={{
              width: "16px",
              height: "16px",
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
            fontSize: "14px",
            fontWeight: isActive ? 600 : 500,
            lineHeight: 1.4,
            color: isActive ? "var(--sidebar-active-fg)" : "var(--text-level-1)",
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

        {/* 右侧操作区：chat数量 + 新建 + 更多，容器负 margin 抵消 padding-right 贴边 */}
        <div style={{ display: "flex", alignItems: "center", gap: "2px", marginRight: "-8px", flexShrink: 0 }}>
        {/* chat 数量角标：为 0 时不显示，tabular-nums 等宽缩放稳定 */}
        {chats.length > 0 && (
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
        )}

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
              width: "var(--sidebar-icon-size-sm)",
              height: "var(--sidebar-icon-size-sm)",
            }}
          />
        </button>
        </div>
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

