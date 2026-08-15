import { create } from "zustand";
import { useDockStore } from "./dockStore";

/** 产出物条目：Agent 写入/生成的文件 */
export interface ArtifactItem {
  /** 文件绝对路径（Windows: E:\...） */
  path: string;
  /** 文件名（用于展示） */
  fileName: string;
  /** 所属项目根目录绝对路径（用于反查 projectId 调文件 API），无项目绑定为 null */
  projectPath: string | null;
  /** 产生该产出物的工具名（可选展示） */
  tool?: string;
}

/** 从绝对/相对路径提取文件名 */
export function artifactFileName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() || path;
}

interface ArtifactDataState {
  /** 本次会话已收集的产出物列表 */
  artifacts: ArtifactItem[];
  /** 当前选中预览的产出物路径（null=未选中） */
  selectedPath: string | null;
  /** 打开产出物：加入列表（去重）、定位预览，并打开右侧面板的"产出物"标签 */
  openArtifact: (item: ArtifactItem) => void;
  /** 仅收集入列表（流式期间，不改变选中/标签状态） */
  addArtifact: (item: ArtifactItem) => void;
  /** 切换选中 */
  select: (path: string) => void;
  /** 清空（切换会话时） */
  reset: () => void;
}

export const useArtifactStore = create<ArtifactDataState>((set, get) => ({
  artifacts: [],
  selectedPath: null,
  openArtifact: (item) => {
    const { artifacts } = get();
    const exists = artifacts.some((a) => a.path === item.path);
    set({ artifacts: exists ? artifacts : [...artifacts, item], selectedPath: item.path });
    // 打开右侧面板并激活"产出物"标签
    useDockStore.getState().openTab("artifacts");
  },
  addArtifact: (item) => {
    const { artifacts } = get();
    if (artifacts.some((a) => a.path === item.path)) return;
    set({ artifacts: [...artifacts, item] });
  },
  select: (path) => set({ selectedPath: path }),
  reset: () => set({ artifacts: [], selectedPath: null }),
}));
