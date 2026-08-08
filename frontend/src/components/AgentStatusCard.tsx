"use client";

import { memo } from "react";
import { Check, AlertTriangle } from "lucide-react";
import type { AgentStateUpdateEvent } from "@/types/runtime";

interface AgentStatusCardProps {
  /** 当前 Agent 状态流转事件；null 时卡片不渲染 */
  state: AgentStateUpdateEvent | null;
}

/**
 * 动态 Agent 状态名片：替代单调的"正在输入..."指示器。
 *
 * 消费 SSE 推送的 agent_state_update 事件，实时展示：
 * - agent_role（加粗带主色）：当前执行任务的 Agent 角色
 * - task_progress（徽章样式）：任务进度指示（如 "任务 1/5"）
 * - action_detail：当前动作详情
 * - 加载动画：working/waiting_for_tool 时三个错峰跳动圆点
 * - 终态反馈：completed 显示绿色勾、error 显示红色感叹号（1.5s 后由父级清空隐藏）
 *
 * 挂载位置：消息列表与输入框之间的专属区域（chat/[id]/page.tsx）。
 * 仅当 state 非 null 时渲染；终态（completed/error）短暂停留后由 useChatStream 自动清空。
 */
export const AgentStatusCard = memo(function AgentStatusCard({ state }: AgentStatusCardProps) {
  if (!state) return null;

  const { status, agent_role, action_detail, task_progress } = state;

  const isWorking = status === "working" || status === "waiting_for_tool";
  const isCompleted = status === "completed";
  const isError = status === "error";

  // 状态色：working=主色 / completed=成功色 / error=错误色
  const accentColor = isError
    ? "var(--color-error)"
    : isCompleted
      ? "var(--color-success)"
      : "var(--color-primary)";

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: "10px",
      maxWidth: "800px",
      margin: "0 auto 8px auto",
      padding: "8px 14px",
      borderRadius: "var(--radius-md)",
      background: "var(--bg-level-3)",
      border: "1px solid var(--border-primary)",
      animation: "slideDown 0.2s ease-out",
    }}>
      {/* 状态图标区：working 时三个跳动圆点，终态时静态图标 */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: isWorking ? "3px" : "0",
        flexShrink: 0,
        width: "20px",
        justifyContent: "center",
      }}>
        {isWorking && (
          <>
            <Dot delay="0ms" color={accentColor} />
            <Dot delay="150ms" color={accentColor} />
            <Dot delay="300ms" color={accentColor} />
          </>
        )}
        {isCompleted && (
          <Check style={{ width: "16px", height: "16px", color: accentColor }} />
        )}
        {isError && (
          <AlertTriangle style={{ width: "16px", height: "16px", color: accentColor }} />
        )}
      </div>

      {/* Agent 角色名（加粗带状态色） */}
      <span style={{
        fontSize: "13px",
        fontWeight: 600,
        color: accentColor,
        whiteSpace: "nowrap",
        flexShrink: 0,
      }}>
        {agent_role}
      </span>

      {/* 任务进度徽章（仅有时渲染） */}
      {task_progress && (
        <span style={{
          display: "inline-flex",
          alignItems: "center",
          padding: "2px 8px",
          borderRadius: "var(--radius-full)",
          background: "color-mix(in srgb, var(--color-primary) 12%, transparent)",
          border: "1px solid color-mix(in srgb, var(--color-primary) 30%, transparent)",
          fontSize: "11px",
          fontWeight: 500,
          lineHeight: 1.4,
          color: "var(--color-primary)",
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}>
          {task_progress}
        </span>
      )}

      {/* 动作详情（自动截断） */}
      <span style={{
        flex: 1,
        minWidth: 0,
        fontSize: "12px",
        lineHeight: 1.4,
        color: "var(--text-level-3)",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}>
        {action_detail}
      </span>
    </div>
  );
});

/** 跳动圆点：使用全局 bounce keyframes + 错峰 animationDelay */
function Dot({ delay, color }: { delay: string; color: string }) {
  return (
    <span style={{
      display: "inline-block",
      width: "5px",
      height: "5px",
      borderRadius: "50%",
      background: color,
      animation: "bounce 0.8s ease-in-out infinite",
      animationDelay: delay,
      flexShrink: 0,
    }} />
  );
}
