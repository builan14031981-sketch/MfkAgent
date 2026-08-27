import { create } from "zustand";

export interface ChatTabItem {
  chatId: number;
  title: string;
  agentId?: string;
  projectId?: number | null;
}

const STORAGE_KEY = "mfk_chat_tabs";
const ACTIVE_TAB_KEY = "mfk_active_chat_tab";

function loadSavedTabs(): { tabs: ChatTabItem[]; activeChatId: number | null } {
  if (typeof window === "undefined") return { tabs: [], activeChatId: null };
  try {
    const rawTabs = localStorage.getItem(STORAGE_KEY);
    const rawActive = localStorage.getItem(ACTIVE_TAB_KEY);
    const tabs: ChatTabItem[] = rawTabs ? JSON.parse(rawTabs) : [];
    const activeChatId = rawActive ? Number(rawActive) : null;
    return { tabs: Array.isArray(tabs) ? tabs : [], activeChatId };
  } catch {
    return { tabs: [], activeChatId: null };
  }
}

function saveTabsToStorage(tabs: ChatTabItem[], activeChatId: number | null) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tabs));
    if (activeChatId != null) {
      localStorage.setItem(ACTIVE_TAB_KEY, String(activeChatId));
    } else {
      localStorage.removeItem(ACTIVE_TAB_KEY);
    }
  } catch {
    // 忽略存储异常
  }
}

interface TabStoreState {
  tabs: ChatTabItem[];
  activeChatId: number | null;
  /** 打开或激活标签。默认在当前位置切换，只有 forceNewTab 为 true 时才追加新标签页 */
  openTab: (tab: ChatTabItem, options?: { forceNewTab?: boolean }) => void;
  /** 关闭单个标签，返回下一个应激活的 chatId（若关闭的是当前激活项） */
  closeTab: (chatId: number) => number | null;
  /** 关闭其他标签 */
  closeOtherTabs: (chatId: number) => void;
  /** 关闭右侧所有标签 */
  closeRightTabs: (chatId: number) => number | null;
  /** 关闭所有标签 */
  closeAllTabs: () => void;
  /** 激活指定标签 */
  setActiveTab: (chatId: number | null) => void;
  /** 更新指定标签标题 */
  updateTabTitle: (chatId: number, title: string) => void;
  /** 左右轮转切换标签（1：右，-1：左） */
  cycleTab: (direction: 1 | -1) => number | null;
  /** 数字直达第 index 个标签（0-indexed） */
  jumpToTab: (index: number) => number | null;
  /** 自动清理不存在的脏标签 */
  sanitizeTabs: (validChatIds: Set<number>) => void;
  cleanStaleTabs: (validChatIds: Set<number>) => void;
}

