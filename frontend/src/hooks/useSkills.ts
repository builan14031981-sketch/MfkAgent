/* eslint-disable react-hooks/exhaustive-deps */

"use client";

import { useEffect } from "react";
import { useSkillStore } from "@/lib/skillStore";

export type { SkillInfo } from "@/lib/skillStore";

/**
 * Skill 库 hook —— 薄封装全局共享 store（lib/skillStore.ts）。
 *
 * 所有调用方（设置页各 view / 加号菜单 / 聊天页）订阅同一份数据，
 * 「加入 Skill 库」后加号即时可见；安装走乐观更新，不再闪 loading。
 */
export function useSkills() {
  const store = useSkillStore();

  // 首次挂载且尚无数据时拉取；若其它页面已加载（共享数据存在）则不重复请求
  useEffect(() => {
    if (store.skills.length === 0 && !store.loading) {
      store.fetchSkills();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return store;
}