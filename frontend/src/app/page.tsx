/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { createPortal } from "react-dom";
import { ArrowRight, ChevronDown } from "lucide-react";
import { useAgents, Agent } from "@/hooks/useAgents";
import { useModels, Model } from "@/hooks/useModels";
import { useChat } from "@/hooks/useChat";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";

// agent_id → 用户可见名称映射（内部仍用 general/analyst/coder/writer）
const AGENT_COMBOS: { agentId: string; label: string; desc: string; personality: number }[] = [
  { agentId: "general", label: "小暖", desc: "温暖陪伴", personality: 0 },
  { agentId: "analyst", label: "锐", desc: "理性分析", personality: 100 },
  { agentId: "coder", label: "码农", desc: "编程开发", personality: 75 },
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
  const { settings } = useSettingsStore();
  const [welcome, setWelcome] = useState("");
  const [comboPersonality, setComboPersonality] = useState<number | null>(null);

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
        null,
        currentModel?.id || settings?.default_model || null,
        personalityLevel
      );

      const encodedMessage = encodeURIComponent(userMessage);
      router.push(`/chat/${chat.id}?message=${encodedMessage}`);
    } catch (err) {
      console.error("Failed to create chat:", err);
      setIsCreating(false);
      setInput(userMessage);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      // 防止重复触发
      if (!isCreating && input.trim() && currentAgent) {
        handleSend();
      }
    }
  };

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

        {/* Composer - ChatGPT风格输入框 */}
        <div style={{
          borderRadius: "var(--radius-2xl)",
          background: "var(--bg-level-3)",
          border: "1px solid var(--border-primary)",
          boxShadow: "var(--shadow-lg)",
          overflow: "hidden",
        }}>
          {/* 输入区域 */}
          <div style={{ padding: "24px" }}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t("home.inputPlaceholder")}
              rows={3}
              style={{
                width: "100%",
                background: "transparent",
                border: "none",
                outline: "none",
                resize: "none",
                fontSize: "15px",
                lineHeight: "1.6",
                color: "var(--text-level-2)",
              }}
            />
          </div>

          {/* 底部工具栏 */}
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 16px",
            borderTop: "1px solid var(--border-secondary)",
          }}>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}>
              {/* Agent 紧凑下拉选择器 */}
              {agentsLoading ? (
                <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>{t("common.loading")}</span>
              ) : agents.length > 0 ? (
                <div style={{ position: "relative" }}>
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
                      padding: "5px 10px",
                      borderRadius: "var(--radius-full)",
                      border: "1px solid var(--border-primary)",
                      background: "var(--bg-level-2)",
                      cursor: "pointer",
                      fontSize: "12px",
                      color: "var(--text-level-2)",
                      transition: "all var(--transition-fast)",
                    }}
                  >
                    <span style={{ fontSize: "14px" }}>{currentAgent?.avatar}</span>
                    <span style={{ fontWeight: "500" }}>{display.label}</span>
                    <ChevronDown style={{
                      width: "10px", height: "10px", color: "var(--text-level-4)",
                      transform: showAgentDropdown ? "rotate(180deg)" : "none",
                      transition: "transform var(--transition-fast)",
                    }} />
                  </button>
                  {showAgentDropdown && createPortal(
                    <div id="agent-dropdown-portal" style={{
                      position: "fixed",
                      top: dropdownPos.top,
                      left: dropdownPos.left,
                      minWidth: "200px",
                      maxHeight: "260px",
                      overflowY: "auto",
                      background: "var(--bg-level-2)",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid var(--border-primary)",
                      boxShadow: "var(--shadow-md)",
                      zIndex: 9999,
                      padding: "4px",
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
                              gap: "8px",
                              width: "100%",
                              padding: "7px 10px",
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
                            <span style={{ fontSize: "14px", lineHeight: 1 }}>{agent.avatar}</span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{
                                fontSize: "13px",
                                fontWeight: "500",
                                color: isActive ? "var(--color-primary)" : "var(--text-level-1)",
                              }}>{combo.label}</div>
                              <div style={{
                                fontSize: "11px",
                                color: "var(--text-level-4)",
                                marginTop: "1px",
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
              ) : null}

              {/* 模型选择 */}
              {modelsLoading ? (
                <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>{t("common.loading")}</span>
              ) : models.length > 0 ? (
                <select
                  value={currentModel?.id || ""}
                  onChange={(e) => {
                    const model = models.find(m => m.id === e.target.value);
                    if (model) setSelectedModel(model);
                  }}
                  style={{
                    padding: "5px 10px",
                    borderRadius: "var(--radius-full)",
                    border: "1px solid var(--border-primary)",
                    background: "var(--bg-level-2)",
                    cursor: "pointer",
                    fontSize: "12px",
                    color: "var(--text-level-2)",
                    outline: "none",
                  }}
                >
                  {models.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name}
                    </option>
                  ))}
                </select>
              ) : null}
            </div>

            {/* 发送按钮 */}
            <button
              onClick={handleSend}
              disabled={!input.trim() || !currentAgent || isCreating}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "32px",
                height: "32px",
                borderRadius: "var(--radius-md)",
                border: "none",
                background: input.trim() && currentAgent && !isCreating ? "var(--color-primary)" : "var(--bg-level-4)",
                cursor: input.trim() && currentAgent && !isCreating ? "pointer" : "not-allowed",
                color: "white",
                transition: "all var(--transition-fast)",
              }}
              onMouseEnter={(e) => {
                if (input.trim() && currentAgent && !isCreating) {
                  e.currentTarget.style.background = "var(--color-primary-hover)";
                  e.currentTarget.style.transform = "scale(1.05)";
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = input.trim() && currentAgent && !isCreating ? "var(--color-primary)" : "var(--bg-level-4)";
                e.currentTarget.style.transform = "scale(1)";
              }}
              onMouseDown={(e) => {
                e.currentTarget.style.transform = "scale(0.95)";
              }}
              onMouseUp={(e) => {
                e.currentTarget.style.transform = "scale(1)";
              }}
            >
              <ArrowRight style={{ width: "16px", height: "16px" }} />
            </button>
          </div>
        </div>
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
