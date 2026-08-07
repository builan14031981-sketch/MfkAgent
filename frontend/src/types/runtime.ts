import type { ToolCall } from "@/components/ToolCallCard";

/**
 * Runtime Event 类型判别字段（单一判别依据，SSE 事件 type 直接映射）。
 *
 * 当前渲染支持：thinking / tool / approval / text / task_started / task_completed / task_failed
 * 未来扩展预留：verification / sub_agent / vision / memory
 * （扩展类型已纳入判别联合，渲染层按通用占位处理，字段可后续补充）
 */
export type RuntimeEventType =
  | "thinking"
  | "tool"
  | "approval"
  | "text"
  | "task_started"
  | "task_completed"
  | "task_failed"
  | "verification"
  | "sub_agent"
  | "vision"
  | "memory"
  | "token_usage";

/** 待审批命令（tool_approval 事件载荷） */
export interface ApprovalRequest {
  approval_id: string;
  tool_call_id: string;
  tool: string;
  command: string;
  risk_level: string;
  risk_reason: string;
  chat_id?: number;
}

/** G6-A：LLM 每轮思考结束后的 Token 消耗与上下文水位事件（不进入 timeline 渲染） */
export interface TokenUsageEvent extends RuntimeEventBase {
  type: "token_usage";
  /** 本轮提示词 Token 数 */
  prompt_tokens: number;
  /** 本轮生成 Token 数 */
  completion_tokens: number;
  /** 累计总 Token 数（prompt + completion） */
  total_tokens: number;
  /** 模型上下文窗口上限 */
  model_max_tokens: number;
  /** 上下文水位百分比（0-100） */
  watermark_percentage: number;
}

/** RuntimeEvent 公共基础字段 */
export interface RuntimeEventBase {
  /** 事件唯一 id（渲染 key；tool 事件复用 tool_call_id 保证原地更新） */
  id: string;
  /** 事件类型判别字段 */
  type: RuntimeEventType;
  /** SSE 到达序号（可选，未来时间线排序/重放用） */
  seq?: number;
  /** 事件发生时间戳（可选，未来可视化用） */
  ts?: number;
}

/** 思考段：连续 thinking 增量合并到同一事件（中间穿插 tool 则新建） */
export interface ThinkingEvent extends RuntimeEventBase {
  type: "thinking";
  content: string;
}

/** 工具调用：tool_start 新建，tool_result 按 tool_call_id 原地更新（不移动位置） */
export interface ToolEvent extends RuntimeEventBase {
  type: "tool";
  toolCallId: string;
  toolCall: ToolCall;
}

/** 待审批命令：tool_approval 新建，tool_result 时按 tool_call_id 移除 */
export interface ApprovalEvent extends RuntimeEventBase {
  type: "approval";
  approval: ApprovalRequest;
}

/** 文本段：连续文本 chunk 合并到同一事件 */
export interface TextEvent extends RuntimeEventBase {
  type: "text";
  content: string;
}

// ============================================================================
// Task 事件（多 Agent 任务协同）：task_started / task_completed / task_failed
// ============================================================================

/** 任务生命周期状态 */
export type TaskStatus = "pending" | "running" | "completed" | "failed";

/**
 * 任务节点（运行时累积状态）。
 * 由 task_started 创建，task_completed / task_failed 原地更新对应 task_id。
 */
export interface TaskNode {
  /** 任务唯一 id */
  task_id: string;
  /** 任务内容（人类可读的动作描述） */
  action: string;
  /** 当前状态 */
  status: TaskStatus;
  /** 被分配执行的 Agent 标识（如 coding_agent / research_agent） */
  assigned_agent: string;
  /** 失败时的错误信息（仅 status=failed 时存在） */
  error?: string;
  /** 任务开始时间戳（task_started 时写入，用于排序） */
  started_at?: number;
  /** 任务结束时间戳（completed/failed 时写入） */
  ended_at?: number;
}

/** task_started 事件：新建一个 running 状态的任务节点 */
export interface TaskStartedEvent extends RuntimeEventBase {
  type: "task_started";
  task: TaskNode;
}

/** task_completed 事件：将对应 task_id 的任务更新为 completed */
export interface TaskCompletedEvent extends RuntimeEventBase {
  type: "task_completed";
  task: TaskNode;
}

/** task_failed 事件：将对应 task_id 的任务更新为 failed，并携带 error */
export interface TaskFailedEvent extends RuntimeEventBase {
  type: "task_failed";
  task: TaskNode;
}

/** 三种 Task 事件的联合，便于 hook 统一接收 */
export type TaskEvent =
  | TaskStartedEvent
  | TaskCompletedEvent
  | TaskFailedEvent;

/**
 * 未来扩展事件（verification / sub_agent / vision / memory）：
 * 仅提供最小通用结构 + 类型判别，确保类型系统与渲染层可前瞻兼容；
 * 具体字段在对应功能落地时按 type 细化。
 */
export interface ExtensionEvent extends RuntimeEventBase {
  type: "verification" | "sub_agent" | "vision" | "memory";
  /** 通用负载（未来扩展时按 type 细化为强类型） */
  payload?: unknown;
  /** 通用标题（渲染占位卡片用） */
  title?: string;
  /** 通用内容摘要（渲染占位卡片用） */
  content?: string;
}

/** Runtime Event 判别联合：渲染层按 type 分发 */
export type RuntimeEvent =
  | ThinkingEvent
  | ToolEvent
  | ApprovalEvent
  | TextEvent
  | TaskStartedEvent
  | TaskCompletedEvent
  | TaskFailedEvent
  | ExtensionEvent;
