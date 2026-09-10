"use client";

import { useEffect, useRef } from "react";
import { X, ChevronLeft } from "lucide-react";

interface PanelProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  width?: string;
  height?: string;
  variant?: "center" | "bottom-left";
  /** 头部标题右侧的自定义区域（如设置面板右上角的高级模式开关） */
  headerExtra?: React.ReactNode;
  /** 返回上一级视图回调（存在时在标题左侧渲染标准返回键） */
  onBack?: () => void;
}

export function Panel({ isOpen, onClose, title, children, width = "700px", height, variant = "center", headerExtra, onBack }: PanelProps) {
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
          padding: "16px 22px 14px",
          borderBottom: "1px solid var(--border-secondary)",
          gap: "12px",
          flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
            {onBack && (
              <button
                type="button"
                onClick={onBack}
                aria-label="返回上一级"
                title="返回上一级"
                className="mf-icon-btn"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "4px",
                  height: "28px",
                  padding: "0 8px 0 6px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-primary)",
                  background: "var(--bg-level-2)",
                  color: "var(--text-level-2)",
                  cursor: "pointer",
                  fontSize: "12px",
                  fontWeight: 500,
                  transition: "all var(--transition-fast)",
                  flexShrink: 0,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--bg-level-3)";
                  e.currentTarget.style.color = "var(--text-level-1)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "var(--bg-level-2)";
                  e.currentTarget.style.color = "var(--text-level-2)";
                }}
              >
                <ChevronLeft style={{ width: "14px", height: "14px" }} />
                <span>返回</span>
              </button>
            )}
            <h2 style={{
              fontSize: "16px",
              fontWeight: "600",
              color: "var(--text-level-1)",
              margin: 0,
              lineHeight: 1.3,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}>{title}</h2>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", flexShrink: 0 }}>
            {headerExtra}
            <button
              type="button"
              onClick={onClose}
              aria-label="关闭"
              title="关闭 (Esc)"
              className="mf-icon-btn"
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "28px",
                height: "28px",
                padding: 0,
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: "transparent",
                color: "var(--text-level-3)",
                cursor: "pointer",
                transition: "background var(--transition-fast), color var(--transition-fast)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-level-3)";
                e.currentTarget.style.color = "var(--text-level-1)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.color = "var(--text-level-3)";
              }}
            >
              <X style={{ width: "16px", height: "16px" }} />
            </button>
          </div>
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
