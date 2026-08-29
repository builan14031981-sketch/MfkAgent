"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Search, MessageSquare, FolderOpen, X, Plus, Settings } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { useProjects } from "@/hooks/useProjects";
import { useTranslation } from "@/hooks/useTranslation";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectChat: (chatId: number) => void;
  onSelectProject: (projectId: number) => void;
  onNewChat?: () => void;
  onOpenSettings?: () => void;
}

interface CommandItem {
  id: string;
  label: string;
  keywords: string[];
  icon: "plus" | "settings";
  action: () => void;
}

export function CommandPalette({ isOpen, onClose, onSelectChat, onSelectProject, onNewChat, onOpenSettings }: CommandPaletteProps) {
  const { t } = useTranslation();
  const { chats } = useChat();
  const { projects } = useProjects();
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // 命令列表
  const commands = useMemo<CommandItem[]>(() => {
    const list: CommandItem[] = [];
    if (onNewChat) {
      list.push({
        id: "new-chat",
        label: t("commandPalette.newChat"),
        keywords: ["new", "新建", "新对话", "chat", "对话"],
        icon: "plus",
        action: () => { onNewChat(); onClose(); },
      });
    }
    if (onOpenSettings) {
      list.push({
        id: "open-settings",
        label: t("commandPalette.openSettings"),
        keywords: ["settings", "设置", "配置", "preferences"],
        icon: "settings",
        action: () => { onOpenSettings(); onClose(); },
      });
    }
    return list;
  }, [onNewChat, onOpenSettings, t, onClose]);

  // 搜索结果：聊天 + 项目 + 命令
  const results = useMemo(() => {
    const lowerQuery = query.trim().toLowerCase();
    if (!lowerQuery) return { chats: [], projects: [], commands };

    const matchedChats = chats
      .filter(chat => chat.title?.toLowerCase().includes(lowerQuery))
      .slice(0, 5);

    const matchedProjects = projects
      .filter(project => project.name?.toLowerCase().includes(lowerQuery) || project.path?.toLowerCase().includes(lowerQuery))
      .slice(0, 3);

    const matchedCommands = commands.filter(cmd =>
      cmd.label.toLowerCase().includes(lowerQuery) ||
      cmd.keywords.some(k => k.includes(lowerQuery))
    );

    return { chats: matchedChats, projects: matchedProjects, commands: matchedCommands };
  }, [query, chats, projects, commands]);

  // 打开时聚焦输入框
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // ESC 关闭
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  const handleSelect = useCallback((type: "chat" | "project", id: number) => {
    onClose();
    if (type === "chat") onSelectChat(id);
    else onSelectProject(id);
  }, [onClose, onSelectChat, onSelectProject]);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        paddingTop: "20vh",
        background: "var(--overlay-modal)",
        backdropFilter: "blur(4px)",
        animation: "fadeIn 0.15s ease",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          width: "90%",
          maxWidth: 560,
          background: "var(--bg-level-1)",
          borderRadius: "var(--radius-lg)",
          border: "1px solid var(--border-primary)",
          boxShadow: "var(--shadow-lg)",
          overflow: "hidden",
          animation: "scaleIn 0.15s ease",
        }}
      >
        {/* 搜索输入框 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          padding: "16px",
          borderBottom: "1px solid var(--border-secondary)",
        }}>
          <Search style={{ width: 18, height: 18, color: "var(--text-level-4)", flexShrink: 0 }} />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("commandPalette.placeholder")}
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              fontSize: "16px",
              color: "var(--text-level-1)",
            }}
          />
          <button
            onClick={onClose}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 24,
              height: 24,
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "var(--bg-level-3)",
              cursor: "pointer",
              color: "var(--text-level-3)",
            }}
          >
            <X style={{ width: 14, height: 14 }} />
          </button>
        </div>

        {/* 搜索结果 */}
        <div style={{
          maxHeight: 400,
          overflowY: "auto",
          padding: "8px",
        }}>
          {/* 空搜索：显示常用命令 */}
          {!query.trim() && results.commands.length > 0 ? (
            <div>
              <div style={{
                fontSize: "11px",
                fontWeight: 600,
                color: "var(--text-level-4)",
                padding: "8px 12px 4px",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}>
                {t("commandPalette.commands")}
              </div>
              {results.commands.map((cmd) => (
                <button
                  key={cmd.id}
                  className="mf-pressable"
                  onClick={cmd.action}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "12px",
                    width: "100%",
                    padding: "10px 12px",
                    border: "none",
                    borderRadius: "var(--radius-md)",
                    background: "transparent",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "background 0.15s ease",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                >
                  {cmd.icon === "plus" ? (
                    <Plus style={{ width: 16, height: 16, color: "var(--color-primary)", flexShrink: 0 }} />
                  ) : (
                    <Settings style={{ width: 16, height: 16, color: "var(--text-level-4)", flexShrink: 0 }} />
                  )}
                  <span style={{ fontSize: "14px", color: "var(--text-level-1)" }}>{cmd.label}</span>
                </button>
              ))}
            </div>
          ) : results.chats.length === 0 && results.projects.length === 0 && results.commands.length === 0 ? (
            <div style={{
              padding: "24px",
              textAlign: "center",
              color: "var(--text-level-4)",
              fontSize: "14px",
            }}>
              {query ? t("commandPalette.noResults") : t("commandPalette.startTyping")}
            </div>
          ) : (
            <>
              {/* 命令结果 */}
              {results.commands.length > 0 && (
                <div>
                  <div style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    color: "var(--text-level-4)",
                    padding: "8px 12px 4px",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                  }}>
                    {t("commandPalette.commands")}
                  </div>
                  {results.commands.map((cmd) => (
                    <button
                      key={cmd.id}
                      className="mf-pressable"
                      onClick={cmd.action}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        width: "100%",
                        padding: "10px 12px",
                        border: "none",
                        borderRadius: "var(--radius-md)",
                        background: "transparent",
                        cursor: "pointer",
                        textAlign: "left",
                        transition: "background 0.15s ease",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                    >
                      {cmd.icon === "plus" ? (
                        <Plus style={{ width: 16, height: 16, color: "var(--color-primary)", flexShrink: 0 }} />
                      ) : (
                        <Settings style={{ width: 16, height: 16, color: "var(--text-level-4)", flexShrink: 0 }} />
                      )}
                      <span style={{ fontSize: "14px", color: "var(--text-level-1)" }}>{cmd.label}</span>
                    </button>
                  ))}
                </div>
              )}
              {/* 会话结果 */}
              {results.chats.length > 0 && (
                <div>
                  <div style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    color: "var(--text-level-4)",
                    padding: "8px 12px 4px",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                  }}>
                    {t("commandPalette.chats")}
                  </div>
                  {results.chats.map((chat) => (
                    <button
                      key={chat.id}
                      className="mf-pressable"
                      onClick={() => handleSelect("chat", chat.id)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        width: "100%",
                        padding: "10px 12px",
                        border: "none",
                        borderRadius: "var(--radius-md)",
                        background: "transparent",
                        cursor: "pointer",
                        textAlign: "left",
                        transition: "background 0.15s ease",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                    >
                      <MessageSquare style={{ width: 16, height: 16, color: "var(--text-level-4)", flexShrink: 0 }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: "14px",
                          color: "var(--text-level-1)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}>
                          {chat.title || "Untitled Chat"}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {/* 项目结果 */}
              {results.projects.length > 0 && (
                <div>
                  <div style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    color: "var(--text-level-4)",
                    padding: "8px 12px 4px",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                  }}>
                    {t("commandPalette.projects")}
                  </div>
                  {results.projects.map((project) => (
                    <button
                      key={project.id}
                      className="mf-pressable"
                      onClick={() => handleSelect("project", project.id)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        width: "100%",
                        padding: "10px 12px",
                        border: "none",
                        borderRadius: "var(--radius-md)",
                        background: "transparent",
                        cursor: "pointer",
                        textAlign: "left",
                        transition: "background 0.15s ease",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                    >
                      <FolderOpen style={{ width: 16, height: 16, color: "var(--text-level-4)", flexShrink: 0 }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: "14px",
                          color: "var(--text-level-1)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}>
                          {project.name}
                        </div>
                        <div style={{
                          fontSize: "12px",
                          color: "var(--text-level-4)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}>
                          {project.path}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* 底部提示 */}
        <div style={{
          padding: "8px 16px",
          borderTop: "1px solid var(--border-secondary)",
          fontSize: "11px",
          color: "var(--text-level-4)",
          display: "flex",
          justifyContent: "space-between",
        }}>
          <span>{t("commandPalette.navigate")}</span>
          <span>{t("commandPalette.select")}</span>
        </div>
      </div>
    </div>
  );
}
