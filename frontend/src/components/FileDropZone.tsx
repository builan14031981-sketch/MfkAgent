"use client";

import { useState, useEffect, useRef } from "react";
import {
  FileText,
  FileCode2,
  FileImage,
  FileArchive,
  X,
} from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";

export interface DroppedFile {
  name: string;
  path: string;
}

interface FileDropZoneProps {
  onFilesDrop: (files: DroppedFile[]) => void;
}

const CODE_EXTENSIONS = new Set([
  "js", "jsx", "ts", "tsx", "py", "json", "css", "scss", "html", "vue",
  "go", "rs", "java", "c", "cpp", "h", "sh", "yaml", "yml", "xml", "sql",
  "toml", "ini", "md",
]);

const IMAGE_EXTENSIONS = new Set([
  "png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "bmp",
]);

const ARCHIVE_EXTENSIONS = new Set([
  "zip", "rar", "7z", "tar", "gz", "bz2",
]);

function getFileIconElement(fileName: string, size: number) {
  const ext = fileName.split(".").pop()?.toLowerCase() ?? "";
  const iconStyle = {
    width: size,
    height: size,
    color: "var(--color-primary)",
    flexShrink: 0,
  };
  if (IMAGE_EXTENSIONS.has(ext)) return <FileImage style={iconStyle} />;
  if (ARCHIVE_EXTENSIONS.has(ext)) return <FileArchive style={iconStyle} />;
  if (CODE_EXTENSIONS.has(ext)) return <FileCode2 style={iconStyle} />;
  return <FileText style={iconStyle} />;
}

function getFileName(path: string) {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

/**
 * 全屏文件拖拽：文件进入 Chat 区域时渐现毛玻璃遮罩与虚线发光边框。
 * 松手后通过 onFilesDrop 回调把文件路径交给上层挂载为 Context。
 */
export function FileDropZone({ onFilesDrop }: FileDropZoneProps) {
  const { t } = useTranslation();
  const [isDragging, setIsDragging] = useState(false);
  const dragDepthRef = useRef(0);

  useEffect(() => {
    const hasFiles = (e: DragEvent) =>
      Array.from(e.dataTransfer?.types ?? []).includes("Files");

    const handleDragEnter = (e: DragEvent) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      dragDepthRef.current += 1;
      setIsDragging(true);
    };

    const handleDragOver = (e: DragEvent) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
    };

    const handleDragLeave = (e: DragEvent) => {
      if (!hasFiles(e)) return;
      dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
      if (dragDepthRef.current === 0) {
        setIsDragging(false);
      }
    };

    const handleDrop = (e: DragEvent) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      dragDepthRef.current = 0;
      setIsDragging(false);
      const files = Array.from(e.dataTransfer?.files ?? []);
      if (files.length === 0) return;
      const dropped: DroppedFile[] = files.map((file) => {
        const p = file as File & { path?: string };
        return { name: file.name, path: p.path || file.name };
      });
      onFilesDrop(dropped);
    };

    window.addEventListener("dragenter", handleDragEnter);
    window.addEventListener("dragover", handleDragOver);
    window.addEventListener("dragleave", handleDragLeave);
    window.addEventListener("drop", handleDrop);
    return () => {
      window.removeEventListener("dragenter", handleDragEnter);
      window.removeEventListener("dragover", handleDragOver);
      window.removeEventListener("dragleave", handleDragLeave);
      window.removeEventListener("drop", handleDrop);
    };
  }, [onFilesDrop]);

  if (!isDragging) return null;

  return (
    <div style={{
      position: "fixed",
      inset: 0,
      zIndex: 9999,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      pointerEvents: "none",
      background: "color-mix(in srgb, var(--color-primary-light) 30%, transparent)",
      backdropFilter: "blur(8px)",
      WebkitBackdropFilter: "blur(8px)",
      animation: "fadeIn 0.2s ease",
    }}>
      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "12px",
        padding: "40px 64px",
        borderRadius: "var(--radius-2xl)",
        border: "2px dashed var(--color-primary)",
        boxShadow: "0 0 0 4px var(--color-primary-light), 0 0 32px var(--color-primary-light)",
        background: "var(--glass-bg)",
        backdropFilter: "var(--glass-blur)",
        WebkitBackdropFilter: "var(--glass-blur)",
      }}>
        <FileText style={{
          width: "40px",
          height: "40px",
          color: "var(--color-primary)",
        }} />
        <p style={{
          fontSize: "15px",
          fontWeight: "500",
          color: "var(--text-level-1)",
          margin: 0,
        }}>{t("chat.dropToAttach")}</p>
        <p style={{
          fontSize: "12px",
          color: "var(--text-level-3)",
          margin: 0,
        }}>{t("chat.dragHint")}</p>
      </div>
    </div>
  );
}

interface FilePillProps {
  filePath: string;
  onRemove: (path: string) => void;
}

/** 输入框上方的紧凑文件 Pill 标签：文件类型 Icon + 文件名 + 删除按钮 */
export function FilePill({ filePath, onRemove }: FilePillProps) {
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      gap: "6px",
      padding: "3px 6px 3px 10px",
      borderRadius: "var(--radius-full)",
      background: "var(--bg-level-3)",
      border: "1px solid var(--border-primary)",
      fontSize: "12px",
      color: "var(--text-level-2)",
      maxWidth: "220px",
    }}>
      {getFileIconElement(filePath, 12)}
      <span style={{
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}>{getFileName(filePath)}</span>
      <button
        onClick={() => onRemove(filePath)}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "16px",
          height: "16px",
          borderRadius: "var(--radius-full)",
          border: "none",
          background: "transparent",
          cursor: "pointer",
          color: "var(--text-level-4)",
          flexShrink: 0,
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-4)"; e.currentTarget.style.color = "var(--text-level-2)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-level-4)"; }}
        title="Remove"
      >
        <X style={{ width: "10px", height: "10px" }} />
      </button>
    </span>
  );
}

interface FilePillListProps {
  files: string[];
  onRemove: (path: string) => void;
}

/** 文件 Pill 列表容器 */
export function FilePillList({ files, onRemove }: FilePillListProps) {
  if (files.length === 0) return null;
  return (
    <div style={{
      display: "flex",
      flexWrap: "wrap",
      gap: "6px",
      marginBottom: "8px",
    }}>
      {files.map((filePath) => (
        <FilePill key={filePath} filePath={filePath} onRemove={onRemove} />
      ))}
    </div>
  );
}
