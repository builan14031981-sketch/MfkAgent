"use client";

import { memo } from "react";
import { Loader2, Check, X, ListTodo } from "lucide-react";
import type { TaskNode, TaskStatus } from "@/types/runtime";
import { useTranslation } from "@/hooks/useTranslation";

interface TaskProgressCardProps {
  /** 当前回合的任务列表（按 task_started 到达顺序） */
  tasks: TaskNode[];
}

/**
 * Agent 标识 → Badge 配色映射。
 * 不同角色用不同色调，便于一眼区分多 Agent 协同分工。
 * 未列出的 agent 走兜底色（中性灰）。
 */
const AGENT_BADGE: Record<string, { bg: string; color: string }> = {
  coding_agent: { bg: "color-mix(in srgb, var(--color-primary) 12%, transparent)", color: "var(--color-primary)" },
  research_agent: { bg: "color-mix(in srgb, #a855f7 14%, transparent)", color: "#a855f7" },
  backend_agent: { bg: "color-mix(in srgb, #3b82f6 14%, transparent)", color: "#3b82f6" },
  frontend_agent: { bg: "color-mix(in srgb, #ec4899 14%, transparent)", color: "#ec4899" },
  analyst_agent: { bg: "color-mix(in srgb, #f59e0b 14%, transparent)", color: "#f59e0b" },
  writer_agent: { bg: "color-mix(in srgb, #10b981 14%, transparent)", color: "#10b981" },
};
const DEFAULT_BADGE = { bg: "color-mix(in srgb, var(--text-level-4) 14%, transparent)", color: "var(--text-level-2)" };

/** 状态 → 图标 + 主色 */
function StatusIcon({ status }: { status: TaskStatus }) {
  if (status === "running") {
    return <Loader2 style={{ width: 14, height: 14, color: "var(--color-primary)", flexShrink: 0 }} className="animate-spin" />;
  }
  if (status === "completed") {
    return <Check style={{ width: 14, height: 14, color: "var(--color-success, #10b981)", flexShrink: 0 }} />;
  }
  if (status === "failed") {
    return <X style={{ width: 14, height: 14, color: "var(--color-error)", flexShrink: 0 }} />;
  }
  // pending：空心圆点
  return <span style={{ width: 8, height: 8, borderRadius: "50%", border: "1.5px solid var(--text-level-4)", flexShrink: 0 }} />;
}

/** Agent 角色 Badge */
function AgentBadge({ agent }: { agent: string }) {
  const colors = AGENT_BADGE[agent] ?? DEFAULT_BADGE;
  // 友好显示名：去 _agent 后缀 + 首字母大写
  const label = agent.replace(/_agent$/, "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) || agent;
  return (
    <span style={{
      fontSize: "10px",
      fontWeight: 600,
      padding: "1px 6px",
      borderRadius: "var(--radius-xs)",
      background: colors.bg,
      color: colors.color,
      whiteSpace: "nowrap",
      flexShrink: 0,
      lineHeight: "16px",
    }}>{label}</span>
  );
}

/**
 * 多 Agent 任务进度卡片：实时展示当前回合的任务执行情况。
 * - 任务按 task_started 到达顺序排列
 * - Running 显示 spinner，Completed 显示绿色 ✓，Failed 显示红色 ✗
 * - 每个任务带 Agent 角色 Badge（不同颜色）
 * - tasks 为空时不渲染（保持聊天界面干净）
 */
export const TaskProgressCard = memo(function TaskProgressCard({ tasks }: TaskProgressCardProps) {
  const { t } = useTranslation();
  if (tasks.length === 0) return null;

  const completed = tasks.filter((task) => task.status === "completed").length;
  const failed = tasks.filter((task) => task.status === "failed").length;

  return (
    <div style={{
      marginBottom: "12px",
      borderRadius: "var(--radius-md)",
      border: "1px solid var(--border-primary)",
      background: "var(--bg-level-2)",
      padding: "12px 14px",
    }}>
      {/* 头部：标题 + 汇总 */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
        <ListTodo style={{ width: 14, height: 14, color: "var(--text-level-2)", flexShrink: 0 }} />
        <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-level-1)", lineHeight: 1.25 }}>
          {t("chat.taskProgress.title", { defaultValue: "任务执行" })}
        </span>
        <span style={{
          fontSize: "11px",
          color: "var(--text-level-3)",
          marginLeft: "auto",
          flexShrink: 0,
        }}>
          {completed}/{tasks.length}{failed > 0 && ` · ${failed} failed`}
        </span>
      </div>

      {/* 任务列表 */}
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        {tasks.map((task) => (
          <div
            key={task.task_id}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "8px",
              padding: "6px 8px",
              borderRadius: "var(--radius-sm)",
              background: task.status === "failed" ? "color-mix(in srgb, var(--color-error) 6%, transparent)" : "transparent",
            }}
          >
            <div style={{ marginTop: "2px" }}>
              <StatusIcon status={task.status} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
                <span style={{
                  fontSize: "12px",
                  color: task.status === "failed" ? "var(--text-level-1)" : "var(--text-level-2)",
                  lineHeight: 1.4,
                  wordBreak: "break-word",
                }}>{task.action || task.task_id}</span>
                <AgentBadge agent={task.assigned_agent} />
              </div>
              {task.status === "failed" && task.error && (
                <p style={{
                  margin: "4px 0 0 0",
                  fontSize: "11px",
                  lineHeight: 1.5,
                  color: "var(--color-error)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}>{task.error}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
});
