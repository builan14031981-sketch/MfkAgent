"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { Send, Copy, Quote, RefreshCw, Brain, Zap, Folder } from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useModels, Model } from "@/hooks/useModels";
import { useProjects } from "@/hooks/useProjects";
import { useChat } from "@/hooks/useChat";
import { useMessages } from "@/hooks/useMessages";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";
import { apiGet } from "@/lib/api";
import { ToolsPanel } from "@/components/panels/ToolsPanel";
import { ProjectContextPanel } from "@/components/panels/ProjectContextPanel";

export default function ChatPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const chatId = params.id ? Number(params.id) : null;
  const { t } = useTranslation();

  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const [personalityLevel, setPersonalityLevel] = useState(50);
  const [personalityInitialized, setPersonalityInitialized] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { agents } = useAgents();
  const { models } = useModels();
  const { projects } = useProjects();
  const { chats, updateChat } = useChat();
  const { messages, sendMessageStream } = useMessages(chatId);
  const { settings } = useSettingsStore();

  const currentChat = chats.find((c) => c.id === chatId);
  const currentAgent = agents.find((a) => a.id === currentChat?.agent_id);
  const currentProject = (currentChat?.project_id ? projects.find(p => p.id === currentChat.project_id) : null) ?? null;
  const currentModel = selectedModel || models[0] || null;

  // Initialize personality level from settings (adjust during render, avoiding effect setState)
  if (!personalityInitialized && settings?.default_personality) {
    setPersonalityInitialized(true);
    setPersonalityLevel(Number(settings.default_personality));
  }

  const [toolsPanelOpen, setToolsPanelOpen] = useState(false);
  const [projectContextOpen, setProjectContextOpen] = useState(false);
  const [contextFiles, setContextFiles] = useState<string[]>([]);

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
            },
            personalityLevel
          );
        } catch (err) {
          console.error("Failed to auto-send:", err);
          setIsSending(false);
          setStreamingContent("");
        }
      };

      autoSend();
    }
  }, [searchParams, hasAutoSent, chatId, messages, isSending, sendMessageStream, personalityLevel]);

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

  const buildContextPrefix = async () => {
    if (!chatId || contextFiles.length === 0 || !currentProject) return "";
    try {
      const parts: string[] = [];
      for (const filePath of contextFiles) {
        try {
          const params = new URLSearchParams({ path: filePath });
          const data = await apiGet<{ content: string }>(`/api/projects/${currentProject.id}/file?${params}`);
          parts.push(`[文件: ${filePath}]\n${data.content}`);
        } catch (err) {
          console.error(`Failed to read context file ${filePath}:`, err);
        }
      }
      if (parts.length === 0) return "";
      return `[项目文件上下文]\n${parts.join("\n\n")}\n\n`;
    } catch (err) {
      console.error("Failed to build context prefix:", err);
      return "";
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isSending) return;

    const userMessage = input.trim();
    const modelId = currentModel?.id || "mimo-v2.5-pro";
    setInput("");
    setIsSending(true);
    setStreamingContent("");

    try {
      const contextPrefix = await buildContextPrefix();
      const finalMessage = contextPrefix ? `${contextPrefix}${userMessage}` : userMessage;
      await sendMessageStream(
        finalMessage,
        modelId,
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
        },
        personalityLevel
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
        padding: "8px 24px",
        borderBottom: "1px solid rgba(128, 128, 128, 0.15)",
        background: "color-mix(in srgb, var(--bg-level-1) 85%, transparent)",
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
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}>
            {currentProject && (
              <span style={{
                fontSize: "12px",
                color: "var(--color-primary)",
                padding: "4px 8px",
                borderRadius: "var(--radius-full)",
                background: "var(--color-primary-lighter)",
              }}>📁 {currentProject.name}</span>
            )}
            {currentProject && (
              <button
                onClick={() => setProjectContextOpen(true)}
                title={t("chat.projectContext")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "28px",
                  height: "28px",
                  borderRadius: "var(--radius-full)",
                  border: "1px solid var(--border-primary)",
                  background: "var(--bg-level-2)",
                  cursor: "pointer",
                  color: "var(--text-level-2)",
                  transition: "all 0.6s ease",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--bg-level-3)";
                  e.currentTarget.style.borderColor = "var(--color-primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "var(--bg-level-2)";
                  e.currentTarget.style.borderColor = "var(--border-primary)";
                }}
              >
                <Folder style={{ width: "14px", height: "14px" }} />
              </button>
            )}
            <span style={{
              fontSize: "12px",
              color: "var(--text-level-3)",
              padding: "4px 8px",
              borderRadius: "var(--radius-full)",
              background: "var(--bg-level-3)",
            }}>{currentAgent.name}</span>
            {/* 人格滑块 */}
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "0 8px",
            }}>
              <Brain style={{ width: "14px", height: "14px", color: "var(--text-level-4)" }} />
              <input
                type="range"
                min="0"
                max="100"
                step="25"
                value={personalityLevel}
                onChange={(e) => setPersonalityLevel(Number(e.target.value))}
                style={{
                  width: "100px",
                  accentColor: "var(--color-primary)",
                }}
                title={t("settings.ai.defaultPersonality.desc")}
              />
              <span style={{
                fontSize: "11px",
                color: "var(--text-level-4)",
                minWidth: "28px",
                textAlign: "right",
              }}>{personalityLevel}</span>
            </div>
          </div>
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
        }}>
          {/* 输入框行 */}
          <div style={{
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
              onMouseEnter={(e) => {
                if (input.trim() && !isSending) {
                  e.currentTarget.style.background = "var(--color-primary-hover)";
                  e.currentTarget.style.transform = "scale(1.05)";
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = input.trim() && !isSending ? "var(--color-primary)" : "var(--bg-level-3)";
                e.currentTarget.style.transform = "scale(1)";
              }}
              onMouseDown={(e) => {
                e.currentTarget.style.transform = "scale(0.95)";
              }}
              onMouseUp={(e) => {
                e.currentTarget.style.transform = "scale(1)";
              }}
            >
              <Send style={{ width: "18px", height: "18px" }} />
            </button>
          </div>

          {/* 工具栏行 */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            marginTop: "8px",
          }}>
            {/* 模型选择 */}
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
            {/* 工具按钮 */}
            <button
              onClick={() => setToolsPanelOpen(true)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "32px",
                height: "32px",
                borderRadius: "var(--radius-full)",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-2)",
                cursor: "pointer",
                color: "var(--text-level-2)",
                transition: "all 0.6s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-level-3)";
                e.currentTarget.style.borderColor = "var(--color-primary)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "var(--bg-level-2)";
                e.currentTarget.style.borderColor = "var(--border-primary)";
              }}
              title={t("tools.title")}
            >
              <Zap style={{ width: "16px", height: "16px" }} />
            </button>
          </div>
        </div>
        <p style={{
          textAlign: "center",
          fontSize: "12px",
          color: "var(--text-level-4)",
          marginTop: "8px",
          marginBottom: 0,
        }}>{t("chat.aiMayError")}</p>
      </div>

      {/* Tools Panel */}
      <ToolsPanel isOpen={toolsPanelOpen} onClose={() => setToolsPanelOpen(false)} />

      {/* Project Context Panel */}
      <ProjectContextPanel
        isOpen={projectContextOpen}
        onClose={() => setProjectContextOpen(false)}
        project={currentProject}
        selectedFiles={contextFiles}
        onToggleFile={(path) => {
          setContextFiles(prev =>
            prev.includes(path) ? prev.filter(p => p !== path) : [...prev, path]
          );
        }}
        onClearFiles={() => setContextFiles([])}
      />
    </>
  );
}
