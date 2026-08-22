"use client";

/**
 * Skill 库全局单一数据源（zustand）。
 *
 * 背景问题（2026-08 修复）：Skill 的「安装 = 加入 Skill 库（出现在加号可调用）」，
 * 但旧 useSkills() 在每个组件（ExtensionHome / ManageSkillList / SkillDetail / 聊天页）
 * 各自开一份独立本地 state，互不同步 —— 设置里加入后加号看不见。
 * 这里收敛成一份全局 state，所有 useSkills() 订阅同一数据，安装状态即时同步。
 *
 * 同时解决「加入后回到顶部」：install/uninstall 采用乐观更新（后端成功后本地立刻切换 installed），
 * 不再整库 refetch + loading 闪烁，避免列表卸载导致滚动回落。
 */
import { create } from "zustand";
import { apiGet, apiPost } from "./api";

export interface SkillInfo {
  id: string;
  name: string;
  category: string;
  description: string;
  version: string;
  tags: string[];
  installed: boolean;
  /** Skill 说明书正文，用于会话级注入（作为文档喂给当前会话） */
  prompt?: string;
}

interface SkillStoreState {
  skills: SkillInfo[];
  loading: boolean;
  error: string | null;
  fetchSkills: () => Promise<void>;
  installSkill: (id: string) => Promise<void>;
  uninstallSkill: (id: string) => Promise<void>;
  refetch: () => Promise<void>;
}

export const useSkillStore = create<SkillStoreState>((set, get) => ({
  skills: [],
  loading: false,
  error: null,

  fetchSkills: async () => {
    if (get().loading) return;
    set({ loading: true });
    try {
      const data = await apiGet<{ skills: SkillInfo[] }>("/api/skills/builtin");
      set({ skills: data.skills || [], error: null, loading: false });
    } catch (err: unknown) {
      set({ error: err instanceof Error ? err.message : "Unknown error", loading: false });
    }
  },

  installSkill: async (id) => {
    try {
      await apiPost("/api/skills/install", { skill_id: id });
    } catch (err) {
      console.error("Failed to install skill:", err);
      return;
    }
    // 乐观更新：仅切换本地 installed，不整库 refetch（避免 loading 闪烁 / 列表卸载回顶）
    set((s) => ({
      skills: s.skills.map((x) => (x.id === id ? { ...x, installed: true } : x)),
    }));
  },

  uninstallSkill: async (id) => {
    try {
      await apiPost("/api/skills/uninstall", { skill_id: id });
    } catch (err) {
      console.error("Failed to uninstall skill:", err);
      return;
    }
    set((s) => ({
      skills: s.skills.map((x) => (x.id === id ? { ...x, installed: false } : x)),
    }));
  },

  refetch: () => get().fetchSkills(),
}));