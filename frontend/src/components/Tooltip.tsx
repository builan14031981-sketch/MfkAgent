"use client";

import React, { useState, useRef, useEffect, useLayoutEffect, useCallback } from "react";
import { createPortal } from "react-dom";

export interface TooltipProps {
  content: React.ReactNode;
  shortcut?: string;
  side?: "top" | "bottom" | "left" | "right";
  delay?: number;
  children: React.ReactElement;
  disabled?: boolean;
}

export function Tooltip({
  content,
  shortcut,
  side = "top",
  delay = 180,
  children,
  disabled = false,
}: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [coords, setCoords] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const triggerRef = useRef<HTMLElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    setMounted(true);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const updatePosition = useCallback(() => {
    if (!triggerRef.current || !tooltipRef.current) return;
    const triggerRect = triggerRef.current.getBoundingClientRect();
    const tooltipRect = tooltipRef.current.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const gap = 6;

    let x = 0;
    let y = 0;

    switch (side) {
      case "bottom":
        x = triggerRect.left + (triggerRect.width - tooltipRect.width) / 2;
        y = triggerRect.bottom + gap;
        break;
      case "left":
        x = triggerRect.left - tooltipRect.width - gap;
        y = triggerRect.top + (triggerRect.height - tooltipRect.height) / 2;
        break;
      case "right":
        x = triggerRect.right + gap;
        y = triggerRect.top + (triggerRect.height - tooltipRect.height) / 2;
        break;
      case "top":
      default:
        x = triggerRect.left + (triggerRect.width - tooltipRect.width) / 2;
        y = triggerRect.top - tooltipRect.height - gap;
        break;
    }

    // 视口边缘碰撞保护（杜绝溢出屏幕）
    x = Math.max(8, Math.min(x, vw - tooltipRect.width - 8));
    y = Math.max(8, Math.min(y, vh - tooltipRect.height - 8));

    setCoords({ x, y });
  }, [side]);

  useLayoutEffect(() => {
    if (visible) {
      updatePosition();
    }
  }, [visible, updatePosition]);

  const handleMouseEnter = () => {
    if (disabled || !content) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setVisible(true);
    }, delay);
  };

  const handleMouseLeave = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setVisible(false);
  };

  const handleClick = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setVisible(false);
  };

  if (!content || disabled) {
    return children;
  }

  // 克隆子元素并绑定事件，移除子元素身上的原生 title 防止触发系统原生丑陋小方框
  const target = children as React.ReactElement<any>;
  const clonedChild = React.cloneElement(target, {
    ref: (node: HTMLElement | null) => {
      triggerRef.current = node;
      // 保留原有 ref（如果有）
      const origRef = (target as any).ref;
      if (typeof origRef === "function") origRef(node);
      else if (origRef && typeof origRef === "object") origRef.current = node;
    },
    onMouseEnter: (e: React.MouseEvent) => {
      target.props?.onMouseEnter?.(e);
      handleMouseEnter();
    },
    onMouseLeave: (e: React.MouseEvent) => {
      target.props?.onMouseLeave?.(e);
      handleMouseLeave();
    },
    onClick: (e: React.MouseEvent) => {
      target.props?.onClick?.(e);
      handleClick();
    },
    // 强制抹除原生 title
    title: undefined,
  });

  return (
    <>
      {clonedChild}
      {mounted &&
        visible &&
        createPortal(
          <div
            ref={tooltipRef}
            style={{
              position: "fixed",
              left: coords.x,
              top: coords.y,
              zIndex: 9999,
              pointerEvents: "none",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 8px",
              borderRadius: "4px",
              background: "rgba(22, 23, 26, 0.94)",
              backdropFilter: "blur(8px)",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              boxShadow: "0 4px 12px rgba(0, 0, 0, 0.24), 0 1px 3px rgba(0, 0, 0, 0.12)",
              fontSize: "11.5px",
              lineHeight: 1.2,
              fontWeight: 500,
              color: "#ffffff",
              letterSpacing: "-0.01em",
              whiteSpace: "nowrap",
              animation: "mfkTooltipFadeIn 0.12s cubic-bezier(0.16, 1, 0.3, 1)",
            }}
          >
            <span>{content}</span>
            {shortcut && (
              <kbd
                style={{
                  fontFamily: "inherit",
                  fontSize: "10px",
                  lineHeight: 1,
                  padding: "2px 4px",
                  borderRadius: "3px",
                  background: "rgba(255, 255, 255, 0.15)",
                  border: "1px solid rgba(255, 255, 255, 0.2)",
                  color: "rgba(255, 255, 255, 0.85)",
                  fontWeight: 500,
                }}
              >
                {shortcut}
              </kbd>
            )}
          </div>,
          document.body
        )}
    </>
  );
}
