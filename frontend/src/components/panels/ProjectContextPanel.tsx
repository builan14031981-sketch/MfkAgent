"use client";
/* eslint-disable react-hooks/set-state-in-effect */

import { useState, useEffect, useRef } from "react";
import { X, Folder, FileText, CheckSquare, FolderUp } from "lucide-react";
import { apiGet } from "@/lib/api";
import { useTranslation } from "@/hooks/useTranslation";
import type { Project } from "@/hooks/useProjects";

export interface ProjectFileEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
}

interface ProjectContextPanelProps {
  isOpen: boolean;
  onClose: () => void;
  project: Project | null;
  selectedFiles: string[];
  onToggleFile: (path: string) => void;
  onClearFiles: () => void;
}

export function ProjectContextPanel({
  isOpen,
  onClose,
  project,
  selectedFiles,
  onToggleFile,
  onClearFiles,
}: ProjectContextPanelProps) {
  const { t } = useTranslation();
  const [files, setFiles] = useState<ProjectFileEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [subpath, setSubpath] = useState("");
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Esc 键关闭：与 Panel.tsx / QuoteMenu / ThemeSwitcher 行为对齐
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  // 点击外部关闭：延迟 100ms 注册，避免"打开当次 click 立即触发关闭"
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    if (isOpen) {
      const timer = setTimeout(() => document.addEventListener("mousedown", handleClickOutside), 100);
      return () => {
        clearTimeout(timer);
        document.removeEventListener("mousedown", handleClickOutside);
      };
    }
  }, [isOpen, onClose]);

  async function fetchFiles(dir: string) {
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (dir) params.append("subpath", dir);
      const data = await apiGet<ProjectFileEntry[]>(`/api/projects/${project!.id}/files?${params}`);
      setFiles(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!isOpen || !project) return;
    fetchFiles(subpath);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, project, subpath]);

  const handleEnterDir = (dirPath: string) => {
    setSubpath(dirPath);
  };

  const handleGoUp = () => {
    if (!subpath) return;
    const parts = subpath.split("/");
    parts.pop();
    setSubpath(parts.join("/"));
  };

  if (!isOpen || !project) return null;

  const isRoot = subpath === "";

  return (
    <div
      ref={panelRef}
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        width: "400px",
        height: "100vh",
        background: "var(--bg-level-1)",
        borderLeft: "1px solid var(--border-primary)",
        boxShadow: "var(--shadow-lg)",
        zIndex: 1000,
        display: "flex",
        flexDirection: "column",
        animation: "slideIn 0.2s ease",
      }}
    >
      <style jsx>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>

      {/* Header */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "16px 20px",
        borderBottom: "1px solid var(--border-primary)",
      }}>
        <h3 style={{ fontSize: "16px", fontWeight: "600", margin: 0 }}>
          {t("chat.projectContext")}
        </h3>
        <button
          onClick={onClose}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "32px",
            height: "32px",
            borderRadius: "var(--radius-md)",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            color: "var(--text-level-3)",
            transition: "all 0.6s ease",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
        >
          <X style={{ width: "18px", height: "18px" }} />
        </button>
      </div>

      {/* Project Info */}
      <div style={{
        padding: "16px 20px",
        borderBottom: "1px solid var(--border-secondary)",
      }}>
        <p style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: "0 0 4px 0" }}>
          {project.name}
        </p>
        <p style={{
          fontSize: "12px",
          color: "var(--text-level-3)",
          margin: 0,
          fontFamily: "monospace",
          wordBreak: "break-all",
        }}>
          {project.path}
        </p>
      </div>

      {/* Breadcrumb / Nav */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "10px 20px",
        borderBottom: "1px solid var(--border-secondary)",
      }}>
        {!isRoot && (
          <button
            onClick={handleGoUp}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              padding: "4px 8px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "var(--bg-level-2)",
              cursor: "pointer",
              fontSize: "12px",
              color: "var(--text-level-2)",
            }}
          >
            <FolderUp style={{ width: "14px", height: "14px" }} />
            {t("projects.rootDirectory")}
          </button>
        )}
        <span style={{
          fontSize: "12px",
          color: "var(--text-level-3)",
          fontFamily: "monospace",
          flex: 1,
          textAlign: "right",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}>
          {subpath || "/"}
        </span>
      </div>

      {/* File List */}
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 8px" }}>
        {loading ? (
          <p style={{ textAlign: "center", color: "var(--text-level-3)", fontSize: "13px", padding: "24px 0" }}>
            {t("common.loading")}
          </p>
        ) : error ? (
          <p style={{ textAlign: "center", color: "var(--color-error)", fontSize: "13px", padding: "24px 0" }}>
            {error}
          </p>
        ) : files.length === 0 ? (
          <div style={{ textAlign: "center", padding: "24px 0" }}>
            <p style={{ fontSize: "13px", color: "var(--text-level-3)", margin: "0 0 4px 0" }}>
              {t("projects.emptyDirectory")}
            </p>
            <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: 0 }}>
              {t("projects.emptyDirectoryDesc")}
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {files.map((file) =>
              file.is_dir ? (
                <button
                  key={file.path}
                  onClick={() => handleEnterDir(file.path)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "8px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    textAlign: "left",
                    fontSize: "13px",
                    color: "var(--text-level-2)",
                    transition: "all 0.6s ease",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                >
                  <Folder style={{ width: "16px", height: "16px", color: "var(--text-level-4)", flexShrink: 0 }} />
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {file.name}
                  </span>
                </button>
              ) : (
                <button
                  key={file.path}
                  onClick={() => onToggleFile(file.path)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "8px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "none",
                    background: selectedFiles.includes(file.path) ? "var(--bg-level-3)" : "transparent",
                    cursor: "pointer",
                    textAlign: "left",
                    fontSize: "13px",
                    color: "var(--text-level-2)",
                    transition: "all 0.6s ease",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = selectedFiles.includes(file.path) ? "var(--bg-level-3)" : "transparent";
                  }}
                >
                  {selectedFiles.includes(file.path) ? (
                    <CheckSquare style={{ width: "16px", height: "16px", color: "var(--color-primary)", flexShrink: 0 }} />
                  ) : (
                    <FileText style={{ width: "16px", height: "16px", color: "var(--text-level-4)", flexShrink: 0 }} />
                  )}
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {file.name}
                  </span>
                  <span style={{ fontSize: "11px", color: "var(--text-level-4)", flexShrink: 0 }}>
                    {file.size > 0 ? `${(file.size / 1024).toFixed(1)}KB` : ""}
                  </span>
                </button>
              )
            )}
          </div>
        )}
      </div>

      {/* Selected Files Footer */}
      <div style={{
        padding: "16px 20px",
        borderTop: "1px solid var(--border-primary)",
        background: "var(--bg-level-2)",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
          <span style={{ fontSize: "12px", fontWeight: "500", color: "var(--text-level-3)" }}>
            {t("chat.selectedFiles")} ({selectedFiles.length})
          </span>
          {selectedFiles.length > 0 && (
            <button
              onClick={onClearFiles}
              style={{
                fontSize: "12px",
                color: "var(--color-primary)",
                border: "none",
                background: "transparent",
                cursor: "pointer",
                padding: 0,
              }}
            >
              {t("common.clear")}
            </button>
          )}
        </div>
        {selectedFiles.length === 0 ? (
          <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: 0 }}>
            {t("chat.noFilesSelected")}
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "4px", maxHeight: "160px", overflowY: "auto" }}>
            {selectedFiles.map((path) => (
              <div key={path} style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "6px 10px",
                borderRadius: "var(--radius-sm)",
                background: "var(--bg-level-1)",
              }}>
                <FileText style={{ width: "12px", height: "12px", color: "var(--color-primary)", flexShrink: 0 }} />
                <span style={{
                  fontSize: "12px",
                  color: "var(--text-level-2)",
                  fontFamily: "monospace",
                  flex: 1,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}>
                  {path}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
