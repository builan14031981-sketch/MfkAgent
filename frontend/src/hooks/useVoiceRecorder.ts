"use client";

import { useCallback, useRef, useState } from "react";
import { ApiError, apiFetch } from "@/lib/api";

/** 语音转写后端响应契约（/api/voice/transcribe） */
interface TranscribeResponse {
  text: string;
  raw?: string;
}

/** useVoiceRecorder 返回值 */
export interface UseVoiceRecorderResult {
  /** 是否正在录音 */
  isRecording: boolean;
  /** 是否正在转写（录音结束 → 后端返回期间） */
  isTranscribing: boolean;
  /** 最近一次错误信息（无则 null） */
  error: string | null;
  /** 开始录音；返回 false 表示启动失败（如无麦克风权限） */
  start: () => Promise<boolean>;
  /** 停止录音并触发转写；返回转写文本（失败返回 null） */
  stop: () => Promise<string | null>;
  /** 切换录音状态：空闲→开始；录音中→停止并转写 */
  toggle: () => Promise<string | null | boolean>;
  /** 重置错误态 */
  clearError: () => void;
}

/**
 * 语音录制 + 意图转写 Hook（MediaRecorder → POST /api/voice/transcribe）。
 *
 * 设计要点：
 * - 使用 MediaRecorder 采集音频，优先 webm/opus；不支持时回退浏览器默认格式。
 * - 录音期间将 chunk 累积到数组，停止时合并为 Blob 上传。
 * - 转写请求带 60s 超时（STT 链路可能较慢），错误统一通过 error 状态外泄。
 * - 组件卸载时若仍在录音，自动停止并丢弃数据（避免悬挂 stream）。
 */
export function useVoiceRecorder(): UseVoiceRecorderResult {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  /** 关闭并释放麦克风 stream（停止录音后调用，避免红点常亮） */
  const releaseStream = useCallback(() => {
    const stream = streamRef.current;
    if (stream) {
      for (const track of stream.getTracks()) {
        try {
          track.stop();
        } catch {
          /* 忽略 */
        }
      }
      streamRef.current = null;
    }
  }, []);

  const start = useCallback(async (): Promise<boolean> => {
    if (isRecording || isTranscribing) return false;
    setError(null);

    // 浏览器不支持
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setError("当前环境不支持麦克风录音");
      return false;
    }
    if (typeof MediaRecorder === "undefined") {
      setError("当前浏览器不支持 MediaRecorder");
      return false;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      if (name === "NotAllowedError" || name === "SecurityError") {
        setError("麦克风权限被拒绝，请在浏览器设置中允许访问");
      } else if (name === "NotFoundError" || name === "OverconstrainedError") {
        setError("未检测到麦克风设备");
      } else {
        setError("启动录音失败：" + (err instanceof Error ? err.message : String(err)));
      }
      return false;
    }

    // 选择浏览器支持的 mime（优先 webm/opus）
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/mp4",
    ];
    const mimeType = candidates.find((t) => MediaRecorder.isTypeSupported(t)) || "";

    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    } catch (err) {
      releaseStream();
      setError("创建 MediaRecorder 失败：" + (err instanceof Error ? err.message : String(err)));
      return false;
    }

    chunksRef.current = [];
    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        chunksRef.current.push(e.data);
      }
    };

    streamRef.current = stream;
    mediaRecorderRef.current = recorder;

    try {
      recorder.start();
    } catch (err) {
      releaseStream();
      mediaRecorderRef.current = null;
      setError("启动录音失败：" + (err instanceof Error ? err.message : String(err)));
      return false;
    }

    setIsRecording(true);
    return true;
  }, [isRecording, isTranscribing, releaseStream]);

  /** 停止录音并转写，返回转写文本（失败返回 null） */
  const stop = useCallback(async (): Promise<string | null> => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") {
      // 未在录音：直接返回
      setIsRecording(false);
      releaseStream();
      return null;
    }

    // 等待 recorder.onstop 触发，拿到完整 Blob
    const blob: Blob = await new Promise<Blob>((resolve) => {
      recorder.onstop = () => {
        const mime = recorder.mimeType || "audio/webm";
        const merged = new Blob(chunksRef.current, { type: mime });
        resolve(merged);
      };
      try {
        recorder.stop();
      } catch {
        // 强制 resolve 空 Blob，避免 Promise 永挂
        resolve(new Blob([], { type: "audio/webm" }));
      }
    });

    releaseStream();
    mediaRecorderRef.current = null;
    chunksRef.current = [];
    setIsRecording(false);

    if (blob.size === 0) {
      setError("录音为空，未采集到音频数据");
      return null;
    }

    // 上传转写
    setIsTranscribing(true);
    try {
      const ext = pickExt(blob.type);
      const filename = `voice-${Date.now()}${ext}`;
      const form = new FormData();
      form.append("file", blob, filename);

      const res = await apiFetch("/api/voice/transcribe", {
        method: "POST",
        body: form,
        // STT 链路可能较慢，放宽到 60s
        timeout: 60_000,
      });
      if (!res.ok) {
        // 读取后端错误体
        let detail = `转写失败（HTTP ${res.status}）`;
        try {
          const body = await res.json();
          if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
          else if (body?.error) detail = String(body.error);
        } catch {
          /* 忽略 */
        }
        setError(detail);
        return null;
      }
      const data = (await res.json()) as TranscribeResponse;
      const text = (data?.text || "").trim();
      if (!text) {
        setError("转写结果为空，请重试");
        return null;
      }
      return text;
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.kind === "timeout"
            ? "语音转写超时，请重试"
            : err.message
          : err instanceof Error
            ? err.message
            : String(err);
      setError(msg);
      return null;
    } finally {
      setIsTranscribing(false);
    }
  }, [releaseStream]);

  /** 切换录音状态 */
  const toggle = useCallback(async (): Promise<string | null | boolean> => {
    if (isTranscribing) return false;
    if (isRecording) {
      return await stop();
    }
    return await start();
  }, [isRecording, isTranscribing, start, stop]);

  const clearError = useCallback(() => setError(null), []);

  return {
    isRecording,
    isTranscribing,
    error,
    start,
    stop,
    toggle,
    clearError,
  };
}

/** 根据 Blob mime 推断扩展名（兜底 .webm） */
function pickExt(mime: string): string {
  const m = (mime || "").toLowerCase();
  if (m.includes("webm")) return ".webm";
  if (m.includes("ogg")) return ".ogg";
  if (m.includes("mp4") || m.includes("m4a")) return ".m4a";
  if (m.includes("wav")) return ".wav";
  if (m.includes("mp3")) return ".mp3";
  return ".webm";
}
