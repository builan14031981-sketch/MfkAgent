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
      // 2026-08-16：输入区最大宽度 768px → 1200px（默认 1280 窗口下两侧仅约 40px 呼吸空间，
      // 消除此前两侧 256px 的大白边；窗口更宽时居中留白，避免输入框拉得过长）
      maxWidth: "1200px",
      margin: "0 auto",
      padding: "0 0 8px 0",
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



