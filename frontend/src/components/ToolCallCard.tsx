"use client";

import { useMemo, useState, useCallback, useEffect } from "react";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { resolveToolMeta } from "@/lib/toolMeta";
import { useTranslation } from "@/hooks/useTranslation";
import { useProjectPath } from "@/lib/projectPathContext";
import { CLOSE_FILE_CTX_MENU } from "@/hooks/useFilePathInteraction";

export type ToolStatus = "pending" | "running" | "success" | "failed" | "cancelled";

/** 大日志保护：超过 50KB 时仅渲染前/后段，防止一次性挂载巨量文本卡死 DOM */
const MAX_LOG_CHARS = 51200; // 50KB（字符计）
const MAX_LOG_PREVIEW_CHARS = 400; // 前/后各保留字符数

/**
 * ToolCall 数据（兼容 v2 事件流 + 旧持久化记录）：
 * - v2 实时事件：tool / tool_call_id / input / success / result / duration_ms
 * - 旧记录（Message.tool_calls）：name / path / success / arguments / result
 */
export interface ToolCall {
  name?: string;
  tool?: string;
  path?: string;
  success?: boolean;
  status?: ToolStatus;
  result?: string;
  arguments?: Record<string, unknown>;
  input?: Record<string, unknown>;
  duration_ms?: number;
  error?: string;
  tool_call_id?: string;
  /** 后端文件类工具返回的绝对路径（tool_result 事件携带） */
  file_path?: string;
}

function resultSummary(result: string | undefined, maxLen = 80): string {
  if (!result) return "";
  const firstLine = result.split("\n")[0].trim();
  return firstLine.length > maxLen ? `${firstLine.slice(0, maxLen)}…` : firstLine;
}

/** 归一化：兼容新老字段，补全 tool / input / status（前端去重与渲染统一入口） */
export function normalizeToolCall(tc: ToolCall): ToolCall {
  const tool = tc.tool ?? tc.name ?? "";
  const input = tc.input ?? tc.arguments ?? {};
  const status: ToolStatus =
    tc.status ??
    (tc.success === false ? "failed" : tc.success === true ? "success" : "pending");
  return { ...tc, tool, input, status };
}

/**
 * ToolCallCard v2 —— 数据驱动 + 状态机渲染：
 * - pending / running / success / failed / cancelled
 * - 图标与标题由 tool + input 派生（lib/toolMeta），不再按 name 硬编码
 * - 工具名标签（tool）+ result 完整内容可展开查看（F-2）
 */
