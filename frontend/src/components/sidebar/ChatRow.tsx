"use client";

import { useRef } from "react";
import { useRouter } from "next/navigation";
import { Pin, MessageSquare, MoreHorizontal } from "lucide-react";
import type { Chat } from "@/hooks/useChat";
import type { OrbStage } from "@/lib/streamStore";
import { ThinkingOrb } from "thinking-orbs";
import { useTranslation } from "@/hooks/useTranslation";
import { formatRelativeTime, formatFullTime, useNowTick } from "@/lib/timeFormat";

interface ChatRowProps {
  chat: Chat;
  indented: boolean;
  isActive: boolean;
  streamingStage?: OrbStage | null;
  isRenaming: boolean;
  renameValue: string;
  onRenameValueChange: (value: string) => void;
  onRenameCommit: () => void;
  onRenameCancel: () => void;
  onContextMenu: (e: React.MouseEvent, chatId: number) => void;
  onMore: (e: React.MouseEvent, chatId: number) => void;
}

/**
 * 会话行（通用对话 / 项目内共用）
 *
 * V77 设计规则（与 ProjectNode 对齐）：
 * - 行内图标统一 var(--sidebar-icon-size) = 14px
 * - 小标识（Pin）统一 var(--sidebar-icon-size-sm) = 12px
 * - 行内次级按钮统一 22×22 / 圆角 radius-sm
 * - 活动态：背景 --sidebar-active-bg + 文字 --sidebar-active-fg + 2px 左侧指示条
 * - hover 才显形的按钮：默认 opacity 0（color 保持，避免脱色相）
 */
export function ChatRow({
  chat,
  indented,
  isActive,
  streamingStage,
  isRenaming,
  renameValue,
  onRenameValueChange,
  onRenameCommit,
  onRenameCancel,
  onContextMenu,
  onMore,
}: ChatRowProps) {
  const router = useRouter();
  const renameInputRef = useRef<HTMLInputElement>(null);
  const isPinned = chat.is_pinned;
  // 2026-08-12：标题右侧最后交互时间（共享 60s tick 防过期）
  const { t } = useTranslation();
  const now = useNowTick();

  return (
    <div
      key={chat.id}
      style={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        // 缩进：项目内 22px 对齐项目图标起点；通用对话 0
        padding: indented
          ? "3px var(--sidebar-row-px) 3px 22px"
          : "3px var(--sidebar-row-px)",
        borderRadius: "var(--radius-sm)",
        background: isActive ? "var(--sidebar-active-bg)" : "transparent",
        cursor: "pointer",
        marginBottom: "1px",
        transition: "background var(--transition-fast)",
      }}
      onClick={() => !isRenaming && router.push(`/chat/${chat.id}`)}
      onContextMenu={(e) => onContextMenu(e, chat.id)}
      onMouseEnter={(e) => {
        if (!isActive) e.currentTarget.style.background = "var(--bg-level-3)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = isActive
          ? "var(--sidebar-active-bg)"
          : "transparent";
      }}
      onMouseDown={(e) => {
        e.currentTarget.style.transform = "scale(0.98)";
      }}
      onMouseUp={(e) => {
        e.currentTarget.style.transform = "scale(1)";
      }}
    >
      {/* 活动会话：2px 左侧指示条（与 ProjectNode 对齐） */}
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
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          flex: 1,
          overflow: "hidden",
        }}
      >
        {isPinned && (
          <Pin
            style={{
              width: "var(--sidebar-icon-size-sm)",
              height: "var(--sidebar-icon-size-sm)",
              flexShrink: 0,
              color: "var(--sidebar-active-fg)",
            }}
          />
        )}
        {streamingStage && (
          <ThinkingOrb state={streamingStage} size={20} theme="auto" />
        )}
        {isRenaming ? (
          <input
            ref={renameInputRef}
            value={renameValue}
            onChange={(e) => onRenameValueChange(e.target.value)}
            onBlur={onRenameCommit}
            onKeyDown={(e) => {
              if (e.key === "Enter") onRenameCommit();
              if (e.key === "Escape") onRenameCancel();
            }}
            onClick={(e) => e.stopPropagation()}
            autoFocus
            style={{
              flex: 1,
              fontSize: "13px",
              lineHeight: "var(--line-height-normal)",
              color: "var(--text-level-2)",
              background: "var(--bg-level-2)",
              border: "1px solid var(--sidebar-active-fg)",
              borderRadius: "var(--radius-xs)",
              padding: "2px 6px",
              outline: "none",
            }}
          />
        ) : (
          <span
            style={{
              flex: 1,
              minWidth: 0,
              fontSize: "13px",
              fontWeight: 400,
              lineHeight: "var(--line-height-normal)",
              // 活动态用 primary 色（与 ProjectNode 对齐，不靠字重区分）
              color: isActive
                ? "var(--sidebar-active-fg)"
                : "var(--text-level-2)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {chat.title}
          </span>
        )}
        {/* 2026-08-12：最后交互时间（标题同行右侧，重命名时隐藏） */}
        {!isRenaming && chat.updated_at && (
          <span
            title={formatFullTime(chat.updated_at)}
            style={{
              fontSize: "10px",
              lineHeight: 1,
              color: "var(--text-level-4)",
              fontVariantNumeric: "tabular-nums",
              whiteSpace: "nowrap",
              flexShrink: 0,
              marginLeft: "6px",
            }}
          >
            {formatRelativeTime(chat.updated_at, t, now)}
          </span>
        )}
      </div>
      {/* ... 按钮：22×22 / 圆角 radius-sm / 默认 opacity 0 */}
      <button
        onClick={(e) => onMore(e, chat.id)}
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
          opacity: 0,
          transition: "opacity var(--transition-fast), background var(--transition-fast), color var(--transition-fast)",
          outline: "none",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.opacity = "1";
          e.currentTarget.style.background = "var(--bg-level-3)";
          e.currentTarget.style.color = "var(--text-level-1)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.opacity = "0";
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
  );
}
