export const API_BASE = "http://127.0.0.1:8001";

export async function apiFetch(path: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
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
