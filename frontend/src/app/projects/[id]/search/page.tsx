"use client";

import { useState } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  ArrowLeft,
  Search,
  Folder,
  File,
} from "lucide-react";
import { useProjects } from "@/hooks/useProjects";
import { useFileSearch } from "@/hooks/useFileSearch";

export default function FileSearchPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = Number(params.id);

  const { projects } = useProjects();
  const currentProject = projects.find((p) => p.id === projectId);

  const [query, setQuery] = useState("");
  const { results, loading, error } = useFileSearch(projectId, query);

  const handleFileClick = (path: string, isDir: boolean) => {
    if (isDir) {
      router.push(`/projects/${projectId}/files?subpath=${encodeURIComponent(path)}`);
    } else {
      router.push(`/projects/${projectId}/file?path=${encodeURIComponent(path)}`);
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
        }}>文件搜索</h1>

        {/* 搜索框 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          marginBottom: "24px",
        }}>
          <div style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "12px 16px",
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-1)",
          }}>
            <Search style={{ width: "18px", height: "18px", color: "var(--text-level-3)" }} />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索文件名..."
              style={{
                flex: 1,
                border: "none",
                outline: "none",
                background: "transparent",
                fontSize: "14px",
                color: "var(--text-level-2)",
              }}
            />
          </div>
        </div>

        {/* 搜索结果 */}
        {loading ? (
          <p style={{ color: "var(--text-level-3)" }}>搜索中...</p>
        ) : error ? (
          <p style={{ color: "var(--color-error)" }}>{error}</p>
        ) : !query.trim() ? (
          <div style={{
            padding: "48px",
            textAlign: "center",
            borderRadius: "var(--radius-lg)",
            background: "var(--bg-level-1)",
          }}>
            <Search style={{ width: "48px", height: "48px", color: "var(--text-level-4)", marginBottom: "16px" }} />
            <p style={{ fontSize: "14px", color: "var(--text-level-3)", margin: 0 }}>输入关键词搜索文件</p>
          </div>
        ) : results.length === 0 ? (
          <div style={{
            padding: "48px",
            textAlign: "center",
            borderRadius: "var(--radius-lg)",
            background: "var(--bg-level-1)",
          }}>
            <Search style={{ width: "48px", height: "48px", color: "var(--text-level-4)", marginBottom: "16px" }} />
            <p style={{ fontSize: "14px", color: "var(--text-level-3)", margin: 0 }}>未找到匹配的文件</p>
            <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: "4px 0 0 0" }}>尝试其他关键词</p>
          </div>
        ) : (
          <div style={{
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--border-primary)",
            overflow: "hidden",
          }}>
            {results.map((file, index) => (
              <div
                key={file.path}
                onClick={() => handleFileClick(file.path, file.is_dir)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "12px 16px",
                  background: "var(--bg-level-2)",
                  borderBottom: index < results.length - 1 ? "1px solid var(--border-secondary)" : "none",
                  cursor: "pointer",
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
