"use client";

/**
 * TodoPanel —— 待办事项看板 (从零极简构建版)
 *
 * 视觉规范：
 * - 严格对齐侧边栏 ChatRow / 搜索框美学风格 (8px 圆角、var(--bg-level-2) 容器)
 * - 单层纯净 Hover 高亮 (var(--bg-level-3))，绝对零 borderLeft 弧线打架与尖锐矩形
 * - 双重撤回机制：已完成条目 [单击复选框] 或 [双击文字] 均可极速撤回
 * - 100% 静默刷新 (fetchTodos(true))，撤回与完成动画绝不上闪“加载中...”
 */
import { useState, useCallback, useRef, useEffect } from "react";
import { Check, Trash2, ChevronRight, ListTodo, Plus } from "lucide-react";
import { useTodos, type Todo } from "@/hooks/useTodos";
import { useTranslation } from "@/hooks/useTranslation";

const TODO_COLLAPSED_KEY = "mfk_todo_collapsed";
const TODO_SHOW_COMPLETED_KEY = "mfk_todo_show_completed";
const TODO_LIST_MAX_HEIGHT = "min(280px, 38vh)";

function readLocalBool(key: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

export function TodoPanel({
  forceExpanded = false,
  hideHeader = false,
}: {
  forceExpanded?: boolean;
  hideHeader?: boolean;
}) {
  const { t } = useTranslation();
  const {
    todos,
    completedTodos,
    loading,
    createTodo,
    completeTodo,
    revertTodo,
    removeTodoFromList,
    removeCompletedFromList,
    deleteTodo,
    fetchTodos,
    fetchCompletedTodos,
  } = useTodos();

  const [inputValue, setInputValue] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [showCompleted, setShowCompleted] = useState(false);
  const [completingIds, setCompletingIds] = useState<Set<string>>(new Set());
  const [revertingIds, setRevertingIds] = useState<Set<string>>(new Set());

  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (forceExpanded) {
      setCollapsed(false);
    } else {
      setCollapsed(readLocalBool(TODO_COLLAPSED_KEY));
    }
    setShowCompleted(readLocalBool(TODO_SHOW_COMPLETED_KEY));
  }, [forceExpanded]);

  // 新建待办
  const handleAddTodo = useCallback(
    async (refocus = true) => {
      const title = inputValue.trim();
      if (!title || isSubmitting) return;
      setIsSubmitting(true);
      setInputValue("");
      await createTodo(title);
      setIsSubmitting(false);
      if (refocus) inputRef.current?.focus();
    },
    [inputValue, isSubmitting, createTodo]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAddTodo();
      }
    },
    [handleAddTodo]
  );

  // 完成待办 (打勾)
  const handleToggleComplete = useCallback(
    async (id: string) => {
      setCompletingIds((prev) => new Set(prev).add(id));
      await completeTodo(id);
      fetchCompletedTodos();
      setTimeout(() => {
        removeTodoFromList(id);
        setCompletingIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }, 250);
    },
    [completeTodo, removeTodoFromList, fetchCompletedTodos]
  );

  // 撤回待办 (取消打勾) -> 静默刷新零闪烁
  const handleToggleRevert = useCallback(
    async (id: string) => {
      setRevertingIds((prev) => new Set(prev).add(id));
      await revertTodo(id);
      fetchTodos(true); // 静默拉取，避免触发 loading
      setTimeout(() => {
        removeCompletedFromList(id);
        setRevertingIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }, 250);
    },
    [revertTodo, removeCompletedFromList, fetchTodos]
  );

  // 删除待办
  const handleDelete = useCallback(
    async (id: string) => {
      await deleteTodo(id);
      fetchCompletedTodos();
    },
    [deleteTodo, fetchCompletedTodos]
  );

  // 一键清理已完成
  const handleClearCompleted = useCallback(async () => {
    const ids = completedTodos.map((t) => t.id);
    await Promise.all(ids.map((id) => deleteTodo(id).catch(() => undefined)));
    fetchCompletedTodos();
  }, [completedTodos, deleteTodo, fetchCompletedTodos]);

  // 展开/收起已完成列表
  const handleToggleCompleted = useCallback(() => {
    setShowCompleted((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(TODO_SHOW_COMPLETED_KEY, next ? "1" : "0");
      } catch {
        /* noop */
      }
      if (next) fetchCompletedTodos();
      return next;
    });
  }, [fetchCompletedTodos]);

  // 折叠面板高度过渡
  useEffect(() => {
    if (!listRef.current) return;
    if (collapsed) {
      listRef.current.style.maxHeight = "0px";
      listRef.current.style.opacity = "0";
    } else {
      listRef.current.style.maxHeight = TODO_LIST_MAX_HEIGHT;
      listRef.current.style.opacity = "1";
    }
  }, [collapsed]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchCompletedTodos();
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchCompletedTodos]);

  const pendingCount = todos.length;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        background: "var(--bg-level-2)",
        border: "1px solid var(--border-primary)",
        borderRadius: "var(--radius-lg)",
        padding: "4px 6px",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* 折叠 Header */}
      {!hideHeader && (
        <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <button
            onClick={() => {
              setCollapsed((c) => {
                const next = !c;
                try {
                  localStorage.setItem(TODO_COLLAPSED_KEY, next ? "1" : "0");
                } catch {
                  /* noop */
                }
                return next;
              });
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              flex: 1,
              minWidth: 0,
              padding: "5px 8px",
              border: "none",
              borderRadius: "var(--radius-md)",
              background: "transparent",
              cursor: "pointer",
              outline: "none",
              transition: "background 0.12s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            <ChevronRight
              style={{
                width: "12px",
                height: "12px",
                color: "var(--text-level-4)",
                flexShrink: 0,
                transform: collapsed ? "rotate(0deg)" : "rotate(90deg)",
                transition: "transform var(--transition-fast)",
              }}
            />
            <ListTodo style={{ width: "13px", height: "13px", color: "var(--color-primary)", flexShrink: 0 }} />
            <span
              style={{
                fontSize: "12px",
                fontWeight: 600,
                color: "var(--text-level-1)",
                whiteSpace: "nowrap",
              }}
            >
              {t("todo.title")}
            </span>
            {pendingCount > 0 && (
              <span
                style={{
                  marginLeft: "auto",
                  minWidth: "16px",
                  height: "16px",
                  padding: "0 5px",
                  borderRadius: "8px",
                  background: "var(--color-primary)",
                  color: "#ffffff",
                  fontSize: "10px",
                  fontWeight: 600,
                  lineHeight: "16px",
                  textAlign: "center",
                  flexShrink: 0,
                }}
              >
                {pendingCount}
              </span>
            )}
          </button>

          <button
            onClick={() => {
              setCollapsed(false);
              requestAnimationFrame(() => inputRef.current?.focus());
            }}
            title={t("todo.add")}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "22px",
              height: "22px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              color: "var(--text-level-4)",
              flexShrink: 0,
              padding: 0,
              outline: "none",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
              e.currentTarget.style.color = "var(--color-primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--text-level-4)";
            }}
          >
            <Plus style={{ width: "13px", height: "13px" }} />
          </button>
        </div>
      )}

      {/* 展开可滚动列表区 */}
      <div
        ref={listRef}
        style={{
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          maxHeight: TODO_LIST_MAX_HEIGHT,
          opacity: 1,
          transition: "max-height 0.2s ease, opacity 0.2s ease",
        }}
      >
        <div style={{ flex: 1, overflowY: "auto", minHeight: 0, padding: "2px 2px" }}>
          {loading ? (
            <div style={{ padding: "6px 8px", textAlign: "center" }}>
              <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>{t("common.loading")}</span>
            </div>
          ) : (
            todos.map((todo) => {
              const isCompleting = completingIds.has(todo.id);
              return (
                <PendingRow
                  key={todo.id}
                  todo={todo}
                  isCompleting={isCompleting}
                  onComplete={handleToggleComplete}
                  onDelete={handleDelete}
                  t={t}
                />
              );
            })
          )}

          {/* 已完成列表折叠头 */}
          {completedTodos.length > 0 && (
            <div
              style={{
                borderTop: "1px solid var(--border-secondary)",
                margin: "4px 4px 2px",
                paddingTop: "4px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <button
                  onClick={handleToggleCompleted}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    color: "var(--text-level-4)",
                    fontSize: "11px",
                    padding: "2px 4px",
                    borderRadius: "var(--radius-sm)",
                    outline: "none",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = "var(--text-level-2)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = "var(--text-level-4)";
                  }}
                >
                  <ChevronRight
                    style={{
                      width: "10px",
                      height: "10px",
                      transform: showCompleted ? "rotate(90deg)" : "rotate(0deg)",
                      transition: "transform 0.15s ease",
                    }}
                  />
                  <span>
                    {showCompleted
                      ? t("todo.hideCompleted")
                      : `${t("todo.viewCompleted")} (${completedTodos.length})`}
                  </span>
                </button>

                <button
                  onClick={handleClearCompleted}
                  title={t("todo.clearCompleted")}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "3px",
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    color: "var(--text-level-4)",
                    fontSize: "10.5px",
                    padding: "2px 4px",
                    borderRadius: "var(--radius-sm)",
                    outline: "none",
                    opacity: 0.8,
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = "var(--color-error)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = "var(--text-level-4)";
                  }}
                >
                  <Trash2 style={{ width: "10px", height: "10px" }} />
                  <span>{t("todo.clearCompleted")}</span>
                </button>
              </div>

              {showCompleted &&
                completedTodos.map((todo) => {
                  const isReverting = revertingIds.has(todo.id);
                  return (
                    <CompletedRow
                      key={todo.id}
                      todo={todo}
                      isReverting={isReverting}
                      onRevert={handleToggleRevert}
                      onDelete={handleDelete}
                      t={t}
                    />
                  );
                })}
            </div>
          )}
        </div>

        {/* 底部内嵌输入框 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "4px 8px 4px 6px",
            borderTop: "1px solid var(--border-secondary)",
            flexShrink: 0,
          }}
        >
          <span
            style={{
              width: "14px",
              height: "14px",
              borderRadius: "50%",
              border: "1.5px dashed var(--text-level-4)",
              flexShrink: 0,
              opacity: 0.6,
            }}
          />
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={() => handleAddTodo(false)}
            placeholder={t("todo.placeholder")}
            disabled={isSubmitting}
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              fontSize: "12px",
              color: "var(--text-level-1)",
              minWidth: 0,
              padding: "2px 0",
            }}
          />
          {inputValue.trim() && (
            <button
              onClick={() => handleAddTodo()}
              disabled={isSubmitting}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "18px",
                height: "18px",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: "var(--color-primary)",
                cursor: "pointer",
                color: "#fff",
                flexShrink: 0,
                padding: 0,
                outline: "none",
              }}
            >
              <Check style={{ width: "11px", height: "11px", strokeWidth: 3 }} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/** 单条未完成待办：纯净 8px 圆角，绝对零 borderLeft 划线与杂质黑粗边 */
function PendingRow({
  todo,
  isCompleting,
  onComplete,
  onDelete,
  t,
}: {
  todo: Todo;
  isCompleting: boolean;
  onComplete: (id: string) => void;
  onDelete: (id: string) => void;
  t: (key: string) => string;
}) {
  const [hovered, setHovered] = useState(false);
  const [delHovered, setDelHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "5px 8px",
        borderRadius: "var(--radius-md)",
        background: hovered && !isCompleting ? "var(--bg-level-3)" : "transparent",
        opacity: isCompleting ? 0 : 1,
        transform: isCompleting ? "translateX(4px)" : "translateX(0)",
        transition: "opacity 0.25s ease, transform 0.25s ease, background 0.12s ease",
        marginBottom: "2px",
      }}
    >
      {/* 圆形 Checkbox */}
      <button
        onClick={() => onComplete(todo.id)}
        disabled={isCompleting}
        title={t("todo.complete")}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "15px",
          height: "15px",
          borderRadius: "50%",
          border: isCompleting ? "1.5px solid var(--color-primary)" : "1.5px solid var(--text-level-4)",
          background: isCompleting ? "color-mix(in srgb, var(--color-primary) 15%, transparent)" : "transparent",
          cursor: "pointer",
          flexShrink: 0,
          padding: 0,
          outline: "none",
          transition: "all 0.15s ease",
        }}
      >
        {isCompleting && <Check style={{ width: "9px", height: "9px", color: "var(--color-primary)" }} />}
      </button>

      {/* 文本 */}
      <span
        style={{
          flex: 1,
          fontSize: "12px",
          lineHeight: 1.4,
          color: "var(--text-level-2)",
          textDecoration: isCompleting ? "line-through" : "none",
          wordBreak: "break-word",
          minWidth: 0,
        }}
      >
        {todo.title}
      </span>

      {/* 垃圾桶按钮：Hover 显形 */}
      <button
        onClick={() => onDelete(todo.id)}
        onMouseEnter={() => setDelHovered(true)}
        onMouseLeave={() => setDelHovered(false)}
        title={t("common.delete")}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "18px",
          height: "18px",
          borderRadius: "var(--radius-sm)",
          border: "none",
          background: delHovered ? "color-mix(in srgb, var(--color-error) 15%, transparent)" : "transparent",
          cursor: "pointer",
          color: delHovered ? "var(--color-error)" : "var(--text-level-4)",
          opacity: hovered ? 1 : 0,
          transition: "opacity 0.12s ease, color 0.12s ease, background 0.12s ease",
          flexShrink: 0,
          padding: 0,
          outline: "none",
        }}
      >
        <Trash2 style={{ width: "11px", height: "11px" }} />
      </button>
    </div>
  );
}

