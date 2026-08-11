"use client";

import { useRef, useEffect, useState } from "react";
import { Plus, FileUp, FolderPlus, Trash2, Folder, ChevronRight } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import type { Project } from "@/hooks/useProjects";
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
  /** 已注册项目列表：传入后「关联项目」展开为二级选择面板 */
  projects?: Project[];
  /** 从已有项目列表中选择一个 */
  onSelectExistingProject?: (projectId: number) => void;
}

/** + 极简菜单按钮：上传文件 / 关联项目 / 清空上下文 */
export function UploadMenu({ open, onToggle, onPickFile, onPickDirectory, onClearContext, hasContext, onClose, projects, onSelectExistingProject }: UploadMenuProps) {
  const { t } = useTranslation();
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const [projectSubOpen, setProjectSubOpen] = useState(false);
  const subRef = useRef<HTMLDivElement>(null);

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

  // 有关联项目列表时，「关联项目」变为二级入口
  const hasProjectList = Array.isArray(projects) && projects.length > 0;

  return (
    <div style={{ position: "relative", flexShrink: 0 }}>
      <button
        ref={btnRef}
        data-upload-menu-trigger=""
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

          {/* 关联项目：有列表时展开为二级面板，否则直接选目录 */}
          {hasProjectList ? (
            <div style={{ position: "relative" }}>
              <button
                onClick={() => setProjectSubOpen((v) => !v)}
                style={{
                  ...popoverItemStyle,
                  justifyContent: "space-between",
                  background: projectSubOpen ? "var(--bg-level-3)" : "transparent",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
                onMouseLeave={(e) => { if (!projectSubOpen) e.currentTarget.style.background = "transparent"; }}
              >
                <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <FolderPlus style={{ width: "15px", height: "15px", color: "var(--color-primary)", flexShrink: 0 }} />
                  <span>{t("chat.menu.linkProject")}</span>
                </span>
                <ChevronRight style={{
                  width: "12px",
                  height: "12px",
                  color: "var(--text-level-4)",
                  transform: projectSubOpen ? "rotate(90deg)" : "rotate(0deg)",
                  transition: "transform 0.15s ease",
                }} />
              </button>

              {/* 二级项目选择面板 */}
              {projectSubOpen && (
                <div
                  ref={subRef}
                  style={{
                    position: "absolute",
                    left: "100%",
                    top: "-4px",
                    marginLeft: "4px",
                    minWidth: "180px",
                    maxHeight: "240px",
                    overflowY: "auto",
                    background: "var(--bg-level-1)",
                    border: "1px solid var(--border-primary)",
                    borderRadius: "var(--radius-md)",
                    boxShadow: "var(--shadow-lg)",
                    padding: "4px",
                    zIndex: 1000,
                  }}
                >
                  {/* 已有项目列表 */}
                  {projects!.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => {
                        onClose();
                        onSelectExistingProject?.(p.id);
                      }}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        width: "100%",
                        padding: "6px 10px",
                        border: "none",
                        borderRadius: "var(--radius-sm)",
                        background: "transparent",
                        cursor: "pointer",
                        fontSize: "12px",
                        color: "var(--text-level-2)",
                        textAlign: "left",
                        outline: "none",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                      title={p.path}
                    >
                      <Folder style={{ width: "13px", height: "13px", color: "var(--color-primary)", flexShrink: 0 }} />
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.name}</span>
                    </button>
                  ))}
                  {/* 分割线 + 选择新目录 */}
                  <div style={{ height: "1px", background: "var(--border-secondary)", margin: "4px 0" }} />
                  <button
                    onClick={() => { onClose(); onPickDirectory(); }}
                    style={{
                      ...popoverItemStyle,
                      fontSize: "12px",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                  >
                    <FolderPlus style={{ width: "13px", height: "13px", color: "var(--text-level-3)", flexShrink: 0 }} />
                    <span style={{ color: "var(--text-level-3)" }}>{t("chat.menu.selectNewDirectory")}</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={() => { onClose(); onPickDirectory(); }}
              style={popoverItemStyle}
              onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
            >
              <FolderPlus style={{ width: "15px", height: "15px", color: "var(--color-primary)", flexShrink: 0 }} />
              <span>{t("chat.menu.linkProject")}</span>
            </button>
          )}

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
