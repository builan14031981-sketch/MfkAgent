"use client";

import { memo } from "react";
import { Folder } from "lucide-react";
import type { Chat } from "@/hooks/useChat";
import type { Project } from "@/hooks/useProjects";
import type { Agent } from "@/hooks/useAgents";
import type { OrbStage } from "@/lib/streamStore";
import type { TokenUsageEvent } from "@/types/runtime";
import { AgentIcon } from "@/components/AgentIcon";
import { AgentOrb } from "@/components/AgentOrb";
import { ContextDashboard } from "@/components/ContextDashboard";

interface ChatHeaderProps {
  chat: Chat | undefined;
  agent: Agent | undefined;
  project: Project | null;
  streamingStage?: OrbStage | null;
  tokenUsage?: TokenUsageEvent | null;
  isEditingTitle: boolean;
  editTitle: string;
  onEditTitleChange: (value: string) => void;
  onStartEditTitle: () => void;
  onSaveTitle: () => void;
  onCancelEditTitle: () => void;
  onOpenProjectContext: () => void;
}

/**
 * 将绝对路径缩略为「盘符/根 › 末级目录」格式：
 * - Windows: E:\work\Mfkagent → "E: › Mfkagent"
 * - Mac/Linux: /Users/work/Mfkagent → "/ › Mfkagent"
 * - 兜底（无 path 或末级为空）：返回 project.name
 */
function formatProjectPath(path: string | undefined, name: string): string {
  if (!path) return name;
  const normalized = path.replace(/\\/g, "/");
  const segments = normalized.split("/").filter(Boolean);
  if (segments.length === 0) return name;
  const last = segments[segments.length - 1];
  if (!last) return name;
  // 仅一级目录：直接返回（避免 "name › name" 重复）
  if (segments.length === 1) return last;
  const root = normalized.startsWith("/") ? "/" : segments[0];
  return `${root} › ${last}`;
}

/**
 * 聊天页头部：会话标题（点击编辑）+ Agent / 项目标识。
 * memo：流式期间父级高频更新 state，本组件 props 稳定时跳过重渲染。
 *
 * 项目胶囊合并了「路径显示 + 完整路径 tooltip + 打开项目上下文面板」三重职责，
 * 点击胶囊即打开 ProjectContextPanel（不再保留右侧冗余图标按钮）。
 */
export const ChatHeader = memo(function ChatHeader({
  chat,
  agent,
  project,
  streamingStage,
  tokenUsage,
  isEditingTitle,
  editTitle,
  onEditTitleChange,
  onStartEditTitle,
  onSaveTitle,
  onCancelEditTitle,
  onOpenProjectContext,
}: ChatHeaderProps) {
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
        {agent &&
          (streamingStage ? (
            <AgentOrb stage={streamingStage} size={20} />
          ) : (
            <AgentIcon id={agent.id} size={18} style={{ color: "var(--color-primary)" }} />
          ))}
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
          {/* F-Context 上下文仪表盘：Token 消耗 + 水位预警（仅流式期间有数据时显示） */}
          <ContextDashboard usage={tokenUsage ?? null} />
          {project && (
            <span
              onClick={onOpenProjectContext}
              title={project.path || project.name}
              style={{
                fontSize: "12px",
                color: "var(--color-primary)",
                padding: "4px 8px",
                borderRadius: "var(--radius-full)",
                background: "var(--color-primary-lighter)",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                cursor: "pointer",
                maxWidth: "280px",
                overflow: "hidden",
                whiteSpace: "nowrap",
                textOverflow: "ellipsis",
                transition: "background 0.2s ease",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "color-mix(in srgb, var(--color-primary) 14%, var(--color-primary-lighter))"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "var(--color-primary-lighter)"; }}
            >
              <Folder style={{ width: "12px", height: "12px", flexShrink: 0 }} />
              {formatProjectPath(project.path, project.name)}
            </span>
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
