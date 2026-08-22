"use client";

import { useState, useRef, useEffect } from "react";
import { X, ZoomIn } from "lucide-react";

/** 单个截图项 */
export interface ScreenshotItem {
  id: string;
  /** base64 data URL，用于缩略图和预览 */
  dataUrl: string;
  /** 原始 File 对象，发送时上传 */
  file: File;
}

interface ScreenshotPreviewBarProps {
  screenshots: ScreenshotItem[];
  onRemove: (id: string) => void;
  onPreview: (item: ScreenshotItem) => void;
}

/**
 * 截图缩略图条：显示在输入框上方
 * 每个缩略图 96x72px，圆角，边框，右上角删除按钮
 * 点击缩略图放大预览
 */
export function ScreenshotPreviewBar({ screenshots, onRemove, onPreview }: ScreenshotPreviewBarProps) {
  if (screenshots.length === 0) return null;

  return (
    <div style={{
      display: "flex",
      flexWrap: "wrap",
      gap: "8px",
      marginBottom: "8px",
      padding: "0 2px",
    }}>
      {screenshots.map((item) => (
        <ScreenshotThumbnail
          key={item.id}
          item={item}
          onRemove={onRemove}
          onPreview={onPreview}
        />
      ))}
    </div>
  );
}

interface ScreenshotThumbnailProps {
  item: ScreenshotItem;
  onRemove: (id: string) => void;
  onPreview: (item: ScreenshotItem) => void;
}

/** 单个截图缩略图 */
function ScreenshotThumbnail({ item, onRemove, onPreview }: ScreenshotThumbnailProps) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      style={{
        position: "relative",
        width: "96px",
        height: "72px",
        borderRadius: "8px",
        overflow: "hidden",
        border: "1px solid var(--border-primary)",
        background: "var(--bg-level-2)",
        cursor: "zoom-in",
        flexShrink: 0,
        boxShadow: hovered ? "0 2px 8px rgba(0,0,0,0.15)" : "none",
        transition: "box-shadow 0.15s",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => onPreview(item)}
      title="点击放大预览"
    >
      {/* 缩略图 */}
      <img
        src={item.dataUrl}
        alt="截图"
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          display: "block",
        }}
      />

      {/* hover 遮罩 + 放大图标 */}
      {hovered && (
        <div style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          background: "rgba(0,0,0,0.3)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}>
          <ZoomIn style={{ width: "20px", height: "20px", color: "#fff" }} />
        </div>
      )}

      {/* 删除按钮 */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onRemove(item.id);
        }}
        style={{
          position: "absolute",
          top: "4px",
          right: "4px",
          width: "20px",
          height: "20px",
          borderRadius: "50%",
          border: "none",
          background: "rgba(0,0,0,0.6)",
          color: "#fff",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: 0,
          opacity: hovered ? 1 : 0.7,
          transition: "opacity 0.15s",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(220,50,50,0.9)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(0,0,0,0.6)"; }}
        title="删除截图"
      >
        <X style={{ width: "12px", height: "12px" }} />
      </button>
    </div>
  );
}
