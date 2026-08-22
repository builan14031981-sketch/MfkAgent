"use client";

/**
 * SettingsToast —— 设置面板内保存反馈浮条
 *
 * 消费 lib/toastStore.ts 的全局 toast store；挂在 SettingsPanel 的 relative 内容容器内，
 * absolute 定位右上角，3 秒自动消失。成功/失败两种样式复用项目 CSS variables。
 */
import { useEffect } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { useSettingsToast } from "@/lib/toastStore";

export function SettingsToast() {
  const { message, type, hideToast } = useSettingsToast();

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(hideToast, 3000);
    return () => clearTimeout(timer);
  }, [message, hideToast]);

  if (!message || !type) return null;

  const isError = type === "error";
  const Icon = isError ? XCircle : CheckCircle2;
  const color = isError ? "var(--color-danger, #ef4444)" : "var(--color-success)";
  const bg = isError ? "rgba(239,68,68,0.1)" : "rgba(16,185,129,0.12)";

  return (
    <div
      role={isError ? "alert" : "status"}
      style={{
        position: "absolute",
        top: "10px",
        right: "16px",
        zIndex: 300,
        display: "flex",
        alignItems: "center",
        gap: "8px",
        maxWidth: "calc(100% - 200px)",
        padding: "8px 14px",
        borderRadius: "var(--radius-md)",
        background: bg,
        border: `1px solid ${isError ? "rgba(239,68,68,0.3)" : "rgba(16,185,129,0.3)"}`,
        fontSize: "12px",
        color: "var(--text-level-1)",
        boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
        pointerEvents: "none",
      }}
    >
      <Icon style={{ width: "14px", height: "14px", color, flexShrink: 0 }} />
      <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {message}
      </span>
    </div>
  );
}