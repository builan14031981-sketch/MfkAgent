/** 后端 API 基址：优先读环境变量，缺省回退本地默认端口（Electron 桌面应用场景） */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8001";

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

// ──── 附件图片 URL 构造（ChatMessage + ImageLightbox 共用） ────

/** 构造消息附件图片的后端访问 URL */
export function getAttachmentImageUrl(chatId: number, path: string): string {
  return `${API_BASE}/api/chat/${chatId}/file?path=${encodeURIComponent(path)}`;
}

// ──── 安全中心（专业向安全可视化，只读） ────

export type PolicyAction = "allow" | "approve" | "block";

export interface PolicyTool {
  name: string;
  category: string;
  reason: string;
  read_only: boolean;
  actions: Record<string, PolicyAction>;
}

export interface PolicyData {
  modes: string[];
  read_only_tools: string[];
  write_tools: PolicyTool[];
  note: string;
}

export async function getSecurityPolicy(): Promise<PolicyData> {
  return apiGet<PolicyData>("/api/security/policy");
}

export interface SecurityStatus {
  sandbox_path_guard: boolean;
  forbidden_dirs_enabled: boolean;
  disk_quota_gb: Record<string, number>;
  run_command_timeout_sec: number;
  execute_command_timeout_sec: number;
  execute_command_output_chars: number;
  plan_readonly: boolean;
}

export async function getSecurityStatus(): Promise<SecurityStatus> {
  return apiGet<SecurityStatus>("/api/security/status");
}

export interface AuditItem {
  id: number;
  chat_id: number | null;
  agent_run_id: number | null;
  tool_name: string;
  command: string;
  cwd: string | null;
  duration_ms: number;
  exit_code: number | null;
  output_size: number;
  success: boolean;
  error_message: string | null;
  created_at: string | null;
}

export interface AuditPage {
  total: number;
  offset: number;
  limit: number;
  items: AuditItem[];
}

export interface AuditQuery {
  limit?: number;
  offset?: number;
  tool_name?: string;
  success?: boolean;
}

export async function getAuditLogs(query: AuditQuery = {}): Promise<AuditPage> {
  const params = new URLSearchParams();
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  if (query.offset !== undefined) params.set("offset", String(query.offset));
  if (query.tool_name) params.set("tool_name", query.tool_name);
  if (query.success !== undefined) params.set("success", String(query.success));
  const qs = params.toString();
  return apiGet<AuditPage>(`/api/security/audit${qs ? `?${qs}` : ""}`);
}

/** 构造审计日志 CSV 导出下载 URL（含当前筛选） */
export function getAuditExportUrl(query: { tool_name?: string; success?: boolean } = {}): string {
  const params = new URLSearchParams();
  if (query.tool_name) params.set("tool_name", query.tool_name);
  if (query.success !== undefined) params.set("success", String(query.success));
  const qs = params.toString();
  return `${API_BASE}/api/security/audit/export${qs ? `?${qs}` : ""}`;
}

// ──── 应用日志 ────

export interface LogFileInfo {
  name: string;
  size: number;
  modified: string;
}

export interface LogFileList {
  files: LogFileInfo[];
}

export interface LogLine {
  timestamp: string;
  level: string;
  message: string;
  raw: string;
}

export interface LogPage {
  total: number;
  page: number;
  page_size: number;
  lines: LogLine[];
}

export async function getLogFiles(): Promise<LogFileList> {
  return apiGet<LogFileList>("/api/security/logs");
}

export async function getLogContent(params: {
  level?: string;
  search?: string;
  page?: number;
  page_size?: number;
}): Promise<LogPage> {
  const qp = new URLSearchParams();
  if (params.level) qp.set("level", params.level);
  if (params.search) qp.set("search", params.search);
  if (params.page !== undefined) qp.set("page", String(params.page));
  if (params.page_size !== undefined) qp.set("page_size", String(params.page_size));
  const qs = qp.toString();
  return apiGet<LogPage>(`/api/security/logs/current${qs ? `?${qs}` : ""}`);
}

