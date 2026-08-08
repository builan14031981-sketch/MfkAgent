"use client";

import { useState, useRef, useEffect, useCallback, memo } from "react";
import { Send, Folder, X } from "lucide-react";
import { selectDirectory } from "@/lib/selectDirectory";
import { FilePill } from "@/components/FileDropZone";
import { AgentSelector } from "@/components/chat-input/AgentSelector";
import { ModelSelector } from "@/components/chat-input/ModelSelector";
import { ModeSelector } from "@/components/chat-input/ModeSelector";
import { ReasoningSelector } from "@/components/chat-input/ReasoningSelector";
import { UploadMenu } from "@/components/chat-input/UploadMenu";
import type { Model } from "@/hooks/useModels";

export type ReasoningEffort = "none" | "high" | "max";
/** 会话工作模式：build（可写）/ plan（只读） */
export type ChatMode = "build" | "plan";

export interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isSending: boolean;
  placeholder: string;
  disabled?: boolean;

  /** 输入区最小高度（px），引导弹窗等场景可调大；默认 72 */
  inputMinHeight?: number;

  /** 外部注入 textarea ref（供引用/编辑后自动聚焦） */
  textareaRef?: React.RefObject<HTMLTextAreaElement | null>;

  /** 草稿本地持久化 key（如 mfk_draft_${chatId}），提供则自动读写 localStorage */
  draftKey?: string;

  models: Model[];
  modelId: string | null;
  onModelChange: (id: string) => void;

  reasoningEffort: ReasoningEffort;
  onReasoningChange: (e: ReasoningEffort) => void;

  mode: ChatMode;
  onModeChange: (m: ChatMode) => void;

  // Agent 锁定：仅一级入口（首页）允许切换，二级对话页隐藏切换下拉
  allowAgentChange?: boolean;
  agentId?: string | null;
  onAgentChange?: (agentId: string) => void;

  onUploadFile: (file: File) => void;
  onSelectDirectory: (path: string) => void;
  onClearContext: () => void;
  hasContext: boolean;

  files: string[];
  onRemoveFile: (path: string) => void;
  projectName?: string | null;
  onRemoveProject?: () => void;
}

/**
 * 一体化紧凑输入卡片：
 * textarea + 底部工具栏（+ 菜单 / 模型选择 / 思考胶囊 / 发送按钮）合并为单卡片，
 * 1px 淡边框 + 柔和阴影。草稿状态（文件 / 项目 Pill）渲染在 textarea 上方。
 *
 * 下拉选择器（Agent / Model / Mode / Reasoning / Upload）已拆分到
 * `components/chat-input/*`，本组件只负责互斥展开协调、草稿持久化与发送。
 */
