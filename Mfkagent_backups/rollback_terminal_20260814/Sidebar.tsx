"use client";

import { useState, useMemo, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  Settings,
  FolderPlus,
  ChevronRight,
  MessageSquare,
  FolderOpen,
  PanelLeftClose,
} from "lucide-react";
import { useChat, Chat } from "@/hooks/useChat";
import { useProjects } from "@/hooks/useProjects";
import type { Project } from "@/hooks/useProjects";
import { useAgents } from "@/hooks/useAgents";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";
import { useStreamStore } from "@/lib/streamStore";
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

export function Sidebar({ currentChatId, onSettingsClick, collapsed, onToggleSidebar }: SidebarProps) {
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

  const handleDeleteChat = async (id: number) => {
    try {
      await deleteChat(id);
      if (currentChatId === id) {
        router.push("/");
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
      {/* 新建任务 */}
      <div style={{ padding: "12px 12px 4px", display: "flex", alignItems: "center", gap: "6px" }}>
        <button
          ref={newTaskBtnRef}
          onClick={() => router.push("/")}
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "6px 10px",
            borderRadius: "var(--radius-md)",
            border: "none",
            outline: "none",
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
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "28px",
              height: "28px",
              padding: 0,
              border: "none",
              borderRadius: "var(--radius-sm)",
              background: "transparent",
              cursor: "pointer",
              color: "var(--text-level-4)",
              flexShrink: 0,
              transition: "background 0.15s ease, color 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
              e.currentTarget.style.color = "var(--text-level-2)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--text-level-4)";
            }}
            title="收起侧边栏"
          >
            <PanelLeftClose size={16} />
          </button>
        )}
      </div>

      {/* 待办面板（可折叠，位于 New Task 与 Projects 之间） */}
      <div style={{ padding: "0 4px" }}>
        <TodoPanel />
      </div>

      {/* 聊天列表 */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: "0 8px 12px",
      }}>
        {/* ===== 项目工作区 ===== */}
        <div style={{ marginBottom: "8px" }}>
          {/* section header：sticky 吸顶，列表在外层可滚容器内独立滚动（2026-08-11 父不动子滚原则） */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            position: "sticky",
            top: 0,
            zIndex: 1,
            background: "var(--bg-level-1)",
          }}>
            <button
              onClick={toggleProjectWorkspace}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                flex: 1,
                minWidth: 0,
                padding: "2px 4px",
                border: "none",
                background: "transparent",
                cursor: "pointer",
                outline: "none",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
            >
              <ChevronRight style={{
                width: "var(--sidebar-icon-size-sm)",
                height: "var(--sidebar-icon-size-sm)",
                color: "var(--text-level-4)",
                flexShrink: 0,
                transform: collapsedProjectWorkspace ? "rotate(0deg)" : "rotate(90deg)",
                transition: "transform var(--transition-fast)",
              }} />
              <FolderOpen style={{ width: "var(--sidebar-icon-size-sm)", height: "var(--sidebar-icon-size-sm)", color: "var(--text-level-4)", flexShrink: 0 }} />
              <p style={{
                fontSize: "11px",
                fontWeight: "600",
                color: "var(--text-level-4)",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                margin: 0,
                whiteSpace: "nowrap",
              }}>{t("sidebar.projectWorkspace")}</p>
            </button>
            <button
              onClick={() => setProjectModalOpen(true)}
              title={t("sidebar.openProject")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "20px",
                height: "20px",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: "transparent",
                cursor: "pointer",
                color: "var(--text-level-3)",
                flexShrink: 0,
                padding: 0,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; e.currentTarget.style.color = "var(--color-primary)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-level-3)"; }}
            >
              <FolderPlus style={{ width: "12px", height: "12px" }} />
            </button>
          </div>

          <div
            ref={projectWorkspaceRef}
            style={{
              overflow: "hidden",
              maxHeight: "2000px",
              opacity: 1,
              transition: "max-height var(--transition-normal), opacity var(--transition-normal)",
            }}
          >
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
        </div>

        {/* ===== 通用对话 ===== */}
        <div>
          {/* section header：sticky 吸顶于自己 section 顶部（父带子原则，2026-08-12）。
              旧设计 top:28 硬编码了与兄弟标题（项目工作区）的叠放关系，但项目标题随自己 section 滚走后会被释放，
              导致本标题孤悬在 28px 处头顶留白（用户报「悬浮」）。兄弟不互相定位，各自只管自己的孩子 → top:0 */}
          <button
            onClick={toggleGeneralChats}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              width: "100%",
              padding: "2px 4px",
              border: "none",
              background: "var(--bg-level-1)",
              cursor: "pointer",
              outline: "none",
              position: "sticky",
              top: 0,
              zIndex: 1,
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "var(--bg-level-1)"; }}
          >
            <ChevronRight style={{
              width: "var(--sidebar-icon-size-sm)",
              height: "var(--sidebar-icon-size-sm)",
              color: "var(--text-level-4)",
              flexShrink: 0,
              transform: collapsedGeneralChats ? "rotate(0deg)" : "rotate(90deg)",
              transition: "transform var(--transition-fast)",
            }} />
            <MessageSquare style={{ width: "var(--sidebar-icon-size-sm)", height: "var(--sidebar-icon-size-sm)", color: "var(--text-level-4)", flexShrink: 0 }} />
            <p style={{
              fontSize: "11px",
              fontWeight: "600",
              color: "var(--text-level-4)",
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              margin: 0,
              whiteSpace: "nowrap",
            }}>{t("sidebar.generalChats")}</p>
          </button>

          <div
            ref={generalChatsListRef}
            style={{
              overflow: "hidden",
              maxHeight: "2000px",
              opacity: 1,
              transition: "max-height var(--transition-normal), opacity var(--transition-normal)",
            }}
          >
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
              generalChats.map(renderGeneralChatRow)
            )}
          </div>
        </div>
      </div>

      {/* 右键 / 更多菜单 */}
      <SidebarContextMenu
        state={contextMenu}
        chats={chats}
        projects={projects}
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

      {/* 打开/新建项目工作区 面板 */}
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
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 10px",
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

      {/* 项目初始化向导弹窗 */}
      <ProjectInitModal
        project={initProject}
        onClose={() => setInitProject(null)}
        onCreated={() => {
          window.dispatchEvent(new Event("mfk-projects-changed"));
        }}
      />

      {/* 项目内快速新建会话：复用 ProjectInitModal */}
      <ProjectInitModal
        project={quickCreateProject}
        onClose={() => setQuickCreateProject(null)}
        onCreated={() => {
          window.dispatchEvent(new Event("mfk-projects-changed"));
        }}
      />

      {/* 底部提示条：绝对定位，不影响主布局 */}
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
