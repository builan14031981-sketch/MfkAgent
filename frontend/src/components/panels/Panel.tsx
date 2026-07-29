"use client";

import { useEffect } from "react";
import { X } from "lucide-react";

interface PanelProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  width?: string;
}

export function Panel({ isOpen, onClose, title, children, width = "400px" }: PanelProps) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <>
      {/* 遮罩层 */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0, 0, 0, 0.3)",
          zIndex: 100,
          animation: "fadeIn 0.2s ease",
        }}
      />
      {/* 面板 */}
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width,
          background: "var(--bg-level-1)",
          borderLeft: "1px solid var(--border-primary)",
          zIndex: 101,
          display: "flex",
          flexDirection: "column",
          animation: "slideInFromRight 0.3s ease",
        }}
      >
        {/* 面板头部 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 20px",
          borderBottom: "1px solid var(--border-primary)",
        }}>
          <h2 style={{
            fontSize: "16px",
            fontWeight: "600",
            color: "var(--text-level-1)",
            margin: 0,
          }}>{title}</h2>
          <button
            onClick={onClose}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "32px",
              height: "32px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              color: "var(--text-level-3)",
            }}
          >
            <X style={{ width: "18px", height: "18px" }} />
          </button>
        </div>
        {/* 面板内容 */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "20px",
        }}>
          {children}
        </div>
      </div>
    </>
  );
}
