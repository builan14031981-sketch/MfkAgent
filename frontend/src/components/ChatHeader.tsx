"use client";

import { memo } from "react";
import { Folder } from "lucide-react";
import type { Chat } from "@/hooks/useChat";
import type { Project } from "@/hooks/useProjects";
import type { Agent } from "@/hooks/useAgents";
import { useTranslation } from "@/hooks/useTranslation";
import { AgentIcon } from "@/components/AgentIcon";

interface ChatHeaderProps {
  chat: Chat | undefined;
  agent: Agent | undefined;
  project: Project | null;
  isEditingTitle: boolean;
  editTitle: string;
  onEditTitleChange: (value: string) => void;
  onStartEditTitle: () => void;
  onSaveTitle: () => void;
  onCancelEditTitle: () => void;
  onOpenProjectContext: () => void;
}

/**
 * 聊天页头部：会话标题（点击编辑）+ Agent / 项目标识。
 * memo：流式期间父级高频更新 state，本组件 props 稳定时跳过重渲染。
 */
export const ChatHeader = memo(function ChatHeader({
  chat,
  agent,
  project,
  isEditingTitle,
  editTitle,
  onEditTitleChange,
  onStartEditTitle,
  onSaveTitle,
  onCancelEditTitle,
  onOpenProjectContext,
}: ChatHeaderProps) {
  const { t } = useTranslation();

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "8px 24px",
      background: "transparent",
      flexShrink: 0,
    }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
      }}>
        {agent && (
          <AgentIcon id={agent.id} size={18} style={{ color: "var(--color-primary)" }} />
        )}
        {isEditingTitle ? (
          <input
            type="text"
            value={editTitle}
            onChange={(e) => onEditTitleChange(e.target.value)}
            onBlur={onSaveTitle}
            onKeyDown={(e) => {
              if (e.key === "Enter") onSaveTitle();
              if (e.key === "Escape") onCancelEditTitle();
            }}
            autoFocus
            style={{
              fontSize: "16px",
              fontWeight: "600",
              color: "var(--text-level-1)",
              background: "transparent",
              border: "none",
              outline: "none",
              padding: 0,
              margin: 0,
              width: "200px",
            }}
          />
        ) : (
          <h1
            onClick={onStartEditTitle}
            style={{
              fontSize: "16px",
              fontWeight: "600",
              color: "var(--text-level-1)",
              margin: 0,
              cursor: "pointer",
            }}
          >{chat?.title || "Chat"}</h1>
        )}
      </div>
      {agent && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}>
          {project && (
            <span style={{
              fontSize: "12px",
              color: "var(--color-primary)",
              padding: "4px 8px",
              borderRadius: "var(--radius-full)",
              background: "var(--color-primary-lighter)",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
            }}>
              <Folder style={{ width: "12px", height: "12px" }} />
              {project.name}
            </span>
          )}
          {project && (
            <button
              onClick={onOpenProjectContext}
              title={t("chat.projectContext")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "28px",
                height: "28px",
                borderRadius: "var(--radius-full)",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-2)",
                cursor: "pointer",
                color: "var(--text-level-2)",
                transition: "all 0.6s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-level-3)";
                e.currentTarget.style.borderColor = "var(--color-primary)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "var(--bg-level-2)";
                e.currentTarget.style.borderColor = "var(--border-primary)";
              }}
            >
              <Folder style={{ width: "14px", height: "14px" }} />
            </button>
          )}
          <span style={{
            fontSize: "12px",
            color: "var(--text-level-3)",
            padding: "4px 8px",
            borderRadius: "var(--radius-full)",
            background: "var(--bg-level-3)",
          }}>{agent.name}</span>
        </div>
      )}
    </div>
  );
});
