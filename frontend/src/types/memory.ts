/**
 * 记忆类型：Phase 10 Memory 2.0 自动提炼引擎产出。
 * 旧数据（V1）可能缺失该字段，组件读取时必须用 `memory_type || "fact"` 兜底，
 * 严禁假设字段必然存在导致空指针/渲染异常。
 */
export type MemoryType = "preference" | "fact" | "workflow" | "project";

export interface MemoryItem {
  id: number;
  scope: "global" | "agent" | "project";
  agent_id: string | null;
  project_id: number | null;
  content: string;
  created_at: string;
  /** Phase 10 新增（可选，向后兼容）：记忆分类 */
  memory_type?: MemoryType;
  /** Phase 10 新增（可选）：提炼置信度，范围 0-1 */
  confidence?: number;
  /** Phase 10 新增（可选）：来源会话 ID */
  source_chat_id?: number;
}

export type MemoryScope = "global" | "agent" | "project";
