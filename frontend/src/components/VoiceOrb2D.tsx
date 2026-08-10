"use client";

import { Mic, Loader2 } from "lucide-react";

export interface VoiceOrb2DProps {
  /** 是否处于录音/说话状态（true=录音指示环） */
  isActive: boolean;
  /** 是否正在转写（true=单色 spinner） */
  isTranscribing?: boolean;
  /** 点击回调（由父组件决定开始/停止录音） */
  onClick?: () => void;
  /** 透传样式（位置/布局由父组件控制） */
  style?: React.CSSProperties;
  /** 无障碍标题 */
  title?: string;
  /** 是否禁用 */
  disabled?: boolean;
}

/** 逻辑尺寸（px），与旧版保持一致 */
const SIZE = 28;

/**
 * 语音输入指示器（V2 Quiet 版，替代原 Canvas 发光小球）。
 *
 * 设计原则：系统状态反馈，而非 AI 玩具——
 * - Idle：单色 Mic 图标（Secondary Text，描边随全局 1.75 规范）。
 * - 录音中：图标升为 accent，外圈 1px 指示环微幅扩散淡出（无光晕）。
 * - 转写中：单色 spinner（复用全局 mf-spinner 语言）。
 *
 * 组件名与 props 契约保持不变，父组件（ChatInput）零改动。
 */
export function VoiceOrb2D({
  isActive,
  isTranscribing = false,
  onClick,
  style,
  title,
  disabled = false,
}: VoiceOrb2DProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
      style={{
        position: "relative",
        width: `${SIZE}px`,
        height: `${SIZE}px`,
        padding: 0,
        border: "none",
        borderRadius: "50%",
        background: "transparent",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.4 : 1,
        outline: "none",
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: isActive || isTranscribing ? "var(--mf-accent)" : "var(--text-level-3)",
        transition: "color var(--mf-motion-base), opacity var(--mf-motion-base)",
        ...style,
      }}
    >
      {/* 录音指示环：1px 描边微幅扩散，无发光 */}
      {isActive && !isTranscribing && <span className="mf-voice-ring" aria-hidden />}

      {isTranscribing ? (
        <Loader2 size={16} strokeWidth={1.75} className="animate-spin" style={{ opacity: 0.85 }} />
      ) : (
        <Mic size={16} strokeWidth={1.75} />
      )}
    </button>
  );
}
