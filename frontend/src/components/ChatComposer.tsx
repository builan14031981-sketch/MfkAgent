"use client";

import { memo } from "react";
import { ChatInput, ChatInputProps } from "@/components/ChatInput";
import { useTranslation } from "@/hooks/useTranslation";

/**
 * 一体化底置容器（Codex / Cursor 模式）：
 * ChatInput 卡片 + 免责声明统一封装在贴底容器中，
 * 主页与 Chat 页共用同一结构，保证发送跳转时输入框物理位置完全一致、无抖动。
 *
 * memo：流式期间父级每次 chunk 更新 state，props 稳定（回调已 useCallback）时
 * 跳过重渲染，避免每次渲染重跑 ChatInput 及其下拉选择器树。
 */
export const ChatComposer = memo(function ChatComposer(props: ChatInputProps) {
  const { t } = useTranslation();
  return (
    <div style={{
      width: "100%",
      maxWidth: "768px",
      margin: "0 auto",
      padding: "8px 16px",
    }}>
      <ChatInput {...props} />
      <p style={{
        textAlign: "center",
        fontSize: "11px",
        lineHeight: 1.4,
        color: "var(--text-level-4)",
        margin: 0,
        paddingTop: "4px",
        paddingBottom: "4px",
        pointerEvents: "none",
      }}>{t("chat.aiMayError")}</p>
    </div>
  );
});
