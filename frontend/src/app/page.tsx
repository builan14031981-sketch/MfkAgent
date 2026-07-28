/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Plus,
  ArrowRight,
  Settings,
} from "lucide-react";
import { useAgents, Agent } from "@/hooks/useAgents";
import { useProjects } from "@/hooks/useProjects";

const welcomeMessages = [
  "嗨，今天感觉怎么样？",
  "今天想做哪个项目？",
  "有什么新的灵感吗？",
  "准备好开始工作了吗？",
  "需要我帮你做什么？",
];

export default function Home() {
  const router = useRouter();
  const [input, setInput] = useState("");
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const { agents, loading: agentsLoading } = useAgents();
  const { projects, loading: projectsLoading } = useProjects();
  const [welcome, setWelcome] = useState(welcomeMessages[0]);

  useEffect(() => {
    setWelcome(welcomeMessages[Math.floor(Math.random() * welcomeMessages.length)]);
    // eslint-disable-next-line react-hooks/set-state-in-effect
  }, []);

  const currentAgent = selectedAgent || agents[0] || null;

  const handleSend = () => {
    if (!input.trim() || !currentAgent) return;
    router.push(`/chat/${currentAgent.id}?q=${encodeURIComponent(input)}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
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
      display: "flex",
      height: "100vh",
      background: "var(--bg-level-2)",
    }}>
      {/* 左侧 Workspace */}
      <aside style={{
        width: "280px",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        borderRight: "1px solid var(--border-primary)",
        background: "var(--bg-level-1)",
      }}>
        {/* 新建任务 */}
        <div style={{ padding: "16px" }}>
          <button
            onClick={() => router.push("/")}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 16px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "var(--bg-level-3)",
              cursor: "pointer",
              fontSize: "14px",
            }}
          >
            <Plus style={{ width: "16px", height: "16px" }} />
            <span>New Task</span>
          </button>
        </div>

        {/* 项目列表 */}
        <div style={{ padding: "0 16px", marginBottom: "8px" }}>
          <div style={{
            padding: "12px",
            borderRadius: "var(--radius-md)",
            background: "var(--color-primary-lighter)",
          }}>
            <p style={{
              fontSize: "12px",
              fontWeight: "500",
              color: "var(--color-primary)",
              margin: 0,
            }}>Project</p>
            {projectsLoading ? (
              <p style={{ fontSize: "14px", margin: "4px 0 0 0", color: "var(--text-level-3)" }}>加载中...</p>
            ) : projects.length > 0 ? (
              projects.map((project) => (
                <p key={project.id} style={{
                  fontSize: "14px",
                  fontWeight: "500",
                  margin: "4px 0 0 0",
                }}>{project.name}</p>
              ))
            ) : (
              <p style={{ fontSize: "14px", margin: "4px 0 0 0", color: "var(--text-level-3)" }}>暂无项目</p>
            )}
          </div>
        </div>

        {/* 历史记录 */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "0 16px 16px 16px",
        }}>
          <p style={{
            padding: "0 12px",
            marginBottom: "4px",
            fontSize: "10px",
            fontWeight: "600",
            color: "var(--text-level-4)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}>History</p>
          <p style={{
            padding: "8px 12px",
            fontSize: "14px",
            color: "var(--text-level-3)",
          }}>暂无聊天记录</p>
        </div>

        {/* 设置 */}
        <div style={{
          padding: "16px",
          borderTop: "1px solid var(--border-primary)",
        }}>
          <button
            onClick={() => router.push("/settings")}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 12px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "14px",
              color: "var(--text-level-3)",
            }}
          >
            <Settings style={{ width: "16px", height: "16px" }} />
            <span>Settings</span>
          </button>
        </div>
      </aside>

      {/* 右侧 Workspace Canvas */}
      <main style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        overflow: "auto",
        paddingTop: "120px",
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
                placeholder="输入内容开始工作..."
                rows={3}
                style={{
                  width: "100%",
                  background: "transparent",
                  border: "none",
                  outline: "none",
                  resize: "none",
                  fontSize: "16px",
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
                  <span style={{ fontSize: "13px", color: "var(--text-level-3)" }}>加载中...</span>
                ) : agents.length > 0 ? (
                  <button
                    onClick={handleAgentSwitch}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "6px 14px",
                      borderRadius: "var(--radius-full)",
                      border: "none",
                      background: "var(--bg-level-2)",
                      cursor: "pointer",
                      fontSize: "13px",
                      color: "var(--text-level-3)",
                    }}
                  >
                    <span style={{ fontSize: "14px" }}>{currentAgent?.avatar}</span>
                    <span>{currentAgent?.name}</span>
                  </button>
                ) : null}
              </div>

              {/* 发送按钮 */}
              <button
                onClick={handleSend}
                disabled={!input.trim() || !currentAgent}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "40px",
                  height: "40px",
                  borderRadius: "var(--radius-md)",
                  border: "none",
                  background: input.trim() && currentAgent ? "var(--color-primary)" : "var(--bg-level-4)",
                  cursor: input.trim() && currentAgent ? "pointer" : "not-allowed",
                  color: "white",
                  transition: "all var(--transition-fast)",
                }}
              >
                <ArrowRight style={{ width: "18px", height: "18px" }} />
              </button>
            </div>
          </div>
        </motion.div>
      </main>

      {/* 底部提示 - 固定在页面底部 */}
      <div style={{
        position: "fixed",
        bottom: "16px",
        left: 0,
        right: 0,
        textAlign: "center",
        fontSize: "12px",
        color: "var(--text-level-4)",
        pointerEvents: "none",
      }}>MfkAgent 可能会犯错，请核实重要信息</div>
    </div>
  );
}
