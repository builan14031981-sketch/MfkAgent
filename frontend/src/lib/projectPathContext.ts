"use client";

import { createContext, useContext } from "react";

/** 当前项目根目录路径，供 ToolCallCard 等组件解析相对文件路径 */
export const ProjectPathContext = createContext<string | null>(null);

export function useProjectPath(): string | null {
  return useContext(ProjectPathContext);
}