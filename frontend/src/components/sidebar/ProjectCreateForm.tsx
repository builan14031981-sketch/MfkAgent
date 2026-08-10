"use client";

import { Folder, FolderSearch } from "lucide-react";
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
}: ProjectCreateFormProps) {
  const { t } = useTranslation();

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
        ) : projects.map((project) => (
          <button
            key={project.id}
            onClick={() => onOpenProjectWorkspace(project.id)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              padding: "8px 10px",
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
