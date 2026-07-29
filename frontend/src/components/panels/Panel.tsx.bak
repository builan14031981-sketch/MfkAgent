"use client";

import { useEffect, useRef } from "react";

interface PanelProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  width?: string;
}

export function Panel({ isOpen, onClose, title, children, width = "380px" }: PanelProps) {
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
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    if (isOpen) {
      setTimeout(() => document.addEventListener("mousedown", handleClickOutside), 100);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <>
      {/* 遮罩层 - 半透明，不阻挡交互 */}
      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0, 0, 0, 0.15)",
          zIndex: 99,
          animation: "fadeIn 0.15s ease",
        }}
      />
      {/* 面板 - 从左下角展开 */}
      <div
        ref={panelRef}
        style={{
          position: "fixed",
          bottom: "16px",
          left: "296px", // Sidebar 宽度 280px + 16px 间距
          width,
          maxHeight: "calc(100vh - 32px)",
          background: "var(--bg-level-1)",
          borderRadius: "var(--radius-xl)",
          boxShadow: "var(--shadow-lg), 0 0 0 1px var(--border-primary)",
          zIndex: 100,
          display: "flex",
          flexDirection: "column",
          transformOrigin: "bottom left",
          animation: "panelOpen 0.25s ease forwards",
          opacity: 0,
          transform: "scale(0.95) translateY(10px)",
        }}
      >
        {/* 面板头部 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 20px 12px",
          borderBottom: "1px solid var(--border-secondary)",
        }}>
          <h2 style={{
            fontSize: "15px",
            fontWeight: "600",
            color: "var(--text-level-1)",
            margin: 0,
          }}>{title}</h2>
        </div>
        {/* 面板内容 */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px 20px 20px",
        }}>
          {children}
        </div>
      </div>
    </>
  );
}
