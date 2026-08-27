"use client";

import { useState, useMemo, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import {
  Plus,
  Settings,
  FolderPlus,
  ChevronRight,
  ChevronDown,
  MessageSquare,
  Folder,
  FolderOpen,
  PanelLeftClose,
  CheckSquare,
} from "lucide-react";
import { useChat, Chat } from "@/hooks/useChat";
import { useProjects } from "@/hooks/useProjects";
import type { Project } from "@/hooks/useProjects";
import { useAgents } from "@/hooks/useAgents";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";
import { useStreamStore } from "@/lib/streamStore";
import { useTabStore } from "@/lib/tabStore";
import { Search, X } from "lucide-react";
import { selectDirectory } from "@/lib/selectDirectory";
import { Panel } from "./panels/Panel";
import { ProjectInitModal } from "./ProjectInitModal";
import { ChatRow } from "./sidebar/ChatRow";
import { ProjectNode } from "./sidebar/ProjectNode";
import { SidebarContextMenu, SidebarContextMenuState } from "./sidebar/SidebarContextMenu";
import { ProjectCreateForm } from "./sidebar/ProjectCreateForm";
import { TodoPanel } from "./TodoPanel";

// ── localStorage keys ──
const COLLAPSED_PROJECTS_KEY = "mfk_sidebar_collapsed_projects";
const COLLAPSED_GENERAL_CHATS_KEY = "mfk_sidebar_collapsed_general_chats";
const COLLAPSED_PROJECT_WORKSPACE_KEY = "mfk_sidebar_collapsed_project_workspace";

function readLocalBool(key: string): boolean {
  if (typeof window === "undefined") return false;
  try { return localStorage.getItem(key) === "1"; }
  catch { return false; }
}

/** 弹窗挂到 body，脱离 zoom 容器，fixed 定位正常 */
function Portal({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return createPortal(children, document.body);
}

function readLocalNumSet(key: string): Set<number> {
  if (typeof window === "undefined") return new Set();
  try {
    const saved = localStorage.getItem(key);
    if (!saved) return new Set();
    const arr = JSON.parse(saved);
    return Array.isArray(arr) ? new Set(arr) : new Set();
  } catch { return new Set(); }
}

interface SidebarProps {
  currentChatId?: number | null;
  onSettingsClick?: () => void;
  collapsed?: boolean;
  onToggleSidebar?: () => void;
  onOpenCommandPalette?: () => void;
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

export function Sidebar({ currentChatId, onSettingsClick, collapsed, onToggleSidebar, onOpenCommandPalette }: SidebarProps) {
  const router = useRouter();
  const { t } = useTranslation();
  const { chats, deleteChat, updateChat, pinChat, archiveChat, refetch: refetchChats } = useChat();
  const { projects, createProject, deleteProject, pinProject, archiveProject, refetch: refetchProjects } = useProjects(1, 100);
  const { agents } = useAgents();
  const { settings } = useSettingsStore();
  const streams = useStreamStore((s) => s.streams);

  const [contextMenu, setContextMenu] = useState<SidebarContextMenuState>({
    visible: false,
    x: 0,
    y: 0,
    chatId: null,
    projectId: null,
  });
  const [renamingChatId, setRenamingChatId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [collapsedProjects, setCollapsedProjects] = useState<Set<number>>(new Set());
  const [hoveredProjectId, setHoveredProjectId] = useState<number | null>(null);
  const [projectModalOpen, setProjectModalOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectPath, setNewProjectPath] = useState("");
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [initProject, setInitProject] = useState<Project | null>(null);
  const [quickCreateProject, setQuickCreateProject] = useState<Project | null>(null);
  const [collapsedGeneralChats, setCollapsedGeneralChats] = useState(false);
  const generalChatsListRef = useRef<HTMLDivElement>(null);
  const [collapsedProjectWorkspace, setCollapsedProjectWorkspace] = useState(false);
  const projectWorkspaceRef = useRef<HTMLDivElement>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [todoPopupOpen, setTodoPopupOpen] = useState(false);

  // 客户端挂载后从 localStorage 同步 UI 折叠状态（避免 SSR hydration mismatch）
  useEffect(() => {
    setCollapsedProjects(readLocalNumSet(COLLAPSED_PROJECTS_KEY));
  }, []);
  useEffect(() => {
    setCollapsedGeneralChats(readLocalBool(COLLAPSED_GENERAL_CHATS_KEY));
  }, []);
  useEffect(() => {
    setCollapsedProjectWorkspace(readLocalBool(COLLAPSED_PROJECT_WORKSPACE_KEY));
  }, []);

  // 阻止 Chromium 自动聚焦启发式：页面加载时若"新建任务"按钮被自动聚焦，立即移除焦点
  // 仅在 mount 时执行一次，不影响用户后续点击 / Tab 键聚焦
  const newTaskBtnRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (newTaskBtnRef.current && document.activeElement === newTaskBtnRef.current) {
      newTaskBtnRef.current.blur();
    }
  }, []);

  // 按项目分组：有 project_id 的进项目工作区，null 进通用对话
  const { projectChats, pinnedChats, recentChats } = useMemo(() => {
    const map = new Map<number, Chat[]>();
    const pinned: Chat[] = [];
    const recent: Chat[] = [];
    for (const chat of chats) {
      if (chat.project_id != null) {
        const list = map.get(chat.project_id) ?? [];
        list.push(chat);
        map.set(chat.project_id, list);
      } else if (chat.is_pinned) {
        pinned.push(chat);
      } else {
        recent.push(chat);
      }
    }
    for (const [id, list] of map) {
      map.set(id, sortChats(list));
    }
    return {
      projectChats: map,
      pinnedChats: sortChats(pinned),
      recentChats: sortChats(recent),
    };
  }, [chats]);

  // 搜索过滤：匹配标题（不区分大小写），搜索时扁平展示所有匹配聊天
  const filteredChats = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return null;
    return chats
      .filter((c) => c.title?.toLowerCase().includes(q))
      .sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime());
  }, [chats, searchQuery]);

  // 自动展开当前会话所在的项目
  const activeProjectId = useMemo(() => {
    if (currentChatId == null) return null;
    const chat = chats.find((c) => c.id === currentChatId);
    return chat?.project_id ?? null;
  }, [chats, currentChatId]);

  // 项目工作区变更（如在会话中通过 + 菜单关联本地项目）后刷新树
  useEffect(() => {
    const handleProjectsChanged = () => {
      refetchProjects();
      refetchChats();
    };
    window.addEventListener("mfk-projects-changed", handleProjectsChanged);
    return () => window.removeEventListener("mfk-projects-changed", handleProjectsChanged);
  }, [refetchProjects, refetchChats]);

  // 当前会话所在项目保持展开（渲染时派生，避免在 effect 中 setState）
  // ⚠️ 已移除强制展开逻辑：用户手动折叠优先，不因活跃会话自动展开

  // 通用对话折叠/展开动画
  useEffect(() => {
    if (!generalChatsListRef.current) return;
    if (collapsedGeneralChats) {
      generalChatsListRef.current.style.maxHeight = "0px";
      generalChatsListRef.current.style.opacity = "0";
    } else {
      generalChatsListRef.current.style.maxHeight = "2000px";
      generalChatsListRef.current.style.opacity = "1";
    }
  }, [collapsedGeneralChats]);

  // 项目工作区折叠/展开动画
  useEffect(() => {
    if (!projectWorkspaceRef.current) return;
    if (collapsedProjectWorkspace) {
      projectWorkspaceRef.current.style.maxHeight = "0px";
      projectWorkspaceRef.current.style.opacity = "0";
    } else {
      projectWorkspaceRef.current.style.maxHeight = "2000px";
      projectWorkspaceRef.current.style.opacity = "1";
    }
  }, [collapsedProjectWorkspace]);

  const handleContextMenu = (e: React.MouseEvent, chatId: number) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      visible: true,
      x: e.clientX,
      y: e.clientY,
      chatId,
      projectId: null,
    });
  };

  // `...` 更多按钮：会话行
  const handleMoreChat = (e: React.MouseEvent, chatId: number) => {
    e.stopPropagation();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setContextMenu({
      visible: true,
      x: rect.right - 160,
      y: rect.top,
      chatId,
      projectId: null,
    });
  };

  // `...` 更多按钮：项目节点
  const handleMoreProject = (e: React.MouseEvent, projectId: number) => {
    e.stopPropagation();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setContextMenu({
      visible: true,
      x: rect.right - 160,
      y: rect.top,
      chatId: null,
      projectId,
    });
  };

  // 项目节点右键菜单（与 ... 菜单一致：置顶 / 删除）
  const handleProjectContextMenu = (e: React.MouseEvent, projectId: number) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      visible: true,
      x: e.clientX,
      y: e.clientY,
      chatId: null,
      projectId,
    });
  };

  const closeContextMenu = useCallback(() => {
    setContextMenu((prev) => ({ ...prev, visible: false }));
  }, []);

  const handleOpenInNewTab = (chatId: number) => {
    const targetChat = chats.find((c) => c.id === chatId);
    useTabStore.getState().openTab({
      chatId,
      title: targetChat?.title || "对话",
      agentId: targetChat?.agent_id,
      projectId: targetChat?.project_id ?? null,
    }, { forceNewTab: true });
    router.push(`/chat/${chatId}`);
    closeContextMenu();
  };

  const handleDeleteChat = async (id: number) => {
    try {
      await deleteChat(id);
      useTabStore.getState().closeTab(id);
      if (currentChatId === id) {
        const nextActiveId = useTabStore.getState().activeChatId;
        if (nextActiveId != null) {
          router.push(`/chat/${nextActiveId}`);
        } else {
          router.push("/");
        }
      }
    } catch (err) {
      console.error("Failed to delete chat:", err);
    }
    closeContextMenu();
  };

  const handleDeleteProject = async (id: number) => {
    try {
      await deleteProject(id);
    } catch (err) {
      console.error("Failed to delete project:", err);
    }
    closeContextMenu();
  };

  // 归档会话：进行中（SSE 流活跃）的会话不可归档
  const handleArchiveChat = async (id: number) => {
    if (streams[id] != null) {
      closeContextMenu();
      alert(t("chat.cannotArchiveRunning"));
      return;
    }
    try {
      await archiveChat(id);
      useTabStore.getState().closeTab(id);
      if (currentChatId === id) {
        const nextActiveId = useTabStore.getState().activeChatId;
        if (nextActiveId != null) {
          router.push(`/chat/${nextActiveId}`);
        } else {
          router.push("/");
        }
      }
    } catch (err) {
      console.error("Failed to archive chat:", err);
    }
    closeContextMenu();
  };

  // 归档项目：级联归档其下会话（后端处理）；仅提示一次确认
  const handleArchiveProject = async (id: number) => {
    const project = projects.find((p) => p.id === id);
    if (!project) {
      closeContextMenu();
      return;
    }
    if (!window.confirm(t("chat.archiveProjectConfirm", { name: project.name }))) {
      closeContextMenu();
      return;
    }
    try {
      await archiveProject(id);
    } catch (err) {
      console.error("Failed to archive project:", err);
    }
    closeContextMenu();
  };

  const handlePinProject = async (id: number, pinned: boolean) => {
    try {
      await pinProject(id, pinned);
    } catch (err) {
      console.error("Failed to pin project:", err);
    }
    closeContextMenu();
  };

  // 在系统文件管理器中打开项目目录（仅 Electron 环境可用）
  const handleOpenProjectFolder = useCallback(async (projectId: number) => {
    const project = projects.find((p) => p.id === projectId);
    const targetPath = project?.path;
    // 边界：项目不存在 / 路径为空 / 非 Electron 环境 → 静默退出（不打断菜单）
    if (!targetPath) {
      closeContextMenu();
      return;
    }
    if (typeof window === "undefined" || !window.electronAPI?.openPath) {
      closeContextMenu();
      return;
    }
    try {
      await window.electronAPI.openPath(targetPath);
    } catch (err) {
      console.error("Failed to open project folder:", err);
    }
    closeContextMenu();
  }, [projects, closeContextMenu]);

  const handleRenameCommit = async () => {
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

  const handlePin = async (chatId: number) => {
    const chat = chats.find((c) => c.id === chatId);
    if (!chat) return;
    try {
      await pinChat(chatId, !chat.is_pinned);
    } catch (err) {
      console.error("Failed to pin chat:", err);
    }
    closeContextMenu();
  };

  const startRename = (chatId: number) => {
    const chat = chats.find((c) => c.id === chatId);
    if (!chat) return;
    setRenamingChatId(chatId);
    setRenameValue(chat.title);
    closeContextMenu();
  };

  const toggleProject = (projectId: number) => {
    setCollapsedProjects((prev) => {
      const next = new Set(prev);
      if (next.has(projectId)) {
        next.delete(projectId);
      } else {
        next.add(projectId);
      }
      try { localStorage.setItem(COLLAPSED_PROJECTS_KEY, JSON.stringify([...next])); } catch { /* noop */ }
      return next;
    });
  };

  const toggleProjectWorkspace = () => {
    setCollapsedProjectWorkspace((prev) => {
      const next = !prev;
      try { localStorage.setItem(COLLAPSED_PROJECT_WORKSPACE_KEY, next ? "1" : "0"); } catch { /* noop */ }
      return next;
    });
  };

  const toggleGeneralChats = () => {
    setCollapsedGeneralChats((prev) => {
      const next = !prev;
      try { localStorage.setItem(COLLAPSED_GENERAL_CHATS_KEY, next ? "1" : "0"); } catch { /* noop */ }
      return next;
    });
  };

  // 在指定项目下快速新建会话：弹出 ProjectInitModal 复用窗口
  const quickCreateChat = useCallback(async (projectId: number) => {
    const project = projects.find((p) => p.id === projectId);
    if (project) setQuickCreateProject(project);
  }, [projects]);

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
      setInitProject(project);
    } catch (err) {
      console.error("Failed to create project:", err);
    } finally {
      setIsCreatingProject(false);
    }
  };

  // 原生文件夹选择：选中即自动创建项目（无需手动粘贴/点击创建），随后弹初始化向导
  const handlePickDirectory = async () => {
    const dir = await selectDirectory();
    if (!dir) return;
    const name = dir.split(/[\\/]/).filter(Boolean).pop() || dir;
    setNewProjectName(name);
    setNewProjectPath(dir);
    try {
      const project = await createProject(name, dir);
      setNewProjectName("");
      setNewProjectPath("");
      setProjectModalOpen(false);
      setInitProject(project);
    } catch (err) {
      // 自动创建失败：保留表单填充，用户可手动提交
      console.error("Failed to auto-create project from directory:", err);
    }
  };

  const openProjectWorkspace = (projectId: number) => {
    setProjectModalOpen(false);
    router.push(`/projects/${projectId}/files`);
  };

  const renderGeneralChatRow = (chat: Chat) => {
    return (
      <ChatRow
        key={chat.id}
        chat={chat}
        indented={false}
        isActive={chat.id === currentChatId}
        streamingStage={streams[chat.id] ?? null}
        isRenaming={renamingChatId === chat.id}
        renameValue={renameValue}
        onRenameValueChange={setRenameValue}
        onRenameCommit={handleRenameCommit}
        onRenameCancel={() => setRenamingChatId(null)}
        onContextMenu={handleContextMenu}
        onMore={handleMoreChat}
      />
    );
  };

  return (
    <aside style={{
      width: "var(--sidebar-width)",
      minWidth: collapsed ? 0 : undefined,
      height: "100%",
      display: "flex",
      flexDirection: "column",
      borderRight: collapsed ? "none" : "1px solid var(--border-primary)",
      background: "var(--bg-level-1)",
      flexShrink: 0,
      position: "relative",
      overflow: collapsed ? "hidden" : "visible",
      transition: "width 0.3s cubic-bezier(0.4, 0, 0.2, 1), border-right 0.3s ease",
    }}>
      {/* 内容缩放包装：框架固定，只缩放内容 */}
      <div data-zoomable="sidebar-content" style={{ width: "100%", flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
      {/* 顶部品牌区 */}
      <div style={{ padding: "14px 12px 8px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-level-1)", letterSpacing: "-0.01em" }}>
          MfkAgent
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: "2px" }}>
          {/* 待办入口 */}
          <button
            onClick={() => setTodoPopupOpen((v) => !v)}
            className="sb-btn--ghost"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "28px",
              height: "28px",
              padding: 0,
              borderRadius: "var(--radius-md)",
              position: "relative",
            }}
            title="待办"
          >
            <CheckSquare style={{ width: "16px", height: "16px" }} />
          </button>
          {onToggleSidebar && (
            <button
              onClick={onToggleSidebar}
              className="sb-btn"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "28px",
                height: "28px",
                padding: 0,
                borderRadius: "var(--radius-sm)",
                color: "var(--text-level-4)",
                flexShrink: 0,
              }}
              title={t("sidebar.collapse")}
            >
              <PanelLeftClose size={16} />
            </button>
          )}
        </div>
      </div>

      {/* 搜索框：实时过滤聊天标题 */}
      <div style={{ padding: "0 12px 8px" }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: "5px 8px",
          borderRadius: "var(--radius-md)",
          background: "var(--bg-level-3)",
          border: "1px solid transparent",
          transition: "border-color 0.15s ease",
        }}
        onFocus={(e) => { e.currentTarget.style.borderColor = "var(--border-primary)"; }}
        onBlur={(e) => { e.currentTarget.style.borderColor = "transparent"; }}
        >
          <Search style={{ width: "14px", height: "14px", color: "var(--text-level-4)", flexShrink: 0 }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t("sidebar.searchPlaceholder")}
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              fontSize: "12px",
              color: "var(--text-level-2)",
              minWidth: 0,
            }}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "16px",
                height: "16px",
                padding: 0,
                border: "none",
                background: "transparent",
                cursor: "pointer",
                color: "var(--text-level-4)",
                flexShrink: 0,
              }}
            >
              <X style={{ width: "12px", height: "12px" }} />
            </button>
          )}
        </div>
      </div>

      {/* 新建任务按钮 */}
      <div style={{ padding: "0 12px 10px" }}>
        <button
          ref={newTaskBtnRef}
          onClick={() => router.push("/")}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "6px",
            padding: "7px 10px",
            borderRadius: "var(--radius-md)",
            fontSize: "13px",
            fontWeight: 500,
            color: "var(--text-level-1)",
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-primary)",
            cursor: "pointer",
            outline: "none",
            transition: "background var(--transition-fast), border-color var(--transition-fast)",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; e.currentTarget.style.borderColor = "var(--color-primary)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-level-2)"; e.currentTarget.style.borderColor = "var(--border-primary)"; }}
        >
          <Plus style={{ width: "14px", height: "14px" }} />
          <span>{t("sidebar.newTask")}</span>
        </button>
      </div>

      {/* 聊天列表 */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: "0 8px 12px",
      }}>
        {/* 搜索结果：有搜索词时扁平展示 */}
        {filteredChats && (
          <div>
            {filteredChats.length === 0 ? (
              <div style={{ padding: "16px 8px", textAlign: "center" }}>
                <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: 0 }}>
                  {t("sidebar.noSearchResults")}
                </p>
              </div>
            ) : (
              filteredChats.map((chat) => renderGeneralChatRow(chat))
            )}
          </div>
        )}
        {/* 原分组：搜索时隐藏 */}
        <div style={{ display: filteredChats ? "none" : "block" }}>
        {/* ===== 置顶 ===== */}
        {pinnedChats.length > 0 && (
          <div style={{ marginBottom: "12px" }}>
            <div style={{
              padding: "0 8px 4px",
              fontSize: "11px",
              fontWeight: 600,
              color: "var(--text-level-4)",
              letterSpacing: "0.05em",
              textTransform: "uppercase",
            }}>
              {t("sidebar.pinned")}
            </div>
            {pinnedChats.map(renderGeneralChatRow)}
          </div>
        )}

        {/* ===== 项目 ===== */}
        <div style={{ marginBottom: "12px" }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 8px 4px",
          }}>
            <button
              onClick={toggleProjectWorkspace}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "4px",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                padding: 0,
              }}
            >
              {collapsedProjectWorkspace ? (
                <ChevronRight style={{ width: "12px", height: "12px", color: "var(--text-level-4)", flexShrink: 0 }} />
              ) : (
                <ChevronDown style={{ width: "12px", height: "12px", color: "var(--text-level-4)", flexShrink: 0 }} />
              )}
              <span style={{
                fontSize: "11px",
                fontWeight: 600,
                color: "var(--text-level-4)",
                letterSpacing: "0.05em",
                textTransform: "uppercase",
              }}>
                {t("sidebar.projects")}
              </span>
            </button>
            <button
              onClick={() => setProjectModalOpen(true)}
              className="sb-btn--icon-sm"
              title={t("sidebar.openProject")}
              style={{ opacity: 0.6 }}
            >
              <FolderPlus style={{ width: "12px", height: "12px" }} />
            </button>
          </div>
          {!collapsedProjectWorkspace && (
            <div style={{ maxHeight: "320px", overflowY: "auto" }}>
          {projects.length === 0 ? (
            <button
              onClick={() => setProjectModalOpen(true)}
              className="sb-btn--dashed"
            >
              <FolderPlus style={{ width: "13px", height: "13px", flexShrink: 0 }} />
              <span>{t("sidebar.noProjectsDesc")}</span>
            </button>
          ) : projects.map((project) => (
            <ProjectNode
              key={project.id}
              project={project}
              chats={projectChats.get(project.id) ?? []}
              isCollapsed={collapsedProjects.has(project.id)}
              isActiveProject={activeProjectId === project.id}
              isHovered={hoveredProjectId === project.id}
              onToggleCollapse={() => toggleProject(project.id)}
              onHoverChange={(hovered) => setHoveredProjectId(hovered ? project.id : null)}
              onContextMenu={handleProjectContextMenu}
              onMoreProject={handleMoreProject}
              onQuickCreateChat={quickCreateChat}
              currentChatId={currentChatId}
              streams={streams}
              renamingChatId={renamingChatId}
              renameValue={renameValue}
              onRenameValueChange={setRenameValue}
              onRenameCommit={handleRenameCommit}
              onRenameCancel={() => setRenamingChatId(null)}
              onChatContextMenu={handleContextMenu}
              onChatMore={handleMoreChat}
            />
          ))}
          </div>
          )}
        </div>

        {/* ===== 最近对话 ===== */}
        <div>
          <div style={{
            padding: "0 8px 4px",
            fontSize: "11px",
            fontWeight: 600,
            color: "var(--text-level-4)",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
          }}>
            {t("sidebar.recent")}
          </div>
          {chats.length === 0 ? (
            <div style={{ padding: "12px", textAlign: "center" }}>
              <p style={{ fontSize: "13px", color: "var(--text-level-3)", margin: 0 }}>{t("sidebar.noChats")}</p>
              <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: "2px 0 0 0" }}>{t("sidebar.noChatsDesc")}</p>
            </div>
          ) : recentChats.length === 0 && pinnedChats.length === 0 && projects.length > 0 ? (
            <p style={{ padding: "4px 8px", fontSize: "12px", color: "var(--text-level-4)", margin: 0 }}>
              {t("sidebar.noChats")}
            </p>
          ) : (
            recentChats.map(renderGeneralChatRow)
          )}
        </div>
        </div>
      </div>

      {/* 右键菜单：Portal 挂 body */}
      <Portal>
      <SidebarContextMenu
        state={contextMenu}
        chats={chats}
        projects={projects}
        onOpenInNewTab={handleOpenInNewTab}
        onRenameChat={startRename}
        onPinChat={handlePin}
        onArchiveChat={handleArchiveChat}
        onDeleteChat={handleDeleteChat}
        onPinProject={(id) => handlePinProject(id, !projects.find((p) => p.id === id)?.is_pinned)}
        onArchiveProject={handleArchiveProject}
        onDeleteProject={handleDeleteProject}
        onOpenProjectFolder={handleOpenProjectFolder}
        onClose={closeContextMenu}
      />
      </Portal>

      {/* 新建项目面板：Portal 挂 body */}
      <Portal>
      <Panel
        isOpen={projectModalOpen}
        onClose={() => setProjectModalOpen(false)}
        title={t("sidebar.openProject")}
        width="420px"
      >
        <ProjectCreateForm
          projects={projects}
          newProjectName={newProjectName}
          newProjectPath={newProjectPath}
          isCreatingProject={isCreatingProject}
          onNameChange={setNewProjectName}
          onPathChange={setNewProjectPath}
          onCreateProject={handleCreateProject}
          onPickDirectory={handlePickDirectory}
          onOpenProjectWorkspace={openProjectWorkspace}
          // 2026-08-11：行主点击 = 关面板 + 弹“已关联项目”向导新开会话（原行点击跳文件工作区已降为 hover 图标）
          onQuickCreateChat={(id) => {
            setProjectModalOpen(false);
            quickCreateChat(id);
          }}
          onRemoveProject={handleDeleteProject}
        />
      </Panel>
      </Portal>

      {/* 底部按钮 */}
      <div style={{
        padding: "12px",
        paddingBottom: activeProjectId == null ? "32px" : "12px",
        borderTop: "1px solid var(--border-primary)",
        transition: "padding-bottom 0.2s ease",
      }}>
        {onSettingsClick && (
          <button
            onClick={onSettingsClick}
            className="sb-btn"
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 10px",
              borderRadius: "var(--radius-md)",
              fontSize: "13px",
              color: "var(--text-level-3)",
            }}
          >
            <Settings style={{ width: "16px", height: "16px" }} />
            <span>{t("sidebar.settings")}</span>
          </button>
        )}
      </div>

      {/* 待办浮层：fixed 定位脱离父容器裁剪，TodoPanel forceExpanded 强制展开 */}
      {todoPopupOpen && (
        <>
          <div
            style={{ position: "fixed", inset: 0, zIndex: 40 }}
            onClick={() => setTodoPopupOpen(false)}
          />
          <div style={{
            position: "fixed",
            top: "50px",
            left: "calc(var(--sidebar-width, 260px) + 8px)",
            width: "280px",
            maxHeight: "400px",
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-primary)",
            borderRadius: "var(--radius-lg)",
            boxShadow: "0 8px 24px rgba(0,0,0,0.15)",
            zIndex: 50,
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
          }}>
            <div style={{ flex: 1, overflowY: "auto", padding: "4px 8px 8px" }}>
              <TodoPanel forceExpanded={true} />
            </div>
          </div>
        </>
      )}

      {/* 项目向导弹窗：Portal 挂 body */}
      <Portal>
      <ProjectInitModal
        project={initProject}
        onClose={() => setInitProject(null)}
        onCreated={() => {
          window.dispatchEvent(new Event("mfk-projects-changed"));
        }}
      />

      <ProjectInitModal
        project={quickCreateProject}
        onClose={() => setQuickCreateProject(null)}
        onCreated={() => {
          window.dispatchEvent(new Event("mfk-projects-changed"));
        }}
      />
      </Portal>

      {/* 底部提示条：绝对定位，不影响主布局，不缩放 */}
      </div>
      {activeProjectId == null && (
        <div style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          padding: "4px 12px",
          fontSize: "10px",
          lineHeight: 1.4,
          color: "var(--text-level-4)",
          background: "var(--bg-level-1)",
          borderTop: "1px solid var(--border-primary)",
          zIndex: 1,
          whiteSpace: "pre-line",
        }}>
          {t("chat.noProjectHint")}
        </div>
      )}
    </aside>
  );
}



