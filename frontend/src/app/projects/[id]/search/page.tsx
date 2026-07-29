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
import { useTranslation } from "@/hooks/useTranslation";

export default function FileSearchPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = Number(params.id);
  const { t } = useTranslation();

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
        }}>{t("projects.fileSearch")}</h1>

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
              placeholder={t("projects.searchPlaceholder")}
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
          <p style={{ color: "var(--text-level-3)" }}>{t("common.loading")}</p>
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
            <p style={{ fontSize: "14px", color: "var(--text-level-3)", margin: 0 }}>{t("projects.searchHint")}</p>
          </div>
        ) : results.length === 0 ? (
          <div style={{
            padding: "48px",
            textAlign: "center",
            borderRadius: "var(--radius-lg)",
            background: "var(--bg-level-1)",
          }}>
            <Search style={{ width: "48px", height: "48px", color: "var(--text-level-4)", marginBottom: "16px" }} />
            <p style={{ fontSize: "14px", color: "var(--text-level-3)", margin: 0 }}>{t("projects.noResults")}</p>
            <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: "4px 0 0 0" }}>{t("projects.noResultsDesc")}</p>
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
