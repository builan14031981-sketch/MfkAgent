import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { RuntimeEvent, TaskNode, TokenUsageEvent, AgentStateUpdateEvent } from "@/types/runtime";

/**
 * 流式加载阶段（对应 ThinkingOrb 动画状态）：
 * - working    — 已发送、等待首个事件
 * - solving    — 正在思考（thinking 事件）
 * - searching  — 正在调用工具（tool 事件）
 * - listening  — 等待用户审批（approval 事件）
 * - composing  — 正在生成正文（text 事件）
 */
export type OrbStage = "working" | "solving" | "searching" | "listening" | "composing";

/** 单个会话的响应式流状态（存储在 Zustand 中，驱动 UI 渲染） */
export interface StreamSessionState {
  isSending: boolean;
  timeline: RuntimeEvent[];
  tasks: TaskNode[];
  tokenUsage: TokenUsageEvent | null;
  streamingError: string | null;
  reasoningActive: boolean;
  currentAgentState: AgentStateUpdateEvent | null;
}

/** 单个会话的非响应式引用（不触发重渲染，直接 mutate） */
export interface StreamSessionRefs {
  abortController: AbortController | null;
  toolIndex: Map<string, number>;
  taskIndex: Map<string, number>;
  thinkingBuffer: string;
  thinkingRaf: number | null;
  firstText: boolean;
  agentStateTimer: ReturnType<typeof setTimeout> | null;
}

function createDefaultSession(): StreamSessionState {
  return {
    isSending: false,
    timeline: [],
    tasks: [],
    tokenUsage: null,
    streamingError: null,
    reasoningActive: false,
    currentAgentState: null,
  };
}

function createDefaultRefs(): StreamSessionRefs {
  return {
    abortController: null,
    toolIndex: new Map(),
    taskIndex: new Map(),
    thinkingBuffer: "",
    thinkingRaf: null,
    firstText: true,
    agentStateTimer: null,
  };
}

interface StreamStore {
  /** 当前 UI 活跃会话（chat 页挂载时写入，卸载置 null）：供后台流结束时的通知判定使用 */
  activeChatId: number | null;
  setActiveChatId: (chatId: number | null) => void;

  /** chatId → 流式加载阶段（侧边栏指示器） */
  streams: Record<number, OrbStage>;
  setStream: (chatId: number, stage: OrbStage | null) => void;

  /** chatId → 会话流状态（多会话并发架构核心） */
  sessions: Record<number, StreamSessionState>;
  /** chatId → 非响应式引用（Map/Timer/AbortController 等） */
  refsMap: Map<number, StreamSessionRefs>;

  /** 读取指定 chatId 的会话状态（不存在则返回默认值） */
  getSession: (chatId: number) => StreamSessionState;
  /** 更新指定 chatId 的会话状态（函数式更新） */
  updateSession: (chatId: number, updater: (prev: StreamSessionState) => Partial<StreamSessionState>) => void;
  /** 重置指定 chatId 的会话状态到默认值 */
  resetSession: (chatId: number) => void;
  /** 移除指定 chatId 的会话（流结束且无需保留时清理） */
  removeSession: (chatId: number) => void;
  /** 读取指定 chatId 的非响应式引用（不存在则创建） */
  getRefs: (chatId: number) => StreamSessionRefs;
  /** 清理指定 chatId 的 refs 中的定时器并移除 */
  cleanupRefs: (chatId: number) => void;
}

/**
 * 全局流式状态 Store：
 * 1. streams：侧边栏加载指示器（按 chatId 读取 OrbStage）
 * 2. sessions/refsMap：多会话并发流状态（按 chatId 索引，互不干扰）
 *
 * 架构变更（Phase 2）：废弃"切换 chatId 时 abort 旧 SSE"的错误逻辑，
 * 改为每个 chatId 维护独立的 timeline + AbortController，
 * 切换会话仅切换 UI 订阅的 chatId，后台 SSE 连接继续运行。
 */
export const useStreamStore = create<StreamStore>()(
  persist(
    (set, get) => ({
  activeChatId: null,
  setActiveChatId: (chatId) => set({ activeChatId: chatId }),

  streams: {},
  setStream: (chatId, stage) =>
    set((state) => {
      const streams = { ...state.streams };
      if (stage === null) {
        delete streams[chatId];
      } else {
        streams[chatId] = stage;
      }
      return { streams };
    }),

  sessions: {},
  refsMap: new Map(),

  getSession: (chatId) => {
    return get().sessions[chatId] ?? createDefaultSession();
  },

  updateSession: (chatId, updater) => {
    set((state) => {
      const prev = state.sessions[chatId] ?? createDefaultSession();
      const patch = updater(prev);
      return {
        sessions: {
          ...state.sessions,
          [chatId]: { ...prev, ...patch },
        },
      };
    });
  },

  resetSession: (chatId) => {
    set((state) => ({
      sessions: {
        ...state.sessions,
        [chatId]: createDefaultSession(),
      },
    }));
  },

  removeSession: (chatId) => {
    set((state) => {
      const sessions = { ...state.sessions };
      delete sessions[chatId];
      return { sessions };
    });
  },

  getRefs: (chatId) => {
    const { refsMap } = get();
    let refs = refsMap.get(chatId);
    if (!refs) {
      refs = createDefaultRefs();
      // 直接 mutate Map（Map 本身是引用类型，不触发 Zustand 重渲染）
      refsMap.set(chatId, refs);
    }
    return refs;
  },

  cleanupRefs: (chatId) => {
    const { refsMap } = get();
    const refs = refsMap.get(chatId);
    if (refs) {
      if (refs.agentStateTimer) {
        clearTimeout(refs.agentStateTimer);
        refs.agentStateTimer = null;
      }
      if (refs.thinkingRaf != null) {
        cancelAnimationFrame(refs.thinkingRaf);
        refs.thinkingRaf = null;
      }
      refsMap.delete(chatId);
    }
  },
}),
  {
    name: "mfk-task-store",
    // ⚠️ 设计意图：partialize 仅序列化 sessions.tasks（任务面板数据），
    // refsMap（Map 类型，含 AbortController/Timer 等不可序列化对象）不参与持久化。
    // merge 返回 { ...current, ... } 时 current.refsMap 是内存中的 Map 实例，直接透传。
    // 修改 partialize 时切勿包含 refsMap，否则 hydration 会将其退化为普通 Object，导致 .get/.set 崩溃。
    partialize: (state) => ({
      sessions: Object.fromEntries(
        Object.entries(state.sessions).map(([chatId, session]) => [
          chatId,
          { tasks: session.tasks },
        ])
      ),
    }),
    merge: (persisted, current) => {
      const p = persisted as { sessions?: Record<string, { tasks: TaskNode[] }> };
      if (!p.sessions) return current;
      const mergedSessions = { ...current.sessions };
      for (const [chatIdStr, data] of Object.entries(p.sessions)) {
        const chatId = Number(chatIdStr);
        if (data.tasks && data.tasks.length > 0) {
          if (!mergedSessions[chatId] || mergedSessions[chatId].tasks.length === 0) {
            mergedSessions[chatId] = {
              ...(mergedSessions[chatId] ?? createDefaultSession()),
              tasks: data.tasks,
            };
          }
        }
      }
      return { ...current, sessions: mergedSessions };
    },
  })
);
