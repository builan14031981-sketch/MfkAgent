"use client";

import { useEffect } from "react";
import { X, Download } from "lucide-react";

interface ScreenshotLightboxProps {
  /** 图片 base64 data URL */
  dataUrl: string;
  /** 关闭回调 */
  onClose: () => void;
  /** 另存为回调（可选） */
  onSaveAs?: () => void;
}

/**
 * 截图放大预览：全屏半透明遮罩 + 居中大图
 * 点击遮罩或按 ESC 关闭
 */
export function ScreenshotLightbox({ dataUrl, onClose, onSaveAs }: ScreenshotLightboxProps) {
  // ESC 关闭
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", handler);
    // 禁止背景滚动
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        background: "rgba(0, 0, 0, 0.8)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 99999,
        cursor: "zoom-out",
      }}
    >
      {/* 关闭按钮 */}
      <button
        onClick={(e) => { e.stopPropagation(); onClose(); }}
        style={{
          position: "absolute",
          top: "20px",
          right: "20px",
          width: "36px",
          height: "36px",
          borderRadius: "50%",
          border: "none",
          background: "rgba(255,255,255,0.1)",
          color: "#fff",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "background 0.15s",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.2)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.1)"; }}
        title="关闭 (ESC)"
      >
        <X style={{ width: "18px", height: "18px" }} />
      </button>

      {/* 大图 */}
      <img
        src={dataUrl}
        alt="截图预览"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: "80vw",
          maxHeight: "75vh",
          objectFit: "contain",
          borderRadius: "8px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
          cursor: "default",
        }}
      />

      {/* 底部操作栏 */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          marginTop: "16px",
          display: "flex",
          gap: "12px",
          alignItems: "center",
        }}
      >
        {onSaveAs && (
          <button
            onClick={onSaveAs}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "8px 16px",
              borderRadius: "6px",
              border: "1px solid rgba(255,255,255,0.2)",
              background: "rgba(255,255,255,0.1)",
              color: "#fff",
              fontSize: "13px",
              cursor: "pointer",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.2)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.1)"; }}
          >
            <Download style={{ width: "14px", height: "14px" }} />
            另存为
          </button>
        )}
      </div>
    </div>
  );
}
