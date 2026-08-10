"use client";

import { useRef } from "react";
import { useRouter } from "next/navigation";
import { Pin, MessageSquare, MoreHorizontal } from "lucide-react";
import type { Chat } from "@/hooks/useChat";
import type { OrbStage } from "@/lib/streamStore";
import { ThinkingOrb } from "thinking-orbs";

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

/** 会话行（通用对话 / 项目内共用） */
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

  return (
    <div
      key={chat.id}
      style={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: indented ? "5px 10px 5px 26px" : "5px 10px",
        borderRadius: "var(--radius-sm)",
        background: isActive ? "var(--color-primary-light)" : "transparent",
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
        e.currentTarget.style.background = isActive ? "var(--color-primary-light)" : "transparent";
      }}
      onMouseDown={(e) => {
        e.currentTarget.style.transform = "scale(0.98)";
      }}
      onMouseUp={(e) => {
        e.currentTarget.style.transform = "scale(1)";
      }}
    >
      {/* 激活会话：2px 细指示条 */}
      {isActive && (
        <span style={{
          position: "absolute",
          left: "8px",
          top: "20%",
          bottom: "20%",
          width: "2px",
          borderRadius: "var(--radius-full)",
          background: "var(--color-primary)",
        }} />
      )}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "6px",
        flex: 1,
        overflow: "hidden",
      }}>
        {isPinned && (
          <Pin style={{ width: "11px", height: "11px", flexShrink: 0, color: "var(--color-primary)" }} />
        )}
        {streamingStage ? (
          <ThinkingOrb state={streamingStage} size={20} theme="auto" />
        ) : (
          <MessageSquare style={{ width: "13px", height: "13px", flexShrink: 0, color: isActive ? "var(--color-primary)" : "var(--text-level-3)" }} />
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
            fontSize: "13px",
            color: isActive ? "var(--text-level-1)" : "var(--text-level-2)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}>{chat.title}</span>
        )}
      </div>
      <button
        onClick={(e) => onMore(e, chat.id)}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "22px",
          height: "22px",
          borderRadius: "var(--radius-xs)",
          border: "none",
          background: "transparent",
          cursor: "pointer",
          color: "var(--text-level-4)",
          flexShrink: 0,
          opacity: 0,
          transition: "opacity var(--transition-fast)",
          outline: "none",
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
        <MoreHorizontal style={{ width: "14px", height: "14px" }} />
      </button>
    </div>
  );
}
