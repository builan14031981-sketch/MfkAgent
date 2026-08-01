"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { Plus, FileUp, FolderPlus, Trash2, Send, Brain, Folder, X, Check, ChevronDown, Wrench, Compass } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { selectDirectory } from "@/lib/selectDirectory";
import { FilePill } from "@/components/FileDropZone";
import { useAgents } from "@/hooks/useAgents";
import { AgentIcon } from "@/components/AgentIcon";
import type { Model } from "@/hooks/useModels";

export type ReasoningEffort = "none" | "low" | "high";
/** 会话工作模式：build（可写）/ plan（只读） */
export type ChatMode = "build" | "plan";

// agent_id → 展示组合（label/desc/personality），仅在 allowAgentChange 时渲染
const AGENT_COMBOS: { agentId: string; label: string; desc: string; personality: number }[] = [
  { agentId: "coder", label: "代码审查 AI", desc: "代码审查、开发与架构", personality: 75 },
  { agentId: "frontend_ui", label: "前端 UI 设计 AI", desc: "界面设计与前端实现", personality: 50 },
  { agentId: "backend", label: "后端 AI", desc: "服务端与数据逻辑", personality: 75 },
  { agentId: "general", label: "小暖", desc: "温暖陪伴", personality: 0 },
  { agentId: "analyst", label: "锐", desc: "理性分析", personality: 100 },
  { agentId: "writer", label: "笔神", desc: "写作创作", personality: 25 },
];

export interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isSending: boolean;
  placeholder: string;
  disabled?: boolean;

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
  onAgentChange?: (agentId: string, personality: number) => void;

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
 */
