"use client";

import { useState } from "react";
import { Folder, FolderOpen, FolderSearch, Trash2 } from "lucide-react";
import type { Project } from "@/hooks/useProjects";
import { useTranslation } from "@/hooks/useTranslation";

interface ProjectCreateFormProps {
  projects: Project[];
  newProjectName: string;
  newProjectPath: string;
  isCreatingProject: boolean;
  onNameChange: (value: string) => void;
  onPathChange: (value: string) => void;
  onCreateProject: () => void;
  onPickDirectory: () => void;
  onOpenProjectWorkspace: (projectId: number) => void;
  // 2026-08-11：行主点击 = 在该项目新开会话；移除关联 = 软删进回收站（不碰本地文件夹）
  onQuickCreateChat: (projectId: number) => void;
  onRemoveProject: (projectId: number) => void;
}

/** 打开/新建项目工作区面板内容：已有项目列表 + 新建项目表单 */
export function ProjectCreateForm({
  projects,
  newProjectName,
  newProjectPath,
  isCreatingProject,
  onNameChange,
  onPathChange,
  onCreateProject,
  onPickDirectory,
  onOpenProjectWorkspace,
  onQuickCreateChat,
  onRemoveProject,
}: ProjectCreateFormProps) {
  const { t } = useTranslation();
  // 行 hover 态 + 移除两步确认态（确认中即使鼠标离开也保持可见）
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const [confirmRemoveId, setConfirmRemoveId] = useState<number | null>(null);

  return (
    <>
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
        ) : projects.map((project) => {
          const hovered = hoveredId === project.id;
          const confirming = confirmRemoveId === project.id;
          return (
          <div
            key={project.id}
            role="button"
            onClick={() => onQuickCreateChat(project.id)}
            title="在该项目中新开会话"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              padding: "8px 10px",
              borderRadius: "var(--radius-md)",
              border: `1px solid ${hovered ? "var(--color-primary)" : "var(--border-primary)"}`,
              background: hovered ? "var(--color-primary-light)" : "var(--bg-level-2)",
              cursor: "pointer",
              textAlign: "left",
              transition: "border-color 0.15s, background 0.15s",
            }}
            onMouseEnter={() => setHoveredId(project.id)}
            onMouseLeave={() => setHoveredId((h) => (h === project.id ? null : h))}
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
            {/* hover 操作组：打开文件工作区 / 移除关联（hover 或确认中可见） */}
            <span style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              flexShrink: 0,
              opacity: hovered || confirming ? 1 : 0,
              pointerEvents: hovered || confirming ? "auto" : "none",
              transition: "opacity 0.15s",
            }}>
              <span
                title="打开文件工作区"
                onClick={(e) => { e.stopPropagation(); onOpenProjectWorkspace(project.id); }}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "center",
                  width: "22px", height: "22px", borderRadius: "var(--radius-sm)",
                  color: "var(--text-level-3)", cursor: "pointer",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; e.currentTarget.style.color = "var(--text-level-1)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-level-3)"; }}
              >
                <FolderOpen style={{ width: "13px", height: "13px" }} />
              </span>
              {confirming ? (
                <span
                  title="再点一次确认移除"
                  onClick={(e) => { e.stopPropagation(); setConfirmRemoveId(null); onRemoveProject(project.id); }}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "center",
                    height: "22px", padding: "0 6px", borderRadius: "var(--radius-sm)",
                    background: "var(--color-error)", color: "#fff",
                    fontSize: "11px", cursor: "pointer",
                  }}
                >确认?</span>
              ) : (
                <span
                  title="移除关联（会话进回收站，本地文件夹不受影响）"
                  onClick={(e) => {
                    e.stopPropagation();
                    setConfirmRemoveId(project.id);
                    // 2 秒未二次确认自动复位
                    window.setTimeout(() => {
                      setConfirmRemoveId((c) => (c === project.id ? null : c));
                    }, 2000);
                  }}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "center",
                    width: "22px", height: "22px", borderRadius: "var(--radius-sm)",
                    color: "var(--text-level-3)", cursor: "pointer",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; e.currentTarget.style.color = "var(--color-error)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-level-3)"; }}
                >
                  <Trash2 style={{ width: "13px", height: "13px" }} />
                </span>
              )}
            </span>
          </div>
          );
        })}
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
          onClick={onPickDirectory}
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
          onChange={(e) => onNameChange(e.target.value)}
          placeholder={t("sidebar.projectName")}
          style={{
            padding: "6px 10px",
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
          onChange={(e) => onPathChange(e.target.value)}
          placeholder={t("sidebar.projectPath")}
          style={{
            padding: "6px 10px",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-2)",
            fontSize: "13px",
            fontFamily: "monospace",
            color: "var(--text-level-2)",
            outline: "none",
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") onCreateProject();
          }}
        />
        <button
          onClick={onCreateProject}
          disabled={!newProjectName.trim() || !newProjectPath.trim() || isCreatingProject}
          style={{
            padding: "6px 10px",
            borderRadius: "var(--radius-md)",
            border: "none",
            background: newProjectName.trim() && newProjectPath.trim() && !isCreatingProject ? "var(--color-primary)" : "var(--bg-level-3)",
            cursor: newProjectName.trim() && newProjectPath.trim() && !isCreatingProject ? "pointer" : "not-allowed",
            fontSize: "13px",
            fontWeight: "500",
            color: newProjectName.trim() && newProjectPath.trim() && !isCreatingProject ? "var(--text-on-primary)" : "var(--text-level-3)",
          }}
        >
          {t("sidebar.createProject")}
        </button>
      </div>
    </>
  );
}
