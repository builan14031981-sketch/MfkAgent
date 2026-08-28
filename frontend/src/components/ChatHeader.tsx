"use client";

import { memo, useState, useRef, useEffect, useCallback } from "react";
import { Folder, FolderPlus, ChevronDown, ArrowRightLeft, Unlink, Download } from "lucide-react";
import type { Chat } from "@/hooks/useChat";
import type { Project } from "@/hooks/useProjects";
import type { Agent } from "@/hooks/useAgents";
import type { OrbStage } from "@/lib/streamStore";
import type { TokenUsageEvent } from "@/types/runtime";
import { AgentIcon } from "@/components/AgentIcon";
import { ContextDashboard } from "@/components/ContextDashboard";
import { useTranslation } from "@/hooks/useTranslation";

interface ChatHeaderProps {
  chat: Chat | undefined;
  agent: Agent | undefined;
  project: Project | null;
  streamingStage?: OrbStage | null;
  tokenUsage?: TokenUsageEvent | null;
  onCompress?: () => void;
  isCompressing?: boolean;
  isEditingTitle: boolean;
  editTitle: string;
  onEditTitleChange: (value: string) => void;
  onStartEditTitle: () => void;
  onSaveTitle: () => void;
  onCancelEditTitle: () => void;
  onOpenProjectContext: () => void;
  /** 已注册项目列表（供切换使用） */
  projects?: Project[];
  /** 切换到指定项目 */
  onSwitchProject?: (projectId: number) => void;
  /** 解绑当前项目 */
  onUnbindProject?: () => void;
  /** 直接选择本地目录（右上角「关联项目」胶囊点击调用，替代触发加号菜单） */
  onSelectDirectory?: () => void;
  /** 新建对话（Phase1：聊天头部新建按钮 + Ctrl+N 快捷键） */
  onNewChat?: () => void;
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
 * 点击胶囊即打开 ProjectContextPanel。
 * 胶囊右侧小箭头展开下拉菜单：切换项目 / 解绑项目。
 */
export const ChatHeader = memo(function ChatHeader({
  chat,
  agent,
  project,
  tokenUsage,
  onCompress,
  isCompressing,
  isEditingTitle,
  editTitle,
  onEditTitleChange,
  onStartEditTitle,
  onSaveTitle,
  onCancelEditTitle,
  onOpenProjectContext,
  projects,
  onSwitchProject,
  onUnbindProject,
  onSelectDirectory,
}: ChatHeaderProps) {
  const { t } = useTranslation();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const dropRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // 点击外部关闭下拉
  useEffect(() => {
    if (!dropdownOpen) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (dropRef.current?.contains(target)) return;
      if (triggerRef.current?.contains(target)) return;
      setDropdownOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [dropdownOpen]);

  const toggleDropdown = useCallback(() => setDropdownOpen((v) => !v), []);

  const handleSwitch = useCallback((projectId: number) => {
    setDropdownOpen(false);
    onSwitchProject?.(projectId);
  }, [onSwitchProject]);

  const handleUnbind = useCallback(() => {
    setDropdownOpen(false);
    onUnbindProject?.();
  }, [onUnbindProject]);

  const handleExport = useCallback(async () => {
    if (!chat || exporting) return;
    setExporting(true);
    try {
      const res = await fetch(`/api/chat/${chat.id}/export?format=markdown`);
      const data = await res.json();
      const blob = new Blob([data.content], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = data.filename || `${chat.title || "chat"}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Export failed:", e);
    } finally {
      setExporting(false);
    }
  }, [chat, exporting]);

  // 其他项目（排除当前已绑定的）
  const otherProjects = (projects ?? []).filter((p) => p.id !== project?.id);

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "6px 24px",
      background: "transparent",
      flexShrink: 0,
    }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
      }}>
        {agent && (
          <AgentIcon id={agent.id} size={18} style={{ color: "var(--text-level-3)" }} />
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
              fontSize: "14px",
              fontWeight: "600",
              color: "var(--text-level-1)",
              background: "transparent",
              border: "none",
              outline: "none",
              padding: 0,
              margin: 0,
              width: "200px",
              lineHeight: "1.4",
            }}
          />
        ) : (
          <h1
            onClick={onStartEditTitle}
            style={{
              fontSize: "14px",
              fontWeight: "600",
              color: "var(--text-level-1)",
              margin: 0,
              lineHeight: "1.4",
              cursor: "pointer",
              transition: "color 0.15s ease",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--color-primary)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-level-1)"; }}
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
          <ContextDashboard usage={tokenUsage ?? null} onCompress={onCompress} isCompressing={isCompressing} />
          {project && (
            <span
              onClick={onOpenProjectContext}
              title={project.path || project.name}
              style={{
                fontSize: "12px",
                color: "var(--text-level-3)",
                padding: "4px 8px",
                borderRadius: "var(--radius-full)",
                background: "var(--bg-level-3)",
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
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-4)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            >
              <Folder style={{ width: "12px", height: "12px", flexShrink: 0 }} />
              {formatProjectPath(project.path, project.name)}
            </span>
          )}
          {/* 项目操作下拉：切换 / 解绑 */}
          {project && otherProjects.length > 0 && (
            <div style={{ position: "relative" }}>
              <button
                ref={triggerRef}
                onClick={toggleDropdown}
                title={t("chat.menu.switchProject")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "20px",
                  height: "20px",
                  padding: 0,
                  borderRadius: "var(--radius-sm)",
                  border: "none",
                  background: dropdownOpen ? "var(--bg-level-3)" : "transparent",
                  cursor: "pointer",
                  color: "var(--text-level-3)",
                  transition: "all 0.15s ease",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                onMouseLeave={(e) => { if (!dropdownOpen) e.currentTarget.style.background = "transparent"; }}
              >
                <ChevronDown style={{
                  width: "14px",
                  height: "14px",
                  transform: dropdownOpen ? "rotate(180deg)" : "rotate(0deg)",
                  transition: "transform 0.15s ease",
                }} />
              </button>
              {dropdownOpen && (
                <div
                  ref={dropRef}
                  style={{
                    position: "absolute",
                    right: 0,
                    top: "100%",
                    marginTop: "4px",
                    minWidth: "180px",
                    maxHeight: "240px",
                    overflowY: "auto",
                    background: "var(--bg-level-1)",
                    border: "1px solid var(--border-primary)",
                    borderRadius: "var(--radius-md)",
                    boxShadow: "var(--shadow-lg)",
                    padding: "4px",
                    zIndex: 1000,
                  }}
                >
                  {/* 切换项目列表 */}
                  {otherProjects.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => handleSwitch(p.id)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        width: "100%",
                        padding: "6px 10px",
                        border: "none",
                        borderRadius: "var(--radius-sm)",
                        background: "transparent",
                        cursor: "pointer",
                        fontSize: "12px",
                        color: "var(--text-level-2)",
                        textAlign: "left",
                        outline: "none",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                      title={p.path}
                    >
                      <ArrowRightLeft style={{ width: "12px", height: "12px", color: "var(--color-primary)", flexShrink: 0 }} />
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.name}</span>
                    </button>
                  ))}
                  {/* 分割线 + 解绑 */}
                  <div style={{ height: "1px", background: "var(--border-secondary)", margin: "4px 0" }} />
                  <button
                    onClick={handleUnbind}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      width: "100%",
                      padding: "6px 10px",
                      border: "none",
                      borderRadius: "var(--radius-sm)",
                      background: "transparent",
                      cursor: "pointer",
                      fontSize: "12px",
                      color: "var(--color-error)",
                      textAlign: "left",
                      outline: "none",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                  >
                    <Unlink style={{ width: "12px", height: "12px", flexShrink: 0 }} />
                    <span>{t("chat.menu.unbindProject")}</span>
                  </button>
                </div>
              )}
            </div>
          )}
          {/* 无项目时显示关联入口胶囊 */}
          {!project && (
            <span
              onClick={() => onSelectDirectory?.()}
              title={t("chat.noProjectHint")}
              style={{
                fontSize: "12px",
                color: "var(--text-level-3)",
                padding: "4px 8px",
                borderRadius: "var(--radius-full)",
                background: "var(--bg-level-3)",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "background 0.2s ease",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-4)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            >
              <FolderPlus style={{ width: "12px", height: "12px", flexShrink: 0 }} />
              {t("chat.linkProjectNow")}
            </span>
          )}
          <span
            style={{
              fontSize: "12px",
              color: "var(--text-level-3)",
              padding: "4px 8px",
              borderRadius: "var(--radius-full)",
              background: "var(--bg-level-3)",
              cursor: "default",
              transition: "background 0.2s ease, color 0.2s ease",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-4)"; e.currentTarget.style.color = "var(--text-level-2)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; e.currentTarget.style.color = "var(--text-level-3)"; }}
          >{agent.name}</span>
          {/* 导出对话为 Markdown */}
          <button
            onClick={handleExport}
            disabled={exporting}
            title={t("chat.export")}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "24px",
              height: "24px",
              padding: 0,
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "transparent",
              cursor: exporting ? "wait" : "pointer",
              color: "var(--text-level-3)",
              opacity: exporting ? 0.5 : 1,
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => { if (!exporting) e.currentTarget.style.background = "var(--bg-level-4)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            <Download style={{ width: "14px", height: "14px" }} />
          </button>
        </div>
      )}
    </div>
  );
});
