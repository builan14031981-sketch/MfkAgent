"use client";

import { useRef, useEffect } from "react";
import { Plus, FileUp, FolderPlus, Trash2 } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import {
  popoverStyle,
  popoverItemStyle,
  itemHoverBackground,
  pillActiveBackground,
  pillActiveColor,
  ghostPillHoverBackground,
  ghostPillHoverColor,
  ghostPillHoverShadow,
} from "./styles";

interface UploadMenuProps {
  open: boolean;
  onToggle: () => void;
  onPickFile: () => void;
  onPickDirectory: () => void;
  onClearContext: () => void;
  hasContext: boolean;
  onClose: () => void;
}

/** + 极简菜单按钮：上传文件 / 关联项目 / 清空上下文 */
export function UploadMenu({ open, onToggle, onPickFile, onPickDirectory, onClearContext, hasContext, onClose }: UploadMenuProps) {
  const { t } = useTranslation();
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (btnRef.current?.contains(target)) return;
      if (popRef.current?.contains(target)) return;
      onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, onClose]);

  return (
    <div style={{ position: "relative", flexShrink: 0 }}>
      <button
        ref={btnRef}
        onClick={onToggle}
        title={t("chat.menu.uploadFile")}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "28px",
          height: "28px",
          padding: "0",
          borderRadius: "var(--radius-full)",
          border: "1px solid transparent",
          background: open ? pillActiveBackground : "transparent",
          cursor: "pointer",
          color: open ? pillActiveColor : "var(--text-level-4)",
          flexShrink: 0,
          outline: "none",
          transition: "all 0.2s ease-in-out",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = ghostPillHoverBackground;
          e.currentTarget.style.color = ghostPillHoverColor;
          e.currentTarget.style.boxShadow = ghostPillHoverShadow;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = open ? pillActiveBackground : "transparent";
          e.currentTarget.style.color = open ? pillActiveColor : "var(--text-level-4)";
          e.currentTarget.style.boxShadow = "none";
        }}
      >
        <Plus style={{
          width: "16px",
          height: "16px",
          transform: open ? "rotate(45deg)" : "rotate(0deg)",
          transition: "transform var(--transition-normal)",
        }} />
      </button>

      {open && (
        <div ref={popRef} style={popoverStyle}>
          <button
            onClick={() => { onClose(); onPickFile(); }}
            style={popoverItemStyle}
            onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            <FileUp style={{ width: "15px", height: "15px", color: "var(--color-primary)", flexShrink: 0 }} />
            <span>{t("chat.menu.uploadFile")}</span>
          </button>
          <button
            onClick={() => { onClose(); onPickDirectory(); }}
            style={popoverItemStyle}
            onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            <FolderPlus style={{ width: "15px", height: "15px", color: "var(--color-primary)", flexShrink: 0 }} />
            <span>{t("chat.menu.linkProject")}</span>
          </button>
          <div style={{
            height: "1px",
            background: "var(--border-secondary)",
            margin: "4px 0",
          }} />
          <button
            onClick={() => { onClose(); onClearContext(); }}
            disabled={!hasContext}
            style={{
              ...popoverItemStyle,
              color: hasContext ? "var(--color-error)" : "var(--text-level-4)",
              cursor: hasContext ? "pointer" : "not-allowed",
            }}
            onMouseEnter={(e) => { if (hasContext) e.currentTarget.style.background = itemHoverBackground; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            <Trash2 style={{ width: "15px", height: "15px", color: hasContext ? "var(--color-error)" : "var(--text-level-4)", flexShrink: 0 }} />
            <span>{t("chat.menu.clearContext")}</span>
          </button>
        </div>
      )}
    </div>
  );
}
