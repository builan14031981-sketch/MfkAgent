"use client";

import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  Settings,
  MessageSquare,
  Trash2,
  Pin,
  PinOff,
  Edit2,
  Folder,
  FolderOpen,
  FolderPlus,
  FolderSearch,
  ChevronRight,
} from "lucide-react";
import { useChat, Chat } from "@/hooks/useChat";
import { useProjects } from "@/hooks/useProjects";
import { useAgents } from "@/hooks/useAgents";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";
import { selectDirectory } from "@/lib/selectDirectory";
import { Panel } from "./panels/Panel";

interface SidebarProps {
  currentChatId?: number | null;
  onSettingsClick?: () => void;
}

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  chatId: number | null;
}

/** 排序：置顶的聊天在前，再按更新时间倒序 */
function sortChats(chats: Chat[]): Chat[] {
  return [...chats].sort((a, b) => {
    const aPin = a.is_pinned ? -1 : 0;
    const bPin = b.is_pinned ? -1 : 0;
    if (aPin !== bPin) return aPin - bPin;
    return new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime();
  });
}

export function Sidebar({ currentChatId, onSettingsClick }: SidebarProps) {
  const router = useRouter();
  const { t } = useTranslation();
  const { chats, deleteChat, updateChat, pinChat, createChat, refetch: refetchChats } = useChat();
  const { projects, createProject, refetch: refetchProjects } = useProjects(1, 100);
  const { agents } = useAgents();
  const { settings } = useSettingsStore();

  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false,
    x: 0,
    y: 0,
    chatId: null,
  });
  const [renamingChatId, setRenamingChatId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [collapsedProjects, setCollapsedProjects] = useState<Set<number>>(new Set());
  const [hoveredProjectId, setHoveredProjectId] = useState<number | null>(null);
  const [projectModalOpen, setProjectModalOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectPath, setNewProjectPath] = useState("");
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const contextMenuRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  // 按项目分组：有 project_id 的进项目工作区，null 进通用对话
  const { projectChats, generalChats } = useMemo(() => {
    const map = new Map<number, Chat[]>();
    const general: Chat[] = [];
    for (const chat of chats) {
      if (chat.project_id != null) {
        const list = map.get(chat.project_id) ?? [];
        list.push(chat);
        map.set(chat.project_id, list);
      } else {
        general.push(chat);
      }
    }
    for (const [id, list] of map) {
      map.set(id, sortChats(list));
    }
    return { projectChats: map, generalChats: sortChats(general) };
  }, [chats]);

  // 自动展开当前会话所在的项目
  const activeProjectId = useMemo(() => {
    if (currentChatId == null) return null;
    const chat = chats.find((c) => c.id === currentChatId);
    return chat?.project_id ?? null;
  }, [chats, currentChatId]);


  // 点击外部关闭右键菜单
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node)) {
        setContextMenu(prev => ({ ...prev, visible: false }));
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // 项目工作区变更（如在会话中通过 + 菜单关联本地项目）后刷新树
  useEffect(() => {
    const handleProjectsChanged = () => {
      refetchProjects();
      refetchChats();
    };
    window.addEventListener("mfk-projects-changed", handleProjectsChanged);
    return () => window.removeEventListener("mfk-projects-changed", handleProjectsChanged);
  }, [refetchProjects, refetchChats]);

  // 重命名输入框自动聚焦
  useEffect(() => {
    if (renamingChatId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingChatId]);

  // 当前会话所在项目保持展开（渲染时派生，避免在 effect 中 setState）
  const effectiveCollapsed = useMemo(() => {
    const set = new Set(collapsedProjects);
    if (activeProjectId != null) set.delete(activeProjectId);
    return set;
  }, [collapsedProjects, activeProjectId]);

  const handleContextMenu = (e: React.MouseEvent, chatId: number) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      visible: true,
      x: e.clientX,
      y: e.clientY,
      chatId,
    });
  };

  const handleDeleteChat = async (id: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await deleteChat(id);
      if (currentChatId === id) {
        router.push("/");
      }
    } catch (err) {
      console.error("Failed to delete chat:", err);
    }
    setContextMenu(prev => ({ ...prev, visible: false }));
  };

  const handleRename = async () => {
    if (!renamingChatId || !renameValue.trim()) {
      setRenamingChatId(null);
      return;
    }
    try {
      await updateChat(renamingChatId, { title: renameValue.trim() });
    } catch (err) {
      console.error("Failed to rename chat:", err);
    }
    setRenamingChatId(null);
  };

  const handlePin = async (chatId: number, pinned: boolean) => {
    try {
      await pinChat(chatId, pinned);
    } catch (err) {
      console.error("Failed to pin chat:", err);
    }
    setContextMenu(prev => ({ ...prev, visible: false }));
  };

  const startRename = (chatId: number, currentTitle: string) => {
    setRenamingChatId(chatId);
    setRenameValue(currentTitle);
    setContextMenu(prev => ({ ...prev, visible: false }));
  };

  const toggleProject = (projectId: number) => {
    setCollapsedProjects((prev) => {
      const next = new Set(prev);
      if (next.has(projectId)) {
        next.delete(projectId);
      } else {
        next.add(projectId);
      }
      return next;
    });
  };

  // 在指定项目下快速新建会话
  const quickCreateChat = useCallback(async (projectId: number) => {
    const agentId = settings?.default_agent || agents[0]?.id || "general";
    const modelId = settings?.default_model || null;
    const personality = settings?.default_personality ? Number(settings.default_personality) : 50;
    try {
      const chat = await createChat(agentId, t("sidebar.newChatTitle"), projectId, modelId, personality);
      router.push(`/chat/${chat.id}`);
    } catch (err) {
      console.error("Failed to create chat in project:", err);
    }
  }, [settings, agents, createChat, router, t]);

  const handleCreateProject = async () => {
    const name = newProjectName.trim();
    const path = newProjectPath.trim();
    if (!name || !path || isCreatingProject) return;
    setIsCreatingProject(true);
    try {
      const project = await createProject(name, path);
      setNewProjectName("");
      setNewProjectPath("");
      setProjectModalOpen(false);
      window.dispatchEvent(new Event("mfk-projects-changed"));
      router.push(`/projects/${project.id}/files`);
    } catch (err) {
      console.error("Failed to create project:", err);
    } finally {
      setIsCreatingProject(false);
    }
  };

  // 原生文件夹选择：自动填充名称与路径
  const handlePickDirectory = async () => {
    const dir = await selectDirectory();
    if (!dir) return;
    const name = dir.split(/[\\/]/).filter(Boolean).pop() || dir;
    setNewProjectName(name);
    setNewProjectPath(dir);
  };

  const openProjectWorkspace = (projectId: number) => {
    setProjectModalOpen(false);
    router.push(`/projects/${projectId}/files`);
  };

  /** 会话行（通用对话 / 项目内共用） */
  const renderChatRow = (chat: Chat, indented: boolean) => {
    const isActive = chat.id === currentChatId;
    const isPinned = chat.is_pinned;
    const isRenaming = renamingChatId === chat.id;

    return (
      <div
        key={chat.id}
        style={{
          position: "relative",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: indented ? "5px 12px 5px 28px" : "5px 12px",
          borderRadius: "var(--radius-sm)",
          background: isActive ? "var(--color-primary-light)" : "transparent",
          cursor: "pointer",
          marginBottom: "1px",
          transition: "background var(--transition-fast)",
        }}
        onClick={() => !isRenaming && router.push(`/chat/${chat.id}`)}
        onContextMenu={(e) => handleContextMenu(e, chat.id)}
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
          <MessageSquare style={{ width: "13px", height: "13px", flexShrink: 0, color: isActive ? "var(--color-primary)" : "var(--text-level-3)" }} />
          {isRenaming ? (
            <input
              ref={renameInputRef}
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onBlur={handleRename}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleRename();
                if (e.key === "Escape") setRenamingChatId(null);
              }}
              onClick={(e) => e.stopPropagation()}
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
          onClick={(e) => handleDeleteChat(chat.id, e)}
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
          <Trash2 style={{ width: "12px", height: "12px" }} />
        </button>
      </div>
    );
  };

  return (
    <aside style={{
      width: "260px",
      height: "100%",
      display: "flex",
      flexDirection: "column",
      borderRight: "1px solid var(--border-primary)",
      background: "var(--bg-level-1)",
      flexShrink: 0,
      position: "relative",
    }}>
      {/* 新建任务 */}
      <div style={{ padding: "12px 12px 4px" }}>
        <button
          onClick={() => router.push("/")}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "8px 12px",
            borderRadius: "var(--radius-md)",
            border: "none",
            background: "var(--bg-level-3)",
            cursor: "pointer",
            fontSize: "14px",
            color: "var(--text-level-1)",
            transition: "background var(--transition-fast)",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-4)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
        >
          <Plus style={{ width: "16px", height: "16px" }} />
          <span>{t("sidebar.newTask")}</span>
        </button>
      </div>

      {/* 聊天列表 */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: "0 8px 12px",
      }}>
        {/* ===== 项目工作区 ===== */}
        <div style={{ marginBottom: "8px" }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 8px 4px",
          }}>
            <p style={{
              fontSize: "11px",
              fontWeight: "600",
              color: "var(--text-level-4)",
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              margin: 0,
            }}>{t("sidebar.projectWorkspace")}</p>
            <button
              onClick={() => setProjectModalOpen(true)}
              title={t("sidebar.openProject")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "22px",
                height: "22px",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: "transparent",
                cursor: "pointer",
                color: "var(--text-level-3)",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; e.currentTarget.style.color = "var(--color-primary)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-level-3)"; }}
            >
              <FolderPlus style={{ width: "14px", height: "14px" }} />
            </button>
          </div>

          {projects.length === 0 ? (
            <button
              onClick={() => setProjectModalOpen(true)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                width: "100%",
                padding: "6px 8px",
                borderRadius: "var(--radius-sm)",
                border: "1px dashed var(--border-primary)",
                background: "transparent",
                cursor: "pointer",
                fontSize: "12px",
                color: "var(--text-level-3)",
                textAlign: "left",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--color-primary)"; e.currentTarget.style.color = "var(--color-primary)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-primary)"; e.currentTarget.style.color = "var(--text-level-3)"; }}
            >
              <FolderPlus style={{ width: "13px", height: "13px", flexShrink: 0 }} />
              <span>{t("sidebar.noProjectsDesc")}</span>
            </button>
          ) : projects.map((project) => {
            const isCollapsed = effectiveCollapsed.has(project.id);
            const projectChatsList = projectChats.get(project.id) ?? [];
            const isHovered = hoveredProjectId === project.id;
            const isActiveProject = activeProjectId === project.id;
            return (
              <div key={project.id} style={{ marginBottom: "1px" }}>
                {/* 项目文件夹节点 */}
                <div
                  onClick={() => toggleProject(project.id)}
                  onMouseEnter={() => setHoveredProjectId(project.id)}
                  onMouseLeave={() => setHoveredProjectId(null)}
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
                  <span style={{
                    fontSize: "11px",
                    color: "var(--text-level-4)",
                    flexShrink: 0,
                    fontVariantNumeric: "tabular-nums",
                  }}>{projectChatsList.length}</span>
                  {/* 悬停显示 +：快速新建会话 */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      quickCreateChat(project.id);
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
                </div>
                {/* 项目内会话 */}
                {!isCollapsed && projectChatsList.length > 0 && (
                  <div style={{ paddingTop: "1px" }}>
                    {projectChatsList.map((chat) => renderChatRow(chat, true))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* ===== 通用对话 ===== */}
        <div>
          <div style={{ padding: "8px 8px 4px" }}>
            <p style={{
              fontSize: "11px",
              fontWeight: "600",
              color: "var(--text-level-4)",
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              margin: 0,
            }}>{t("sidebar.generalChats")}</p>
          </div>
          {chats.length === 0 ? (
            <div style={{ padding: "12px", textAlign: "center" }}>
              <p style={{ fontSize: "13px", color: "var(--text-level-3)", margin: 0 }}>{t("sidebar.noChats")}</p>
              <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: "2px 0 0 0" }}>{t("sidebar.noChatsDesc")}</p>
            </div>
          ) : generalChats.length === 0 && projects.length > 0 ? (
            <p style={{ padding: "4px 8px", fontSize: "12px", color: "var(--text-level-4)", margin: 0 }}>
              {t("sidebar.noChats")}
            </p>
          ) : (
            generalChats.map((chat) => renderChatRow(chat, false))
          )}
        </div>
      </div>

      {/* 右键菜单 */}
      {contextMenu.visible && contextMenu.chatId && (
        <div
          ref={contextMenuRef}
          style={{
            position: "fixed",
            left: contextMenu.x,
            top: contextMenu.y,
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-primary)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-lg)",
            padding: "4px",
            zIndex: 1000,
            minWidth: "160px",
            opacity: 0,
            transform: "scale(0.95)",
            animation: "contextMenuOpen 0.15s ease forwards",
          }}
        >
          <button
            onClick={() => {
              const chat = chats.find(c => c.id === contextMenu.chatId);
              if (chat) startRename(chat.id, chat.title);
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              width: "100%",
              padding: "8px 12px",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "13px",
              color: "var(--text-level-2)",
              borderRadius: "var(--radius-sm)",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            <Edit2 style={{ width: "14px", height: "14px" }} />
            <span>{t("sidebar.rename")}</span>
          </button>
          <button
            onClick={() => {
              const chat = chats.find(c => c.id === contextMenu.chatId);
              if (chat) handlePin(chat.id, !chat.is_pinned);
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              width: "100%",
              padding: "8px 12px",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "13px",
              color: "var(--text-level-2)",
              borderRadius: "var(--radius-sm)",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            {contextMenu.chatId && chats.find(c => c.id === contextMenu.chatId)?.is_pinned ? (
              <>
                <PinOff style={{ width: "14px", height: "14px" }} />
                <span>{t("sidebar.unpin")}</span>
              </>
            ) : (
              <>
                <Pin style={{ width: "14px", height: "14px" }} />
                <span>{t("sidebar.pin")}</span>
              </>
            )}
          </button>
          <div style={{
            height: "1px",
            background: "var(--border-secondary)",
            margin: "4px 0",
          }} />
          <button
            onClick={() => contextMenu.chatId && handleDeleteChat(contextMenu.chatId)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              width: "100%",
              padding: "8px 12px",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "13px",
              color: "var(--color-error)",
              borderRadius: "var(--radius-sm)",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            <Trash2 style={{ width: "14px", height: "14px" }} />
            <span>{t("sidebar.delete")}</span>
          </button>
        </div>
      )}

      {/* 打开/新建项目工作区 面板 */}
      <Panel
        isOpen={projectModalOpen}
        onClose={() => setProjectModalOpen(false)}
        title={t("sidebar.openProject")}
        width="420px"
      >
        <p style={{
          fontSize: "13px",
          color: "var(--text-level-3)",
          margin: "0 0 16px 0",
        }}>{t("sidebar.openProjectDesc")}</p>

        {/* 已有项目列表 */}
        <p style={{
          fontSize: "12px",
          fontWeight: "600",
          color: "var(--text-level-4)",
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          margin: "0 0 8px 0",
        }}>{t("sidebar.projectWorkspace")}</p>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginBottom: "24px" }}>
          {projects.length === 0 ? (
            <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: 0 }}>
              {t("sidebar.noProjects")} · {t("sidebar.noProjectsDesc")}
            </p>
          ) : projects.map((project) => (
            <button
              key={project.id}
              onClick={() => openProjectWorkspace(project.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "10px 12px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-2)",
                cursor: "pointer",
                textAlign: "left",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--color-primary)"; e.currentTarget.style.background = "var(--color-primary-light)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-primary)"; e.currentTarget.style.background = "var(--bg-level-2)"; }}
            >
              <Folder style={{ width: "16px", height: "16px", color: "var(--color-primary)", flexShrink: 0 }} />
              <span style={{ flex: 1, minWidth: 0 }}>
                <span style={{
                  display: "block",
                  fontSize: "13px",
                  fontWeight: "500",
                  color: "var(--text-level-1)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}>{project.name}</span>
                <span style={{
                  display: "block",
                  fontSize: "11px",
                  color: "var(--text-level-4)",
                  fontFamily: "monospace",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}>{project.path}</span>
              </span>
            </button>
          ))}
        </div>

        {/* 新建项目 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          margin: "0 0 8px 0",
        }}>
          <p style={{
            fontSize: "12px",
            fontWeight: "600",
            color: "var(--text-level-4)",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
            margin: 0,
          }}>{t("sidebar.newProject")}</p>
          <button
            onClick={handlePickDirectory}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              padding: "3px 8px",
              borderRadius: "var(--radius-full)",
              border: "1px solid var(--border-primary)",
              background: "transparent",
              cursor: "pointer",
              fontSize: "11px",
              color: "var(--text-level-3)",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--color-primary)"; e.currentTarget.style.color = "var(--color-primary)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-primary)"; e.currentTarget.style.color = "var(--text-level-3)"; }}
          >
            <FolderSearch style={{ width: "12px", height: "12px" }} />
            <span>{t("sidebar.pickDirectory")}</span>
          </button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <input
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
            placeholder={t("sidebar.projectName")}
            style={{
              padding: "8px 12px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-2)",
              fontSize: "13px",
              color: "var(--text-level-2)",
              outline: "none",
            }}
          />
          <input
            value={newProjectPath}
            onChange={(e) => setNewProjectPath(e.target.value)}
            placeholder={t("sidebar.projectPath")}
            style={{
              padding: "8px 12px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-2)",
              fontSize: "13px",
              fontFamily: "monospace",
              color: "var(--text-level-2)",
              outline: "none",
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleCreateProject();
            }}
          />
          <button
            onClick={handleCreateProject}
            disabled={!newProjectName.trim() || !newProjectPath.trim() || isCreatingProject}
            style={{
              padding: "8px 12px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: newProjectName.trim() && newProjectPath.trim() && !isCreatingProject ? "var(--color-primary)" : "var(--bg-level-3)",
              cursor: newProjectName.trim() && newProjectPath.trim() && !isCreatingProject ? "pointer" : "not-allowed",
              fontSize: "13px",
              fontWeight: "500",
              color: newProjectName.trim() && newProjectPath.trim() && !isCreatingProject ? "white" : "var(--text-level-3)",
            }}
          >
            {t("sidebar.createProject")}
          </button>
        </div>
      </Panel>

      {/* 底部按钮 */}
      <div style={{
        padding: "12px",
        borderTop: "1px solid var(--border-primary)",
      }}>
        {onSettingsClick && (
          <button
            onClick={onSettingsClick}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "8px 12px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "13px",
              color: "var(--text-level-3)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
              e.currentTarget.style.color = "var(--text-level-2)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--text-level-3)";
            }}
          >
            <Settings style={{ width: "15px", height: "15px" }} />
            <span>{t("sidebar.settings")}</span>
          </button>
        )}
      </div>
    </aside>
  );
}
