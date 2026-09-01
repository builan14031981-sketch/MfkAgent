/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback, useMemo } from "react";
import { apiGet, apiPatch } from "@/lib/api";
import { useSettingsStore } from "@/lib/store";

export interface Agent {
  id: string;
  name: string;
  description: string;
  avatar: string;
  system_prompt: string;
  identity: string;
  capabilities: string[];
  status: string;
  default_personality_level?: number | null;
  expression_profile?: string | null;
  group?: string;
}

/**
 * Agent 英文名映射（英文模式下显示）。
 * 中文模式显示后端返回的中文名，英文模式显示这里的英文名。
 * 未配置的 agent 英文模式下保持中文名。
 *
 * ⚠️ 与 agents 表的中文名是两套数据：改中文名（DB）后必须同步这张表，
 *    否则英文模式会继续用旧名（2026-08-31 批量改名时就发生过一次）。
 */
const AGENT_EN_NAMES: Record<string, string> = {
  // ── 主 agent：意象概念名，与中文名同源（固本=稳固根基 / 明鉴=明镜照见 …）──
  general: "An",
  coder: "Bedrock",
  frontend_ui: "Compass",
  g: "Lucent",
  spark: "Lumen",
  pianai: "Solace",
  writer_jiangnan: "Tide",
  defense_ppt_expert: "Folio",
  creative_image: "Palette",
  sts2_coach: "STS2 Coach",
  // ── 隐藏主 agent ──
  product: "Strategist",
  writer: "Quill",
  writer_narrative: "Narrator",
  personal: "Aide",
  research: "Scout",
  // ── 子代理：功能描述名，不套意象 ──
  sub_code_reviewer: "Code Reviewer",
  sub_researcher: "Web Researcher",
  sub_file_analyst: "File Analyst",
  sub_architecture: "Architect",
  sub_backend: "Backend Engineer",
  sub_frontend: "Frontend Engineer",
  sub_testing: "Test Engineer",
  sub_security: "Security Auditor",
};

/**
 * 解析 agent 显示名。
 *
 * 供「只有 agent_id + 后端中文名、拿不到 agents 列表」的场景使用——
 * 典型是 SSE 时间线里的圆桌发言：名字由后端 roundtable_runtime 用 seat.name 直接下发，
 * 不经过 useAgents 的中文→英文转换，英文模式下会露中文。
 *
 * 在**渲染层**翻译而非入库时翻译：切语言即时生效，历史消息也会跟着变。
 */
export function useAgentDisplayName() {
  const locale = useSettingsStore((s) => s.settings?.language ?? "zh-CN");
  return useCallback(
    (agentId?: string | null, fallback?: string | null): string => {
      const base = fallback || "Agent";
      if (locale !== "en-US" || !agentId) return base;
      return AGENT_EN_NAMES[agentId] ?? base;
    },
    [locale]
  );
}

// 跨实例同步事件：任一实例变更 agents 后广播，所有实例立即重新拉取
export const AGENTS_CHANGED_EVENT = "mfk-agents-changed";

// 跨模块同步事件：其他模块（ProjectInitModal 打开等）触发全局 agents 刷新，
// 供那些不方便调 useAgents() 的场景使用（如 Portal 内的子组件、需主动校验场景）。
export const AGENTS_REFRESH_EVENT = "mfk-agents-refresh";

/** 全局触发 agents 列表刷新（供 ProjectInitModal 等主动调用） */
export function triggerAgentsRefresh() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AGENTS_REFRESH_EVENT));
  }
}

export function useAgents() {
  const [rawAgents, setRawAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const locale = useSettingsStore((s) => s.settings?.language ?? "zh-CN");

  const fetchAgents = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiGet<Agent[]>("/api/agents");
      setRawAgents(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  // 根据当前语言转换 agent 显示名：英文模式下用英文名，中文模式下用后端中文名
  const agents = useMemo(() => {
    if (locale === "en-US") {
      return rawAgents.map((a) => ({
        ...a,
        name: AGENT_EN_NAMES[a.id] ?? a.name,
      }));
    }
    return rawAgents;
  }, [rawAgents, locale]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  // 监听其他实例的变更事件，实时同步
  useEffect(() => {
    const handler = () => {
      fetchAgents();
    };
    window.addEventListener(AGENTS_CHANGED_EVENT, handler);
    return () => window.removeEventListener(AGENTS_CHANGED_EVENT, handler);
  }, [fetchAgents]);

  // 监听外部触发的全局刷新事件（如 ProjectInitModal 打开时主动调用）
  useEffect(() => {
    const handler = () => {
      fetchAgents();
    };
    window.addEventListener(AGENTS_REFRESH_EVENT, handler);
    return () => window.removeEventListener(AGENTS_REFRESH_EVENT, handler);
  }, [fetchAgents]);

  // 变更成功后刷新本实例并向所有实例广播
  const refreshAndBroadcast = useCallback(async () => {
    await fetchAgents();
    window.dispatchEvent(new Event(AGENTS_CHANGED_EVENT));
  }, [fetchAgents]);

  async function updateAgent(id: string, updates: Partial<Agent>) {
    await apiPatch(`/api/agents/${id}`, updates);
    await refreshAndBroadcast();
  }

  return { agents, loading, error, updateAgent };
}