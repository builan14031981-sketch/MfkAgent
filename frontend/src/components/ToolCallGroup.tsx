"use client";

import { useMemo, useState, useCallback, useEffect } from "react";
import { ChevronDown, ChevronUp, Loader2, Wrench } from "lucide-react";
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

/** 毫秒精度的时长格式化：<1s → "120ms"；≥1s → "1.2s" */
function formatMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export type ToolRenderBlock<T> =
  | { kind: "other"; seg: T }
  | { kind: "tool"; tools: ToolCall[]; streaming: boolean };

/**
 * 纯函数：把按真实到达顺序排列的段列表中的连续工具段合并为一组。
 * 中间出现任何非工具段（text/thinking/memory 等）即断开。渲染层计算，不改后端。
 * - getTool(s)：工具段返回其 ToolCall，非工具段返回 undefined（类型守卫式，便于调用处安全取值）
 * 组是否"流式中"：只要组内还有工具处于 running/pending 即视为流式中。
 */
export function groupToolCalls<T>(
  segs: T[],
  getTool: (s: T) => ToolCall | undefined
): ToolRenderBlock<T>[] {
  const blocks: ToolRenderBlock<T>[] = [];
  let acc: ToolCall[] = [];
  const flush = () => {
    if (acc.length) {
      blocks.push({
        kind: "tool",
        tools: acc,
        streaming: acc.some((t) => t.status === "running" || t.status === "pending"),
      });
      acc = [];
    }
  };
  for (const seg of segs) {
    const tc = getTool(seg);
    if (tc) {
      acc.push(tc);
    } else {
      flush();
      blocks.push({ kind: "other", seg });
    }
  }
  flush();
  return blocks;
}

/**
 * 工具行（组内展开态的单个成员，或单工具组的整行）。
 * 保留：右键/双击打开文件、大日志截断、取消态 opacity 0.6、失败红。
 * 精简：纯 chevron（无"展开"二字）、成功态去内联 hint、耗时仅 ≥10ms 或失败才显示。
 */
