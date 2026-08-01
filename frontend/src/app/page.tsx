/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { createPortal } from "react-dom";
import { ChevronDown } from "lucide-react";
import { useAgents, Agent } from "@/hooks/useAgents";
import { useModels, Model } from "@/hooks/useModels";
import { useChat } from "@/hooks/useChat";
import { useProjects } from "@/hooks/useProjects";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";
import { AgentIcon } from "@/components/AgentIcon";
import { ChatInput } from "@/components/ChatInput";
import type { Project } from "@/hooks/useProjects";

// agent_id → 用户可见名称映射（内部仍用 coder/frontend_ui/backend 等）
// 研发核心三角置顶展示：代码审查 AI、前端 UI 设计 AI、后端 AI
const AGENT_COMBOS: { agentId: string; label: string; desc: string; personality: number }[] = [
  { agentId: "coder", label: "代码审查 AI", desc: "代码审查、开发与架构", personality: 75 },
  { agentId: "frontend_ui", label: "前端 UI 设计 AI", desc: "界面设计与前端实现", personality: 50 },
  { agentId: "backend", label: "后端 AI", desc: "服务端与数据逻辑", personality: 75 },
  { agentId: "general", label: "小暖", desc: "温暖陪伴", personality: 0 },
  { agentId: "analyst", label: "锐", desc: "理性分析", personality: 100 },
  { agentId: "writer", label: "笔神", desc: "写作创作", personality: 25 },
];

function getDisplayName(agentId: string) {
  const c = AGENT_COMBOS.find(x => x.agentId === agentId);
  return c ? { label: c.label, desc: c.desc } : { label: agentId, desc: "" };
}

