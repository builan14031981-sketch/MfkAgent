"use client";

import { useEffect, useRef } from "react";

interface PanelProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  width?: string;
  height?: string;
  variant?: "center" | "bottom-left";
  /** 头部标题右侧的自定义区域（如设置面板右上角的开发者模式开关） */
  headerExtra?: React.ReactNode;
}

export function Panel({ isOpen, onClose, title, children, width = "700px", height, variant = "center", headerExtra }: PanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      // portal 弹层（自定义下拉等）物理挂在 body 上，视为面板内交互，
      // 否则会被误判为“点击外部”导致面板关闭、弹层随卸载丢失 click 事件
      if (target instanceof Element && target.closest("[data-portal-popover]")) return;
      if (panelRef.current && !panelRef.current.contains(target)) {
        onClose();
      }
    };
    if (isOpen) {
      setTimeout(() => document.addEventListener("mousedown", handleClickOutside), 100);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const isCenter = variant === "center";

  return (
    <>
      {/* 遮罩层 */}
      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "var(--overlay-modal)",
          zIndex: 99,
          animation: "fadeIn 0.15s ease",
        }}
      />
      {/* 面板（mf-panel-root：移动端在 globals.css 中升级为全屏 sheet） */}
      <div
        ref={panelRef}
        className="mf-panel-root"
        style={{
          position: "fixed",
          ...(isCenter ? {
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width,
            ...(height ? { height } : {}),
            maxWidth: "90vw",
            maxHeight: "80vh",
          } : {
            bottom: "16px",
            left: "296px",
            width,
            maxHeight: "calc(100vh - 32px)",
            transformOrigin: "bottom left",
          }),
          background: "var(--bg-level-1)",
          borderRadius: "var(--radius-xl)",
          boxShadow: "var(--shadow-lg), 0 0 0 1px var(--border-primary)",
          zIndex: 100,
          display: "flex",
          flexDirection: "column",
          animation: isCenter ? "panelCenterOpen 0.25s ease forwards" : "panelOpen 0.25s ease forwards",
          opacity: 0,
        }}
      >
        {/* 面板头部 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "20px 24px 16px",
          borderBottom: "1px solid var(--border-secondary)",
        }}>
          <h2 style={{
            fontSize: "16px",
            fontWeight: "600",
            color: "var(--text-level-1)",
            margin: 0,
          }}>{title}</h2>
          {headerExtra}
        </div>
        {/* 面板内容 */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "20px 24px 24px",
        }}>
          {children}
        </div>
      </div>
    </>
  );
}
