"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { Send, Copy, Quote, RefreshCw } from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useChat } from "@/hooks/useChat";
import { useMessages } from "@/hooks/useMessages";
import { useTranslation } from "@/hooks/useTranslation";

export default function ChatPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const chatId = params.id ? Number(params.id) : null;
  const { t } = useTranslation();

  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { agents } = useAgents();
  const { chats, updateChat } = useChat();
  const { messages, sendMessageStream } = useMessages(chatId);

  const currentChat = chats.find((c) => c.id === chatId);
  const currentAgent = agents.find((a) => a.id === currentChat?.agent_id);

  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [hasAutoSent, setHasAutoSent] = useState(false);
  const autoSendLockRef = useRef(false);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // 从URL参数获取用户输入，自动发送消息
  useEffect(() => {
    const messageParam = searchParams.get("message");
    if (
      messageParam &&
      !hasAutoSent &&
      !autoSendLockRef.current &&
      chatId &&
      messages.length === 0 &&
      !isSending
    ) {
      // 使用ref锁定，防止React StrictMode下重复执行
      autoSendLockRef.current = true;
      setHasAutoSent(true);

      const userMessage = decodeURIComponent(messageParam);

      // 清除URL参数
      const newUrl = `/chat/${chatId}`;
      window.history.replaceState({}, "", newUrl);

      // 自动发送消息
      const autoSend = async () => {
        setIsSending(true);
        setStreamingContent("");
        try {
          await sendMessageStream(
            userMessage,
            "mimo-v2.5-pro",
            (chunk) => {
              setStreamingContent((prev) => prev + chunk);
            },
            () => {
              setStreamingContent("");
              setIsSending(false);
            },
            (error) => {
              console.error("Auto-send stream error:", error);
              setStreamingContent("");
              setIsSending(false);
            }
          );
        } catch (err) {
          console.error("Failed to auto-send:", err);
          setIsSending(false);
          setStreamingContent("");
        }
      };

      autoSend();
    }
  }, [searchParams, hasAutoSent, chatId, messages, isSending, sendMessageStream]);

  if (!chatId) {
    return (
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        background: "var(--bg-level-2)",
      }}>
        <div style={{ textAlign: "center" }}>
          <p style={{ fontSize: "16px", color: "var(--text-level-2)", margin: 0 }}>{t("chat.invalidId")}</p>
          <button
            onClick={() => router.push("/")}
            style={{
              marginTop: "16px",
              padding: "8px 16px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "var(--color-primary)",
              color: "white",
              cursor: "pointer",
              fontSize: "14px",
            }}
          >{t("chat.backToHome")}</button>
        </div>
      </div>
    );
  }

  const handleSend = async () => {
    if (!input.trim() || isSending) return;

    const userMessage = input.trim();
    setInput("");
    setIsSending(true);
    setStreamingContent("");

    try {
      await sendMessageStream(
        userMessage,
        "mimo-v2.5-pro",
        (chunk) => {
          setStreamingContent((prev) => prev + chunk);
        },
        () => {
          setStreamingContent("");
          setIsSending(false);
        },
        (error) => {
          console.error("Stream error:", error);
          setStreamingContent("");
          setIsSending(false);
        }
      );
    } catch (err) {
      console.error("Failed to send message:", err);
      setIsSending(false);
      setStreamingContent("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      // 防止重复触发
      if (!isSending && input.trim()) {
        handleSend();
      }
    }
  };

  const handleStartEditTitle = () => {
    setEditTitle(currentChat?.title || "");
    setIsEditingTitle(true);
  };

  const handleSaveTitle = async () => {
    if (!chatId || !editTitle.trim()) return;
    try {
      await updateChat(chatId, { title: editTitle.trim() });
      setIsEditingTitle(false);
    } catch (err) {
      console.error("Failed to update title:", err);
    }
  };

  return (
    <>
      {/* 聊天头部 */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "16px 24px",
        borderBottom: "1px solid var(--border-primary)",
        background: "var(--bg-level-1)",
        flexShrink: 0,
      }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}>
          {currentAgent && (
            <span style={{ fontSize: "18px" }}>{currentAgent.avatar}</span>
          )}
          {isEditingTitle ? (
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onBlur={handleSaveTitle}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSaveTitle();
                if (e.key === "Escape") setIsEditingTitle(false);
              }}
              autoFocus
              style={{
                fontSize: "16px",
                fontWeight: "600",
                color: "var(--text-level-1)",
                background: "transparent",
                border: "none",
                outline: "none",
                padding: 0,
                margin: 0,
                width: "200px",
              }}
            />
          ) : (
            <h1
              onClick={handleStartEditTitle}
              style={{
                fontSize: "16px",
                fontWeight: "600",
                color: "var(--text-level-1)",
                margin: 0,
                cursor: "pointer",
              }}
            >{currentChat?.title || "Chat"}</h1>
          )}
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
        {messages.length === 0 && !streamingContent ? (
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
            <p style={{ fontSize: "16px", margin: 0 }}>{t("chat.startConversation")}</p>
            <p style={{ fontSize: "13px", margin: "4px 0 0 0", color: "var(--text-level-4)" }}>
              {t("chat.startConversationDesc", { name: currentAgent?.name || "AI" })}
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
                  marginBottom: "24px",
                }}
              >
                {message.role === "user" ? (
                  /* 用户消息：轻量气泡 */
                  <div style={{
                    display: "flex",
                    justifyContent: "flex-end",
                  }}>
                    <div style={{
                      maxWidth: "70%",
                      padding: "10px 14px",
                      borderRadius: "var(--radius-md)",
                      background: "var(--color-primary)",
                      color: "white",
                      fontSize: "14px",
                      lineHeight: "1.6",
                      whiteSpace: "pre-wrap",
                    }}>
                      {message.content}
                    </div>
                  </div>
                ) : (
                  /* AI 回复：无气泡，全宽显示 */
                  <div>
                    {/* AI 标识 */}
                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}>
                      {currentAgent && (
                        <span style={{ fontSize: "16px" }}>{currentAgent.avatar}</span>
                      )}
                      <span style={{
                        fontSize: "13px",
                        fontWeight: "500",
                        color: "var(--text-level-3)",
                      }}>{currentAgent?.name || "AI"}</span>
                    </div>
                    {/* 正文区域 */}
                    <div style={{
                      fontSize: "14px",
                      lineHeight: "1.7",
                      color: "var(--text-level-2)",
                      whiteSpace: "pre-wrap",
                    }}>
                      {message.content}
                    </div>
                    {/* 操作区域 */}
                    <div style={{
                      display: "flex",
                      gap: "8px",
                      marginTop: "8px",
                      opacity: 0,
                      transition: "opacity 0.2s",
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.opacity = "1"}
                    onMouseLeave={(e) => e.currentTarget.style.opacity = "0"}
                    >
                      <button style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: "28px",
                        height: "28px",
                        borderRadius: "var(--radius-sm)",
                        border: "none",
                        background: "transparent",
                        cursor: "pointer",
                        color: "var(--text-level-4)",
                      }}>
                        <Copy style={{ width: "14px", height: "14px" }} />
                      </button>
                      <button style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: "28px",
                        height: "28px",
                        borderRadius: "var(--radius-sm)",
                        border: "none",
                        background: "transparent",
                        cursor: "pointer",
                        color: "var(--text-level-4)",
                      }}>
                        <Quote style={{ width: "14px", height: "14px" }} />
                      </button>
                      <button style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: "28px",
                        height: "28px",
                        borderRadius: "var(--radius-sm)",
                        border: "none",
                        background: "transparent",
                        cursor: "pointer",
                        color: "var(--text-level-4)",
                      }}>
                        <RefreshCw style={{ width: "14px", height: "14px" }} />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {streamingContent && (
              <div style={{ marginBottom: "24px" }}>
                {/* AI 标识 */}
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  marginBottom: "8px",
                }}>
                  {currentAgent && (
                    <span style={{ fontSize: "16px" }}>{currentAgent.avatar}</span>
                  )}
                  <span style={{
                    fontSize: "13px",
                    fontWeight: "500",
                    color: "var(--text-level-3)",
                  }}>{currentAgent?.name || "AI"}</span>
                </div>
                {/* 正文区域 */}
                <div style={{
                  fontSize: "14px",
                  lineHeight: "1.7",
                  color: "var(--text-level-2)",
                  whiteSpace: "pre-wrap",
                }}>
                  {streamingContent}
                  <span style={{
                    display: "inline-block",
                    width: "2px",
                    height: "14px",
                    background: "var(--text-level-2)",
                    marginLeft: "2px",
                    animation: "pulse 1s infinite",
                  }} />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* 输入区域 */}
      <div style={{
        padding: "16px 24px",
        borderTop: "1px solid var(--border-primary)",
        background: "var(--bg-level-1)",
        flexShrink: 0,
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
            placeholder={t("chat.inputPlaceholder")}
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
        }}>{t("chat.aiMayError")}</p>
      </div>
    </>
  );
}
