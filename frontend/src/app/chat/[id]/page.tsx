"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  Plus,
  Settings,
  Send,
  MessageSquare,
  Trash2,
} from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useProjects } from "@/hooks/useProjects";
import { useChat } from "@/hooks/useChat";
import { useMessages } from "@/hooks/useMessages";

export default function ChatPage() {
  const router = useRouter();
  const params = useParams();
  const chatId = Number(params.id);

  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { agents } = useAgents();
  useProjects();
  const { chats, deleteChat } = useChat();
  const { messages, sendMessage, getAIReply } = useMessages(chatId);

  const currentChat = chats.find((c) => c.id === chatId);
  const currentAgent = agents.find((a) => a.id === currentChat?.agent_id);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isSending) return;

    const userMessage = input.trim();
    setInput("");
    setIsSending(true);

    try {
      await sendMessage(userMessage);
      await getAIReply();
    } catch (err) {
      console.error("Failed to send message:", err);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleDeleteChat = async (id: number) => {
    try {
      await deleteChat(id);
      router.push("/");
    } catch (err) {
      console.error("Failed to delete chat:", err);
    }
  };

  return (
    <div style={{
      display: "flex",
      height: "100vh",
      background: "var(--bg-level-2)",
    }}>
      {/* 左侧 Sidebar */}
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

        {/* 聊天列表 */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "0 16px 16px 16px",
        }}>
          <p style={{
            padding: "0 12px",
            marginBottom: "4px",
            fontSize: "12px",
            fontWeight: "600",
            color: "var(--text-level-4)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}>Chats</p>
          {chats.map((chat) => (
            <div
              key={chat.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 12px",
                borderRadius: "var(--radius-sm)",
                background: chat.id === chatId ? "var(--bg-level-3)" : "transparent",
                cursor: "pointer",
                marginBottom: "2px",
              }}
              onClick={() => router.push(`/chat/${chat.id}`)}
            >
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                flex: 1,
                overflow: "hidden",
              }}>
                <MessageSquare style={{ width: "14px", height: "14px", flexShrink: 0 }} />
                <span style={{
                  fontSize: "14px",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}>{chat.title}</span>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteChat(chat.id);
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "24px",
                  height: "24px",
                  borderRadius: "var(--radius-xs)",
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  color: "var(--text-level-4)",
                  flexShrink: 0,
                }}
              >
                <Trash2 style={{ width: "12px", height: "12px" }} />
              </button>
            </div>
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

      {/* 右侧聊天区域 */}
      <main style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        height: "100vh",
      }}>
        {/* 聊天头部 */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 24px",
          borderBottom: "1px solid var(--border-primary)",
          background: "var(--bg-level-1)",
        }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}>
            {currentAgent && (
              <span style={{ fontSize: "18px" }}>{currentAgent.avatar}</span>
            )}
            <h1 style={{
              fontSize: "16px",
              fontWeight: "600",
              color: "var(--text-level-1)",
              margin: 0,
            }}>{currentChat?.title || "Chat"}</h1>
          </div>
          {currentAgent && (
            <span style={{
              fontSize: "12px",
              color: "var(--text-level-3)",
              padding: "4px 8px",
              borderRadius: "var(--radius-full)",
              background: "var(--bg-level-3)",
            }}>{currentAgent.name}</span>
          )}
        </div>

        {/* 消息列表 */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "24px",
        }}>
          {messages.length === 0 ? (
            <div style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              color: "var(--text-level-3)",
            }}>
              {currentAgent && (
                <span style={{ fontSize: "48px", marginBottom: "16px" }}>{currentAgent.avatar}</span>
              )}
              <p style={{ fontSize: "16px", margin: 0 }}>开始对话</p>
              <p style={{ fontSize: "13px", margin: "4px 0 0 0", color: "var(--text-level-4)" }}>
                输入消息开始与 {currentAgent?.name || "AI"} 交流
              </p>
            </div>
          ) : (
            <div style={{
              maxWidth: "800px",
              margin: "0 auto",
            }}>
              {messages.map((message) => (
                <div
                  key={message.id}
                  style={{
                    display: "flex",
                    justifyContent: message.role === "user" ? "flex-end" : "flex-start",
                    marginBottom: "16px",
                  }}
                >
                  <div style={{
                    maxWidth: "70%",
                    padding: "12px 16px",
                    borderRadius: "var(--radius-lg)",
                    background: message.role === "user" ? "var(--color-primary)" : "var(--bg-level-3)",
                    color: message.role === "user" ? "white" : "var(--text-level-2)",
                    fontSize: "14px",
                    lineHeight: "1.6",
                    whiteSpace: "pre-wrap",
                  }}>
                    {message.content}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* 输入区域 */}
        <div style={{
          padding: "16px 24px",
          borderTop: "1px solid var(--border-primary)",
          background: "var(--bg-level-1)",
        }}>
          <div style={{
            maxWidth: "800px",
            margin: "0 auto",
            display: "flex",
            gap: "12px",
            alignItems: "flex-end",
          }}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入消息..."
              rows={1}
              disabled={isSending}
              style={{
                flex: 1,
                padding: "12px 16px",
                borderRadius: "var(--radius-lg)",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-2)",
                fontSize: "14px",
                lineHeight: "1.5",
                color: "var(--text-level-2)",
                resize: "none",
                outline: "none",
                minHeight: "44px",
                maxHeight: "120px",
              }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isSending}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "44px",
                height: "44px",
                borderRadius: "var(--radius-lg)",
                border: "none",
                background: input.trim() && !isSending ? "var(--color-primary)" : "var(--bg-level-3)",
                cursor: input.trim() && !isSending ? "pointer" : "not-allowed",
                color: input.trim() && !isSending ? "white" : "var(--text-level-3)",
                transition: "all var(--transition-fast)",
                flexShrink: 0,
              }}
            >
              <Send style={{ width: "18px", height: "18px" }} />
            </button>
          </div>
          <p style={{
            textAlign: "center",
            fontSize: "12px",
            color: "var(--text-level-4)",
            marginTop: "8px",
            marginBottom: 0,
          }}>MfkAgent 可能会犯错，请核实重要信息</p>
        </div>
      </main>
    </div>
  );
}
