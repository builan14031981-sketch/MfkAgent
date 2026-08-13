"use client";

import { ToolCallRow } from "./ToolCallGroup";
import type { ToolCall } from "./ToolCallGroup";

// 类型与工具函数继续从原模块路径导出，兼容既有 import（runtime.ts / useChatStream / useMessages 等）
export type { ToolCall, ToolStatus } from "./ToolCallGroup";
export { normalizeToolCall } from "./ToolCallGroup";

/**
 * ToolCallCard —— 兼容导出 wrapper。
 * 新版工具渲染统一走 ToolCallGroup / ToolCallRow（见 ToolCallGroup.tsx），
 * 本文件保留组件与类型导出以兼容既有 import 路径，不再承载渲染逻辑。
 */
export function ToolCallCard({ toolCall }: { toolCall: ToolCall }) {
  return <ToolCallRow toolCall={toolCall} />;
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
