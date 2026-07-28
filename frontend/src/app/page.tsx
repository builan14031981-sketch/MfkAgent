"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Plus,
  ArrowRight,
  Sparkles,
  Bot,
  MessageSquare,
  Settings,
} from "lucide-react";

const presetAgents = [
  {
    id: "warm",
    name: "小暖",
    avatar: "🌸",
    description: "情感理解型助手",
    tagline: "先理解你，再陪你解决问题。",
  },
  {
    id: "rui",
    name: "锐",
    avatar: "⚔️",
    description: "理性决策型助手",
    tagline: "不要迎合问题，解决问题。",
  },
  {
    id: "coder",
    name: "码农",
    avatar: "💻",
    description: "编程开发助手",
    tagline: "代码说话，少废话。",
  },
  {
    id: "writer",
    name: "笔神",
    avatar: "✍️",
    description: "写作创作助手",
    tagline: "让文字更有力量。",
  },
];

const historyItems = [
  { id: "1", title: "Chat with Warm", agentId: "warm", time: "today" },
  { id: "2", title: "Code review", agentId: "coder", time: "today" },
  { id: "3", title: "Write documentation", agentId: "writer", time: "yesterday" },
];

export default function Home() {
  const router = useRouter();
  const [input, setInput] = useState("");
  const [selectedAgent, setSelectedAgent] = useState(presetAgents[0]);

  const handleSend = () => {
    if (!input.trim()) return;
    router.push(`/chat/${selectedAgent.id}?q=${encodeURIComponent(input)}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
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

        {/* 项目 */}
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
            <p style={{
              fontSize: "14px",
              fontWeight: "500",
              margin: "4px 0 0 0",
            }}>MfkAgent</p>
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
          }}>Today</p>
          {historyItems
            .filter((item) => item.time === "today")
            .map((item) => (
              <button
                key={item.id}
                onClick={() => router.push(`/chat/${item.agentId}`)}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "8px 12px",
                  borderRadius: "var(--radius-sm)",
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  fontSize: "14px",
                  color: "var(--text-level-3)",
                  textAlign: "left",
                }}
              >
                <MessageSquare style={{ width: "14px", height: "14px" }} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.title}</span>
              </button>
            ))}
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
            }}>和你的AI助手开始工作</p>
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
                {/* Agent 胶囊按钮 */}
                <button
                  onClick={() => {}}
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
                  <span style={{ fontSize: "14px" }}>{selectedAgent.avatar}</span>
                  <span>{selectedAgent.name}</span>
                </button>
              </div>

              {/* 发送按钮 */}
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "40px",
                  height: "40px",
                  borderRadius: "var(--radius-md)",
                  border: "none",
                  background: input.trim() ? "var(--color-primary)" : "var(--bg-level-4)",
                  cursor: input.trim() ? "pointer" : "not-allowed",
                  color: "white",
                  transition: "all var(--transition-fast)",
                }}
              >
                <ArrowRight style={{ width: "18px", height: "18px" }} />
              </button>
            </div>
          </div>

          {/* 底部提示 */}
          <p style={{
            textAlign: "center",
            fontSize: "12px",
            color: "var(--text-level-4)",
            marginTop: "24px",
          }}>MfkAgent 可能会犯错，请核实重要信息</p>
        </motion.div>
      </main>
    </div>
  );
}