export default function Home() {
  const router = useRouter();
  const { t, tArray } = useTranslation();
  const [input, setInput] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const [showAgentDropdown, setShowAgentDropdown] = useState(false);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const { agents, loading: agentsLoading } = useAgents();
  const { models, loading: modelsLoading } = useModels();
  const { createChat } = useChat();
  const { createProject } = useProjects();
  const { settings } = useSettingsStore();
  const [welcome, setWelcome] = useState("");
  const [comboPersonality, setComboPersonality] = useState<number | null>(null);
  const [pendingProject, setPendingProject] = useState<Project | null>(null);
  const [pendingFiles, setPendingFiles] = useState<string[]>([]);
  const [reasoningEffort, setReasoningEffort] = useState<"none" | "low" | "high">("none");

  // 点击外部关闭下拉 (portal 渲染到 body，用 buttonRef 判断)
  useEffect(() => {
    if (!showAgentDropdown) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (buttonRef.current?.contains(target)) return;
      const portal = document.getElementById("agent-dropdown-portal");
      if (portal?.contains(target)) return;
      setShowAgentDropdown(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showAgentDropdown]);

  useEffect(() => {
    const messages = tArray("home.welcome");
    setWelcome(messages[Math.floor(Math.random() * messages.length)]);
  }, [tArray]);

  // 根据 Settings 默认模型预选
  useEffect(() => {
    if (!modelsLoading && models.length > 0 && !selectedModel) {
      const defaultModelId = settings?.default_model;
      if (defaultModelId) {
        const found = models.find((m) => m.id === defaultModelId);
        if (found) setSelectedModel(found);
      }
    }
  }, [modelsLoading, models, settings?.default_model, selectedModel]);

  const currentAgent = selectedAgent || (settings?.default_agent ? agents.find(a => a.id === settings.default_agent) || null : null) || agents[0] || null;
  const currentModel = selectedModel || models[0] || null;
  const display = currentAgent ? getDisplayName(currentAgent.id) : { label: "", desc: "" };

  const handleSelectCombo = (c: typeof AGENT_COMBOS[number]) => {
    const agent = agents.find((a) => a.id === c.agentId);
    if (agent) setSelectedAgent(agent);
    setComboPersonality(c.personality);
    setShowAgentDropdown(false);
  };

  const handleSend = async () => {
    if (!input.trim() || !currentAgent || isCreating) return;

    const userMessage = input.trim();
    setIsCreating(true);
    setInput("");

    try {
      const personalityLevel = comboPersonality ?? (settings?.default_personality ? Number(settings.default_personality) : 50);
      const chat = await createChat(
        currentAgent.id,
        userMessage.slice(0, 50) || "New Chat",
        pendingProject?.id ?? null,
        currentModel?.id || settings?.default_model || null,
        personalityLevel,
        pendingFiles
      );

      const encodedMessage = encodeURIComponent(userMessage);
      router.push(`/chat/${chat.id}?message=${encodedMessage}`);
    } catch (err) {
      console.error("Failed to create chat:", err);
      setIsCreating(false);
      setInput(userMessage);
    }
  };

  // 草稿预挂载：首页无 Chat 状态下附加文件 / 关联项目，创建会话时一并提交
  const handleAttachFile = useCallback((file: File) => {
    const fileWithPath = file as File & { path?: string };
    const path = fileWithPath.path || file.name;
    setPendingFiles((prev) => (prev.includes(path) ? prev : [...prev, path]));
  }, []);

  const handleLinkProject = useCallback(async (dirPath: string) => {
    const name = dirPath.split(/[\\/]/).filter(Boolean).pop() || dirPath;
    const project = await createProject(name, dirPath);
    setPendingProject(project);
    window.dispatchEvent(new Event("mfk-projects-changed"));
  }, [createProject]);

  const handleClearDraft = useCallback(() => {
    setPendingFiles([]);
    setPendingProject(null);
  }, []);

  const removePendingFile = useCallback((path: string) => {
    setPendingFiles((prev) => prev.filter((p) => p !== path));
  }, []);

  return (
    <div style={{
      flex: 1,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "flex-start",
      overflow: "auto",
      paddingTop: "120px",
      position: "relative",
    }}>
      {/* 内容区 - 居中 */}
      <motion.div
        initial={false}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        style={{
          width: "100%",
          maxWidth: "900px",
          padding: "0 40px",
        }}
      >
        {/* Logo */}
        <div style={{
          textAlign: "center",
          marginBottom: "48px",
        }}>
          <h1 style={{
            fontSize: "48px",
            fontWeight: "600",
            letterSpacing: "-0.02em",
            color: "var(--text-level-1)",
            margin: 0,
          }}>MfkAgent</h1>
          <p style={{
            fontSize: "16px",
            color: "var(--text-level-3)",
            marginTop: "12px",
          }}>{welcome}</p>
        </div>

        {/* Composer - 一体化紧凑输入卡片 */}
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          isSending={isCreating}
          placeholder={t("home.inputPlaceholder")}
          models={models}
          modelId={currentModel?.id || null}
          onModelChange={(id) => {
            const model = models.find(m => m.id === id);
            if (model) setSelectedModel(model);
          }}
          reasoningEffort={reasoningEffort}
          onReasoningChange={setReasoningEffort}
          onUploadFile={handleAttachFile}
          onSelectDirectory={handleLinkProject}
          onClearContext={handleClearDraft}
          hasContext={pendingFiles.length > 0 || !!pendingProject}
          files={pendingFiles}
          onRemoveFile={removePendingFile}
          projectName={pendingProject?.name || null}
          onRemoveProject={() => setPendingProject(null)}
          leftExtra={
            agentsLoading ? (
              <span style={{ fontSize: "12px", color: "var(--text-level-3)", flexShrink: 0 }}>{t("common.loading")}</span>
            ) : agents.length > 0 ? (
              <div style={{ position: "relative", flexShrink: 0 }}>
                <button
                  ref={buttonRef}
                  onClick={() => {
                    const rect = buttonRef.current?.getBoundingClientRect();
                    if (rect) setDropdownPos({ top: rect.bottom + 4, left: rect.left });
                    setShowAgentDropdown(!showAgentDropdown);
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    height: "28px",
                    padding: "0 10px",
                    borderRadius: "var(--radius-full)",
                    border: "1px solid var(--border-primary)",
                    background: showAgentDropdown ? "var(--bg-level-4)" : "var(--bg-level-3)",
                    cursor: "pointer",
                    fontSize: "12px",
                    fontWeight: 500,
                    color: showAgentDropdown ? "var(--color-primary)" : "var(--text-level-2)",
                    whiteSpace: "nowrap",
                    transition: "all var(--transition-fast)",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "var(--bg-level-4)";
                    e.currentTarget.style.color = "var(--color-primary)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = showAgentDropdown ? "var(--bg-level-4)" : "var(--bg-level-3)";
                    e.currentTarget.style.color = showAgentDropdown ? "var(--color-primary)" : "var(--text-level-2)";
                  }}
                >
                  <AgentIcon id={currentAgent?.id} size={14} style={{ flexShrink: 0 }} />
                  <span style={{ fontWeight: 500 }}>{display.label}</span>
                  <ChevronDown style={{
                    width: "12px", height: "12px", color: "var(--text-level-4)",
                    marginLeft: "4px",
                    transform: showAgentDropdown ? "rotate(180deg)" : "rotate(0deg)",
                    transition: "transform var(--transition-fast)",
                  }} />
                </button>
                {showAgentDropdown && createPortal(
                  <div id="agent-dropdown-portal" style={{
                    position: "fixed",
                    top: dropdownPos.top,
                    left: dropdownPos.left,
                    minWidth: "200px",
                    maxHeight: "220px",
                    overflowY: "auto",
                    background: "var(--bg-level-2)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--border-primary)",
                    boxShadow: "var(--shadow-md)",
                    zIndex: 9999,
                    padding: "3px",
                  }}>
                    {AGENT_COMBOS.map((combo) => {
                      const agent = agents.find((a) => a.id === combo.agentId);
                      if (!agent) return null;
                      const isActive = currentAgent?.id === combo.agentId && comboPersonality === combo.personality;
                      return (
                        <button
                          key={combo.agentId}
                          onClick={() => handleSelectCombo(combo)}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                            width: "100%",
                            padding: "5px 8px",
                            border: "none",
                            borderRadius: "var(--radius-sm)",
                            background: isActive ? "var(--color-primary-lighter)" : "transparent",
                            cursor: "pointer",
                            textAlign: "left",
                            transition: "background 0.1s",
                          }}
                          onMouseEnter={(e) => {
                            if (!isActive) e.currentTarget.style.background = "var(--bg-level-3)";
                          }}
                          onMouseLeave={(e) => {
                            if (!isActive) e.currentTarget.style.background = "transparent";
                          }}
                        >
                          <AgentIcon id={agent.id} size={13} style={{ flexShrink: 0, color: "var(--text-level-3)" }} />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{
                              fontSize: "12px",
                              fontWeight: "500",
                              color: isActive ? "var(--color-primary)" : "var(--text-level-1)",
                            }}>{combo.label}</div>
                            <div style={{
                              fontSize: "10px",
                              color: "var(--text-level-4)",
                            }}>{combo.desc}</div>
                          </div>
                          {isActive && (
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
            ) : null
          }
        />
      </motion.div>

      {/* 底部提示 */}
      <p style={{
        textAlign: "center",
        fontSize: "12px",
        color: "var(--text-level-4)",
        marginTop: "auto",
        paddingBottom: "16px",
        pointerEvents: "none",
      }}>MfkAgent 可能会犯错，请核实重要信息</p>
    </div>
  );
}
