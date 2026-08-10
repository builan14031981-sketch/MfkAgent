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
  /** 原始 File 对象（upload 端点需要；全局拖拽有，DroppedFile 构造时附带） */
  file?: File;
}

/** 附件类型分类（决定后端处理方式：text→注入Prompt，image→多模态，binary→仅元数据） */
export type AttachmentKind = "text" | "image" | "binary";

/** 前端统一的附件数据结构（传递给后端的元数据，不含文件内容） */
export interface Attachment {
  /** 客户端唯一 id（React key + 去重） */
  id: string;
  /** 文件名（含扩展名） */
  name: string;
  /** 项目相对路径（项目内文件）或 null（外部文件） */
  path: string | null;
  /** MIME 类型，未知则 "application/octet-stream" */
  mime: string;
  /** 文件大小（字节） */
  size: number;
  /** 类型分类 */
  kind: AttachmentKind;
  /** 扩展名（小写，无点） */
  ext: string;
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

/** 纯文本扩展名（CODE_EXTENSIONS 不覆盖的，如 txt/log/csv 等） */
const TEXT_EXTENSIONS = new Set([
  "txt", "log", "csv", "env", "conf", "cfg", "properties",
  "bat", "ps1", "cmd", "rst", "tex", "rtf",
]);

/** 获取文件扩展名（小写，无点） */
export function getFileExt(fileName: string): string {
  return fileName.split(".").pop()?.toLowerCase() ?? "";
}

/** 按扩展名 + MIME 分类附件类型 */
export function classifyAttachment(name: string, mime: string): AttachmentKind {
  const ext = getFileExt(name);
  if (IMAGE_EXTENSIONS.has(ext) || mime.startsWith("image/")) return "image";
  if (ARCHIVE_EXTENSIONS.has(ext)) return "binary";
  if (CODE_EXTENSIONS.has(ext) || TEXT_EXTENSIONS.has(ext) || mime.startsWith("text/")) return "text";
  return "binary";
}

/** 将绝对路径转为项目相对路径（无法转换时返回 null） */
export function toProjectRelative(absPath: string, projectRoot?: string | null): string | null {
  if (!projectRoot) return null;
  const normalize = (p: string) => p.replace(/\\/g, "/");
  const root = normalize(projectRoot).replace(/\/+$/, "");
  const filePath = normalize(absPath);
  if (filePath.startsWith(root + "/")) {
    return filePath.slice(root.length + 1);
  }
  return null;
}

/**
 * 从 File 对象构造 Attachment（Electron 下 File.path 为绝对路径）。
 * projectRoot 提供时尝试转为项目相对路径，否则 path 为 null。
 */
export function fileToAttachment(file: File, projectRoot?: string | null): Attachment {
  const fileWithPath = file as File & { path?: string };
  const absPath = fileWithPath.path || file.name;
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
    name: file.name,
    path: toProjectRelative(absPath, projectRoot),
    mime: file.type || "application/octet-stream",
    size: file.size,
    kind: classifyAttachment(file.name, file.type),
    ext: getFileExt(file.name),
  };
}

/** 从 DroppedFile 构造 Attachment（全屏拖拽路径，无 size/mime 信息，按扩展名推断） */
export function droppedFileToAttachment(dropped: DroppedFile, projectRoot?: string | null): Attachment {
  const ext = getFileExt(dropped.name);
  const mime = ext === "png" ? "image/png"
    : ext === "jpg" || ext === "jpeg" ? "image/jpeg"
    : ext === "gif" ? "image/gif"
    : ext === "webp" ? "image/webp"
    : ext === "svg" ? "image/svg+xml"
    : "application/octet-stream";
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
    name: dropped.name,
    path: toProjectRelative(dropped.path, projectRoot),
    mime,
    size: 0, // DroppedFile 无 size 信息
    kind: classifyAttachment(dropped.name, mime),
    ext,
  };
}

/** 附件去重合并（按 path 或 name 匹配） */
export function mergeAttachments(prev: Attachment[], next: Attachment[]): Attachment[] {
  const result = [...prev];
  for (const att of next) {
    const exists = result.some(
      (a) => (att.path && a.path === att.path) || (a.name === att.name && a.size === att.size && a.size > 0)
    );
    if (!exists) result.push(att);
  }
  return result;
}