export function ToolCallRow({ toolCall }: { toolCall: ToolCall }) {
  const normalized = useMemo(() => normalizeToolCall(toolCall), [toolCall]);
  const { t } = useTranslation();
  const { tool, input, status, result, duration_ms, error } = normalized;
  const [expanded, setExpanded] = useState(false);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const projectPath = useProjectPath();

  /** 文件类工具：提取文件路径，供右键/双击菜单打开资源管理器 */
  const filePath = useMemo(() => {
    if (normalized.file_path && typeof normalized.file_path === "string") {
      return normalized.file_path;
    }
    const fileTools = ["write_file", "read_file", "list_directory", "list_files"];
    if (!fileTools.includes(tool ?? "")) return null;
    const raw =
      (input as Record<string, unknown> | undefined)?.["relative_path"] ||
      (input as Record<string, unknown> | undefined)?.["path"];
    if (typeof raw !== "string" || !raw) return null;
    if (projectPath && !raw.match(/^[A-Za-z]:[\\/]/)) {
      return projectPath.replace(/[\\/]+$/, "") + "\\" + raw.replace(/^[\\/]+/, "");
    }
    return raw;
  }, [tool, input, projectPath, normalized.file_path]);

  const { icon: Icon, title } = useMemo(
    () => resolveToolMeta(tool ?? "", input),
    [tool, input]
  );

  const failed = status === "failed";
  const cancelled = status === "cancelled";
  const running = status === "running";

  // 详情：失败时优先展示 error，否则展示完整 result
  const detail = failed && error ? error : result;
  const hasDetail = typeof detail === "string" && detail.trim() !== "";

  // 大日志截断：超过 50KB 只保留前/后段，中间以提示条衔接
  const { logHead, logTail, logTruncated, logTotal } = useMemo(() => {
    if (typeof detail !== "string" || detail.length <= MAX_LOG_CHARS) {
      return {
        logHead: detail,
        logTail: null,
        logTruncated: false,
        logTotal: typeof detail === "string" ? detail.length : 0,
      };
    }
    return {
      logHead: detail.slice(0, MAX_LOG_PREVIEW_CHARS),
      logTail: detail.slice(detail.length - MAX_LOG_PREVIEW_CHARS),
      logTruncated: true,
      logTotal: detail.length,
    };
  }, [detail]);

  // 失败行红字错误摘要（一眼可见原因），成功态不展示内联 hint
  const failedSummary = failed
    ? error
      ? resultSummary(error, 50)
      : resultSummary(result, 50) || "失败"
    : null;

  // 耗时：仅 ≥10ms 或失败才显示
  const showDuration =
    duration_ms !== undefined && duration_ms !== null && (duration_ms >= 10 || failed);

  const toggleExpand = () => {
    if (hasDetail) setExpanded((v) => !v);
  };

  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      if (!filePath || typeof window === "undefined" || !window.electronAPI?.openInFolder) return;
      e.preventDefault();
      e.stopPropagation();
      window.dispatchEvent(new CustomEvent(CLOSE_FILE_CTX_MENU));
      setContextMenu({ x: e.clientX, y: e.clientY });
    },
    [filePath]
  );

  const closeContextMenu = useCallback(() => setContextMenu(null), []);

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

  return (
    <>
      <div style={{ marginBottom: "6px", minWidth: 0, opacity: cancelled ? 0.6 : 1 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            minWidth: 0,
            cursor: hasDetail ? "pointer" : "default",
          }}
          onClick={toggleExpand}
        >
          <Icon
            style={{
              width: "12px",
              height: "12px",
              color: failed ? "var(--color-error)" : "var(--text-level-4)",
              flexShrink: 0,
            }}
          />
          <code
            onContextMenu={handleContextMenu}
            onDoubleClick={filePath ? handleOpenInFolder : undefined}
            title={filePath ? t("chat.openInFileManager") : undefined}
            style={{
              fontSize: "12px",
              color: failed ? "var(--color-error)" : "var(--text-level-3)",
              fontFamily: "var(--font-geist-mono), var(--font-family)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              minWidth: 0,
              flex: 1,
              cursor: filePath ? "context-menu" : undefined,
              textDecoration: filePath ? "underline dotted" : undefined,
              textUnderlineOffset: "3px",
            }}
          >
            {title}
          </code>
          {running && (
            <Loader2
              className="animate-spin"
              style={{
                width: "12px",
                height: "12px",
                color: "var(--text-level-4)",
                flexShrink: 0,
                marginLeft: "auto",
              }}
            />
          )}
          {/* 失败行红字错误摘要（成功态不显示内联 hint） */}
          {!running && failedSummary && (
            <span
              style={{
                fontSize: "11px",
                color: "var(--color-error)",
                marginLeft: "auto",
                flexShrink: 0,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                maxWidth: "45%",
              }}
            >
              {failedSummary}
            </span>
          )}
          {/* 耗时：≥10ms 或失败才显示 */}
          {!running && showDuration && (
            <span
              style={{
                fontSize: "11px",
                color: "var(--text-level-4)",
                flexShrink: 0,
                whiteSpace: "nowrap",
                marginLeft: failedSummary ? "4px" : "auto",
              }}
            >
              {formatMs(duration_ms as number)}
            </span>
          )}
          {/* 纯 chevron：仅含 result 的行显示 */}
          {hasDetail && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                marginLeft: "4px",
                flexShrink: 0,
                color: "var(--text-level-4)",
              }}
            >
              {expanded ? (
                <ChevronUp style={{ width: "12px", height: "12px" }} />
              ) : (
                <ChevronDown style={{ width: "12px", height: "12px" }} />
              )}
            </span>
          )}
        </div>
        {expanded && hasDetail && (
          <div
            style={{
              marginTop: "4px",
              paddingLeft: "10px",
              borderLeft: "1px solid var(--border-primary)",
            }}
          >
            <pre
              style={{
                margin: 0,
                maxHeight: "240px",
                overflow: "auto",
                fontSize: "12px",
                lineHeight: "1.6",
                fontFamily: "var(--font-geist-mono), var(--font-family)",
                color: failed ? "var(--color-error)" : "var(--text-level-3)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {logTruncated && logHead != null ? (
                <>
                  {logHead}
                  <span
                    style={{
                      display: "block",
                      padding: "4px 0",
                      fontSize: "11px",
                      color: "var(--text-level-4)",
                      fontStyle: "italic",
                    }}
                  >
                    {t("chat.logTruncated", { count: String(logTotal) })}
                  </span>
                  {logTail}
                </>
              ) : (
                detail
              )}
            </pre>
          </div>
        )}
      </div>
      {/* 右键菜单 */}
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
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            {t("chat.openInFileManager")}
          </button>
        </div>
      )}
    </>
  );
}