export const useTabStore = create<TabStoreState>((set, get) => {
  const initial = loadSavedTabs();
  const sanitizeTabs = (validChatIds: Set<number>) => {
    const { tabs, activeChatId } = get();
    if (tabs.length === 0) return;
    const validTabs = tabs.filter((t) => validChatIds.has(t.chatId));
    if (validTabs.length !== tabs.length) {
      let nextActive = activeChatId;
      if (activeChatId != null && !validChatIds.has(activeChatId)) {
        nextActive = validTabs.length > 0 ? validTabs[0].chatId : null;
      }
      saveTabsToStorage(validTabs, nextActive);
      set({ tabs: validTabs, activeChatId: nextActive });
    }
  };

  return {
    tabs: initial.tabs,
    activeChatId: initial.activeChatId,
    sanitizeTabs,
    cleanStaleTabs: sanitizeTabs,

    openTab: (newTab, options) => {
      const { tabs, activeChatId } = get();
      const existingIndex = tabs.findIndex((t) => t.chatId === newTab.chatId);
      let updatedTabs: ChatTabItem[];

      if (existingIndex >= 0) {
        // 该对话已经在标签栏中：更新信息并直接激活该标签
        updatedTabs = [...tabs];
        updatedTabs[existingIndex] = {
          ...updatedTabs[existingIndex],
          title: newTab.title || updatedTabs[existingIndex].title,
          agentId: newTab.agentId || updatedTabs[existingIndex].agentId,
          projectId: newTab.projectId !== undefined ? newTab.projectId : updatedTabs[existingIndex].projectId,
        };
      } else if (options?.forceNewTab || tabs.length === 0) {
        // 显式要求开启新标签页，或当前没有任何标签页：追加新标签
        updatedTabs = [...tabs, newTab];
      } else {
        // 普通导航（无 forceNewTab 标识）：在当前激活页签位置直接替换，避免纵向/横向盲目死塞新标签
        const activeIndex = tabs.findIndex((t) => t.chatId === activeChatId);
        const replaceIndex = activeIndex >= 0 ? activeIndex : tabs.length - 1;
        updatedTabs = [...tabs];
        updatedTabs[replaceIndex] = newTab;
      }

      saveTabsToStorage(updatedTabs, newTab.chatId);
      set({ tabs: updatedTabs, activeChatId: newTab.chatId });
    },

    closeTab: (chatId) => {
      const { tabs, activeChatId } = get();
      const targetIndex = tabs.findIndex((t) => t.chatId === chatId);
      if (targetIndex === -1) return activeChatId;

      const updatedTabs = tabs.filter((t) => t.chatId !== chatId);
      let nextActiveId = activeChatId;

      if (activeChatId === chatId) {
        if (updatedTabs.length === 0) {
          nextActiveId = null;
        } else {
          // 优先激活右侧相邻标签，若关闭的是最右侧则激活左侧相邻
          const newIndex = Math.min(targetIndex, updatedTabs.length - 1);
          nextActiveId = updatedTabs[newIndex].chatId;
        }
      }

      saveTabsToStorage(updatedTabs, nextActiveId);
      set({ tabs: updatedTabs, activeChatId: nextActiveId });
      return nextActiveId;
    },

    closeOtherTabs: (chatId) => {
      const { tabs } = get();
      const target = tabs.find((t) => t.chatId === chatId);
      const updatedTabs = target ? [target] : [];
      saveTabsToStorage(updatedTabs, chatId);
      set({ tabs: updatedTabs, activeChatId: chatId });
    },

    closeRightTabs: (chatId) => {
      const { tabs, activeChatId } = get();
      const targetIndex = tabs.findIndex((t) => t.chatId === chatId);
      if (targetIndex === -1) return activeChatId;

      const updatedTabs = tabs.slice(0, targetIndex + 1);
      let nextActiveId = activeChatId;

      // 如果当前激活的标签在被关闭的右侧区域中，切回当前目标标签
      if (!updatedTabs.some((t) => t.chatId === activeChatId)) {
        nextActiveId = chatId;
      }

      saveTabsToStorage(updatedTabs, nextActiveId);
      set({ tabs: updatedTabs, activeChatId: nextActiveId });
      return nextActiveId;
    },

    closeAllTabs: () => {
      saveTabsToStorage([], null);
      set({ tabs: [], activeChatId: null });
    },

    setActiveTab: (chatId) => {
      const { tabs } = get();
      saveTabsToStorage(tabs, chatId);
      set({ activeChatId: chatId });
    },

    updateTabTitle: (chatId, title) => {
      const { tabs, activeChatId } = get();
      if (!title || !title.trim()) return;
      const updatedTabs = tabs.map((t) =>
        t.chatId === chatId ? { ...t, title: title.trim() } : t
      );
      saveTabsToStorage(updatedTabs, activeChatId);
      set({ tabs: updatedTabs });
    },

    cycleTab: (direction) => {
      const { tabs, activeChatId } = get();
      if (tabs.length <= 1) return activeChatId;
      const currentIndex = tabs.findIndex((t) => t.chatId === activeChatId);
      if (currentIndex === -1) {
        const nextId = tabs[0].chatId;
        saveTabsToStorage(tabs, nextId);
        set({ activeChatId: nextId });
        return nextId;
      }
      const nextIndex = (currentIndex + direction + tabs.length) % tabs.length;
      const nextId = tabs[nextIndex].chatId;
      saveTabsToStorage(tabs, nextId);
      set({ activeChatId: nextId });
      return nextId;
    },

    jumpToTab: (index) => {
      const { tabs } = get();
      if (index < 0 || index >= tabs.length) return null;
      const targetId = tabs[index].chatId;
      saveTabsToStorage(tabs, targetId);
      set({ activeChatId: targetId });
      return targetId;
    },
  };
});
