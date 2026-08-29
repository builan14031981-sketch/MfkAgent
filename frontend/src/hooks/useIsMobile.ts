"use client";

import { useEffect, useState } from "react";

/**
 * 移动端断点检测（安卓端 M1）。
 * SSR/首帧返回 false（桌面布局），挂载后按媒体查询同步，桌面渲染零影响。
 */
const QUERY = "(max-width: 768px)";

export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia(QUERY);
    const sync = () => setIsMobile(mql.matches);
    sync();
    mql.addEventListener("change", sync);
    return () => mql.removeEventListener("change", sync);
  }, []);

  return isMobile;
}