function getFileIconElement(fileName: string, size: number) {
  const ext = getFileExt(fileName);
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

/** 格式化文件大小为可读字符串 */
export function formatFileSize(bytes: number): string {
  if (bytes <= 0) return "";
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
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

    // 输入框区域（ChatInput 已自带卡片级拖拽高亮）由局部处理器接管，
    // 全局遮罩在此跳过，避免双重视觉反馈（用 closest 拦截冒泡）。
    const isInputDropTarget = (e: DragEvent) => {
      const target = e.target as Element | null;
      return !!target?.closest?.('[data-mfk-dropzone="input"]');
    };

    const handleDragEnter = (e: DragEvent) => {
      if (!hasFiles(e)) return;
      if (isInputDropTarget(e)) return;
      e.preventDefault();
      dragDepthRef.current += 1;
      setIsDragging(true);
    };

    const handleDragOver = (e: DragEvent) => {
      if (!hasFiles(e)) return;
      if (isInputDropTarget(e)) return;
      e.preventDefault();
    };

    const handleDragLeave = (e: DragEvent) => {
      if (!hasFiles(e)) return;
      if (isInputDropTarget(e)) return;
      dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
      if (dragDepthRef.current === 0) {
        setIsDragging(false);
      }
    };

    const handleDrop = (e: DragEvent) => {
      if (!hasFiles(e)) return;
      if (isInputDropTarget(e)) {
        // 输入框内由 ChatInput 自行处理；无论如何收敛全局遮罩状态，防止残留
        dragDepthRef.current = 0;
        setIsDragging(false);
        return;
      }
      e.preventDefault();
      dragDepthRef.current = 0;
      setIsDragging(false);
      const files = Array.from(e.dataTransfer?.files ?? []);
      if (files.length === 0) return;
      const dropped: DroppedFile[] = files.map((file) => {
        const p = file as File & { path?: string };
        return { name: file.name, path: p.path || file.name, file };
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

/** 按 kind 获取附件的强调色 */
function getAttachmentColor(kind: AttachmentKind): string {
  switch (kind) {
    case "image": return "var(--color-secondary, #8b5cf6)";
    case "binary": return "var(--text-level-4)";
    default: return "var(--color-primary)";
  }
}

interface AttachmentChipProps {
  attachment: Attachment;
  onRemove: (id: string) => void;
}

/**
 * 附件 Chip：按类型区分视觉样式（text 蓝 / image 紫 / binary 灰），
 * 展示图标 + 文件名 + 大小 + kind 标签。
 */
export function AttachmentChip({ attachment, onRemove }: AttachmentChipProps) {
  const color = getAttachmentColor(attachment.kind);
  const sizeText = formatFileSize(attachment.size);
  const kindLabel = attachment.kind === "image" ? "IMG" : attachment.kind === "binary" ? "BIN" : "TXT";

  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      gap: "6px",
      padding: "3px 6px 3px 10px",
      borderRadius: "var(--radius-full)",
      background: "var(--bg-level-3)",
      border: `1px solid ${color === "var(--text-level-4)" ? "var(--border-primary)" : color}`,
      fontSize: "12px",
      color: "var(--text-level-2)",
      maxWidth: "260px",
    }}>
      {attachment.kind === "image" ? (
        <FileImage style={{ width: 12, height: 12, color, flexShrink: 0 }} />
      ) : attachment.kind === "binary" ? (
        <FileArchive style={{ width: 12, height: 12, color, flexShrink: 0 }} />
      ) : (
        <FileCode2 style={{ width: 12, height: 12, color, flexShrink: 0 }} />
      )}
      <span style={{
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}>{attachment.name}</span>
      {sizeText && (
        <span style={{ fontSize: 10, color: "var(--text-level-4)", flexShrink: 0 }}>{sizeText}</span>
      )}
      <span style={{
        fontSize: 9,
        fontWeight: 600,
        color,
        flexShrink: 0,
        padding: "1px 4px",
        borderRadius: "var(--radius-full)",
        background: color === "var(--text-level-4)" ? "var(--bg-level-4)" : "color-mix(in srgb, " + color + " 12%, transparent)",
      }}>{kindLabel}</span>
      <button
        onClick={() => onRemove(attachment.id)}
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

interface AttachmentChipListProps {
  attachments: Attachment[];
  onRemove: (id: string) => void;
}

/** 附件 Chip 列表容器 */
export function AttachmentChipList({ attachments, onRemove }: AttachmentChipListProps) {
  if (attachments.length === 0) return null;
  return (
    <div style={{
      display: "flex",
      flexWrap: "wrap",
      gap: "6px",
      marginBottom: "8px",
    }}>
      {attachments.map((att) => (
        <AttachmentChip key={att.id} attachment={att} onRemove={onRemove} />
      ))}
    </div>
  );
}
