"use client";

import { FileCode, FileText } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";

export interface ToolCall {
  name: string;
  path: string;
  success?: boolean;
}

interface ToolCallCardProps {
  toolCall: ToolCall;
}

/**
 * 文件操作事件卡片：
 * - write_file: 新建/修改文件（FileCode 图标 + "已自动写入硬盘"淡色提示）
 * - read_file:  读取文件（FileText 图标）
 * 渲染在 AI 回复气泡上方，极简高精度。
 */
export function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const { t } = useTranslation();
  const isWrite = toolCall.name === "write_file";

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: "8px",
      marginBottom: "8px",
      padding: "6px 12px",
      borderRadius: "var(--radius-md)",
      background: "var(--bg-level-3)",
      border: "1px solid var(--border-primary)",
    }}>
      {isWrite ? (
        <FileCode style={{ width: "14px", height: "14px", color: "var(--color-success)", flexShrink: 0 }} />
      ) : (
        <FileText style={{ width: "14px", height: "14px", color: "var(--color-info)", flexShrink: 0 }} />
      )}
      <code style={{
        fontSize: "12px",
        color: "var(--text-level-2)",
        fontFamily: "var(--font-family)",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
        minWidth: 0,
      }}>{toolCall.path}</code>
      {isWrite && (
        <span style={{
          fontSize: "11px",
          color: "var(--text-level-4)",
          marginLeft: "auto",
          flexShrink: 0,
        }}>{t("chat.toolWritten")}</span>
      )}
    </div>
  );
}

export function ToolCallCardList({ toolCalls }: { toolCalls: ToolCall[] }) {
  if (toolCalls.length === 0) return null;
  return (
    <>
      {toolCalls.map((tc, i) => (
        <ToolCallCard key={`${tc.name}-${tc.path}-${i}`} toolCall={tc} />
      ))}
    </>
  );
}
