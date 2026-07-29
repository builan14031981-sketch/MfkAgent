/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { useAgents, Agent } from "@/hooks/useAgents";
import { useChat } from "@/hooks/useChat";
import { useTranslation } from "@/hooks/useTranslation";

export default function Home() {
  const router = useRouter();
  const { t } = useTranslation();
  const [input, setInput] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const { agents, loading: agentsLoading } = useAgents();
  const { createChat } = useChat();
  const [welcome, setWelcome] = useState("");

  useEffect(() => {
    const welcomeMessages = t("home.welcome", {});
    const messages = typeof welcomeMessages === "string" ? [welcomeMessages] : welcomeMessages;
    setWelcome(messages[Math.floor(Math.random() * messages.length)]);
  }, [t]);

  const currentAgent = selectedAgent || agents[0] || null;

  const handleSend = async () => {
    if (!input.trim() || !currentAgent || isCreating) return;

    const userMessage = input.trim();
    setIsCreating(true);
    setInput("");

    try {
      const chat = await createChat(
        currentAgent.id,
        userMessage.slice(0, 50) || "New Chat"
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

  const handleAgentSwitch = () => {
    if (agents.length === 0) return;
    const currentIdx = agents.findIndex((a) => a.id === currentAgent?.id);
    const nextIdx = (currentIdx + 1) % agents.length;
    setSelectedAgent(agents[nextIdx]);
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
        initial={{ opacity: 0, y: 20 }}
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
          <div style={{ padding: "20px" }}>
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
            padding: "12px 20px",
            borderTop: "1px solid var(--border-secondary)",
          }}>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}>
              {/* Agent 选择 */}
              {agentsLoading ? (
                <span style={{ fontSize: "13px", color: "var(--text-level-3)" }}>{t("common.loading")}</span>
              ) : agents.length > 0 ? (
                <div style={{ position: "relative" }}>
                  <button
                    onClick={handleAgentSwitch}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "8px 14px",
                      borderRadius: "var(--radius-full)",
                      border: "1px solid var(--border-primary)",
                      background: "var(--bg-level-2)",
                      cursor: "pointer",
                      fontSize: "13px",
                      color: "var(--text-level-2)",
                      transition: "all var(--transition-fast)",
                    }}
                    title={currentAgent?.description}
                  >
                    <span style={{ fontSize: "16px" }}>{currentAgent?.avatar}</span>
                    <span style={{ fontWeight: "500" }}>{currentAgent?.name}</span>
                  </button>
                </div>
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
                width: "40px",
                height: "40px",
                borderRadius: "var(--radius-md)",
                border: "none",
                background: input.trim() && currentAgent && !isCreating ? "var(--color-primary)" : "var(--bg-level-4)",
                cursor: input.trim() && currentAgent && !isCreating ? "pointer" : "not-allowed",
                color: "white",
                transition: "all var(--transition-fast)",
              }}
            >
              <ArrowRight style={{ width: "18px", height: "18px" }} />
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
