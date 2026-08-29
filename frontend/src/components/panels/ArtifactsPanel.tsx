"use client";

import { useEffect, useMemo, useState } from "react";
import { Package, FileText, Image as ImageIcon } from "lucide-react";
import { useArtifactStore } from "@/lib/artifactStore";
import { useProjects } from "@/hooks/useProjects";
import { useFileContent } from "@/hooks/useFileContent";
import { useTranslation } from "@/hooks/useTranslation";
import { getCurrentApiBase, withTokenParam, deviceAuthHeaders } from "@/lib/api";

/** 图片扩展名：走附件端点（base64）预览 */
const IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"];
/** 文档扩展名：暂不支持内联预览 */
const DOC_EXTS = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"];

function extOf(path: string): string {
  const idx = path.lastIndexOf(".");
  return idx >= 0 ? path.slice(idx).toLowerCase() : "";
}

interface AttachmentData {
  content_base64: string;
  mime: string;
}

/**
 * 产出物内容区（浏览器式右侧面板的"产出物"标签内容）。
 * - 无自身外壳/宽度/全屏：外壳与标签栏由 DockPanel 承载
 * - 文本/代码：走 /api/projects/{id}/file（文件内容端点）
 * - 图片：走 /api/projects/{id}/attachment（base64 附件端点）
 */
export function ArtifactsPanel() {
  const { t } = useTranslation();
  const artifacts = useArtifactStore((s) => s.artifacts);
  const selectedPath = useArtifactStore((s) => s.selectedPath);
  const select = useArtifactStore((s) => s.select);

  const { projects } = useProjects(1, 100);

  const selected = useMemo(
    () => artifacts.find((a) => a.path === selectedPath) ?? null,
    [artifacts, selectedPath]
  );

  // 通过 projectPath 反查 projectId（文件/附件 API 需要）
  const projectId = useMemo(() => {
    if (!selected?.projectPath) return null;
    return projects.find((p) => p.path === selected.projectPath)?.id ?? null;
  }, [selected, projects]);

  const ext = selected ? extOf(selected.path) : "";
  const isImage = IMAGE_EXTS.includes(ext);
  const isDoc = DOC_EXTS.includes(ext);

  // 文本/代码：文件内容端点
  const { fileContent, loading, error } = useFileContent(
    !isImage ? projectId : null,
    !isImage ? selected?.path ?? "" : ""
  );

  // 图片：附件端点（base64 → data URI）
  const [img, setImg] = useState<{ src: string; mime: string } | null>(null);
  const [imgLoading, setImgLoading] = useState(false);
  const [imgError, setImgError] = useState<string | null>(null);
  useEffect(() => {
    setImg(null);
    setImgError(null);
    if (!selected || !isImage || !projectId) return;
    let cancelled = false;
    setImgLoading(true);
    const params = new URLSearchParams({ path: selected.path });
    fetch(withTokenParam(`${getCurrentApiBase()}/api/projects/${projectId}/attachment?${params}`), {
      headers: deviceAuthHeaders(),
    })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = (await r.json()) as AttachmentData;
        if (!cancelled) {
          setImg({ src: `data:${data.mime};base64,${data.content_base64}`, mime: data.mime });
          setImgLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setImgError(e instanceof Error ? e.message : "Unknown error");
          setImgLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [selected, isImage, projectId]);

  const needsProject = !selected?.projectPath || !projectId;

  const renderBody = () => {
    if (artifacts.length === 0) {
      return (
        <div style={centerStyle}>
          <Package style={{ width: "20px", height: "20px", color: "var(--text-level-4)", marginBottom: 8 }} />
          <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>{t("artifact.empty")}</span>
        </div>
      );
    }
    if (!selected) {
      return (
        <div style={centerStyle}>
          <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>{t("artifact.selectHint")}</span>
        </div>
      );
    }
    if (needsProject) {
      return (
        <div style={centerStyle}>
          <FolderOpenIcon />
          <span style={{ fontSize: "12px", color: "var(--text-level-3)", marginTop: 8 }}>
            {t("artifact.needProject")}
          </span>
        </div>
      );
    }
    if (isImage) {
      if (imgLoading) {
        return (
          <div style={centerStyle}>
            <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>{t("common.loading")}</span>
          </div>
        );
      }
      if (imgError || !img) {
        return (
          <div style={centerStyle}>
            <span style={{ fontSize: "12px", color: "var(--color-error)" }}>
              {imgError ?? t("artifact.loadFailed")}
            </span>
          </div>
        );
      }
      return (
        <div style={{ flex: 1, overflow: "auto", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: 12 }}>
          <img
            src={img.src}
            alt={selected.fileName}
            style={{ maxWidth: "100%", borderRadius: "var(--radius-md)" }}
          />
        </div>
      );
    }
    if (isDoc) {
      return (
        <div style={centerStyle}>
          <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>{t("artifact.unsupported")}</span>
        </div>
      );
    }
    if (loading) {
      return (
        <div style={centerStyle}>
          <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>{t("common.loading")}</span>
        </div>
      );
    }
    if (error) {
      return (
        <div style={centerStyle}>
          <span style={{ fontSize: "12px", color: "var(--color-error)" }}>{error}</span>
        </div>
      );
    }
    if (fileContent) {
      return (
        <pre style={{
          flex: 1,
          margin: 0,
          overflow: "auto",
          padding: "10px 12px",
          fontSize: "12px",
          lineHeight: "1.6",
          fontFamily: "var(--font-geist-mono), var(--font-family)",
          color: "var(--text-level-2)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-all",
        }}>
          {fileContent.content}
        </pre>
      );
    }
    return null;
  };

  return (
    <>
      {/* 产出物切换 tab（横向滚动） */}
      {artifacts.length > 0 && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          padding: "4px 8px",
          borderBottom: "1px solid var(--border-primary)",
          overflowX: "auto",
          flexShrink: 0,
          scrollbarWidth: "thin",
        }}>
          {artifacts.map((a) => {
            const active = a.path === selectedPath;
            return (
              <button
                key={a.path}
                onClick={() => select(a.path)}
                title={a.path}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                  maxWidth: "160px",
                  padding: "2px 8px",
                  borderRadius: "var(--radius-sm)",
                  border: active ? "1px solid var(--color-primary)" : "1px solid transparent",
                  background: active ? "var(--color-primary-lighter)" : "transparent",
                  cursor: "pointer",
                  fontSize: "11px",
                  color: active ? "var(--color-primary)" : "var(--text-level-3)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  outline: "none",
                  flexShrink: 0,
                }}
              >
                {IMAGE_EXTS.includes(extOf(a.path)) ? (
                  <ImageIcon style={{ width: "11px", height: "11px", flexShrink: 0 }} />
                ) : (
                  <FileText style={{ width: "11px", height: "11px", flexShrink: 0 }} />
                )}
                <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{a.fileName}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* 内容区 */}
      {renderBody()}
    </>
  );
}

function FolderOpenIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--text-level-4)" }}>
      <path d="M4 6a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" />
    </svg>
  );
}

const centerStyle: React.CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  padding: "12px",
};
