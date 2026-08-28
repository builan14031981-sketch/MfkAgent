import { create } from "zustand";

// ── localStorage keys ──
const DOCK_OPEN_KEY = "mfk_dock_open";
const DOCK_WIDTH_KEY = "mfk_dock_width";
const DOCK_FULLSCREEN_KEY = "mfk_dock_fullscreen";
const DOCK_ACTIVE_TAB_KEY = "mfk_dock_active_tab";
const DOCK_TABS_KEY = "mfk_dock_tabs";

/** 右侧面板宽度边界（px） */
export const DOCK_MIN = 260;
export const DOCK_MAX = 720;
export const DOCK_DEFAULT = 480;

/** 面板标签：终端 / 产出物 / 浏览器 */
export type DockTabId = "terminal" | "artifacts" | "browser";

/** 标签顺序（决定标签栏排列） */
export const DOCK_TAB_ORDER: DockTabId[] = ["terminal", "artifacts", "browser"];

function readLocal(key: string): string | null {
  if (typeof window === "undefined") return null;
  try { return localStorage.getItem(key); } catch { return null; }
}

function writeLocal(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* noop */ }
}

interface DockUIState {
  /** 面板是否打开（任一标签在标签栏中） */
  isOpen: boolean;
  /** 右侧面板宽度（px） */
  width: number;
  /** 是否全屏（覆盖整个窗口） */
  isFullscreen: boolean;
  /** 当前激活标签（决定渲染哪个内容） */
  activeTab: DockTabId;
  /** 标签是否在标签栏中（false=已通过 X 关闭） */
  tabs: Record<DockTabId, boolean>;
  /** 打开某标签（面板打开 + 加入标签栏 + 激活） */
  openTab: (tab: DockTabId) => void;
  /** 关闭某标签（从标签栏移除；无剩余标签则关闭整个面板） */
  closeTab: (tab: DockTabId) => void;
  /** 切换某标签：关→开并激活 / 开且非当前→切换激活 / 开且当前→关闭 */
  toggleTab: (tab: DockTabId) => void;
  /** 激活某标签（仅当其在标签栏中） */
  setActiveTab: (tab: DockTabId) => void;
  /** 展开面板：恢复上次的标签组合；若全部标签都已关闭则打开当前激活标签 */
  open: () => void;
  setWidth: (w: number) => void;
  toggleFullscreen: () => void;
  /** 关闭整个面板（所有标签关闭） */
  close: () => void;
}

export const useDockStore = create<DockUIState>((set, get) => ({
  isOpen: false,
  width: DOCK_DEFAULT,
  isFullscreen: false,
  activeTab: "terminal",
  tabs: { terminal: true, artifacts: false, browser: false },
  openTab: (tab) => {
    const tabs = { ...get().tabs, [tab]: true };
    writeLocal(DOCK_OPEN_KEY, "1");
    writeLocal(DOCK_ACTIVE_TAB_KEY, tab);
    writeLocal(DOCK_TABS_KEY, DOCK_TAB_ORDER.filter((id) => tabs[id]).join(","));
    writeLocal(DOCK_FULLSCREEN_KEY, "0");
    set({ isOpen: true, activeTab: tab, tabs, isFullscreen: false });
  },
  closeTab: (tab) => {
    const tabs = { ...get().tabs, [tab]: false };
    const remaining = DOCK_TAB_ORDER.filter((id) => tabs[id]);
    if (remaining.length === 0) {
      writeLocal(DOCK_OPEN_KEY, "0");
      writeLocal(DOCK_TABS_KEY, "");
      set({ isOpen: false, tabs });
      return;
    }
    // 若关闭的是当前激活标签，自动切到剩余标签中第一个
    const activeTab = get().activeTab === tab ? remaining[0] : get().activeTab;
    writeLocal(DOCK_ACTIVE_TAB_KEY, activeTab);
    writeLocal(DOCK_TABS_KEY, remaining.join(","));
    set({ tabs, activeTab });
  },
  toggleTab: (tab) => {
    if (!get().tabs[tab]) {
      get().openTab(tab);
    } else if (get().activeTab === tab) {
      get().closeTab(tab);
    } else {
      get().setActiveTab(tab);
    }
  },
  open: () => {
    const { activeTab, tabs } = get();
    const nextTabs = { ...tabs };
    // 若上次把所有标签都关闭了，则默认打开当前激活标签（保证展开后至少有一个标签）
    if (!DOCK_TAB_ORDER.some((id) => nextTabs[id])) {
      nextTabs[activeTab] = true;
    }
    writeLocal(DOCK_OPEN_KEY, "1");
    writeLocal(DOCK_TABS_KEY, DOCK_TAB_ORDER.filter((id) => nextTabs[id]).join(","));
    writeLocal(DOCK_ACTIVE_TAB_KEY, activeTab);
    writeLocal(DOCK_FULLSCREEN_KEY, "0");
    set({ isOpen: true, tabs: nextTabs, activeTab, isFullscreen: false });
  },
  setActiveTab: (tab) => {
    if (!get().tabs[tab]) return;
    writeLocal(DOCK_ACTIVE_TAB_KEY, tab);
    set({ activeTab: tab });
  },
  setWidth: (w) => {
    const clamped = Math.min(Math.max(w, DOCK_MIN), DOCK_MAX);
    writeLocal(DOCK_WIDTH_KEY, String(clamped));
    set({ width: clamped });
  },
  toggleFullscreen: () => {
    const next = !get().isFullscreen;
    writeLocal(DOCK_FULLSCREEN_KEY, next ? "1" : "0");
    set({ isFullscreen: next });
  },
  close: () => {
    writeLocal(DOCK_OPEN_KEY, "0");
    // 收起面板：保留标签组合与激活标签，再次展开时恢复原样
    set({ isOpen: false });
  },
}));

export function hydrateDockUI() {
  if (typeof window === "undefined") return;
  const openVal = readLocal(DOCK_OPEN_KEY);
  const widthVal = readLocal(DOCK_WIDTH_KEY);
  const fsVal = readLocal(DOCK_FULLSCREEN_KEY);
  const activeVal = readLocal(DOCK_ACTIVE_TAB_KEY);
  const tabsVal = readLocal(DOCK_TABS_KEY);
  const width = widthVal
    ? Math.min(Math.max(Number(widthVal) || DOCK_DEFAULT, DOCK_MIN), DOCK_MAX)
    : DOCK_DEFAULT;
  const hasStoredTabs = !!tabsVal;
  const tabs = {
    terminal: hasStoredTabs ? tabsVal!.split(",").includes("terminal") : openVal === "1",
    artifacts: hasStoredTabs ? tabsVal!.split(",").includes("artifacts") : false,
    browser: hasStoredTabs ? tabsVal!.split(",").includes("browser") : false,
  };
  // 面板可见性以 DOCK_OPEN_KEY 为准；tabs 仅描述标签组合（收起面板后刷新不应自动展开）
  const isOpen = openVal === "1" && (tabs.terminal || tabs.artifacts || tabs.browser);
  const activeTab = DOCK_TAB_ORDER.includes(activeVal as DockTabId) && tabs[activeVal as DockTabId]
    ? (activeVal as DockTabId)
    : (DOCK_TAB_ORDER.find((id) => tabs[id]) ?? "terminal");
  useDockStore.setState({ isOpen, width, isFullscreen: false, activeTab, tabs });
}

