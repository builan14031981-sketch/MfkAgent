"use client";

import { memo, useState, useEffect, useRef } from "react";
import { Loader2, Check, X, ListTodo, ChevronUp, ChevronDown } from "lucide-react";
import type { TaskNode, TaskStatus } from "@/types/runtime";
import { useTranslation } from "@/hooks/useTranslation";

interface TaskProgressCardProps {
  /** 当前回合的任务列表（按 task_started 到达顺序） */
  tasks: TaskNode[];
  /** 2026-08-11：会话 id，用于按会话持久化折叠态（不传则不持久化） */
  chatId?: number | null;
  /** 2026-08-11：是否处于实时流式中——自动展开仅限流式期间的新任务，
   * 刷新/历史恢复导致的 tasks 增长不得覆盖用户持久化的折叠态 */
  live?: boolean;
}

/**
 * V2 规范：Agent 身份不再分配专属色（废除彩虹徽章）。
 * 统一中性灰阶徽章；仅任务状态使用语义色（running=accent / failed=error）。
 */
const AGENT_BADGE: { bg: string; color: string } = { bg: "color-mix(in srgb, var(--text-level-4) 12%, transparent)", color: "var(--text-level-2)" };
const DEFAULT_BADGE = AGENT_BADGE;

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

/** Agent 角色 Badge（V2：统一中性灰阶，不再按角色分色） */
function AgentBadge({ agent }: { agent: string }) {
  const colors = DEFAULT_BADGE;
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
 * - Running 显示 spinner，Completed 显示灰色 ✓，Failed 显示红色 ✗
 * - 每个任务带 Agent 角色 Badge（统一中性灰阶，V2 规范）
 * - tasks 为空时不渲染（保持聊天界面干净）
 */
export const TaskProgressCard = memo(function TaskProgressCard({ tasks, chatId = null, live = false }: TaskProgressCardProps) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(false);
  const prevTaskCountRef = useRef(tasks.length);

  // 2026-08-11：折叠态按会话持久化（key 带 chatId，刷新/切换会话后读回，不再重置为展开）
  useEffect(() => {
    // 会话切换时同步任务计数基线，避免误触发下方“新任务自动展开”
    prevTaskCountRef.current = tasks.length;
    if (chatId == null) { setCollapsed(false); return; }
    try {
      setCollapsed(window.localStorage.getItem(`mfk_task_card_collapsed_${chatId}`) === "1");
    } catch { /* localStorage 不可用时默认展开 */ setCollapsed(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId]);

  // 智能行为：流式期间新任务到达时自动展开（并同步持久化）。
  // 注意：live=false（刷新/历史恢复）时 tasks 从 0/缓存增长不是“新任务”，
  // 绝不能覆盖用户持久化的折叠态（此前无 live 守卫，刷新后自动展开把 "1" 覆写为 "0"，导致收起态失效）。
  useEffect(() => {
    const prevCount = prevTaskCountRef.current;
    prevTaskCountRef.current = tasks.length;
    if (live && tasks.length > prevCount) {
      setCollapsed(false);
      if (chatId != null) {
        try { window.localStorage.setItem(`mfk_task_card_collapsed_${chatId}`, "0"); } catch { /* noop */ }
      }
    }
  }, [tasks, chatId, live]);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      if (chatId != null) {
        try { window.localStorage.setItem(`mfk_task_card_collapsed_${chatId}`, next ? "1" : "0"); } catch { /* noop */ }
      }
      return next;
    });
  };

  if (tasks.length === 0) return null;

  const completed = tasks.filter((task) => task.status === "completed").length;
  const failed = tasks.filter((task) => task.status === "failed").length;
  const running = tasks.filter((task) => task.status === "running").length;

  return (
    <div style={{
      borderRadius: "var(--radius-md)",
      border: "1px solid var(--border-primary)",
      background: "var(--bg-level-3)",
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
          onClick={toggleCollapsed}
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