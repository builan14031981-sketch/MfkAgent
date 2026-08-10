"use client";

import { memo, useState, useEffect, useRef } from "react";
import { Loader2, Check, X, ListTodo, ChevronUp, ChevronDown } from "lucide-react";
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
    return <Check style={{ width: 14, height: 14, color: "var(--text-level-4)", flexShrink: 0 }} />;
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
  const [collapsed, setCollapsed] = useState(false);
  const prevTaskCountRef = useRef(tasks.length);

  // 智能行为：新任务到达时自动展开
  useEffect(() => {
    const prevCount = prevTaskCountRef.current;
    prevTaskCountRef.current = tasks.length;
    if (tasks.length > prevCount) {
      setCollapsed(false);
    }
  }, [tasks]);

  if (tasks.length === 0) return null;

  const completed = tasks.filter((task) => task.status === "completed").length;
  const failed = tasks.filter((task) => task.status === "failed").length;
  const running = tasks.filter((task) => task.status === "running").length;

  return (
    <div style={{
      borderRadius: "var(--radius-md)",
      border: "1px solid var(--border-primary)",
      background: "var(--bg-level-2)",
      boxShadow: "0 2px 8px rgba(0,0,0,0.04)",
      padding: "4px 12px",
      position: "relative",
    }}>
      {/* 头部：标题 + 汇总 + 折叠按钮 */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <ListTodo style={{ width: 14, height: 14, color: "var(--text-level-2)", flexShrink: 0 }} />
        <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-level-1)", lineHeight: 1.25 }}>
          {t("chat.taskProgress.title")}
        </span>
        <span style={{
          fontSize: "11px",
          color: "var(--text-level-3)",
          marginLeft: "auto",
          flexShrink: 0,
        }}>
          {completed}/{tasks.length}{failed > 0 && ` · ${failed} failed`}
        </span>
        {/* 折叠/展开按钮 */}
        <button
          onClick={() => setCollapsed((prev) => !prev)}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "24px",
            height: "24px",
            padding: 0,
            border: "none",
            borderRadius: "var(--radius-sm)",
            background: "transparent",
            cursor: "pointer",
            color: "var(--text-level-3)",
            flexShrink: 0,
            transition: "background 0.15s ease",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          title={collapsed ? t("chat.taskProgress.expand") : t("chat.taskProgress.collapse")}
        >
          {collapsed ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {/* 收起态：显示摘要 */}
      {collapsed && (
        <div style={{
          marginTop: "2px",
          fontSize: "12px",
          color: "var(--text-level-3)",
          lineHeight: 1.4,
        }}>
          {running > 0 ? (
            <span>{completed}/{tasks.length} {t("chat.taskProgress.completed")} · {running} {t("chat.taskProgress.running")}</span>
          ) : (
            <span>{completed}/{tasks.length} {t("chat.taskProgress.completed")}</span>
          )}
        </div>
      )}

      {/* 任务列表 */}
      {!collapsed && (
        <div style={{ display: "flex", flexDirection: "column", marginTop: "2px" }}>
          {tasks.map((task) => {
            const isCompleted = task.status === "completed";
            const isFailed = task.status === "failed";
            const isRunning = task.status === "running";
            return (
              <div
                key={task.task_id}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "8px",
                  padding: "2px 8px",
                  borderRadius: "var(--radius-sm)",
                  background: isFailed
                    ? "color-mix(in srgb, var(--color-error) 8%, transparent)"
                    : "transparent",
                  opacity: isCompleted ? 0.65 : 1,
                  transition: "opacity 0.2s ease",
                }}
              >
                <div style={{ marginTop: "1px" }}>
                  <StatusIcon status={task.status} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
                    <span style={{
                      fontSize: "12px",
                      color: isFailed
                        ? "var(--color-error)"
                        : isCompleted
                        ? "var(--text-level-3)"
                        : "var(--text-level-2)",
                      lineHeight: 1.4,
                      wordBreak: "break-word",
                    }}>{task.action || task.task_id}</span>
                    <AgentBadge agent={task.assigned_agent} />
                  </div>
                  {isFailed && task.error && (
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
            );
          })}
        </div>
      )}
    </div>
  );
});