/** 单条已完成待办：支持 [单击复选框] 与 [双击文字] 极速撤回 */
function CompletedRow({
  todo,
  isReverting,
  onRevert,
  onDelete,
  t,
}: {
  todo: Todo;
  isReverting: boolean;
  onRevert: (id: string) => void;
  onDelete: (id: string) => void;
  t: (key: string) => string;
}) {
  const [hovered, setHovered] = useState(false);
  const [delHovered, setDelHovered] = useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "4px 8px",
        borderRadius: "var(--radius-md)",
        background: hovered ? "var(--bg-level-3)" : "transparent",
        opacity: isReverting ? 0 : 1,
        transform: isReverting ? "translateX(-4px)" : "translateX(0)",
        transition: "opacity 0.25s ease, transform 0.25s ease, background 0.12s ease",
        marginBottom: "2px",
      }}
    >
      <button
        onClick={() => onRevert(todo.id)}
        disabled={isReverting}
        title="点击撤回待办"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "14px",
          height: "14px",
          borderRadius: "50%",
          border: isReverting ? "1.5px solid var(--text-level-4)" : "1.5px solid var(--color-primary)",
          background: isReverting ? "transparent" : "color-mix(in srgb, var(--color-primary) 12%, transparent)",
          cursor: "pointer",
          flexShrink: 0,
          padding: 0,
          outline: "none",
        }}
      >
        {!isReverting && <Check style={{ width: "9px", height: "9px", color: "var(--color-primary)" }} />}
      </button>

      <span
        onDoubleClick={() => onRevert(todo.id)}
        title="双击撤回待办"
        style={{
          flex: 1,
          fontSize: "11.5px",
          lineHeight: 1.4,
          color: isReverting ? "var(--text-level-2)" : "var(--text-level-4)",
          textDecoration: isReverting ? "none" : "line-through",
          wordBreak: "break-word",
          minWidth: 0,
          cursor: "pointer",
        }}
      >
        {todo.title}
      </span>

      <button
        onClick={() => onDelete(todo.id)}
        onMouseEnter={() => setDelHovered(true)}
        onMouseLeave={() => setDelHovered(false)}
        title={t("common.delete")}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "18px",
          height: "18px",
          borderRadius: "var(--radius-sm)",
          border: "none",
          background: delHovered ? "color-mix(in srgb, var(--color-error) 15%, transparent)" : "transparent",
          cursor: "pointer",
          color: delHovered ? "var(--color-error)" : "var(--text-level-4)",
          opacity: hovered ? 1 : 0,
          transition: "opacity 0.12s ease, color 0.12s ease, background 0.12s ease",
          flexShrink: 0,
          padding: 0,
          outline: "none",
        }}
      >
        <Trash2 style={{ width: "10px", height: "10px" }} />
      </button>
    </div>
  );
}
