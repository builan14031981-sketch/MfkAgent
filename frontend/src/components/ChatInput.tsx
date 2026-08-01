"use client";

import { useState, useRef, useEffect } from "react";
import { Plus, FileUp, FolderPlus, Trash2, Send, Brain, Folder, X, Check, ChevronDown } from "lucide-react";
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
  const [reasoningOpen, setReasoningOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const reasoningRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 点击外部关闭弹出层（+ 菜单 / 思考模式下拉）
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
      if (reasoningRef.current && !reasoningRef.current.contains(e.target as Node)) {
        setReasoningOpen(false);
      }
    };
    if (!menuOpen && !reasoningOpen) return;
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpen, reasoningOpen]);

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

  // 统一 Toolbar Pill 控件外观：28px 高、12px 字、medium、px-2.5、同背景同箭头
  const pillStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "6px",
    height: "28px",
    padding: "0 10px",
    borderRadius: "var(--radius-full)",
    border: "1px solid var(--border-primary)",
    background: "var(--bg-level-3)",
    cursor: "pointer",
    fontSize: "12px",
    fontWeight: 500,
    color: "var(--text-level-2)",
    whiteSpace: "nowrap",
    transition: "all var(--transition-fast)",
    flexShrink: 0,
  };

  const chevronStyle: React.CSSProperties = {
    width: "12px",
    height: "12px",
    color: "var(--text-level-4)",
    marginLeft: "4px",
    flexShrink: 0,
  };

  const popoverStyle: React.CSSProperties = {
    position: "absolute",
    bottom: "calc(100% + 8px)",
    left: 0,
    minWidth: "180px",
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
  };

  const popoverItemStyle: React.CSSProperties = {
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

  const reasoningModes: { value: ReasoningEffort; label: string }[] = [
    { value: "none", label: t("chat.reasoning.off") },
    { value: "low", label: t("chat.reasoning.fast") },
    { value: "high", label: t("chat.reasoning.deep") },
  ];

  const currentReasoningLabel = reasoningModes.find((m) => m.value === reasoningEffort)?.label ?? "";

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

      {/* Textarea - 舒展自适应 */}
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
          padding: "10px 14px",
          background: "transparent",
          border: "none",
          outline: "none",
          resize: "none",
          fontSize: "14px",
          lineHeight: "1.5rem",
          color: "var(--text-level-2)",
          minHeight: "72px",
          maxHeight: "120px",
          fontFamily: "inherit",
          boxSizing: "border-box",
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
          gap: "8px",
          minWidth: 0,
        }}>
          {/* + 极简菜单按钮（最左第一位）28x28 */}
          <div style={{ position: "relative", flexShrink: 0 }} ref={menuRef}>
            <button
              onClick={() => setMenuOpen((v) => !v)}
              title={t("chat.menu.uploadFile")}
              style={{
                ...pillStyle,
                width: "28px",
                padding: "0",
                borderRadius: "var(--radius-full)",
                background: menuOpen ? "var(--bg-level-4)" : "var(--bg-level-3)",
                color: menuOpen ? "var(--color-primary)" : "var(--text-level-2)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-level-4)";
                e.currentTarget.style.color = "var(--color-primary)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = menuOpen ? "var(--bg-level-4)" : "var(--bg-level-3)";
                e.currentTarget.style.color = menuOpen ? "var(--color-primary)" : "var(--text-level-2)";
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
              <div style={popoverStyle}>
                <button
                  onClick={handlePickFile}
                  style={popoverItemStyle}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                >
                  <FileUp style={{ width: "15px", height: "15px", color: "var(--color-primary)", flexShrink: 0 }} />
                  <span>{t("chat.menu.uploadFile")}</span>
                </button>
                <button
                  onClick={handlePickDirectory}
                  style={popoverItemStyle}
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
                    ...popoverItemStyle,
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

          {/* Agent 选择器（由页面注入，如首页 Agent 下拉） */}
          {leftExtra}

          {/* 模型选择 - 下拉胶囊按钮（无截断，完整显示） */}
          {models.length > 0 && (
            <div style={{
              position: "relative",
              minWidth: 0,
              maxWidth: "200px",
              flexShrink: 0,
            }}>
              <select
                value={modelId || ""}
                onChange={(e) => onModelChange(e.target.value)}
                title={models.find((m) => m.id === modelId)?.name ?? ""}
                style={{
                  ...pillStyle,
                  maxWidth: "200px",
                  minWidth: 0,
                  appearance: "none",
                  WebkitAppearance: "none",
                  paddingRight: "24px",
                }}
              >
                {models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                  </option>
                ))}
              </select>
              <ChevronDown
                style={{
                  ...chevronStyle,
                  position: "absolute",
                  right: "8px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  pointerEvents: "none",
                  marginLeft: 0,
                }}
              />
            </div>
          )}

          {/* 思考模式 - 下拉胶囊按钮 + Popover */}
          <div style={{ position: "relative", flexShrink: 0 }} ref={reasoningRef}>
            <button
              onClick={() => setReasoningOpen((v) => !v)}
              title={currentReasoningLabel}
              style={{
                ...pillStyle,
                background: reasoningOpen ? "var(--bg-level-4)" : "var(--bg-level-3)",
                color: reasoningOpen ? "var(--color-primary)" : "var(--text-level-2)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-level-4)";
                e.currentTarget.style.color = "var(--color-primary)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = reasoningOpen ? "var(--bg-level-4)" : "var(--bg-level-3)";
                e.currentTarget.style.color = reasoningOpen ? "var(--color-primary)" : "var(--text-level-2)";
              }}
            >
              <Brain style={{ width: "13px", height: "13px", color: "var(--text-level-3)", flexShrink: 0 }} />
              <span>{currentReasoningLabel}</span>
              <ChevronDown style={{
                ...chevronStyle,
                transform: reasoningOpen ? "rotate(180deg)" : "rotate(0deg)",
                transition: "transform var(--transition-normal)",
              }} />
            </button>

            {reasoningOpen && (
              <div style={popoverStyle}>
                {reasoningModes.map((mode) => {
                  const active = reasoningEffort === mode.value;
                  return (
                    <button
                      key={mode.value}
                      onClick={() => {
                        onReasoningChange(mode.value);
                        setReasoningOpen(false);
                      }}
                      style={{
                        ...popoverItemStyle,
                        color: active ? "var(--color-primary)" : "var(--text-level-2)",
                        fontWeight: active ? 600 : 400,
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                    >
                      <span style={{ flex: 1 }}>{mode.label}</span>
                      {active && <Check style={{ width: "14px", height: "14px", color: "var(--color-primary)", flexShrink: 0 }} />}
                    </button>
                  );
                })}
              </div>
            )}
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
