"use client";

import { useMemo } from "react";
import { FileCode, FileText, Search, Terminal, GitBranch, Bookmark } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";

export interface ToolCall {
  name: string;
  path?: string;
  success?: boolean;
  /** 工具执行结果全文（汇总事件 / 持久化记录提供） */
  result?: string;
  /** 工具调用参数（后端实时/汇总事件已透传） */
  arguments?: Record<string, unknown>;
}

function argString(args: Record<string, unknown> | undefined, key: string): string {
  if (!args) return "";
  const v = args[key];
  if (typeof v === "string") return v;
  if (typeof v === "number") return String(v);
  return "";
}

/** 从 result 提取首行作为摘要（\n 前截断 80 字符） */
function resultSummary(result: string | undefined, maxLen = 80): string {
  if (!result) return "";
  const firstLine = result.split("\n")[0].trim();
  return firstLine.length > maxLen ? `${firstLine.slice(0, maxLen)}…` : firstLine;
}

/**
 * 工具调用事件卡片（按工具名分流图标与内容）：
 * - write_file: FileCode（绿）+ 路径 + "已写入"
 * - read_file / list_files: FileText + 路径
 * - search_files: Search + `搜索 "query"` + 命中条数
 * - run_command: Terminal + `$ 命令` + `[exit code n]`
 * - git_*: GitBranch + 结果摘要
 * - add_memory: Bookmark + scope + 内容摘要
 * 失败态（success=false 或 result 以"错误"开头）：红色边框 + 错误摘要。
 */
export function ToolCallCard({ toolCall }: { toolCall: ToolCall }) {
  const { t } = useTranslation();
  const { name, path, success, result, arguments: args } = toolCall;

  const failed = success === false || (typeof result === "string" && /^错误/.test(result.trim()));

  const isWrite = name === "write_file";
  const isRead = name === "read_file" || name === "list_files";
  const isSearch = name === "search_files";
  const isCommand = name === "run_command";
  const isGit = name.startsWith("git_");
  const isMemory = name === "add_memory";

  const summary = useMemo(() => resultSummary(result), [result]);
  const exitCode = useMemo(() => {
    if (!result) return "";
    const m = result.match(/\[exit code (\d+)\]/);
    return m ? m[1] : "";
  }, [result]);

  let Icon = FileText;
  let iconColor = "var(--color-info)";
  if (isWrite) {
    Icon = FileCode;
    iconColor = "var(--color-success)";
  } else if (isSearch) {
    Icon = Search;
    iconColor = "var(--color-info)";
  } else if (isCommand) {
    Icon = Terminal;
    iconColor = "var(--color-warning)";
  } else if (isGit) {
    Icon = GitBranch;
    iconColor = "var(--color-info)";
  } else if (isMemory) {
    Icon = Bookmark;
    iconColor = "var(--color-warning)";
  }

  // 主文本 + 右侧提示
  let mainText = path || "";
  let hint: string | null = null;
  if (isWrite) {
    hint = t("chat.toolWritten");
  } else if (isSearch) {
    const q = argString(args, "query");
    mainText = q ? `搜索 "${q}"` : summary || name;
  } else if (isCommand) {
    const cmd = argString(args, "command");
    mainText = cmd ? `$ ${cmd}` : summary || name;
    hint = exitCode ? `[exit code ${exitCode}]` : summary || null;
  } else if (isGit) {
    mainText = summary || name;
  } else if (isMemory) {
    const scope = argString(args, "scope");
    mainText = summary || name;
    hint = scope ? `scope: ${scope}` : null;
  } else if (isRead) {
    mainText = path || summary || name;
  }
  if (!mainText) mainText = name;

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: "8px",
      marginBottom: "8px",
      padding: "6px 12px",
      borderRadius: "var(--radius-md)",
      background: failed ? "color-mix(in srgb, var(--color-error) 8%, var(--bg-level-3))" : "var(--bg-level-3)",
      border: `1px solid ${failed ? "var(--color-error)" : "var(--border-primary)"}`,
    }}>
      <Icon style={{ width: "14px", height: "14px", color: iconColor, flexShrink: 0 }} />
      <code style={{
        fontSize: "12px",
        color: failed ? "var(--color-error)" : "var(--text-level-2)",
        fontFamily: "var(--font-geist-mono), var(--font-family)",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
        minWidth: 0,
      }}>{mainText}</code>
      {hint && (
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
    </div>
  );
}

export function ToolCallCardList({ toolCalls }: { toolCalls: ToolCall[] }) {
  if (toolCalls.length === 0) return null;
  return (
    <>
      {toolCalls.map((tc, i) => (
        <ToolCallCard key={`${tc.name}-${i}`} toolCall={tc} />
      ))}
    </>
  );
}
