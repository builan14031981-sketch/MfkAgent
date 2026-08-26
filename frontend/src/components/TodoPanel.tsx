"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Check, Trash2, ChevronRight, ListTodo, Plus } from "lucide-react";
import { useTodos } from "@/hooks/useTodos";
import { useTranslation } from "@/hooks/useTranslation";

// ── localStorage keys ──
const TODO_COLLAPSED_KEY = "mfk_todo_collapsed";
const TODO_SHOW_COMPLETED_KEY = "mfk_todo_show_completed";

function readLocalBool(key: string): boolean {
  if (typeof window === "undefined") return false;
  try { return localStorage.getItem(key) === "1"; }
  catch { return false; }
}

/**
 * Google Tasks 风格待办面板（侧边栏顶部内嵌版）：
 * - 折叠/展开 Header，折叠时显示未完成数量 Badge
 * - 自定义圆形 Checkbox（hover 悬浮效果）
 * - 勾选 → 划线 + 300ms 平滑淡出 → API 标记 completed
 * - 扁平内嵌式输入框，Enter 直接添加
 * - 全部使用 CSS Variables 与 18 种 Hero Theme 融合
 */
export function TodoPanel({ forceExpanded = false, hideHeader = false }: { forceExpanded?: boolean; hideHeader?: boolean }) {
  const { t } = useTranslation();
  const { todos, completedTodos, loading, createTodo, completeTodo, removeTodoFromList, deleteTodo, fetchCompletedTodos } = useTodos();
  const [inputValue, setInputValue] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [showCompleted, setShowCompleted] = useState(false);
  const [completingIds, setCompletingIds] = useState<Set<string>>(new Set());
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // 客户端挂载后从 localStorage 同步折叠状态（避免 SSR hydration mismatch）
  useEffect(() => {
    if (forceExpanded) {
      setCollapsed(false);
    } else {
      setCollapsed(readLocalBool(TODO_COLLAPSED_KEY));
    }
    setShowCompleted(readLocalBool(TODO_SHOW_COMPLETED_KEY));
  }, [forceExpanded]);

  const handleAddTodo = useCallback(
    async (refocus = true) => {
      const title = inputValue.trim();
      if (!title || isSubmitting) return;
      setIsSubmitting(true);
      setInputValue("");
      // useTodos.createTodo 内部已实现乐观 UI：立即插入列表
      await createTodo(title);
      setIsSubmitting(false);
      // 回车提交后保持焦点方便连续输入；失焦提交则不再抢回焦点
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

  const handlePlusClick = useCallback(() => {
    // 展开面板并聚焦输入框，直接进入"新建待办"态
    setCollapsed(false);
    try { localStorage.setItem(TODO_COLLAPSED_KEY, "0"); } catch { /* noop */ }
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  const handleToggleComplete = useCallback(
    async (id: string) => {
      setCompletingIds((prev) => new Set(prev).add(id));
      await completeTodo(id);
      // 无论是否展开，都刷新已完成列表，保证"查看更多"数字实时更新
      fetchCompletedTodos();
      // 300ms 淡出动画后移除
      setTimeout(() => {
        removeTodoFromList(id);
        setCompletingIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }, 300);
    },
    [completeTodo, removeTodoFromList, fetchCompletedTodos]
  );

  const handleDelete = useCallback(
    async (id: string) => {
      await deleteTodo(id);
      // 无论是否展开，都刷新已完成列表，保证"查看更多"数字实时更新
      fetchCompletedTodos();
    },
    [deleteTodo, fetchCompletedTodos]
  );

  // 展开/收起"已完成"列表：展开时拉取已完成待办
  const handleToggleCompleted = useCallback(() => {
    setShowCompleted((prev) => {
      const next = !prev;
      try { localStorage.setItem(TODO_SHOW_COMPLETED_KEY, next ? "1" : "0"); } catch { /* noop */ }
      if (next) fetchCompletedTodos();
      return next;
    });
  }, [fetchCompletedTodos]);

  // 展开/收起动画
  useEffect(() => {
    if (!listRef.current) return;
    if (collapsed) {
      listRef.current.style.maxHeight = "0px";
      listRef.current.style.opacity = "0";
    } else {
      listRef.current.style.maxHeight = "160px";
      listRef.current.style.opacity = "1";
    }
  }, [collapsed]);

  // 挂载时拉取一次已完成待办，保证"查看更多"数字初始即准确
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
      }}
    >
      {/* 可折叠 Header：左侧折叠按钮 + 右侧常显 "+" 新建按钮 */}
      {!hideHeader && (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
        }}
      >
        <button
          onClick={() => {
            setCollapsed((c) => {
              const next = !c;
              try { localStorage.setItem(TODO_COLLAPSED_KEY, next ? "1" : "0"); } catch { /* noop */ }
              return next;
            });
          }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            flex: 1,
            minWidth: 0,
            padding: "6px 8px",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            outline: "none",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
        >
          <ChevronRight
            style={{
              width: "13px",
              height: "13px",
              color: "var(--text-level-4)",
              flexShrink: 0,
              transform: collapsed ? "rotate(0deg)" : "rotate(90deg)",
              transition: "transform var(--transition-fast)",
            }}
          />
          <ListTodo style={{ width: "13px", height: "13px", color: "var(--text-level-4)", flexShrink: 0 }} />
          <span
            style={{
              fontSize: "11px",
              fontWeight: "600",
              color: "var(--text-level-4)",
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              whiteSpace: "nowrap",
            }}
          >
            {t("todo.title")}
          </span>
          {/* Badge：未完成数量 */}
          {pendingCount > 0 && (
            <span
              style={{
                marginLeft: "auto",
                minWidth: "16px",
                height: "16px",
                padding: "0 5px",
                borderRadius: "8px",
                background: "var(--color-primary)",
                color: "#fff",
                fontSize: "10px",
                fontWeight: "600",
                lineHeight: "16px",
                textAlign: "center",
                flexShrink: 0,
              }}
            >
              {pendingCount}
            </span>
          )}
        </button>
        {/* 常显 "+"：新建待办入口（展开 + 聚焦输入框） */}
        <button
          onClick={handlePlusClick}
          title={t("todo.add")}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "22px",
            height: "22px",
            borderRadius: "var(--radius-sm)",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            color: "var(--text-level-4)",
            flexShrink: 0,
            padding: 0,
            outline: "none",
            transition: "background var(--transition-fast), color var(--transition-fast)",
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

      {/* 待办列表 + 输入框区域（可折叠） */}
      <div
        ref={listRef}
        style={{
          overflowY: "auto",
          maxHeight: "160px",
          opacity: 1,
          transition: "max-height var(--transition-normal), opacity var(--transition-normal)",
        }}
      >
        {/* 待办列表：空列表不渲染任何占位（无大灰框），列表区自然收缩，仅留标题行与内嵌输入框 */}
        <div style={{ padding: "0 4px" }}>
          {loading ? (
            <div style={{ padding: "4px 8px", textAlign: "center" }}>
              <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>
                {t("common.loading")}
              </span>
            </div>
          ) : (
            todos.map((todo) => {
              const isCompleting = completingIds.has(todo.id);
              return (
                <div
                  key={todo.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "2px 8px 2px 10px",
                    borderRadius: "var(--radius-sm)",
                    borderLeft: "2px solid transparent",
                    opacity: isCompleting ? 0 : 1,
                    transform: isCompleting ? "translateX(6px)" : "translateX(0)",
                    transition: "opacity 0.3s ease, transform 0.3s ease, background 0.15s ease, border-color 0.15s ease",
                    position: "relative",
                  }}
                  onMouseEnter={(e) => {
                    if (!isCompleting) {
                      e.currentTarget.style.background = "var(--bg-level-3)";
                      e.currentTarget.style.borderLeftColor = "var(--color-primary)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.borderLeftColor = "transparent";
                  }}
                >
                  {/* 自定义圆形 Checkbox */}
                  <button
                    onClick={() => handleToggleComplete(todo.id)}
                    disabled={isCompleting}
                    title={t("todo.complete")}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "16px",
                      height: "16px",
                      borderRadius: "50%",
                      border: "1.5px solid var(--text-level-4)",
                      background: "transparent",
                      cursor: "pointer",
                      flexShrink: 0,
                      padding: 0,
                      outline: "none",
                      transition: "border-color 0.15s, background 0.15s, transform 0.1s ease",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = "var(--color-primary)";
                      e.currentTarget.style.background = "var(--color-primary-faint, rgba(99,102,241,0.1))";
                    }}
                    onMouseDown={(e) => { if (!isCompleting) e.currentTarget.style.transform = "scale(0.85)"; }}
                    onMouseUp={(e) => { e.currentTarget.style.transform = "scale(1)"; }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = "var(--text-level-4)";
                      e.currentTarget.style.background = "transparent";
                      e.currentTarget.style.transform = "scale(1)";
                    }}
                  >
                    {isCompleting && (
                      <Check
                        style={{
                          width: "10px",
                          height: "10px",
                          color: "var(--color-primary)",
                        }}
                      />
                    )}
                  </button>

                  {/* 待办文字 */}
                  <span
                    style={{
                      flex: 1,
                      fontSize: "12px",
                      lineHeight: 1.4,
                      color: "var(--text-level-2)",
                      textDecoration: isCompleting ? "line-through" : "none",
                      wordBreak: "break-word",
                      transition: "text-decoration 0.2s",
                    }}
                  >
                    {todo.title}
                  </span>

                  {/* 删除按钮（hover 显示） */}
                  <button
                    onClick={() => handleDelete(todo.id)}
                    title={t("common.delete")}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "18px",
                      height: "18px",
                      borderRadius: "var(--radius-sm)",
                      border: "none",
                      background: "transparent",
                      cursor: "pointer",
                      color: "var(--text-level-4)",
                      opacity: 0,
                      transition: "opacity 0.15s",
                      flexShrink: 0,
                      padding: 0,
                      outline: "none",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.color = "var(--color-error)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-level-4)"; }}
                  >
                    <Trash2 style={{ width: "11px", height: "11px" }} />
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* 扁平内嵌式输入框 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "2px 12px 4px",
          }}
        >
          <span
            style={{
              width: "16px",
              height: "16px",
              borderRadius: "50%",
              border: "1.5px dashed var(--text-level-4)",
              flexShrink: 0,
              opacity: 0.5,
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
                opacity: isSubmitting ? 0.6 : 1,
              }}
            >
              <Check style={{ width: "12px", height: "12px" }} />
            </button>
          )}
        </div>

        {/* 查看更多：仅在有已完成待办时显示 */}
        {completedTodos.length > 0 && (
        <div
          style={{
            borderTop: "1px solid var(--border-primary, rgba(255,255,255,0.06))",
            margin: "2px 8px 4px",
            paddingTop: "4px",
          }}
        >
          <button
            onClick={handleToggleCompleted}
            title={showCompleted ? t("todo.hideCompleted") : t("todo.viewCompleted")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              color: "var(--text-level-4)",
              fontSize: "10.5px",
              padding: "2px 6px",
              borderRadius: "var(--radius-sm)",
              outline: "none",
              transition: "color var(--transition-fast), background var(--transition-fast)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
              e.currentTarget.style.color = "var(--text-level-2)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--text-level-4)";
            }}
          >
            <ChevronRight
              style={{
                width: "11px",
                height: "11px",
                flexShrink: 0,
                transform: showCompleted ? "rotate(90deg)" : "rotate(0deg)",
                transition: "transform var(--transition-fast)",
              }}
            />
            <span>
              {showCompleted
                ? t("todo.hideCompleted")
                : `${t("todo.viewCompleted")}${completedTodos.length > 0 ? ` (${completedTodos.length})` : ""}`}
            </span>
          </button>

          {/* 已完成列表 */}
          {showCompleted && (
            <div style={{ padding: "2px 0 0" }}>
              {completedTodos.length === 0 ? (
                <div style={{ padding: "4px 6px", fontSize: "11px", color: "var(--text-level-4)" }}>
                  {t("todo.noCompleted")}
                </div>
              ) : (
                completedTodos.map((todo) => (
                  <div
                    key={todo.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "3px 6px",
                      borderRadius: "var(--radius-sm)",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                  >
                    <span
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: "14px",
                        height: "14px",
                        borderRadius: "50%",
                        border: "1.5px solid var(--color-primary)",
                        background: "var(--color-primary-faint, rgba(99,102,241,0.1))",
                        flexShrink: 0,
                      }}
                    >
                      <Check style={{ width: "9px", height: "9px", color: "var(--color-primary)" }} />
                    </span>
                    <span
                      style={{
                        flex: 1,
                        fontSize: "11.5px",
                        lineHeight: 1.4,
                        color: "var(--text-level-4)",
                        textDecoration: "line-through",
                        wordBreak: "break-word",
                        minWidth: 0,
                      }}
                    >
                      {todo.title}
                    </span>
                    <button
                      onClick={() => handleDelete(todo.id)}
                      title={t("common.delete")}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: "16px",
                        height: "16px",
                        borderRadius: "var(--radius-sm)",
                        border: "none",
                        background: "transparent",
                        cursor: "pointer",
                        color: "var(--text-level-4)",
                        opacity: 0,
                        transition: "opacity 0.15s",
                        flexShrink: 0,
                        padding: 0,
                        outline: "none",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.color = "var(--color-error)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-level-4)"; }}
                    >
                      <Trash2 style={{ width: "10px", height: "10px" }} />
                    </button>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
        )}
      </div>
    </div>
  );
}
