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
  | "thinking_indicator"
  | "tool"
  | "approval"
  | "user_choice"
  | "text"
  | "task_started"
  | "task_completed"
  | "task_failed"
  | "task_skipped"
  | "verification"
  | "sub_agent"
  | "vision"
  | "memory"
  | "memory_saved"
  | "token_usage"
  | "agent_state_update"
  | "roundtable_speaker_start"
  | "roundtable_speaker_end";

/** 待审批命令（tool_approval 事件载荷） */
export interface ApprovalRequest {
  approval_id: string;
  tool_call_id: string;
  tool: string;
  command: string;
  risk_level: string;
  risk_reason: string;
  chat_id?: number;
  /** Phase 1.5：用户审批后标记只读状态（undefined=待审批 / approved / rejected） */
  resolvedAction?: "approved" | "rejected";
}

/** 待抉择（choice_request 事件载荷，对齐后端 make_choice_request）。
 *  - choice_id：后端 choice_registry 生成的唯一 id
 *  - options：2-4 项，每项 {label, description}
 *  - recommended：后端推荐项下标（前端高亮）
 *  - allow_custom：是否允许用户输入自定义想法
 *  - resolvedAction：用户已选择/跳过后的只读状态（undefined=待抉择）
 */
export interface UserChoiceRequest {
  choice_id: string;
  tool_call_id: string;
  question: string;
  options: Array<{ label: string; description: string }>;
  recommended: number | null;
  allow_custom: boolean;
  chat_id?: number;
  created_at?: string;
  /** 用户操作后的状态：selected=N | skipped=true | timeout=true */
  resolvedAction?: { kind: "selected"; selected: number } | { kind: "skipped" } | { kind: "timeout" };
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

/**
 * Agent 状态流转事件（不进入 timeline 渲染，由独立 AgentStatusCard 消费）。
 * 后端在 SSE 流中推送，用于替代单调的"正在输入..."指示器。
 */
export interface AgentStateUpdateEvent extends RuntimeEventBase {
  type: "agent_state_update";
  /** Agent 角色名（如 "Coder Agent"） */
  agent_role: string;
  /** 状态：working=执行中 / waiting_for_tool=等待工具 / completed=完成 / error=出错 */
  status: "working" | "waiting_for_tool" | "completed" | "error";
  /** 当前动作详情（如 "准备调用工具: list_files"） */
  action_detail: string;
  /** 任务进度（如 "任务 1/5"） */
  task_progress: string;
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

/** 思考占位符：发送后立即可见，首 Token 前显示"正在思考..."指示器 */
export interface ThinkingIndicatorEvent extends RuntimeEventBase {
  type: "thinking_indicator";
  /** 已累积的思考文本（空串时仅显示指示器；有内容时显示折叠面板） */
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

/** 待抉择：choice_request 新建，tool_result 时保留为只读记录（V3 起不随 tool_result 移除） */
export interface UserChoiceEvent extends RuntimeEventBase {
  type: "user_choice";
  choice: UserChoiceRequest;
}

/** 文本段：连续文本 chunk 合并到同一事件 */
export interface TextEvent extends RuntimeEventBase {
  type: "text";
  content: string;
  agent_id?: string;
  agent_name?: string;
}

/** 自动提取并保存记忆后的可见通知（memory_saved 事件）。
 * 由后端在对话流推送：告知"已保存 N 条记忆"，非确认卡、不阻塞对话。
 * 同时持久化进 Message.timeline，刷新后随消息展示。 */
export interface MemorySavedEvent extends RuntimeEventBase {
  type: "memory_saved";
  /** 本次提取落库的记忆条数 */
  count: number;
  /** 每条记忆摘要（边栏提示展开项） */
  items: Array<{ memory_type: string; content: string }>;
  chat_id?: number;
}

// ============================================================================
// Task 事件（多 Agent 任务协同）：task_started / task_completed / task_failed
// ============================================================================

/** 任务生命周期状态 */
export type TaskStatus = "pending" | "running" | "completed" | "failed" | "skipped";

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

/** task_skipped 事件：依赖失败/图中断导致的任务跳过（不进入执行队列） */
export interface TaskSkippedEvent extends RuntimeEventBase {
  type: "task_skipped";
  task: TaskNode;
}

/** 四种 Task 事件的联合，便于 hook 统一接收 */
export type TaskEvent =
  | TaskStartedEvent
  | TaskCompletedEvent
  | TaskFailedEvent
  | TaskSkippedEvent;

/**
 * 未来扩展事件（verification / sub_agent / vision / memory）：
 * 仅提供最小通用结构 + 类型判别，确保类型系统与渲染层可前瞻兼容；
 * 具体字段在对应功能落地时按 type 细化。
 */
export interface ExtensionEvent extends RuntimeEventBase {
  /** 注意：sub_agent 已有专用 SubAgentEvent 类型，此处不再包含 */
  type: "verification" | "vision" | "memory";
  /** 通用负载（未来扩展时按 type 细化为强类型） */
  payload?: unknown;
  /** 通用标题（渲染占位卡片用） */
  title?: string;
  /** 通用内容摘要（渲染占位卡片用） */
  content?: string;
}

/**
 * 子代理编排事件（spawn_orchestration 工具编排过程中的进度事件）。
 * 由后端在工具执行时发射，前端按 id 原地更新：running → completed / failed。
 */
export interface SubAgentEvent extends RuntimeEventBase {
  type: "sub_agent";
  /** 角色 id（如 architecture / backend） */
  role: string;
  /** 角色展示名（如 架构师） */
  title: string;
  /** 当前状态：running=编排中 / completed=完成 / failed=失败 */
  status: "running" | "completed" | "failed";
  /** 进度摘要文本 */
  content: string;
}

/** Runtime Event 判别联合：渲染层按 type 分发 */
export interface RoundtableSpeakerStartEvent extends RuntimeEventBase {
  type: "roundtable_speaker_start";
  agent_id?: string;
  agent_name?: string;
}

export interface RoundtableSpeakerEndEvent extends RuntimeEventBase {
  type: "roundtable_speaker_end";
  agent_id?: string;
}

export type RuntimeEvent =
  | ThinkingEvent
  | ThinkingIndicatorEvent
  | ToolEvent
  | ApprovalEvent
  | UserChoiceEvent
  | TextEvent
  | MemorySavedEvent
  | TaskStartedEvent
  | TaskCompletedEvent
  | TaskFailedEvent
  | TaskSkippedEvent
  | SubAgentEvent
  | ExtensionEvent
  | RoundtableSpeakerStartEvent
  | RoundtableSpeakerEndEvent;
