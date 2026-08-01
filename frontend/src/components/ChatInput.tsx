"use client";

import { useState, useRef, useEffect } from "react";
import { Plus, FileUp, FolderPlus, Trash2, Send, Brain, Folder, X } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { selectDirectory } from "@/lib/selectDirectory";
import { FilePill } from "@/components/FileDropZone";
import type { Model } from "@/hooks/useModels";

export type ReasoningEffort = "none" | "low" | "high";

export interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isSending: boolean;
  placeholder: string;
  disabled?: boolean;

  models: Model[];
  modelId: string | null;
  onModelChange: (id: string) => void;

  reasoningEffort: ReasoningEffort;
  onReasoningChange: (e: ReasoningEffort) => void;

  onUploadFile: (file: File) => void;
  onSelectDirectory: (path: string) => void;
  onClearContext: () => void;
  hasContext: boolean;

  files: string[];
  onRemoveFile: (path: string) => void;
  projectName?: string | null;
  onRemoveProject?: () => void;

  leftExtra?: React.ReactNode;
}

/**
 * 一体化紧凑输入卡片：
 * textarea + 底部工具栏（+ 菜单 / 模型选择 / 思考胶囊 / 发送按钮）合并为单卡片，
 * 1px 淡边框 + 柔和阴影。草稿状态（文件 / 项目 Pill）渲染在 textarea 上方。
 */
