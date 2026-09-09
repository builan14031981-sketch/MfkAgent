"use client";

import { memo, useRef } from "react";
import { useRouter } from "next/navigation";
import { Pin, MessageSquare, MoreHorizontal } from "lucide-react";
import type { Chat } from "@/hooks/useChat";
import type { OrbStage } from "@/lib/streamStore";
import { ThinkingOrb } from "thinking-orbs";
import { useTranslation } from "@/hooks/useTranslation";
import { formatRelativeTime, formatFullTime, useNowTick } from "@/lib/timeFormat";
import { Tooltip } from "../Tooltip";

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
export const ChatRow = memo(function ChatRow({
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
        // ZCode 风格：紧凑规整，28px 标准行高
        padding: `4px 8px 4px ${indented ? "24px" : "8px"}`,
        height: "28px",
        borderRadius: "4px",
        background: isActive ? "var(--sidebar-active-bg)" : "transparent",
        cursor: "pointer",
        marginBottom: "1px",
        transition: "background var(--transition-fast)",
      }}
      onClick={() => !isRenaming && router.push(`/chat/${chat.id}`)}
      onContextMenu={(e) => onContextMenu(e, chat.id)}
      onMouseEnter={(e) => {
        if (!isActive) e.currentTarget.style.background = "var(--bg-level-4)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = isActive
          ? "var(--sidebar-active-bg)"
          : "transparent";
      }}
      onMouseDown={(e) => {
        e.currentTarget.style.transform = "scale(0.99)";
      }}
      onMouseUp={(e) => {
        e.currentTarget.style.transform = "scale(1)";
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          flex: 1,
          overflow: "hidden",
          minWidth: 0,
        }}
      >
        {isPinned && (
          <Pin
            style={{
              width: "12px",
              height: "12px",
              flexShrink: 0,
              color: "var(--sidebar-active-fg)",
            }}
          />
        )}
        {streamingStage && (
          <ThinkingOrb state={streamingStage} size={20} theme="auto" />
        )}
        <div style={{ flex: 1, minWidth: 0, overflow: "hidden" }}>
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
                width: "100%",
                fontSize: "12.5px",
                lineHeight: "1.2",
                color: "var(--text-level-1)",
                background: "var(--bg-level-2)",
                border: "1px solid var(--sidebar-active-fg)",
                borderRadius: "3px",
                padding: "1px 4px",
                outline: "none",
              }}
            />
          ) : (
            <span
              style={{
                display: "block",
                fontSize: "12.5px",
                fontWeight: isActive ? 600 : 400,
                lineHeight: 1.3,
                color: isActive
                  ? "var(--sidebar-active-fg)"
                  : "var(--text-level-1)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {chat.title}
            </span>
          )}
        </div>
      </div>
      {/* 右侧操作区：时间 + 更多按钮，容器负 margin 抵消 padding-right 贴边 */}
      <div style={{ display: "flex", alignItems: "center", gap: "2px", flexShrink: 0 }}>
      {/* 2026-08-20：最后交互时间移到整行最右侧，tabular-nums 缩放稳定，重命名时隐藏 */}
      {!isRenaming && chat.updated_at && (
        <Tooltip content={formatFullTime(chat.updated_at)} side="top">
          <span
            style={{
              fontSize: "10px",
              lineHeight: 1,
              color: "var(--text-level-4)",
              fontVariantNumeric: "tabular-nums",
              whiteSpace: "nowrap",
              flexShrink: 0,
              cursor: "default",
            }}
          >
            {formatRelativeTime(chat.updated_at, t, now)}
          </span>
        </Tooltip>
      )}
      {/* ... 按钮：20×20 / 圆角 3px / 默认 opacity 0 */}
      <Tooltip content={t("sidebar.more")} side="top">
        <button
          onClick={(e) => onMore(e, chat.id)}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "20px",
            height: "20px",
            borderRadius: "3px",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            color: "var(--text-level-3)",
            opacity: 0,
            transition: "opacity var(--transition-fast), background var(--transition-fast)",
            outline: "none",
            padding: 0,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--bg-level-3)";
            e.currentTarget.style.color = "var(--text-level-1)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "var(--text-level-3)";
          }}
          className="sb-btn--more"
        >
          <MoreHorizontal style={{ width: "13px", height: "13px" }} />
        </button>
      </Tooltip>
      </div>
    </div>
  );
});
