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

export default function FileContentPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const projectId = Number(params.id);
  const filePath = searchParams.get("path") || "";

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

        {/* 文件信息 */}
        <div style={{ padding: "16px" }}>
          <div style={{
            padding: "12px",
            borderRadius: "var(--radius-md)",
            background: "var(--bg-level-3)",
          }}>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              marginBottom: "8px",
            }}>
              <File style={{ width: "16px", height: "16px", color: "var(--text-level-3)" }} />
              <p style={{
                fontSize: "14px",
                fontWeight: "500",
                color: "var(--text-level-1)",
                margin: 0,
              }}>{fileName}</p>
            </div>
            {fileContent && (
              <>
                <p style={{
                  fontSize: "12px",
                  color: "var(--text-level-4)",
                  margin: "4px 0 0 0",
                }}>路径: {fileContent.path}</p>
                <p style={{
                  fontSize: "12px",
                  color: "var(--text-level-4)",
                  margin: "4px 0 0 0",
                }}>大小: {formatSize(fileContent.size)}</p>
                <p style={{
                  fontSize: "12px",
                  color: "var(--text-level-4)",
                  margin: "4px 0 0 0",
                }}>编码: {fileContent.encoding}</p>
              </>
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
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "16px",
        }}>
          <h1 style={{
            fontSize: "24px",
            fontWeight: "600",
            color: "var(--text-level-1)",
            margin: 0,
          }}>{fileName}</h1>
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
                <span>已复制</span>
              </>
            ) : (
              <>
                <Copy style={{ width: "14px", height: "14px" }} />
                <span>复制</span>
              </>
            )}
          </button>
        </div>

        {/* 文件内容 */}
        {loading ? (
          <p style={{ color: "var(--text-level-3)" }}>加载中...</p>
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
          <p style={{ color: "var(--text-level-3)" }}>请选择文件</p>
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
