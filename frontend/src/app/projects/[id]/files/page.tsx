"use client";

import { useState } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  ArrowLeft,
  Folder,
  File,
  ChevronRight,
  Home,
} from "lucide-react";
import { useProjects } from "@/hooks/useProjects";
import { useProjectFiles, FileEntry } from "@/hooks/useProjectFiles";
import { useTranslation } from "@/hooks/useTranslation";

export default function ProjectFilesPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = Number(params.id);
  const { t } = useTranslation();

  const { projects } = useProjects();
  const currentProject = projects.find((p) => p.id === projectId);

  const [currentPath, setCurrentPath] = useState("");
  const { files, loading, error } = useProjectFiles(projectId, currentPath);

  const pathParts = currentPath ? currentPath.split("/").filter(Boolean) : [];

  const handleFileClick = (file: FileEntry) => {
    if (file.is_dir) {
      setCurrentPath(file.path);
    }
  };

  const handleBreadcrumbClick = (index: number) => {
    if (index === -1) {
      setCurrentPath("");
    } else {
      const newPath = pathParts.slice(0, index + 1).join("/");
      setCurrentPath(newPath);
    }
  };

  return (
    <>
      {/* 顶部栏 */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "16px",
        padding: "16px 24px",
        borderBottom: "1px solid var(--border-primary)",
        background: "var(--bg-level-1)",
        flexShrink: 0,
      }}>
        <button
          onClick={() => router.back()}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "6px 12px",
            borderRadius: "var(--radius-md)",
            border: "none",
            background: "var(--bg-level-3)",
            cursor: "pointer",
            fontSize: "13px",
          }}
        >
          <ArrowLeft style={{ width: "14px", height: "14px" }} />
          <span>{t("common.back")}</span>
        </button>

        {/* 项目信息 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}>
          <span style={{
            fontSize: "12px",
            fontWeight: "500",
            color: "var(--color-primary)",
            padding: "2px 8px",
            borderRadius: "var(--radius-full)",
            background: "var(--color-primary-lighter)",
          }}>{t("project.title")}</span>
          <span style={{
            fontSize: "14px",
            fontWeight: "500",
            color: "var(--text-level-1)",
          }}>{currentProject?.name || "Loading..."}</span>
        </div>
      </div>

      {/* 内容区 */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: "24px 32px",
      }}>
        <h1 style={{
          fontSize: "24px",
          fontWeight: "600",
          color: "var(--text-level-1)",
          margin: "0 0 24px 0",
        }}>{t("projects.fileBrowser")}</h1>

        {/* 面包屑导航 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          marginBottom: "16px",
          fontSize: "14px",
          color: "var(--text-level-3)",
        }}>
          <button
            onClick={() => handleBreadcrumbClick(-1)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              padding: "4px 8px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "14px",
              color: currentPath ? "var(--color-primary)" : "var(--text-level-2)",
            }}
          >
            <Home style={{ width: "14px", height: "14px" }} />
            <span>{t("projects.rootDirectory")}</span>
          </button>
          {pathParts.map((part, index) => (
            <div key={index} style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <ChevronRight style={{ width: "14px", height: "14px" }} />
              <button
                onClick={() => handleBreadcrumbClick(index)}
                style={{
                  padding: "4px 8px",
                  borderRadius: "var(--radius-sm)",
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  fontSize: "14px",
                  color: index === pathParts.length - 1 ? "var(--text-level-2)" : "var(--color-primary)",
                }}
              >
                {part}
              </button>
            </div>
          ))}
        </div>

        {/* 文件列表 */}
        {loading ? (
          <p style={{ color: "var(--text-level-3)" }}>{t("common.loading")}</p>
        ) : error ? (
          <p style={{ color: "var(--color-error)" }}>{error}</p>
        ) : files.length === 0 ? (
          <div style={{
            padding: "48px",
            textAlign: "center",
            borderRadius: "var(--radius-lg)",
            background: "var(--bg-level-1)",
          }}>
            <Folder style={{ width: "48px", height: "48px", color: "var(--text-level-4)", marginBottom: "16px" }} />
            <p style={{ fontSize: "14px", color: "var(--text-level-3)", margin: 0 }}>{t("projects.emptyDirectory")}</p>
            <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: "4px 0 0 0" }}>{t("projects.emptyDirectoryDesc")}</p>
          </div>
        ) : (
          <div style={{
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--border-primary)",
            overflow: "hidden",
          }}>
            {files.map((file, index) => (
              <div
                key={file.path}
                onClick={() => handleFileClick(file)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "12px 16px",
                  background: "var(--bg-level-2)",
                  borderBottom: index < files.length - 1 ? "1px solid var(--border-secondary)" : "none",
                  cursor: file.is_dir ? "pointer" : "default",
                }}
              >
                {file.is_dir ? (
                  <Folder style={{ width: "18px", height: "18px", color: "var(--color-primary)", flexShrink: 0 }} />
                ) : (
                  <File style={{ width: "18px", height: "18px", color: "var(--text-level-3)", flexShrink: 0 }} />
                )}
                <div style={{ flex: 1 }}>
                  <p style={{
                    fontSize: "14px",
                    color: "var(--text-level-2)",
                    margin: 0,
                  }}>{file.name}</p>
                  <p style={{
                    fontSize: "12px",
                    color: "var(--text-level-4)",
                    margin: "2px 0 0 0",
                  }}>{file.path}</p>
                </div>
                {!file.is_dir && (
                  <span style={{
                    fontSize: "12px",
                    color: "var(--text-level-4)",
                  }}>{formatSize(file.size)}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function formatSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}