export function ChatInput({
  value,
  onChange,
  onSend,
  isSending,
  placeholder,
  disabled,
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
  const { t } = useTranslation();
  const { agents, loading: agentsLoading } = useAgents();
  // 互斥规则：同一时刻只允许一个下拉展开，展开新胶囊自动关闭旧胶囊
  const [activePop, setActivePop] = useState<string | null>(null);
  const [agentDropdownPos, setAgentDropdownPos] = useState({ bottom: 0, left: 0 });
  const menuOpen = activePop === "menu";
  const reasoningOpen = activePop === "reasoning";
  const modeOpen = activePop === "mode";
  const modelOpen = activePop === "model";
  const agentOpen = activePop === "agent";

  // 展开/收起指定胶囊（再次点击同胶囊则收起）
  const togglePop = useCallback((key: string | null) => {
    setActivePop((prev) => (prev === key ? null : key));
  }, []);
  const agentBtnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const reasoningRef = useRef<HTMLDivElement>(null);
  const modeRef = useRef<HTMLDivElement>(null);
  const modelRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const internalTextareaRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = externalTextareaRef ?? internalTextareaRef;

  // 点击外部关闭当前展开的弹出层（互斥：同一时刻仅一个）
  useEffect(() => {
    if (!activePop) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      const portal = document.getElementById("agent-dropdown-portal");
      const refFor = (key: string): HTMLElement | null => {
        switch (key) {
          case "agent": return agentBtnRef.current;
          case "menu": return menuRef.current;
          case "reasoning": return reasoningRef.current;
          case "mode": return modeRef.current;
          case "model": return modelRef.current;
          default: return null;
        }
      };
      const el = refFor(activePop);
      if (el && el.contains(target)) return;
      if (activePop === "agent" && portal?.contains(target)) return;
      setActivePop(null);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [activePop]);

  // 自适应高度
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
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
    setActivePop(null);
    fileInputRef.current?.click();
  };

  const handlePickDirectory = async () => {
    setActivePop(null);
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
    outline: "none",
  };

  const chevronStyle: React.CSSProperties = {
    width: "12px",
    height: "12px",
    color: "var(--text-level-4)",
    marginLeft: "4px",
    flexShrink: 0,
  };

  // 下拉面板：统一向上弹出（bottom-full mb-1.5）、最高层级 z-[100]、紧凑高密度
  const popoverStyle: React.CSSProperties = {
    position: "absolute",
    bottom: "calc(100% + 6px)",
    left: 0,
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    minWidth: "140px",
    padding: "4px",
    borderRadius: "var(--radius-xl)",
    background: "var(--bg-level-2)",
    border: "1px solid var(--border-primary)",
    boxShadow: "var(--shadow-lg)",
    zIndex: 100,
    animation: "panelOpen 0.15s ease forwards",
    transformOrigin: "bottom left",
  };

  // 下拉选项：text-xs、font-medium、px-2.5 py-1.5、leading-tight
  const popoverItemStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    width: "100%",
    padding: "6px 10px",
    border: "none",
    background: "transparent",
    cursor: "pointer",
    fontSize: "12px",
    fontWeight: 500,
    lineHeight: 1.25,
    whiteSpace: "nowrap",
    color: "var(--text-level-2)",
    borderRadius: "var(--radius-sm)",
    textAlign: "left",
    outline: "none",
  };

  const reasoningModes: { value: ReasoningEffort; label: string }[] = [
    { value: "none", label: t("chat.reasoning.off") },
    { value: "low", label: t("chat.reasoning.fast") },
    { value: "high", label: t("chat.reasoning.deep") },
  ];

  const modeOptions: { value: ChatMode; label: string; icon: typeof Wrench }[] = [
    { value: "build", label: t("chat.mode.build"), icon: Wrench },
    { value: "plan", label: t("chat.mode.plan"), icon: Compass },
  ];

  const currentReasoningLabel = reasoningModes.find((m) => m.value === reasoningEffort)?.label ?? "";
  const currentModeLabel = modeOptions.find((m) => m.value === mode)?.label ?? "";
  const CurrentModeIcon = modeOptions.find((m) => m.value === mode)?.icon ?? Wrench;
  const currentModelName = models.find((m) => m.id === modelId)?.name ?? modelId ?? "";
  const currentAgentCombo = AGENT_COMBOS.find((c) => c.agentId === agentId);
  const currentAgentLabel = currentAgentCombo?.label ?? agents.find((a) => a.id === agentId)?.name ?? "";

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
              onClick={() => togglePop("menu")}
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
                    setActivePop(null);
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

          {/* Agent 选择器（仅一级入口 allowAgentChange 时展示，向上弹出） */}
          {allowAgentChange && (
            agentsLoading ? (
              <span style={{ fontSize: "12px", color: "var(--text-level-3)", flexShrink: 0 }}>{t("common.loading")}</span>
            ) : (
              <div style={{ position: "relative", flexShrink: 0 }}>
                <button
                  ref={agentBtnRef}
                  onClick={() => {
                    const rect = agentBtnRef.current?.getBoundingClientRect();
                    if (rect) {
                      // 以按钮底部为锚点：bottom = 视口高度 - 按钮底部 → 菜单物理向上弹出
                      setAgentDropdownPos({
                        bottom: window.innerHeight - rect.bottom,
                        left: Math.max(8, Math.min(rect.left, window.innerWidth - 170)),
                      });
                    }
                    togglePop("agent");
                  }}
                  style={{
                    ...pillStyle,
                    background: agentOpen ? "var(--bg-level-4)" : "var(--bg-level-3)",
                    color: agentOpen ? "var(--color-primary)" : "var(--text-level-2)",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "var(--bg-level-4)";
                    e.currentTarget.style.color = "var(--color-primary)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = agentOpen ? "var(--bg-level-4)" : "var(--bg-level-3)";
                    e.currentTarget.style.color = agentOpen ? "var(--color-primary)" : "var(--text-level-2)";
                  }}
                >
                  <AgentIcon id={agentId ?? undefined} size={14} style={{ flexShrink: 0 }} />
                  <span style={{ fontWeight: 500 }}>{currentAgentLabel || agentId}</span>
                  <ChevronDown style={{
                    ...chevronStyle,
                    transform: agentOpen ? "rotate(180deg)" : "rotate(0deg)",
                    transition: "transform var(--transition-normal)",
                  }} />
                </button>
                {agentOpen && createPortal(
                  <div id="agent-dropdown-portal" className="no-scrollbar" style={{
                    position: "fixed",
                    bottom: agentDropdownPos.bottom + 8,
                    left: agentDropdownPos.left,
                    display: "flex",
                    flexDirection: "column",
                    gap: "2px",
                    minWidth: "160px",
                    maxHeight: "220px",
                    overflowY: "auto",
                    padding: "6px",
                    borderRadius: "var(--radius-xl)",
                    background: "var(--bg-level-2)",
                    border: "1px solid var(--border-secondary)",
                    boxShadow: "var(--shadow-lg)",
                    zIndex: 9999,
                  }}>
                    {AGENT_COMBOS.map((combo) => {
                      const active = combo.agentId === agentId;
                      return (
                        <button
                          key={combo.agentId}
                          onClick={() => {
                            onAgentChange?.(combo.agentId, combo.personality);
                            setActivePop(null);
                          }}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                            width: "100%",
                            padding: "6px 10px",
                            border: "none",
                            borderRadius: "var(--radius-sm)",
                            background: active ? "var(--color-primary-lighter)" : "transparent",
                            cursor: "pointer",
                            textAlign: "left",
                            fontSize: "12px",
                            fontWeight: 500,
                            lineHeight: 1.25,
                            outline: "none",
                            transition: "background 0.1s",
                          }}
                          onMouseEnter={(e) => {
                            if (!active) e.currentTarget.style.background = "var(--bg-level-3)";
                          }}
                          onMouseLeave={(e) => {
                            if (!active) e.currentTarget.style.background = "transparent";
                          }}
                        >
                          <AgentIcon id={combo.agentId} size={13} style={{ flexShrink: 0, color: "var(--text-level-3)" }} />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{
                              fontSize: "12px",
                              fontWeight: "500",
                              lineHeight: 1.25,
                              color: active ? "var(--color-primary)" : "var(--text-level-1)",
                            }}>{combo.label}</div>
                            <div style={{
                              fontSize: "10px",
                              lineHeight: 1.25,
                              color: "var(--text-level-4)",
                            }}>{combo.desc}</div>
                          </div>
                          {active && (
                            <span style={{
                              width: "6px", height: "6px",
                              borderRadius: "50%",
                              background: "var(--color-primary)",
                              flexShrink: 0,
                            }} />
                          )}
                        </button>
                      );
                    })}
                  </div>,
                  document.body
                )}
              </div>
            )
          )}

          {/* 模型选择 - 下拉胶囊按钮 + Popover（向上弹出，完整显示） */}
          {models.length > 0 && (
            <div style={{
              position: "relative",
              minWidth: 0,
              maxWidth: "200px",
              flexShrink: 0,
            }} ref={modelRef}>
              <button
                onClick={() => togglePop("model")}
                title={currentModelName}
                style={{
                  ...pillStyle,
                  maxWidth: "200px",
                  background: modelOpen ? "var(--bg-level-4)" : "var(--bg-level-3)",
                  color: modelOpen ? "var(--color-primary)" : "var(--text-level-2)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--bg-level-4)";
                  e.currentTarget.style.color = "var(--color-primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = modelOpen ? "var(--bg-level-4)" : "var(--bg-level-3)";
                  e.currentTarget.style.color = modelOpen ? "var(--color-primary)" : "var(--text-level-2)";
                }}
              >
                <span style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  minWidth: 0,
                }}>{currentModelName}</span>
                <ChevronDown style={{
                  ...chevronStyle,
                  transform: modelOpen ? "rotate(180deg)" : "rotate(0deg)",
                  transition: "transform var(--transition-normal)",
                }} />
              </button>

              {modelOpen && (
                <div style={popoverStyle}>
                  {models.map((model) => {
                    const active = model.id === modelId;
                    return (
                      <button
                        key={model.id}
                        onClick={() => {
                          onModelChange(model.id);
                          setActivePop(null);
                        }}
                        style={{
                          ...popoverItemStyle,
                          color: active ? "var(--color-primary)" : "var(--text-level-2)",
                          fontWeight: active ? 600 : 500,
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                      >
                        <span style={{
                          flex: 1,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}>{model.name}</span>
                        {active && <Check style={{ width: "14px", height: "14px", color: "var(--color-primary)", flexShrink: 0 }} />}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* 工作模式 - 下拉胶囊按钮 + Popover（build 可写 / plan 只读） */}
          <div style={{ position: "relative", flexShrink: 0 }} ref={modeRef}>
            <button
              onClick={() => togglePop("mode")}
              title={currentModeLabel}
              style={{
                ...pillStyle,
                background: modeOpen ? "var(--bg-level-4)" : "var(--bg-level-3)",
                color: modeOpen ? "var(--color-primary)" : "var(--text-level-2)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-level-4)";
                e.currentTarget.style.color = "var(--color-primary)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = modeOpen ? "var(--bg-level-4)" : "var(--bg-level-3)";
                e.currentTarget.style.color = modeOpen ? "var(--color-primary)" : "var(--text-level-2)";
              }}
            >
              <CurrentModeIcon style={{ width: "13px", height: "13px", color: "var(--text-level-3)", flexShrink: 0 }} />
              <span>{currentModeLabel}</span>
              <ChevronDown style={{
                ...chevronStyle,
                transform: modeOpen ? "rotate(180deg)" : "rotate(0deg)",
                transition: "transform var(--transition-normal)",
              }} />
            </button>

            {modeOpen && (
              <div style={{ ...popoverStyle, minWidth: 112 }}>
                {modeOptions.map((opt) => {
                  const active = mode === opt.value;
                  return (
                    <button
                      key={opt.value}
                      onClick={() => {
                        onModeChange(opt.value);
                        setActivePop(null);
                      }}
                      style={{
                        ...popoverItemStyle,
                        color: active ? "var(--color-primary)" : "var(--text-level-2)",
                        fontWeight: active ? 600 : 400,
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                    >
                      <opt.icon style={{ width: "13px", height: "13px", color: "var(--text-level-3)", flexShrink: 0 }} />
                      <span style={{ flex: 1 }}>{opt.label}</span>
                      {active && <Check style={{ width: "14px", height: "14px", color: "var(--color-primary)", flexShrink: 0 }} />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* 思考模式 - 下拉胶囊按钮 + Popover */}
          <div style={{ position: "relative", flexShrink: 0 }} ref={reasoningRef}>
            <button
              onClick={() => togglePop("reasoning")}
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
                        setActivePop(null);
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
}
