"use client";

import { ToolCallRow } from "./ToolCallGroup";
import type { ToolCall } from "./ToolCallGroup";

// 类型与工具函数继续从原模块路径导出，兼容既有 import（runtime.ts / useChatStream / useMessages 等）
export type { ToolCall, ToolStatus } from "./ToolCallGroup";
export { normalizeToolCall } from "./ToolCallGroup";

/**
 * ToolCallCard —— 兼容导出 wrapper（@deprecated）。
 * 新版工具渲染统一走 ToolCallGroup / ToolCallRow（见 ToolCallGroup.tsx），
 * 本文件保留组件与类型导出以兼容既有 import 路径，不再承载渲染逻辑。
 * 2026-08-14 审查确认：ToolCallCard / ToolCallCardList 已无任何调用方（ChatMessage
 * 改用 <ToolCallGroup streaming={false}>），按「不删除、只标注」原则标记 deprecated，
 * 仅保留作为历史兼容导出。后续若确认长期无人引用，可走单独备份流程移除。
 *
 * @deprecated 使用 ToolCallGroup / ToolCallRow 替代（分组渲染）。
 */
export function ToolCallCard({ toolCall }: { toolCall: ToolCall }) {
  return <ToolCallRow toolCall={toolCall} />;
}

/**
 * @deprecated 使用 <ToolCallGroup tools={toolCalls} streaming={false} /> 替代（支持分组折叠）。
 */
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
