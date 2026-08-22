"use client";

/**
 * useTts —— 全局 TTS 朗读管理（单例音频元素 + 会话隔离）
 *
 * 设计要点：
 * - 全局唯一 audio 元素，同一时刻只允许一条消息朗读
 * - sessionId 会话隔离：快速切换时旧 playSegment 不会干扰新的
 * - 用 fetch + blob 加载音频
 * - 切换时只 pause 不清 src，避免空 src 触发 error 串台
 * - onError 忽略空 src 残留错误
 */
import { useCallback, useEffect, useState } from "react";
import { useSettingsStore } from "@/lib/store";
import { API_BASE } from "@/lib/api";

// 全局单例
let globalAudio: HTMLAudioElement | null = null;
let currentPlayingId: number | null = null;
let currentSessionId = 0;

let segmentQueue: string[] = [];
let segmentIndex = 0;

// 当前注册的事件监听器引用
let currentOnEnded: (() => void) | null = null;
let currentOnError: (() => void) | null = null;

function getGlobalAudio(): HTMLAudioElement {
  if (!globalAudio) {
    globalAudio = new Audio();
    globalAudio.preload = "auto";
  }
  return globalAudio;
}

function removeCurrentListeners(audio: HTMLAudioElement) {
  if (currentOnEnded) {
    audio.removeEventListener("ended", currentOnEnded);
    currentOnEnded = null;
  }
  if (currentOnError) {
    audio.removeEventListener("error", currentOnError);
    currentOnError = null;
  }
}

function splitText(text: string): string[] {
  const clean = text.trim();
  if (!clean) return [];
  if (clean.length <= 1800) return [clean];

  const paragraphs = clean.split(/\n+/);
  const segments: string[] = [];
  let buffer = "";

  for (const para of paragraphs) {
    if (!para.trim()) continue;
    const sentences = para.split(/(?<=[。！？!?\.])/);
    for (const s of sentences) {
      if (!s.trim()) continue;
      if ((buffer + s).length > 1800 && buffer) {
        segments.push(buffer.trim());
        buffer = s;
      } else {
        buffer += s;
      }
    }
    if (buffer) {
      segments.push(buffer.trim());
      buffer = "";
    }
  }
  if (buffer) segments.push(buffer.trim());
  return segments.filter(Boolean);
}

export function useTts() {
  const { settings } = useSettingsStore();
  const [playingId, setPlayingId] = useState<number | null>(currentPlayingId);

  const voice = settings?.tts_voice || "zh-CN-YunxiNeural";
  const rate = settings?.tts_rate || "+0%";

  const stop = useCallback(() => {
    currentSessionId++; // 作废所有旧会话
    segmentQueue = [];
    segmentIndex = 0;
    const audio = getGlobalAudio();
    removeCurrentListeners(audio);
    audio.pause();
    audio.currentTime = 0;
    audio.src = "";
    currentPlayingId = null;
    setPlayingId(null);
  }, []);

  const play = useCallback(
    (text: string, messageId: number) => {
      const audio = getGlobalAudio();

      if (currentPlayingId === messageId) {
        stop();
        return;
      }

      // 开启新会话，作废所有旧会话
      const sessionId = ++currentSessionId;

      // 停止之前的播放：只 pause，不清 src
      removeCurrentListeners(audio);
      audio.pause();
      audio.currentTime = 0;

      segmentQueue = splitText(text);
      segmentIndex = 0;
      currentPlayingId = messageId;
      setPlayingId(messageId);

      if (segmentQueue.length === 0) {
        currentPlayingId = null;
        setPlayingId(null);
        return;
      }

      const playSegment = async () => {
        // 会话已过期（被新的 play/stop 作废）
        if (sessionId !== currentSessionId) return;
        if (segmentIndex >= segmentQueue.length) {
          currentPlayingId = null;
          setPlayingId(null);
          return;
        }

        const segment = segmentQueue[segmentIndex];
        const url = `${API_BASE}/api/tts?text=${encodeURIComponent(segment)}&voice=${encodeURIComponent(voice)}&rate=${encodeURIComponent(rate)}`;

        let blobUrl: string | null = null;

        try {
          const response = await fetch(url);
          if (sessionId !== currentSessionId) return; // 会话过期
          if (!response.ok) throw new Error(`HTTP ${response.status}`);

          const blob = await response.blob();
          if (sessionId !== currentSessionId) return;
          if (blob.size === 0) throw new Error("空音频");

          blobUrl = URL.createObjectURL(blob);

          await new Promise<void>((resolve) => {
            const cleanup = () => {
              audio.removeEventListener("ended", onEnded);
              audio.removeEventListener("error", onError);
              if (blobUrl) URL.revokeObjectURL(blobUrl);
            };
            const onEnded = () => { cleanup(); resolve(); };
            const onError = () => {
              const err = audio.error;
              const src = audio.src;
              const isEmptySrcError =
                err?.code === 4 &&
                (!src || src === "" || src === window.location.href);
              if (!isEmptySrcError && sessionId === currentSessionId) {
                console.error("[tts] 音频播放错误 - code:", err?.code, "message:", err?.message, "src:", src);
              }
              cleanup();
              resolve();
            };
            currentOnEnded = onEnded;
            currentOnError = onError;
            audio.addEventListener("ended", onEnded);
            audio.addEventListener("error", onError);

            audio.src = blobUrl!;
            audio.play().catch((e) => {
              if (e.name !== "AbortError" && sessionId === currentSessionId) {
                console.error("[tts] play() 失败:", e);
              }
            });
          });

          if (sessionId !== currentSessionId) return;
          segmentIndex++;
          playSegment();
        } catch (err) {
          if (blobUrl) URL.revokeObjectURL(blobUrl);
          if (err instanceof DOMException && err.name === "AbortError") return;
          if (sessionId === currentSessionId) {
            console.error("[tts] 分段播放失败:", err);
          }
          segmentIndex++;
          if (sessionId === currentSessionId && segmentIndex < segmentQueue.length) {
            playSegment();
          } else {
            currentPlayingId = null;
            setPlayingId(null);
          }
        }
      };

      playSegment();
    },
    [voice, rate, stop]
  );

  const isPlaying = useCallback(
    (messageId: number) => playingId === messageId,
    [playingId]
  );

  useEffect(() => {
    return () => {};
  }, []);

  return { play, stop, isPlaying, playingId };
}
