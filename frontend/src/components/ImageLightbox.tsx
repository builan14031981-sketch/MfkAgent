"use client";

import { useEffect, useCallback, useState } from "react";
import { createPortal } from "react-dom";
import { X, ChevronLeft, ChevronRight } from "lucide-react";

interface ImageLightboxProps {
  /** 当前显示的图片 URL 列表 */
  urls: string[];
  /** 当前显示的图片索引 */
  initialIndex?: number;
  /** 关闭回调 */
  onClose: () => void;
}

/**
 * 全屏图片预览 Lightbox：
 * - 半透明遮罩 + 图片居中
 * - Esc / 点击遮罩 / × 按钮关闭
 * - 多图时左右箭头切换
 * - 仅 fadeIn，关闭时直接卸载
 */
export function ImageLightbox({ urls, initialIndex = 0, onClose }: ImageLightboxProps) {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [imageLoaded, setImageLoaded] = useState(false);

  const hasMultiple = urls.length > 1;

  const goNext = useCallback(() => {
    setCurrentIndex((i) => (i + 1) % urls.length);
    setImageLoaded(false);
  }, [urls.length]);

  const goPrev = useCallback(() => {
    setCurrentIndex((i) => (i - 1 + urls.length) % urls.length);
    setImageLoaded(false);
  }, [urls.length]);

  // Esc 关闭
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (hasMultiple) {
        if (e.key === "ArrowRight") goNext();
        if (e.key === "ArrowLeft") goPrev();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    // 阻止背景滚动
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [onClose, goNext, goPrev, hasMultiple]);

  // 切换图片时重置 loaded 状态
  useEffect(() => {
    setImageLoaded(false);
  }, [currentIndex]);

  // SSR 守卫：document 未就绪时不渲染
  if (typeof document === "undefined") return null;

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 99999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0, 0, 0, 0.78)",
        animation: "fadeIn 0.15s ease",
        cursor: "zoom-out",
      }}
    >
      {/* 关闭按钮 */}
      <button
        onClick={(e) => { e.stopPropagation(); onClose(); }}
        style={{
          position: "absolute",
          top: "16px",
          right: "16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "36px",
          height: "36px",
          borderRadius: "50%",
          border: "none",
          background: "rgba(255, 255, 255, 0.12)",
          color: "rgba(255, 255, 255, 0.8)",
          cursor: "pointer",
          zIndex: 10,
          transition: "background 0.15s ease",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255, 255, 255, 0.24)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255, 255, 255, 0.12)"; }}
      >
        <X style={{ width: "20px", height: "20px" }} />
      </button>

      {/* 多图：左箭头 */}
      {hasMultiple && (
        <button
          onClick={(e) => { e.stopPropagation(); goPrev(); }}
          style={{
            position: "absolute",
            left: "16px",
            top: "50%",
            transform: "translateY(-50%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "40px",
            height: "40px",
            borderRadius: "50%",
            border: "none",
            background: "rgba(255, 255, 255, 0.12)",
            color: "rgba(255, 255, 255, 0.8)",
            cursor: "pointer",
            zIndex: 10,
            transition: "background 0.15s ease",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255, 255, 255, 0.24)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255, 255, 255, 0.12)"; }}
        >
          <ChevronLeft style={{ width: "24px", height: "24px" }} />
        </button>
      )}

      {/* 多图：右箭头 */}
      {hasMultiple && (
        <button
          onClick={(e) => { e.stopPropagation(); goNext(); }}
          style={{
            position: "absolute",
            right: "16px",
            top: "50%",
            transform: "translateY(-50%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "40px",
            height: "40px",
            borderRadius: "50%",
            border: "none",
            background: "rgba(255, 255, 255, 0.12)",
            color: "rgba(255, 255, 255, 0.8)",
            cursor: "pointer",
            zIndex: 10,
            transition: "background 0.15s ease",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255, 255, 255, 0.24)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255, 255, 255, 0.12)"; }}
        >
          <ChevronRight style={{ width: "24px", height: "24px" }} />
        </button>
      )}

      {/* 图片 */}
      <img
        src={urls[currentIndex]}
        onClick={(e) => e.stopPropagation()}
        onLoad={() => setImageLoaded(true)}
        style={{
          maxWidth: "90vw",
          maxHeight: "90vh",
          objectFit: "contain",
          borderRadius: "4px",
          cursor: "default",
          opacity: imageLoaded ? 1 : 0,
          transition: "opacity 0.2s ease",
        }}
      />

      {/* 图片计数 */}
      {hasMultiple && (
        <div
          style={{
            position: "absolute",
            bottom: "20px",
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: "13px",
            color: "rgba(255, 255, 255, 0.6)",
            userSelect: "none",
          }}
        >
          {currentIndex + 1} / {urls.length}
        </div>
      )}
    </div>,
    document.body
  );
}
