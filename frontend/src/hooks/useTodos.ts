import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/api";

export interface Todo {
  id: string;
  project_id: number | null;
  title: string;
  status: "pending" | "completed";
  created_at: string;
  updated_at: string;
}

let optimisticSeq = 0;

export function useTodos() {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [completedTodos, setCompletedTodos] = useState<Todo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTodos = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiGet<Todo[]>(`/api/todos?status=pending`);
      setTodos(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch todos");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchCompletedTodos = useCallback(async () => {
    try {
      setError(null);
      const data = await apiGet<Todo[]>(`/api/todos?status=completed`);
      setCompletedTodos(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch completed todos");
    }
  }, []);

  const createTodo = useCallback(async (title: string) => {
    // 乐观 UI：先插入临时 todo 到列表顶部，再异步发送 POST
    const tempId = `optimistic-${++optimisticSeq}`;
    const now = new Date().toISOString();
    const optimisticTodo: Todo = {
      id: tempId,
      project_id: null,
      title,
      status: "pending",
      created_at: now,
      updated_at: now,
    };
    setTodos((prev) => [optimisticTodo, ...prev]);

    try {
      const realTodo = await apiPost<Todo>("/api/todos", { title, status: "pending" });
      // 用后端返回的真实 todo 替换临时条目
      setTodos((prev) => prev.map((t) => (t.id === tempId ? realTodo : t)));
      return realTodo;
    } catch (err) {
      // 创建失败：移除乐观条目
      setTodos((prev) => prev.filter((t) => t.id !== tempId));
      setError(err instanceof Error ? err.message : "Failed to create todo");
      return null;
    }
  }, []);

  const completeTodo = useCallback(async (id: string) => {
    try {
      await apiPatch<Todo>(`/api/todos/${id}`, { status: "completed" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update todo");
    }
  }, []);

  const removeTodoFromList = useCallback((id: string) => {
    setTodos((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const deleteTodo = useCallback(async (id: string) => {
    // 乐观删除：立即从列表移除
    setTodos((prev) => prev.filter((t) => t.id !== id));
    try {
      await apiDelete(`/api/todos/${id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete todo");
      // 删除失败：重新拉取以恢复
      fetchTodos();
    }
  }, [fetchTodos]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchTodos();
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchTodos]);

  return { todos, completedTodos, loading, error, fetchTodos, fetchCompletedTodos, createTodo, completeTodo, removeTodoFromList, deleteTodo };
}
