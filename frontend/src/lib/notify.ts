"use client";

/**
 * 桌面端原生通知 + 提示音工具（Electron 环境）。
 * - 调用 Electron 主进程 Notification API 弹出 Windows 右下角 Toast。
 * - 提示音通过 Web Audio API 合成短促提示音，3 秒节流防刷屏。
 * - 浏览器环境降级为 Web Notification（若已授权）。
 */

let lastBeepTime = 0;
const BEEP_THROTTLE_MS = 3000;

/** 播放短促提示音（Web Audio API 合成，无需音频文件） */
function playBeep(): void {
  const now = Date.now();
  if (now - lastBeepTime < BEEP_THROTTLE_MS) return; // 3 秒节流
  lastBeepTime = now;
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880; // A5 清脆提示音
    osc.type = "sine";
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.3);
    osc.onended = () => ctx.close();
  } catch {
    /* AudioContext 不可用则静默 */
  }
}

/**
 * 弹出桌面通知 + 提示音。
 * @param title 通知标题
 * @param body 通知正文
 * @param opts.beep 是否播放提示音（默认 true）
 * @param opts.silent 通知本身是否静默（渲染进程自行播音时设 true 避免双重音）
 */
export async function showDesktopNotification(
  title: string,
  body: string,
  opts?: { beep?: boolean; silent?: boolean }
): Promise<void> {
  const beep = opts?.beep ?? true;
  const silent = opts?.silent ?? true; // 默认让 Electron 通知静默，由 Web Audio 播音

  // Electron 环境：走主进程原生 Notification
  if (typeof window !== "undefined" && window.electronAPI?.showNotification) {
    try {
      await window.electronAPI.showNotification({ title, body, silent });
      if (beep) playBeep();
      return;
    } catch {
      /* 降级到 Web Notification */
    }
  }

  // 浏览器降级：Web Notification API
  if (typeof window !== "undefined" && "Notification" in window) {
    try {
      if (Notification.permission === "granted") {
        new Notification(title, { body, silent });
        if (beep) playBeep();
      } else if (Notification.permission !== "denied") {
        const perm = await Notification.requestPermission();
        if (perm === "granted") {
          new Notification(title, { body, silent });
          if (beep) playBeep();
        }
      }
    } catch {
      /* 通知不可用则静默 */
    }
  }
}
