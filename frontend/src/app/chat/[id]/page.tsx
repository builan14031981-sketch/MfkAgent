"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { Copy, Quote, RefreshCw, Folder } from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useModels, Model } from "@/hooks/useModels";
import { useProjects } from "@/hooks/useProjects";
import { useChat } from "@/hooks/useChat";
import { useMessages } from "@/hooks/useMessages";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";
import { apiGet } from "@/lib/api";
import { ProjectContextPanel } from "@/components/panels/ProjectContextPanel";
import { AgentIcon } from "@/components/AgentIcon";
import { FileDropZone } from "@/components/FileDropZone";
import type { DroppedFile } from "@/components/FileDropZone";
import { ChatInput } from "@/components/ChatInput";
import { ToolCallCardList } from "@/components/ToolCallCard";

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
  const [personalityInitForChatId, setPersonalityInitForChatId] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { agents } = useAgents();
  const { models } = useModels();
  const { projects, createProject } = useProjects();
  const { chats, updateChat } = useChat();
  const { messages, sendMessageStream } = useMessages(chatId);
  const { settings } = useSettingsStore();

  const currentChat = chats.find((c) => c.id === chatId);
  const currentAgent = agents.find((a) => a.id === currentChat?.agent_id);
  const currentProject = (currentChat?.project_id ? projects.find(p => p.id === currentChat.project_id) : null) ?? null;
  const currentModel = selectedModel || (currentChat?.model ? models.find(m => m.id === currentChat.model) || null : null) || models[0] || null;

  // 人格初始值：优先读当前会话快照 currentChat.personality_level，仅当其缺失时回退全局默认/50。
  // 切换会话时（chatId 变化）重新初始化，确保老会话继承自己保存的理性度。
  if (personalityInitForChatId !== chatId && currentChat) {
    setPersonalityInitForChatId(chatId);
    const snapshot = currentChat.personality_level;
    setPersonalityLevel(
      snapshot != null
        ? snapshot
        : (settings?.default_personality ? Number(settings.default_personality) : 50)
    );
  }

  const [reasoningEffort, setReasoningEffort] = useState<"none" | "low" | "high">("none");
  const [projectContextOpen, setProjectContextOpen] = useState(false);
  const [contextFiles, setContextFiles] = useState<string[]>([]);
  const [contextInitForChatId, setContextInitForChatId] = useState<number | null>(null);

  // 上下文文件初始值：读会话快照 currentChat.context_files（首页草稿预挂载时随创建请求一起提交）。
  if (contextInitForChatId !== chatId && currentChat) {
    setContextInitForChatId(chatId);
    setContextFiles(currentChat.context_files || []);
  }

  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [hasAutoSent, setHasAutoSent] = useState(false);
  const autoSendLockRef = useRef(false);

  // 将拖入文件的绝对路径转为项目相对路径（挂载 Context 用）
  const toProjectRelativePath = useCallback((absPath: string): string => {
    if (!currentProject) return absPath;
    const normalize = (p: string) => p.replace(/\\/g, "/");
    const projRoot = normalize(currentProject.path).replace(/\/+$/, "");
    const filePath = normalize(absPath);
    if (filePath.startsWith(projRoot + "/")) {
      return filePath.slice(projRoot.length + 1);
    }
    return filePath.split("/").pop() || absPath;
  }, [currentProject]);

  const handleFilesDrop = useCallback((files: DroppedFile[]) => {
    setContextFiles((prev) => {
      const next = [...prev];
      for (const file of files) {
        const relPath = toProjectRelativePath(file.path);
        if (!next.includes(relPath)) next.push(relPath);
      }
      return next;
    });
  }, [toProjectRelativePath]);

  const removeContextFile = useCallback((path: string) => {
    setContextFiles((prev) => prev.filter((p) => p !== path));
  }, []);

  // 上传文件：挂载为当前会话的 Context 文件（Electron 下 File.path 为绝对路径）
  const handleUploadFile = useCallback((file: File) => {
    const fileWithPath = file as File & { path?: string };
    const relPath = toProjectRelativePath(fileWithPath.path || file.name);
    setContextFiles((prev) => (prev.includes(relPath) ? prev : [...prev, relPath]));
  }, [toProjectRelativePath]);

  // 关联本地项目：创建 Project 并绑定到当前会话
  const handleSelectDirectory = useCallback(async (dirPath: string) => {
    if (!chatId) return;
    try {
      const name = dirPath.split(/[\\/]/).filter(Boolean).pop() || dirPath;
      const project = await createProject(name, dirPath);
      await updateChat(chatId, { project_id: project.id });
      window.dispatchEvent(new Event("mfk-projects-changed"));
    } catch (err) {
      console.error("Failed to link project:", err);
    }
  }, [chatId, createProject, updateChat]);

  const handleClearContext = useCallback(() => {
    setContextFiles([]);
  }, []);

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
            currentModel?.id || "mimo-v2.5-pro",
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
            personalityLevel,
            reasoningEffort
          );
        } catch (err) {
          console.error("Failed to auto-send:", err);
          setIsSending(false);
          setStreamingContent("");
        }
      };

      autoSend();
    }
  }, [searchParams, hasAutoSent, chatId, messages, isSending, sendMessageStream, personalityLevel, reasoningEffort, currentModel?.id]);

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
        personalityLevel,
        reasoningEffort
      );
    } catch (err) {
      console.error("Failed to send message:", err);
      setIsSending(false);
      setStreamingContent("");
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
            <AgentIcon id={currentAgent.id} size={18} style={{ color: "var(--color-primary)" }} />
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
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}>
                <Folder style={{ width: "12px", height: "12px" }} />
                {currentProject.name}
              </span>
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
              <AgentIcon id={currentAgent.id} size={48} strokeWidth={1.5} style={{ marginBottom: "16px", color: "var(--text-level-4)" }} />
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
                        <AgentIcon id={currentAgent.id} size={16} style={{ color: "var(--text-level-3)" }} />
                      )}
                      <span style={{
                        fontSize: "13px",
                        fontWeight: "500",
                        color: "var(--text-level-3)",
                      }}>{currentAgent?.name || "AI"}</span>
                    </div>
                    {/* 文件操作事件卡片 */}
                    {message.tool_calls && message.tool_calls.length > 0 && (
                      <ToolCallCardList toolCalls={message.tool_calls} />
                    )}
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
                    <AgentIcon id={currentAgent.id} size={16} style={{ color: "var(--text-level-3)" }} />
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
        padding: "12px 24px 16px 24px",
        borderTop: "1px solid var(--border-primary)",
        background: "var(--bg-level-1)",
        flexShrink: 0,
      }}>
        <div style={{
          maxWidth: "800px",
          margin: "0 auto",
        }}>
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={handleSend}
            isSending={isSending}
            placeholder={t("chat.inputPlaceholder")}
            models={models}
            modelId={currentModel?.id || null}
            onModelChange={(id) => {
              const model = models.find(m => m.id === id);
              if (model) {
                setSelectedModel(model);
                if (chatId) {
                  updateChat(chatId, { model: model.id }).catch((err) =>
                    console.error("Failed to persist model:", err)
                  );
                }
              }
            }}
            reasoningEffort={reasoningEffort}
            onReasoningChange={setReasoningEffort}
            onUploadFile={handleUploadFile}
            onSelectDirectory={handleSelectDirectory}
            onClearContext={handleClearContext}
            hasContext={contextFiles.length > 0}
            files={contextFiles}
            onRemoveFile={removeContextFile}
            projectName={currentProject?.name || null}
          />
        </div>
        <p style={{
          textAlign: "center",
          fontSize: "12px",
          color: "var(--text-level-4)",
          marginTop: "8px",
          marginBottom: 0,
        }}>{t("chat.aiMayError")}</p>
      </div>

      {/* 全屏文件拖拽感知 */}
      <FileDropZone onFilesDrop={handleFilesDrop} />

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