export function getLogDownloadUrl(): string {
  return `${API_BASE}/api/security/logs/download`;
}

// ──── 审批记录 ────

export type ApprovalStatus = "pending" | "approve" | "deny" | "timeout" | "cancelled";

export interface ApprovalItem {
  id: number;
  approval_id: string;
  tool_name: string;
  command: string | null;
  risk_level: string;
  risk_reason: string | null;
  status: ApprovalStatus;
  created_at: string | null;
  resolved_at: string | null;
}

export interface ApprovalPage {
  total: number;
  offset: number;
  limit: number;
  items: ApprovalItem[];
}

export interface ApprovalQuery {
  limit?: number;
  offset?: number;
  status?: ApprovalStatus;
  tool_name?: string;
}

export async function getApprovals(query: ApprovalQuery = {}): Promise<ApprovalPage> {
  const qp = new URLSearchParams();
  if (query.limit !== undefined) qp.set("limit", String(query.limit));
  if (query.offset !== undefined) qp.set("offset", String(query.offset));
  if (query.status) qp.set("status", query.status);
  if (query.tool_name) qp.set("tool_name", query.tool_name);
  const qs = qp.toString();
  return apiGet<ApprovalPage>(`/api/security/approvals${qs ? `?${qs}` : ""}`);
}

// ──── 命令风险预览 ────

export type RiskVerdict = "allow" | "require_approval" | "high_risk" | "deny";
export type RiskLevel = "read_only" | "write" | "destructive";

export interface CommandRiskResult {
  verdict: RiskVerdict;
  risk_level: RiskLevel;
  reason: string;
  command: string;
}

export async function previewCommandRisk(params: {
  command: string;
  mode?: "build" | "plan";
  engine?: "run_command" | "execute_command";
}): Promise<CommandRiskResult> {
  return apiPost<CommandRiskResult>("/api/security/command-risk", params);
}

// ──── 防护清单 ────

export interface AllowedCommand {
  command: string;
  allowed_args: string[] | null;
}

export interface GuardrailTool {
  name: string;
  verdict: RiskVerdict;
  risk_level: RiskLevel;
  reason: string;
}

export interface GuardrailsData {
  forbidden_dirs: string[];
  allowed_commands: AllowedCommand[];
  read_only_tools: string[];
  write_tools: GuardrailTool[];
  disk_quota_gb: Record<string, number>;
}

export async function getGuardrails(): Promise<GuardrailsData> {
  return apiGet<GuardrailsData>("/api/security/guardrails");
}

// ──── 子代理（Sub-Agent）管理 ────

export interface SubAgent {
  id: string;
  name: string;
  description: string;
  avatar: string;
  identity: string;
  capabilities: string[];
  status: string;
  allowed_tools: string[];
  parent_agent_id: string | null;
  is_builtin: boolean;
}

export interface SubAgentInput {
  agent_id: string;
  name: string;
  description?: string;
  avatar?: string;
  identity?: string;
  capabilities?: string[];
  status?: string;
  allowed_tools?: string[];
  parent_agent_id?: string | null;
}

export async function getSubAgents(): Promise<SubAgent[]> {
  return apiGet<SubAgent[]>("/api/sub-agents");
}

export async function getSubAgent(id: string): Promise<SubAgent> {
  return apiGet<SubAgent>(`/api/sub-agents/${encodeURIComponent(id)}`);
}

export async function createSubAgent(input: SubAgentInput): Promise<SubAgent> {
  return apiPost<SubAgent>("/api/sub-agents", input);
}

export async function updateSubAgent(id: string, updates: Partial<SubAgentInput>): Promise<SubAgent> {
  return apiPatch<SubAgent>(`/api/sub-agents/${encodeURIComponent(id)}`, updates);
}

export async function deleteSubAgent(id: string): Promise<void> {
  await apiDelete(`/api/sub-agents/${encodeURIComponent(id)}`);
}

export interface SubAgentToolName {
  tools: string[];
}

export async function getSubAgentAvailableTools(): Promise<SubAgentToolName> {
  return apiGet<SubAgentToolName>("/api/sub-agents/available-tools");
}
