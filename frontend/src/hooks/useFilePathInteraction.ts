"use client";

import { useCallback, useMemo } from "react";
import { useProjectPath } from "@/lib/projectPathContext";

/**
 * 文件路径交互 Hook：封装路径检测、解析、打开文件管理器、复制路径的通用逻辑。
 * 供 MarkdownRenderer 和 ToolCallCard 复用。
 */

/** 全局右键菜单互斥事件名：任何组件打开右键菜单前广播此事件，其他实例监听后关闭自身 */
export const CLOSE_FILE_CTX_MENU = "mfk-close-file-ctx-menu";

/** Windows 绝对路径正则：C:\xxx 或 C:/xxx */
const WIN_ABS_PATH_RE = /^[A-Za-z]:[\\/]/;

/** 常见文件扩展名（用于判断是否为文件路径） */
const FILE_EXT_RE = /\.(ts|tsx|js|jsx|py|md|txt|json|html|css|scss|yaml|yml|xml|svg|png|jpg|jpeg|gif|webp|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|7z|tar|gz|sh|bat|ps1|go|rs|java|c|cpp|h|hpp|cs|rb|php|sql|toml|ini|cfg|env|log|csv)$/i;

/** 相对路径模式：至少含一个 / 或 \，且以文件扩展名结尾 */
const REL_PATH_RE = /^[\w.-]+([\\/][\w.-]+)+$/;

/** 单文件名模式：无目录分隔符，但以文件扩展名结尾（如 README.md） */
const FILE_NAME_ONLY_RE = /^[\w][\w.-]*\.\w+$/;

/**
 * 检测给定字符串是否为文件路径。
 * - Windows 绝对路径：C:\xxx\yyy
 * - 相对路径（含分隔符）：src/app.py、output/novel.txt
 * - 单文件名（含扩展名）：README.md、index.ts
 */
export function isFilePath(text: string): boolean {
  const trimmed = text.trim();
  if (!trimmed || trimmed.length > 500) return false;
  // Windows 绝对路径
  if (WIN_ABS_PATH_RE.test(trimmed)) return true;
  // 含分隔符的相对路径
  if (REL_PATH_RE.test(trimmed)) return true;
  // 单文件名（含扩展名且在常见扩展名列表中）
  if (FILE_NAME_ONLY_RE.test(trimmed) && FILE_EXT_RE.test(trimmed)) return true;
  return false;
}

/**
 * 从文本中提取文件路径（去除首尾空白和可能的标点）。
 */
export function extractFilePath(text: string): string | null {
  const trimmed = text.trim().replace(/[。，、；：！？）】》"'）\])}]+$/, "");
  if (isFilePath(trimmed)) return trimmed;
  return null;
}

/**
 * 将相对路径拼接为绝对路径。
 */
export function resolveFilePath(rawPath: string, projectPath: string | null): string {
  if (WIN_ABS_PATH_RE.test(rawPath)) return rawPath;
  if (projectPath) {
    const base = projectPath.replace(/[\\/]+$/, "");
    return base + "\\" + rawPath.replace(/^[\\/]+/, "").replace(/\//g, "\\");
  }
  return rawPath;
}

/**
 * 文件路径交互 Hook 返回值。
 */
export interface FilePathInteraction {
  /** 解析后的绝对路径（若可解析） */
  resolvedPath: string | null;
  /** 是否为有效文件路径 */
  isFile: boolean;
  /** 双击处理：在文件管理器中打开 */
  onDoubleClick: () => void;
  /** 右键菜单：在文件管理器中打开 */
  openInFolder: () => Promise<void>;
  /** 复制路径到剪贴板 */
  copyPath: () => Promise<void>;
}

/**
 * useFilePathInteraction — 文件路径交互 Hook
 *
 * @param rawPath 原始路径字符串（可以是相对路径或绝对路径）
 */
export function useFilePathInteraction(rawPath: string | null | undefined): FilePathInteraction {
  const projectPath = useProjectPath();

  const resolvedPath = useMemo(() => {
    if (!rawPath) return null;
    const trimmed = rawPath.trim();
    if (!isFilePath(trimmed)) return null;
    return resolveFilePath(trimmed, projectPath);
  }, [rawPath, projectPath]);

  const isFile = resolvedPath !== null;

  const openInFolder = useCallback(async () => {
    if (!resolvedPath) return;
    try {
      await window.electronAPI?.openInFolder?.(resolvedPath);
    } catch {
      // 非 Electron 环境或路径不存在，静默忽略
    }
  }, [resolvedPath]);

  const onDoubleClick = useCallback(() => {
    openInFolder();
  }, [openInFolder]);

  const copyPath = useCallback(async () => {
    if (!resolvedPath) return;
    try {
      await navigator.clipboard.writeText(resolvedPath);
    } catch {
      // Clipboard unavailable
    }
  }, [resolvedPath]);

  return {
    resolvedPath,
    isFile,
    onDoubleClick,
    openInFolder,
    copyPath,
  };
}