export const ChatInput = memo(function ChatInput({
  value,
  onChange,
  onSend,
  isSending,
  placeholder,
  disabled,
  inputMinHeight,
  textareaRef: externalTextareaRef,
  draftKey,
  models,
  modelId,
  onModelChange,
  reasoningEffort,
  onReasoningChange,
  mode,
  onModeChange,
  allowAgentChange = false,
  agentId,
  onAgentChange,
  onUploadFile,
  onSelectDirectory,
  onClearContext,
  hasContext,
  files,
  onRemoveFile,
  projectName,
  onRemoveProject,
}: ChatInputProps) {
  // 互斥规则：同一时刻只允许一个下拉展开，展开新胶囊自动关闭旧胶囊
  const [activePop, setActivePop] = useState<string | null>(null);
  // Ghost UI：底栏整组控件默认低存在感，鼠标移入底栏时平滑显现
  const [toolbarHovered, setToolbarHovered] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const internalTextareaRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = externalTextareaRef ?? internalTextareaRef;

  const menuOpen = activePop === "menu";
  const agentOpen = activePop === "agent";
  const modelOpen = activePop === "model";
  const modeOpen = activePop === "mode";
  const reasoningOpen = activePop === "reasoning";

  const closePop = useCallback(() => setActivePop(null), []);
  const togglePop = useCallback((key: string | null) => {
    setActivePop((prev) => (prev === key ? null : key));
  }, []);

  // 自适应高度：挂载即测 + 首帧 rAF 重测 + 字体就绪重测 + resize 重测。
  // 冷启动时首帧测量可能因布局/字体未稳定而偏大并写死内联高度，且首页 value 不变时
  // 原逻辑永不重测（只能靠用户输入触发 value 变化才纠正）；这里在首帧/字体就绪后自动纠正。
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    let cancelled = false;
    const resize = () => {
      if (cancelled) return;
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 120) + "px";
    };
    resize();
    const raf = requestAnimationFrame(resize);
    const fontsReady =
      typeof document !== "undefined" &&
      typeof document.fonts !== "undefined" &&
      document.fonts.ready;
    if (fontsReady) fontsReady.then(resize).catch(() => {});
    window.addEventListener("resize", resize);
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [value, textareaRef]);

  // 草稿持久化：挂载时从 localStorage 恢复（仅当当前无内容时）
  const draftHydratedRef = useRef(false);
  useEffect(() => {
    if (!draftKey || draftHydratedRef.current) return;
    try {
      const saved = window.localStorage.getItem(draftKey);
      if (saved && !value) {
        onChange(saved);
      }
    } catch {
      // localStorage 不可用则忽略
    }
    draftHydratedRef.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftKey]);

  // 草稿持久化：内容变更且未发送时防抖写入
  useEffect(() => {
    if (!draftKey || !draftHydratedRef.current) return;
    if (value === "") {
      window.localStorage.removeItem(draftKey);
      return;
    }
    const timer = setTimeout(() => {
      try {
        window.localStorage.setItem(draftKey, value);
      } catch {
        // 忽略写入失败
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [draftKey, value]);

  // 草稿持久化：发送成功后清空缓存
  const clearDraft = useCallback(() => {
    if (draftKey) {
      try {
        window.localStorage.removeItem(draftKey);
      } catch {
        // 忽略
      }
    }
  }, [draftKey]);

  const handlePickFile = () => {
    closePop();
    fileInputRef.current?.click();
  };

  const handlePickDirectory = async () => {
    closePop();
    const dir = await selectDirectory();
    if (dir) onSelectDirectory(dir);
  };

  const canSend = value.trim().length > 0 && !isSending && !disabled;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) {
        clearDraft();
        onSend();
      }
    }
  };

  return (
    <div style={{
      position: "relative",
      border: "1px solid var(--border-primary)",
      borderRadius: "var(--radius-2xl)",
      background: "var(--bg-level-2)",
      boxShadow: "0 8px 32px rgba(0,0,0,0.06)",
    }}>
      {/* 草稿 Pills（文件 + 项目） */}
      {(files.length > 0 || (projectName && onRemoveProject)) && (
        <div style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "4px",
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
          minHeight: `${inputMinHeight ?? 72}px`,
          maxHeight: "120px",
          fontFamily: "inherit",
          boxSizing: "border-box",
        }}
      />

      {/* 底部工具栏 - Ghost：整组默认低调（opacity 0.55），移入底栏平滑提升到 1 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "8px",
          padding: "4px 8px 8px 8px",
        }}
        onMouseEnter={() => setToolbarHovered(true)}
        onMouseLeave={() => setToolbarHovered(false)}
      >
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          minWidth: 0,
          opacity: toolbarHovered || activePop !== null ? 1 : 0.55,
          transition: "opacity 0.2s ease-in-out",
        }}>
          {/* + 极简菜单按钮（最左第一位）28x28 */}
          <UploadMenu
            open={menuOpen}
            onToggle={() => togglePop("menu")}
            onClose={closePop}
            onPickFile={handlePickFile}
            onPickDirectory={handlePickDirectory}
            onClearContext={() => {
              closePop();
              onClearContext();
            }}
            hasContext={hasContext}
          />

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

          {/* Agent 选择器（仅一级入口 allowAgentChange 时展示，向上弹出） */}
          {allowAgentChange && (
            <AgentSelector
              open={agentOpen}
              onToggle={() => togglePop("agent")}
              onClose={closePop}
              selectedId={agentId}
              onSelect={(id) => onAgentChange?.(id)}
            />
          )}

          {/* 模型选择 - 下拉胶囊按钮 + Popover（向上弹出，完整显示） */}
          <ModelSelector
            models={models}
            selectedId={modelId}
            onSelect={(id) => {
              closePop();
              onModelChange(id);
            }}
            open={modelOpen}
            onToggle={() => togglePop("model")}
            onClose={closePop}
          />

          {/* 工作模式 - 下拉胶囊按钮 + Popover（build 可写 / plan 只读） */}
          <ModeSelector
            mode={mode}
            onModeChange={(m) => {
              closePop();
              onModeChange(m);
            }}
            open={modeOpen}
            onToggle={() => togglePop("mode")}
            onClose={closePop}
          />

          {/* 思考模式 - 下拉胶囊按钮 + Popover */}
          <ReasoningSelector
            reasoningEffort={reasoningEffort}
            onReasoningChange={(e) => {
              closePop();
              onReasoningChange(e);
            }}
            open={reasoningOpen}
            onToggle={() => togglePop("reasoning")}
            onClose={closePop}
          />
        </div>

        {/* 发送按钮 28x28 - 卡片右下角 */}
        <button
          onClick={() => {
            clearDraft();
            onSend();
          }}
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
            outline: "none",
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
});
