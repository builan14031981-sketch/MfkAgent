/** 相对时间格式化 + 共享分钟级刷新（2026-08-12：侧边栏会话行最后交互时间）。
 *
 * UTC 陷阱说明：后端 updated_at 为无时区信息的 UTC 字符串（datetime.utcnow），
 * 前端 Date.parse 默认按本地时区解析会差 8 小时，必须补 "Z" 后缀。
 */

import { useSyncExternalStore } from "react";

type TranslateFn = (key: string, params?: Record<string, string>) => string;

/** 将后端 UTC 无时区字符串解析为毫秒时间戳（无效返回 null） */
export function parseUtc(isoUtc: string | null | undefined): number | null {
  if (!isoUtc) return null;
  const normalized = isoUtc.endsWith("Z") || /[+-]\d{2}:?\d{2}$/.test(isoUtc) ? isoUtc : isoUtc + "Z";
  const ts = Date.parse(normalized);
  return Number.isNaN(ts) ? null : ts;
}

/**
 * 相对时间展示：<1 分钟 刚刚 / <1 小时 x 分钟前 / <24 小时 x 小时前 /
 * 今年 MM-DD / 跨年 YYYY-MM-DD。
 *
 * @param isoUtc 后端 updated_at（UTC 无时区字符串）
 * @param t      useTranslation 的 t 函数（提供 justNow/minutesAgo/hoursAgo 词条）
 * @param now    当前时间戳（由 useNowTick 提供，保证分钟级刷新）
 */
export function formatRelativeTime(
  isoUtc: string | null | undefined,
  t: TranslateFn,
  now: number = Date.now()
): string {
  const ts = parseUtc(isoUtc);
  if (ts == null) return "";
  const diff = Math.max(0, now - ts);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return t("time.justNow");
  if (minutes < 60) return t("time.minutesAgo", { n: String(minutes) });
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return t("time.hoursAgo", { n: String(hours) });
  const d = new Date(ts);
  const nowD = new Date(now);
  const md = `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  if (d.getFullYear() === nowD.getFullYear()) return md;
  return `${d.getFullYear()}-${md}`;
}

/** 完整本地时间（hover tooltip 用） */
export function formatFullTime(isoUtc: string | null | undefined): string {
  const ts = parseUtc(isoUtc);
  if (ts == null) return "";
  const d = new Date(ts);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ──── 共享分钟级时钟：全应用单一 interval，订阅者归零自动停表 ────

let snapshot = Date.now();
const listeners = new Set<() => void>();
let timer: ReturnType<typeof setInterval> | null = null;

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  if (timer == null) {
    timer = setInterval(() => {
      snapshot = Date.now();
      listeners.forEach((l) => l());
    }, 60000);
  }
  return () => {
    listeners.delete(cb);
    if (listeners.size === 0 && timer != null) {
      clearInterval(timer);
      timer = null;
    }
  };
}

/** 每 60 秒刷新一次的当前时间戳（相对时间防过期，如"x 分钟前"） */
export function useNowTick(): number {
  return useSyncExternalStore(subscribe, () => snapshot);
}