export function ChatInput({
  value,
  onChange,
  onSend,
  isSending,
  placeholder,
  disabled,
  models,
  modelId,
  onModelChange,
  reasoningEffort,
  onReasoningChange,
  onUploadFile,
  onSelectDirectory,
  onClearContext,
  hasContext,
  files,
  onRemoveFile,
  projectName,
  onRemoveProject,
  leftExtra,
}: ChatInputProps) {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 点击外部关闭菜单
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpen]);

  // 自适应高度
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, [value]);

  const handlePickFile = () => {
    setMenuOpen(false);
    fileInputRef.current?.click();
  };

  const handlePickDirectory = async () => {
    setMenuOpen(false);
    const dir = await selectDirectory();
    if (dir) onSelectDirectory(dir);
  };

  const canSend = value.trim().length > 0 && !isSending && !disabled;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) onSend();
    }
  };

  const menuItemStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    width: "100%",
    padding: "8px 12px",
    border: "none",
    background: "transparent",
    cursor: "pointer",
    fontSize: "13px",
    color: "var(--text-level-2)",
    borderRadius: "var(--radius-sm)",
    textAlign: "left",
  };

  return (
    <div style={{
      border: "1px solid var(--border-primary)",
      borderRadius: "var(--radius-xl)",
      background: "var(--bg-level-2)",
      boxShadow: "0 2px 16px rgba(0,0,0,0.08)",
      overflow: "hidden",
    }}>
      {/* 草稿 Pills（文件 + 项目） */}
      {(files.length > 0 || (projectName && onRemoveProject)) && (
        <div style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "6px",
          padding: "10px 12px 0 12px",
        }}>
          {projectName && onRemoveProject && (
            <span style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "3px 6px 3px 10px",
              borderRadius: "var(--radius-full)",
              background: "var(--color-primary-lighter)",
              border: "1px solid var(--color-primary-light)",
              fontSize: "12px",
              color: "var(--color-primary)",
              maxWidth: "220px",
            }}>
              <Folder style={{ width: "12px", height: "12px", flexShrink: 0 }} />
              <span style={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}>{projectName}</span>
              <button
                onClick={onRemoveProject}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "16px",
                  height: "16px",
                  borderRadius: "var(--radius-full)",
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  color: "var(--color-primary)",
                  flexShrink: 0,
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "var(--color-primary-light)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
              >
                <X style={{ width: "10px", height: "10px" }} />
              </button>
            </span>
          )}
          {files.map((filePath) => (
            <FilePill key={filePath} filePath={filePath} onRemove={onRemoveFile} />
          ))}
        </div>
      )}

      {/* Textarea - 紧凑自适应 */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={1}
        disabled={isSending || disabled}
        style={{
          width: "100%",
          padding: "10px 12px",
          background: "transparent",
          border: "none",
          outline: "none",
          resize: "none",
          fontSize: "14px",
          lineHeight: "1.5",
          color: "var(--text-level-2)",
          minHeight: "24px",
          maxHeight: "120px",
          fontFamily: "inherit",
        }}
      />

      {/* 底部工具栏 */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "8px",
        padding: "4px 8px 8px 8px",
      }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          minWidth: 0,
        }}>
          {leftExtra}

          {/* + 极简菜单按钮 28x28 */}
          <div style={{ position: "relative", flexShrink: 0 }} ref={menuRef}>
            <button
              onClick={() => setMenuOpen((v) => !v)}
              title={t("chat.menu.uploadFile")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "28px",
                height: "28px",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: menuOpen ? "var(--color-primary-light)" : "transparent",
                cursor: "pointer",
                color: menuOpen ? "var(--color-primary)" : "var(--text-level-3)",
                transition: "all var(--transition-fast)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-level-3)";
                e.currentTarget.style.color = "var(--color-primary)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = menuOpen ? "var(--color-primary-light)" : "transparent";
                e.currentTarget.style.color = menuOpen ? "var(--color-primary)" : "var(--text-level-3)";
              }}
            >
              <Plus style={{
                width: "16px",
                height: "16px",
                transform: menuOpen ? "rotate(45deg)" : "rotate(0deg)",
                transition: "transform var(--transition-normal)",
              }} />
            </button>

            {/* Quick Menu 毛玻璃卡片 */}
            {menuOpen && (
              <div
                style={{
                  position: "absolute",
                  bottom: "calc(100% + 8px)",
                  left: 0,
                  minWidth: "220px",
                  padding: "4px",
                  borderRadius: "var(--radius-lg)",
                  background: "var(--glass-bg)",
                  backdropFilter: "var(--glass-blur)",
                  WebkitBackdropFilter: "var(--glass-blur)",
                  border: "1px solid var(--glass-border)",
                  boxShadow: "var(--shadow-lg), inset 0 0 0 1px var(--border-secondary)",
                  zIndex: 1001,
                  animation: "panelOpen 0.15s ease forwards",
                  transformOrigin: "bottom left",
                }}
              >
                <button
                  onClick={handlePickFile}
                  style={menuItemStyle}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                >
                  <FileUp style={{ width: "15px", height: "15px", color: "var(--color-primary)", flexShrink: 0 }} />
                  <span>{t("chat.menu.uploadFile")}</span>
                </button>
                <button
                  onClick={handlePickDirectory}
                  style={menuItemStyle}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
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
                  onClick={() => {
                    setMenuOpen(false);
                    onClearContext();
                  }}
                  disabled={!hasContext}
                  style={{
                    ...menuItemStyle,
                    color: hasContext ? "var(--color-error)" : "var(--text-level-4)",
                    cursor: hasContext ? "pointer" : "not-allowed",
                  }}
                  onMouseEnter={(e) => { if (hasContext) e.currentTarget.style.background = "var(--bg-level-3)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                >
                  <Trash2 style={{ width: "15px", height: "15px", color: hasContext ? "var(--color-error)" : "var(--text-level-4)", flexShrink: 0 }} />
                  <span>{t("chat.menu.clearContext")}</span>
                </button>
              </div>
            )}

            {/* 隐藏的文件选择 input */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              style={{ display: "none" }}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onUploadFile(file);
                e.target.value = "";
              }}
            />
          </div>

          {/* 模型选择 - 微型 */}
          {models.length > 0 && (
            <select
              value={modelId || ""}
              onChange={(e) => onModelChange(e.target.value)}
              style={{
                padding: "4px 8px",
                borderRadius: "var(--radius-full)",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-2)",
                cursor: "pointer",
                fontSize: "12px",
                color: "var(--text-level-2)",
                outline: "none",
                maxWidth: "120px",
              }}
            >
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </select>
          )}

          {/* 思考模式 三段胶囊 - 微型 */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "2px",
            padding: "2px",
            borderRadius: "var(--radius-full)",
            background: "var(--bg-level-3)",
          }}>
            <Brain style={{ width: "12px", height: "12px", color: "var(--text-level-4)", marginLeft: "4px" }} />
            {([
              { value: "none", label: t("chat.reasoning.off") },
              { value: "low", label: t("chat.reasoning.fast") },
              { value: "high", label: t("chat.reasoning.deep") },
            ] as const).map((mode) => (
              <button
                key={mode.value}
                onClick={() => onReasoningChange(mode.value)}
                style={{
                  padding: "3px 8px",
                  borderRadius: "var(--radius-full)",
                  border: "none",
                  background: reasoningEffort === mode.value ? "var(--bg-level-1)" : "transparent",
                  cursor: "pointer",
                  fontSize: "11px",
                  color: reasoningEffort === mode.value ? "var(--text-level-1)" : "var(--text-level-3)",
                  transition: "all 0.6s ease",
                }}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>

        {/* 发送按钮 28x28 - 卡片右下角 */}
        <button
          onClick={onSend}
          disabled={!canSend}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "28px",
            height: "28px",
            borderRadius: "var(--radius-md)",
            border: "none",
            background: canSend ? "var(--color-primary)" : "var(--bg-level-3)",
            cursor: canSend ? "pointer" : "not-allowed",
            color: canSend ? "white" : "var(--text-level-3)",
            transition: "all var(--transition-fast)",
            flexShrink: 0,
          }}
          onMouseEnter={(e) => {
            if (canSend) {
              e.currentTarget.style.background = "var(--color-primary-hover)";
              e.currentTarget.style.transform = "scale(1.05)";
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = canSend ? "var(--color-primary)" : "var(--bg-level-3)";
            e.currentTarget.style.transform = "scale(1)";
          }}
          onMouseDown={(e) => { e.currentTarget.style.transform = "scale(0.95)"; }}
          onMouseUp={(e) => { e.currentTarget.style.transform = "scale(1)"; }}
        >
          <Send style={{ width: "14px", height: "14px" }} />
        </button>
      </div>
    </div>
  );
}