/**
 * 工具调用组。
 * - 流式中：只渲染一行头 [spinner] 正在执行 N/M: 当前工具（避免工具风暴期间逐行堆叠）。
 * - 单工具（完成）：直接退化为单行，无计数、无组头。
 * - 多工具（完成）：默认折叠为摘要组头（N 次调用 · 摘要 + 总耗时 + chevron），点击展开成员行。
 */
export function ToolCallGroup({
  tools,
  streaming,
}: {
  tools: ToolCall[];
  streaming: boolean;
}) {
  const normalized = useMemo(() => tools.map(normalizeToolCall), [tools]);
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  const failed = normalized.some((x) => x.status === "failed");
  const cancelledAll = normalized.length > 0 && normalized.every((x) => x.status === "cancelled");

  // 流式中：仅一行头（spinner + 当前工具名），工具逐个切换
  if (streaming) {
    const runningIdx = normalized.findIndex(
      (x) => x.status === "running" || x.status === "pending"
    );
    const idx = runningIdx >= 0 ? runningIdx : normalized.length - 1;
    const cur = normalized[Math.max(0, idx)];
    const { title } = resolveToolMeta(cur?.tool ?? "", cur?.input);
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          marginBottom: "6px",
          minWidth: 0,
          opacity: cancelledAll ? 0.6 : 1,
        }}
      >
        <Loader2
          className="animate-spin"
          style={{ width: "12px", height: "12px", color: "var(--text-level-4)", flexShrink: 0 }}
        />
        <span
          style={{
            fontSize: "12px",
            color: "var(--text-level-3)",
            fontFamily: "var(--font-geist-mono), var(--font-family)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            minWidth: 0,
            flex: 1,
          }}
        >
          {t("chat.toolRunning", {
            current: String(idx + 1),
            total: String(normalized.length),
            name: title,
          })}
        </span>
      </div>
    );
  }

  // 单工具（完成）：直接退化为一行，无计数、无组头
  if (normalized.length === 1) {
    return <ToolCallRow toolCall={normalized[0]} />;
  }

  // 多工具（完成）：默认折叠为摘要组头
  const totalMs = normalized.reduce(
    (s, x) => s + (typeof x.duration_ms === "number" ? x.duration_ms : 0),
    0
  );
  const showTotal = totalMs > 10;
  const summary =
    normalized
      .map((x) => x.tool || "")
      .filter(Boolean)
      .slice(0, 3)
      .join(", ") + (normalized.length > 3 ? "…" : "");

  return (
    <div style={{ marginBottom: "8px", minWidth: 0, opacity: cancelledAll ? 0.6 : 1 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          minWidth: 0,
          cursor: "pointer",
        }}
        onClick={() => setExpanded((v) => !v)}
      >
        <Wrench
          style={{
            width: "12px",
            height: "12px",
            color: failed ? "var(--color-error)" : "var(--text-level-4)",
            flexShrink: 0,
          }}
        />
        <span
          style={{
            fontSize: "12px",
            color: failed ? "var(--color-error)" : "var(--text-level-3)",
            flex: 1,
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {t("chat.toolCallsCount", { count: String(normalized.length) })} · {summary}
        </span>
        {showTotal && (
          <span
            style={{
              fontSize: "11px",
              color: "var(--text-level-4)",
              flexShrink: 0,
              whiteSpace: "nowrap",
            }}
          >
            共 {formatMs(totalMs)}
          </span>
        )}
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            flexShrink: 0,
            color: "var(--text-level-4)",
          }}
        >
          {expanded ? (
            <ChevronUp style={{ width: "12px", height: "12px" }} />
          ) : (
            <ChevronDown style={{ width: "12px", height: "12px" }} />
          )}
        </span>
      </div>
      {expanded && (
        <div style={{ marginTop: "8px", display: "flex", flexDirection: "column" }}>
          {normalized.map((tc, i) => (
            <ToolCallRow key={tc.tool_call_id ?? `${tc.tool}-${i}`} toolCall={tc} />
          ))}
        </div>
      )}
    </div>
  );
}
