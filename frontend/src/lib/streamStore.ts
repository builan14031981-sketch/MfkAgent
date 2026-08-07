import { create } from "zustand";

/**
 * 流式加载阶段（对应 ThinkingOrb 动画状态）：
 * - working    — 已发送、等待首个事件
 * - solving    — 正在思考（thinking 事件）
 * - searching  — 正在调用工具（tool 事件）
 * - listening  — 等待用户审批（approval 事件）
 * - composing  — 正在生成正文（text 事件）
 */
export type OrbStage = "working" | "solving" | "searching" | "listening" | "composing";

interface StreamState {
  /** chatId → 当前加载阶段；不存在该 key 表示该会话未在流式 */
  streams: Record<number, OrbStage>;
  setStream: (chatId: number, stage: OrbStage | null) => void;
}

/**
 * 全局流式状态：侧边栏（AppLayout 兄弟层）与聊天页跨组件共享加载指示。
 * 聊天页 sendStream 开始/结束时写入，期间随 timeline 末位事件派生阶段更新。
 */
export const useStreamStore = create<StreamState>((set) => ({
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
}));
