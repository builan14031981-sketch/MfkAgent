"use client";

import { useRouter, useParams, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  File,
  Copy,
  Check,
} from "lucide-react";
import { useState } from "react";
import { useProjects } from "@/hooks/useProjects";
import { useFileContent } from "@/hooks/useFileContent";
import { useTranslation } from "@/hooks/useTranslation";

export default function FileContentPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = Number(params.id);
  const filePath = searchParams.get("path") || "";
  const { t } = useTranslation();

  const { projects } = useProjects();
  const currentProject = projects.find((p) => p.id === projectId);
  const { fileContent, loading, error } = useFileContent(projectId, filePath);

  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!fileContent) return;
    try {
      await navigator.clipboard.writeText(fileContent.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const fileName = filePath.split("/").pop() || filePath;

  return (
    <>
      {/* 顶部栏 */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "16px 24px",
        borderBottom: "1px solid var(--border-primary)",
        background: "var(--bg-level-1)",
        flexShrink: 0,
      }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "16px",
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

        {/* 项目和文件信息 */}
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
            <span style={{ color: "var(--text-level-4)" }}>/</span>
            <span style={{
              fontSize: "14px",
              color: "var(--text-level-2)",
            }}>{fileName}</span>
          </div>
        </div>

        <button
          onClick={handleCopy}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "8px 12px",
            borderRadius: "var(--radius-md)",
            border: "none",
            background: "var(--bg-level-3)",
            cursor: "pointer",
            fontSize: "13px",
            color: "var(--text-level-2)",
          }}
        >
              {copied ? (
              <>
                <Check style={{ width: "14px", height: "14px" }} />
                <span>{t("common.copied")}</span>
              </>
            ) : (
              <>
                <Copy style={{ width: "14px", height: "14px" }} />
                <span>{t("common.copy")}</span>
              </>
            )}
        </button>
      </div>

      {/* 文件内容 */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: "24px 32px",
      }}>
        {loading ? (
          <p style={{ color: "var(--text-level-3)" }}>{t("common.loading")}</p>
        ) : error ? (
          <p style={{ color: "var(--color-error)" }}>{error}</p>
        ) : fileContent ? (
          <pre style={{
            padding: "16px",
            borderRadius: "var(--radius-lg)",
            background: "var(--bg-level-1)",
            border: "1px solid var(--border-primary)",
            overflow: "auto",
            fontSize: "13px",
            lineHeight: "1.6",
            color: "var(--text-level-2)",
            fontFamily: "monospace",
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
          }}>
            {fileContent.content}
          </pre>
        ) : (
          <p style={{ color: "var(--text-level-3)" }}>{t("projects.selectFile")}</p>
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
