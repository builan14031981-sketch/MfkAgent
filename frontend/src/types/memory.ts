/**
 * 记忆类型：记忆重设计（2026-09）精简为 4 类长期记忆。
 * preference（偏好）/ fact（事实）/ workflow（工作流约定）/ project（项目规则）。
 * 旧的 user_preference / interaction_pattern / relationship_note / current_context
 * 不再入库（临时性/情绪类不落长期库）。
 * 旧数据（V1）可能缺失该字段，组件读取时必须用 `memory_type || "fact"` 兜底。
 */
export type MemoryType =
  | "preference"
  | "fact"
  | "workflow"
  | "project";

export interface MemoryItem {
  id: number;
  scope: "global" | "agent" | "project";
  agent_id: string | null;
  project_id: number | null;
  content: string;
  created_at: string;
  /** 记忆分类（4 类长期记忆；V1 旧数据可能缺失） */
  memory_type?: MemoryType;
  /** 提炼置信度，范围 0-1 */
  confidence?: number;
  /** 来源会话 ID */
  source_chat_id?: number;
  /**
   * 待认领归属标记：模型判为项目级但会话未绑项目时，暂存 global 并置 true。
   * 未认领的记忆不参与上下文注入，仅在前端"待认领"区展示，可归属到具体项目。
   */
  needs_attribution?: boolean;
}

export type MemoryScope = "global" | "agent" | "project";
