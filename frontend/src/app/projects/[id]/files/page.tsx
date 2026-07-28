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

export default function ProjectFilesPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = Number(params.id);

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
    <div style={{
      display: "flex",
      height: "100vh",
      background: "var(--bg-level-2)",
    }}>
      {/* 左侧 Sidebar */}
      <aside style={{
        width: "280px",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        borderRight: "1px solid var(--border-primary)",
        background: "var(--bg-level-1)",
      }}>
        {/* 返回按钮 */}
        <div style={{ padding: "16px" }}>
          <button
            onClick={() => router.back()}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 16px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "var(--bg-level-3)",
              cursor: "pointer",
              fontSize: "14px",
              width: "100%",
            }}
          >
            <ArrowLeft style={{ width: "16px", height: "16px" }} />
            <span>返回</span>
          </button>
        </div>

        {/* 项目信息 */}
        <div style={{ padding: "0 16px" }}>
          <div style={{
            padding: "12px",
            borderRadius: "var(--radius-md)",
            background: "var(--color-primary-lighter)",
          }}>
            <p style={{
              fontSize: "12px",
              fontWeight: "500",
              color: "var(--color-primary)",
              margin: 0,
            }}>Project</p>
            <p style={{
              fontSize: "14px",
              fontWeight: "500",
              margin: "4px 0 0 0",
            }}>{currentProject?.name || "Loading..."}</p>
            {currentProject && (
              <p style={{
                fontSize: "12px",
                color: "var(--text-level-4)",
                margin: "4px 0 0 0",
                wordBreak: "break-all",
              }}>{currentProject.path}</p>
            )}
          </div>
        </div>
      </aside>

      {/* 右侧内容区 */}
      <main style={{
        flex: 1,
        overflowY: "auto",
        padding: "24px 32px",
      }}>
        <h1 style={{
          fontSize: "24px",
          fontWeight: "600",
          color: "var(--text-level-1)",
          margin: "0 0 24px 0",
        }}>文件浏览</h1>

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
            <span>根目录</span>
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
          <p style={{ color: "var(--text-level-3)" }}>加载中...</p>
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
            <p style={{ fontSize: "14px", color: "var(--text-level-3)", margin: 0 }}>空目录</p>
            <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: "4px 0 0 0" }}>此目录下没有文件</p>
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
      </main>
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}
