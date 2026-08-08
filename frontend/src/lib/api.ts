export const API_BASE = "http://127.0.0.1:8001";

/** 请求默认超时（ms） */
export const DEFAULT_TIMEOUT_MS = 30_000;

/** 错误分类 */
export type ApiErrorKind = "network" | "timeout" | "http" | "abort";

/**
 * 统一 API 错误：继承 Error 保证现有 `err instanceof Error` 兼容，
 * 额外带 status / kind 便于上层分类提示。
 */
export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;

  constructor(kind: ApiErrorKind, message: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

/**
 * 基于 AbortController + setTimeout 实现请求超时，避免请求永久悬挂。
 * 注意：fetch 的 AbortError 无法区分「超时」与「外部 signal 主动中断」，
 * 因此对外部 signal 的中断我们抛 "abort"，而仅超时（timeoutId 触发）抛 "timeout"。
 */
function createAbortController(
  timeoutMs: number,
  signal?: AbortSignal | null
): { controller: AbortController | null; timeoutId: ReturnType<typeof setTimeout> | null } {
  if (timeoutMs <= 0) return { controller: null, timeoutId: null };
  const controller = new AbortController();
  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener("abort", () => controller.abort(), { once: true });
    }
  }
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  return { controller, timeoutId };
}

export async function apiFetch(path: string, options: RequestInit & { timeout?: number } = {}) {
  const { timeout = DEFAULT_TIMEOUT_MS, ...rest } = options;
  const { controller, timeoutId } = createAbortController(timeout, rest.signal);
  const fetchOptions: RequestInit = { ...rest };
  if (controller) fetchOptions.signal = controller.signal;
  const timedOut = timeoutId !== null;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, fetchOptions);
  } catch (err) {
    const aborted = err instanceof DOMException && err.name === "AbortError";
    if (aborted && timedOut && timeoutId) {
      clearTimeout(timeoutId);
      throw new ApiError("timeout", `请求超时（${timeout}ms）`, null);
    }
    if (aborted) {
      throw new ApiError("abort", "请求已取消", null);
    }
    throw new ApiError("network", "网络错误：无法连接到服务器", null);
  }
  if (timeoutId) clearTimeout(timeoutId);

  if (!res.ok) {
    // 尝试读取后端错误体（部分接口返回 { detail: ... }）
    let detail: string | null = null;
    try {
      const body = await res.text();
      if (body) {
        try {
          const parsed = JSON.parse(body);
          if (typeof parsed === "string") detail = parsed;
          else if (parsed && typeof parsed.detail === "string") detail = parsed.detail;
          else if (parsed && typeof parsed.error === "string") detail = parsed.error;
          else if (parsed && typeof parsed.message === "string") detail = parsed.message;
        } catch {
          detail = body.slice(0, 200);
        }
      }
    } catch {
      /* 读 body 失败则忽略 */
    }
    const message = detail || `请求失败（HTTP ${res.status}）`;
    throw new ApiError("http", message, res.status);
  }
  return res;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await apiFetch(path);
  return res.json();
}

export async function apiPost<T>(path: string, data: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function apiPatch<T>(path: string, data: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function apiPut<T>(path: string, data: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function apiDelete(path: string): Promise<void> {
  await apiFetch(path, { method: "DELETE" });
}

// ──── G6-B 会话压缩 ────

export interface CompressResponse {
  messages: Array<{
    id: number;
    chat_id: number;
    role: string;
    content: string;
    thinking?: string;
    tool_calls?: Array<Record<string, unknown>>;
    timeline?: Array<Record<string, unknown>>;
    created_at: string;
  }>;
  compressed: boolean;
  original_count: number;
  compressed_count: number;
}

export async function compressMessages(chatId: number, keepRecent = 4): Promise<CompressResponse> {
  return apiPost<CompressResponse>(`/api/chat/${chatId}/compress`, { keep_recent: keepRecent });
}
