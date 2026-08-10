/**
 * 通用格式化工具。
 */

/** 将时长（毫秒）格式化为人类可读文本：<1 分钟 → "8 秒"；≥1 分钟 → "1 分 23 秒" */
export function formatDuration(ms: number): string {
  const totalSec = Math.max(1, Math.round(ms / 1000));
  if (totalSec < 60) return `${totalSec} 秒`;
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return sec > 0 ? `${min} 分 ${sec} 秒` : `${min} 分`;
}
