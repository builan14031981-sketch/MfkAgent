"use client";

/**
 * 桌面端原生通知 + 提示音工具（Electron 环境）。
 * - 调用 Electron 主进程 Notification API 弹出 Windows 右下角 Toast。
 * - 提示音通过 Web Audio API 合成短促提示音，3 秒节流防刷屏。
 * - 浏览器环境降级为 Web Notification（若已授权）。
 */

let lastBeepTime = 0;
const BEEP_THROTTLE_MS = 3000;

// Toast 节流：与提示音同级。多任务同时完成/多个审批连续到达时，
// 防止 Windows 右下角短时间堆叠大量通知；不引入队列，窗口内的重复通知直接丢弃
let lastToastTime = 0;
const TOAST_THROTTLE_MS = 3000;

/**
 * 播放分级提示音（Web Audio API 合成，无需音频文件）。
 * 音色分级（对齐《通知触发策略》矩阵）：
 *  - info      单声 880Hz A5 清脆音（信息/完成）
 *  - success   上行双音 660→880（上行感知=正向结果）
 *  - error     低沉 440Hz 长音（失败/出错）
 *  - attention 急促三连 880×3（审批/抉择需用户操作）
 */
export type BeepKind = "info" | "success" | "error" | "attention";

function beepOnce(ctx: AudioContext, freq: number, at: number, dur: number, vol = 0.15): void {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.frequency.value = freq;
  osc.type = "sine";
  gain.gain.setValueAtTime(vol, at);
  gain.gain.exponentialRampToValueAtTime(0.001, at + dur);
  osc.start(at);
  osc.stop(at + dur);
  osc.onended = () => osc.disconnect();
}

function playBeep(kind: BeepKind = "info"): void {
  const now = Date.now();
  if (now - lastBeepTime < BEEP_THROTTLE_MS) return; // 3 秒节流
  lastBeepTime = now;
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const t = ctx.currentTime;
    if (kind === "success") {
      beepOnce(ctx, 660, t, 0.18, 0.13);
      beepOnce(ctx, 880, t + 0.14, 0.22, 0.13);
    } else if (kind === "error") {
      beepOnce(ctx, 440, t, 0.4, 0.16);
    } else if (kind === "attention") {
      beepOnce(ctx, 880, t, 0.09, 0.16);
      beepOnce(ctx, 880, t + 0.12, 0.09, 0.16);
      beepOnce(ctx, 880, t + 0.24, 0.12, 0.16);
    } else {
      beepOnce(ctx, 880, t, 0.3, 0.15); // info
    }
    // 结尾关闭（最后一个 osc.onended 时关闭 ctx）
    const lastDur = kind === "attention" ? 0.36 : kind === "error" ? 0.4 : 0.36;
    setTimeout(() => ctx.close().catch(() => {}), (lastDur + 0.3) * 1000);
  } catch {
    /* AudioContext 不可用则静默 */
  }
}

/**
 * 弹出桌面通知 + 分级提示音。
 * @param title 通知标题
 * @param body 通知正文
 * @param opts.beep 提示音分级（info/success/error/attention；默认 info）
 * @param opts.beepEnabled 是否播音（默认 true）
 * @param opts.silent 通知本身是否静默（渲染进程自行播音时设 true 避免双重音）
 * @param opts.persistent 通知是否保持显示直到用户交互（默认 false，短显信息类）；
 *                        需交互场景（审批/抉择/错误）传 true
 * @param opts.chatId 通知点击后跳转的目标会话 id（Electron 主进程据此 loadURL）
 */
export interface NotifyOptions {
  beep?: BeepKind;
  beepEnabled?: boolean;
  silent?: boolean;
  persistent?: boolean;
  chatId?: number;
}

export async function showDesktopNotification(
  title: string,
  body: string,
  opts?: NotifyOptions
): Promise<void> {
  const beep = opts?.beep ?? "info";
  const beepEnabled = opts?.beepEnabled ?? true;
  const silent = opts?.silent ?? true; // 默认让 Electron 通知静默，由 Web Audio 播音
  const persistent = opts?.persistent ?? false;
  const chatId = opts?.chatId;

  // Toast 节流：3 秒内已弹过通知则跳过（含提示音，避免音画不同步的割裂感）
  const now = Date.now();
  if (now - lastToastTime < TOAST_THROTTLE_MS) {
    return;
  }
  lastToastTime = now;

  // Electron 环境：走主进程原生 Notification
  if (typeof window !== "undefined" && window.electronAPI?.showNotification) {
    try {
      await window.electronAPI.showNotification({ title, body, silent, persistent, chatId });
      if (beepEnabled) playBeep(beep);
      return;
    } catch {
      /* 降级到 Web Notification */
    }
  }

  // 浏览器降级：Web Notification API
  if (typeof window !== "undefined" && "Notification" in window) {
    try {
      if (Notification.permission === "granted") {
        new Notification(title, { body, silent, requireInteraction: persistent });
        if (beepEnabled) playBeep(beep);
      } else if (Notification.permission !== "denied") {
        const perm = await Notification.requestPermission();
        if (perm === "granted") {
          new Notification(title, { body, silent, requireInteraction: persistent });
          if (beepEnabled) playBeep(beep);
        }
      }
    } catch {
      /* 通知不可用则静默 */
    }
  }
}