export function ToolCallCard({ toolCall }: { toolCall: ToolCall }) {
  const normalized = useMemo(() => normalizeToolCall(toolCall), [toolCall]);
  const { t } = useTranslation();
  const { tool, input, status, result, duration_ms } = normalized;
  const [expanded, setExpanded] = useState(false);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const projectPath = useProjectPath();

  /** 文件类工具：提取文件路径，供右键/双击菜单打开资源管理器 */
  const filePath = useMemo(() => {
    // 优先使用后端返回的结构化 file_path（tool_result 事件）
    if (normalized.file_path && typeof normalized.file_path === "string") {
      return normalized.file_path;
    }
    const fileTools = ["write_file", "read_file", "list_directory", "list_files"];
    if (!fileTools.includes(tool ?? "")) return null;
    const raw = (input as Record<string, unknown> | undefined)?.["relative_path"]
      || (input as Record<string, unknown> | undefined)?.["path"];
    if (typeof raw !== "string" || !raw) return null;
    // 相对路径拼接项目根目录
    if (projectPath && !raw.match(/^[A-Za-z]:[\\/]/)) {
      return projectPath.replace(/[\\/]+$/, "") + "\\" + raw.replace(/^[\\/]+/, "");
    }
    return raw;
  }, [tool, input, projectPath, normalized.file_path]);

  /** 右键打开文件 */
  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    if (!filePath || typeof window === "undefined" || !window.electronAPI?.openInFolder) return;
    e.preventDefault();
    e.stopPropagation();
    // 广播关闭信号：关闭其他所有文件右键菜单
    window.dispatchEvent(new CustomEvent(CLOSE_FILE_CTX_MENU));
    setContextMenu({ x: e.clientX, y: e.clientY });
  }, [filePath]);

  /** 关闭右键菜单 */
  const closeContextMenu = useCallback(() => setContextMenu(null), []);

  /** 执行打开文件 */
  const handleOpenInFolder = useCallback(async () => {
    closeContextMenu();
    if (filePath) {
      try {
        await window.electronAPI?.openInFolder?.(filePath);
      } catch {
        // 忽略错误
      }
    }
  }, [filePath, closeContextMenu]);

  // 关闭右键菜单：监听 click + contextmenu + 全局互斥事件
  useEffect(() => {
    if (!contextMenu) return;
    const close = () => closeContextMenu();
    document.addEventListener("click", close);
    document.addEventListener("contextmenu", close);
    window.addEventListener(CLOSE_FILE_CTX_MENU, close);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("contextmenu", close);
      window.removeEventListener(CLOSE_FILE_CTX_MENU, close);
    };
  }, [contextMenu, closeContextMenu]);

  const { icon: Icon, color, title } = useMemo(
    () => resolveToolMeta(tool ?? "", input),
    [tool, input]
  );

  const failed = status === "failed";
  const cancelled = status === "cancelled";
  const running = status === "running";

  const exitCode = useMemo(() => {
    if (!result) return "";
    const m = result.match(/\[exit code (\d+)\]/);
    return m ? m[1] : "";
  }, [result]);

  const hint = useMemo(() => {
    if (running) return "";
    if (cancelled) return "已取消";
    if (failed) {
      if (normalized.error) return resultSummary(normalized.error, 60);
      const s = resultSummary(result, 60);
      return s || "失败";
    }
    if (exitCode) return `[exit code ${exitCode}]`;
    return resultSummary(result, 80);
  }, [running, cancelled, failed, normalized.error, exitCode, result]);

  const displayColor = failed ? "var(--color-error)" : cancelled ? "var(--text-level-4)" : color;

  const borderColor = failed
    ? "var(--color-error)"
    : cancelled
    ? "var(--border-primary)"
    : running
    ? "var(--color-info)"
    : "var(--border-primary)";

  // 结果详情：失败时优先展示 error，否则展示完整 result（F-2 可展开）
  const detail = failed && normalized.error ? normalized.error : result;
  const hasDetail = typeof detail === "string" && detail.trim() !== "";

  // 大日志截断：超过 50KB 只保留前/后段，中间以提示条衔接
  const { logHead, logTail, logTruncated, logTotal } = useMemo(() => {
    if (typeof detail !== "string" || detail.length <= MAX_LOG_CHARS) {
      return { logHead: detail, logTail: null, logTruncated: false, logTotal: typeof detail === "string" ? detail.length : 0 };
    }
    return {
      logHead: detail.slice(0, MAX_LOG_PREVIEW_CHARS),
      logTail: detail.slice(detail.length - MAX_LOG_PREVIEW_CHARS),
      logTruncated: true,
      logTotal: detail.length,
    };
  }, [detail]);

  const toggleExpand = () => {
    if (hasDetail) setExpanded((v) => !v);
  };

  return (
    <>
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "4px",
        marginBottom: "8px",
        padding: "6px 12px",
        borderRadius: "var(--radius-md)",
        background: failed
          ? "color-mix(in srgb, var(--color-error) 8%, var(--bg-level-3))"
          : running
          ? "color-mix(in srgb, var(--color-info) 6%, var(--bg-level-3))"
          : "var(--bg-level-3)",
        border: `1px solid ${borderColor}`,
        opacity: cancelled ? 0.6 : 1,
        cursor: hasDetail ? "pointer" : "default",
        transition: "border-color 0.15s ease, background 0.15s ease",
      }}
      onClick={toggleExpand}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
        <Icon style={{ width: "14px", height: "14px", color: displayColor, flexShrink: 0 }} />
        {/* 工具名标签 */}
        {tool && (
          <span style={{
            flexShrink: 0,
            padding: "0 6px",
            borderRadius: "var(--radius-xs)",
            fontSize: "10px",
            fontWeight: 600,
            lineHeight: "16px",
            fontFamily: "var(--font-geist-mono), var(--font-family)",
            color: displayColor,
            background: "color-mix(in srgb, var(--bg-level-2) 60%, transparent)",
            border: "1px solid",
            borderColor: "color-mix(in srgb, var(--border-primary) 80%, transparent)",
          }}>{tool}</span>
        )}
        <code
          onContextMenu={handleContextMenu}
          onDoubleClick={filePath ? handleOpenInFolder : undefined}
          title={filePath ? "双击打开文件位置 / 右键 → 在文件管理器中打开" : undefined}
          style={{
          fontSize: "12px",
          color: failed ? "var(--color-error)" : "var(--text-level-2)",
          fontFamily: "var(--font-geist-mono), var(--font-family)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          minWidth: 0,
          flex: 1,
          cursor: filePath ? "context-menu" : undefined,
          textDecoration: filePath ? "underline dotted" : undefined,
          textUnderlineOffset: "3px",
        }}>{title}</code>
        {running && (
          <Loader2
            className="animate-spin"
            style={{ width: "12px", height: "12px", color: "var(--color-info)", flexShrink: 0, marginLeft: "auto" }}
          />
        )}
        {!running && duration_ms !== undefined && duration_ms !== null && (
          <span style={{
            fontSize: "11px",
            color: "var(--text-level-4)",
            marginLeft: "auto",
            flexShrink: 0,
            whiteSpace: "nowrap",
          }}>{duration_ms}ms</span>
        )}
        {!running && (duration_ms === undefined || duration_ms === null) && hint && !hasDetail && (
          <span style={{
            fontSize: "11px",
            color: failed ? "var(--color-error)" : "var(--text-level-4)",
            marginLeft: "auto",
            flexShrink: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            maxWidth: "40%",
          }}>{hint}</span>
        )}
        {hasDetail && (
          <span style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "2px",
            fontSize: "11px",
            color: "var(--text-level-4)",
            marginLeft: "auto",
            flexShrink: 0,
            whiteSpace: "nowrap",
          }}>
            {expanded ? "收起" : "展开"}
            {expanded
              ? <ChevronUp style={{ width: "12px", height: "12px" }} />
              : <ChevronDown style={{ width: "12px", height: "12px" }} />}
          </span>
        )}
      </div>
      {expanded && hasDetail && (
        <div style={{
          marginTop: "4px",
          padding: "8px 10px",
          borderRadius: "var(--radius-sm)",
          background: "color-mix(in srgb, var(--bg-level-2) 70%, transparent)",
          border: "1px solid",
          borderColor: "color-mix(in srgb, var(--border-primary) 60%, transparent)",
        }}>
          <pre style={{
            margin: 0,
            maxHeight: "240px",
            overflow: "auto",
            fontSize: "12px",
            lineHeight: "1.6",
            fontFamily: "var(--font-geist-mono), var(--font-family)",
            color: failed ? "var(--color-error)" : "var(--text-level-2)",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}>
            {logTruncated && logHead != null ? (
              <>
                {logHead}
                <span style={{
                  display: "block",
                  padding: "4px 0",
                  fontSize: "11px",
                  color: "var(--text-level-4)",
                  fontStyle: "italic",
                }}>{t("chat.logTruncated", { count: String(logTotal) })}</span>
                {logTail}
              </>
            ) : (
              detail
            )}
          </pre>
        </div>
      )}
    </div>
      {/* 右键菜单：在文件管理器中打开 */}
      {contextMenu && filePath && (
        <div
          style={{
            position: "fixed",
            left: contextMenu.x,
            top: contextMenu.y,
            zIndex: 9999,
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-primary)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-lg)",
            padding: "4px",
            minWidth: "160px",
          }}
        >
          <button
            onClick={handleOpenInFolder}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              width: "100%",
              padding: "6px 10px",
              border: "none",
              borderRadius: "var(--radius-sm)",
              background: "transparent",
              cursor: "pointer",
              fontSize: "12px",
              color: "var(--text-level-2)",
              textAlign: "left",
              outline: "none",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            在文件管理器中打开
          </button>
        </div>
      )}
    </>
  );
}

export function ToolCallCardList({ toolCalls }: { toolCalls: ToolCall[] }) {
  if (!toolCalls || toolCalls.length === 0) return null;
  return (
    <>
      {toolCalls.map((tc, i) => (
        <ToolCallCard
          key={tc.tool_call_id ?? `${tc.path ?? ""}${tc.name ?? tc.tool}-${i}`}
          toolCall={tc}
        />
      ))}
    </>
  );
}
