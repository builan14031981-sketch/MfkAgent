"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { Folder } from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useModels, Model } from "@/hooks/useModels";
import { useProjects } from "@/hooks/useProjects";
import { useChat } from "@/hooks/useChat";
import { useMessages } from "@/hooks/useMessages";
import type { Message } from "@/hooks/useMessages";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";
import { apiGet } from "@/lib/api";
import { ProjectContextPanel } from "@/components/panels/ProjectContextPanel";
import { AgentIcon } from "@/components/AgentIcon";
import { FileDropZone } from "@/components/FileDropZone";
import type { DroppedFile } from "@/components/FileDropZone";
import { ChatComposer } from "@/components/ChatComposer";
import type { ChatMode } from "@/components/ChatInput";
import { MessageList } from "@/components/MessageList";
import { MessageOutline } from "@/components/MessageOutline";
import type { ToolCall } from "@/components/ToolCallCard";

export default function ChatPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const chatId = params.id ? Number(params.id) : null;
  const { t } = useTranslation();

  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingThinking, setStreamingThinking] = useState("");
  const [streamingToolCalls, setStreamingToolCalls] = useState<ToolCall[]>([]);
  const [streamingError, setStreamingError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const [personalityLevel, setPersonalityLevel] = useState(50);
  const [personalityInitForChatId, setPersonalityInitForChatId] = useState<number | null>(null);

  const { agents } = useAgents();
  const { models } = useModels();
  const { projects, createProject } = useProjects();
  const { chats, updateChat } = useChat();
  const { messages, sendMessageStream, deleteMessagesFrom, refetch, appendMessage } = useMessages(chatId);
  const { settings } = useSettingsStore();

  const currentChat = chats.find((c) => c.id === chatId);
  const currentAgent = agents.find((a) => a.id === currentChat?.agent_id);
  // 稳定引用：避免每次 render 新建对象导致 memo(MessageList) 失效
  const currentAgentView = useMemo(
    () => (currentAgent ? { id: currentAgent.id, name: currentAgent.name } : null),
    [currentAgent]
  );
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

  const [reasoningEffort, setReasoningEffort] = useState<"none" | "high" | "max">("none");
  const [mode, setMode] = useState<ChatMode>("build");
  const [modeInitForChatId, setModeInitForChatId] = useState<number | null>(null);
  const [projectContextOpen, setProjectContextOpen] = useState(false);
  const [activeUserMessageId, setActiveUserMessageId] = useState<number | null>(null);
  const [contextFiles, setContextFiles] = useState<string[]>([]);
  const [contextInitForChatId, setContextInitForChatId] = useState<number | null>(null);

  // 上下文文件初始值：读会话快照 currentChat.context_files（首页草稿预挂载时随创建请求一起提交）。
  if (contextInitForChatId !== chatId && currentChat) {
    setContextInitForChatId(chatId);
    setContextFiles(currentChat.context_files || []);
  }

  // 工作模式初始值：读会话快照 currentChat.mode（build/plan），切换会话时重置
  if (modeInitForChatId !== chatId && currentChat) {
    setModeInitForChatId(chatId);
    setMode(currentChat.mode === "plan" ? "plan" : "build");
  }

  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [hasAutoSent, setHasAutoSent] = useState(false);
  const autoSendLockRef = useRef(false);
  const chatInputRef = useRef<HTMLTextAreaElement | null>(null);

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

  // 引用：把 AI 回复追加到输入框并聚焦（> 引用块格式）
  const handleQuote = useCallback((content: string) => {
    const quoted = content.trim();
    if (!quoted) return;
    const prefix = input.trim() ? input + "\n\n" : "";
    const target = `${prefix}> ${quoted}\n\n`;
    setInput(target);
    requestAnimationFrame(() => {
      const el = chatInputRef.current;
      if (el) {
        el.focus();
        el.setSelectionRange(target.length, target.length);
      }
    });
  }, [input]);

  // 编辑：拉回输入框，删除该消息及其后的所有历史
  const handleEdit = useCallback(async (message: Message) => {
    setInput(message.content);
    try {
      await deleteMessagesFrom(message.id);
    } catch (err) {
      console.error("Failed to clear history on edit:", err);
    }
    requestAnimationFrame(() => {
      const el = chatInputRef.current;
      if (el) {
        el.focus();
        el.setSelectionRange(message.content.length, message.content.length);
      }
    });
  }, [deleteMessagesFrom]);

  // 共享发送管线：对指定用户消息跑流式，处理 thinking/tool/error/complete 全流程。
  // handleRegenerate / handleRetry 复用，保证重试与重生成的错误展示一致。
  const runSendForUser = useCallback(async (userMsg: Message) => {
    setIsSending(true);
    setStreamingContent("");
    setStreamingThinking("");
    setStreamingToolCalls([]);
    setStreamingError(null);
    const modelId = currentModel?.id || "mimo-v2.5-pro";
    try {
      await sendMessageStream(
        userMsg.content,
        modelId,
        (chunk) => setStreamingContent((prev) => prev + chunk),
        () => {
          setStreamingToolCalls([]);
          setIsSending(false);
        },
        (error) => {
          setStreamingContent("");
          setStreamingThinking("");
          setStreamingToolCalls([]);
          setIsSending(false);
          setStreamingError(error);
        },
        personalityLevel,
        reasoningEffort,
        (thinking) => setStreamingThinking((prev) => prev + thinking),
        (toolCall) => {
          setStreamingToolCalls((prev) => {
            const exists = prev.some((t) => t.path === toolCall.path && t.name === toolCall.name);
            return exists ? prev : [...prev, toolCall];
          });
        },
        (batch) => setStreamingToolCalls(batch),
        (finalContent, toolCalls, finalThinking) => {
          setStreamingContent("");
          setStreamingThinking("");
          setStreamingToolCalls([]);
          setStreamingError(null);
          const aiMsg: Message = {
            id: Date.now(),
            chat_id: chatId!,
            role: "assistant",
            content: finalContent,
            thinking: finalThinking || undefined,
            tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
            created_at: new Date().toISOString(),
          };
          appendMessage(aiMsg);
          refetch().catch(() => { /* 静默失败 */ });
        }
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStreamingContent("");
      setStreamingThinking("");
      setStreamingToolCalls([]);
      setIsSending(false);
      setStreamingError(msg);
    }
  }, [sendMessageStream, currentModel?.id, personalityLevel, reasoningEffort, appendMessage, refetch, chatId]);

  // 重试：对最近一条用户消息重新流式生成（错误后 AI 消息未持久化，无需删历史）
  const handleRetry = useCallback(async () => {
    if (isSending) return;
    let userMsg: Message | null = null;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        userMsg = messages[i];
        break;
      }
    }
    if (!userMsg) return;
    await runSendForUser(userMsg);
  }, [isSending, messages, runSendForUser]);

  // 重新生成：删除该 AI 消息及其后历史，找到前一条用户消息重新流式生成
  const handleRegenerate = useCallback(async (messageId: number) => {
    if (isSending) return;
    const idx = messages.findIndex((m) => m.id === messageId);
    if (idx < 0) return;
    // 找到该 AI 消息之前的最近一条用户消息
    let userMsg: Message | null = null;
    for (let i = idx - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        userMsg = messages[i];
        break;
      }
    }
    if (!userMsg) return;
    try {
      await deleteMessagesFrom(messageId);
    } catch (err) {
      console.error("Failed to clear history on regenerate:", err);
      return;
    }
    await runSendForUser(userMsg);
  }, [isSending, messages, deleteMessagesFrom, runSendForUser]);

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
        setStreamingThinking("");
        setStreamingToolCalls([]);
        setStreamingError(null);

        // 乐观更新：先追加用户消息到本地列表
        const tempUserMsg: Message = {
          id: Date.now(),
          chat_id: chatId!,
          role: "user",
          content: userMessage,
          created_at: new Date().toISOString(),
        };
        appendMessage(tempUserMsg);

        try {
          await sendMessageStream(
            userMessage,
            currentModel?.id || "mimo-v2.5-pro",
            (chunk) => {
              setStreamingContent((prev) => prev + chunk);
            },
            () => {
              setStreamingToolCalls([]);
              setIsSending(false);
            },
            (error) => {
              setStreamingContent("");
              setStreamingThinking("");
              setStreamingToolCalls([]);
              setIsSending(false);
              setStreamingError(error);
            },
            personalityLevel,
            reasoningEffort,
            (thinking) => setStreamingThinking((prev) => prev + thinking),
            (toolCall) => {
              setStreamingToolCalls((prev) => {
                const exists = prev.some((t) => t.path === toolCall.path && t.name === toolCall.name);
                return exists ? prev : [...prev, toolCall];
              });
            },
            (batch) => setStreamingToolCalls(batch),
            (finalContent, toolCalls, finalThinking) => {
              // onComplete: 流式内容完整接收，追加 AI 消息到本地列表
              setStreamingContent("");
              setStreamingThinking("");
              setStreamingToolCalls([]);
              setStreamingError(null);
              const aiMsg: Message = {
                id: Date.now() + 1,
                chat_id: chatId!,
                role: "assistant",
                content: finalContent,
                thinking: finalThinking || undefined,
                tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
                created_at: new Date().toISOString(),
              };
              appendMessage(aiMsg);
              // 后台静默同步真实 ID
              refetch().catch(() => { /* 静默失败 */ });
            }
          );
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          setIsSending(false);
          setStreamingContent("");
          setStreamingThinking("");
          setStreamingToolCalls([]);
          setStreamingError(msg);
        }
      };

      autoSend();
    }
  }, [searchParams, hasAutoSent, chatId, messages, isSending, sendMessageStream, personalityLevel, reasoningEffort, currentModel?.id, appendMessage, refetch]);

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
    setStreamingThinking("");
    setStreamingToolCalls([]);
    setStreamingError(null);

    // 乐观更新：先追加用户消息到本地列表（无需等待服务端）
    const tempUserMsg: Message = {
      id: Date.now(),
      chat_id: chatId!,
      role: "user",
      content: userMessage,
      created_at: new Date().toISOString(),
    };
    appendMessage(tempUserMsg);

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
          setStreamingToolCalls([]);
          setIsSending(false);
        },
        (error) => {
          setStreamingContent("");
          setStreamingThinking("");
          setStreamingToolCalls([]);
          setIsSending(false);
          setStreamingError(error);
        },
        personalityLevel,
        reasoningEffort,
        (thinking) => setStreamingThinking((prev) => prev + thinking),
        (toolCall) => {
          setStreamingToolCalls((prev) => {
            const exists = prev.some((t) => t.path === toolCall.path && t.name === toolCall.name);
            return exists ? prev : [...prev, toolCall];
          });
        },
        (batch) => setStreamingToolCalls(batch),
        (finalContent, toolCalls, finalThinking) => {
          // onComplete: 流式内容完整接收，追加 AI 消息到本地列表
          setStreamingContent("");
          setStreamingThinking("");
          setStreamingToolCalls([]);
          setStreamingError(null);
          const aiMsg: Message = {
            id: Date.now() + 1,
            chat_id: chatId!,
            role: "assistant",
            content: finalContent,
            thinking: finalThinking || undefined,
            tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
            created_at: new Date().toISOString(),
          };
          appendMessage(aiMsg);
          // 后台静默同步真实 ID（不触发 loading，不驱动滚动）
          refetch().catch(() => { /* 静默失败 */ });
        }
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setIsSending(false);
      setStreamingContent("");
      setStreamingThinking("");
      setStreamingToolCalls([]);
      setStreamingError(msg);
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
        background: "transparent",
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

      {/* 消息列表（智能吸底滚动 + Markdown 渲染 + 代码块折叠）+ 对话大纲悬浮导航 */}
      <div style={{
        position: "relative",
        flex: 1,
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
      }}>
        <MessageList
          messages={messages}
          streamingContent={streamingContent}
          streamingThinking={streamingThinking}
          streamingToolCalls={streamingToolCalls}
          streamingError={streamingError}
          isStreaming={isSending}
          currentAgent={currentAgentView}
          onQuote={handleQuote}
          onRegenerate={handleRegenerate}
          onRetry={handleRetry}
          onEdit={handleEdit}
          onActiveUserMessageChange={setActiveUserMessageId}
          scrollPersistenceKey={chatId ? `mfk_chat_scroll_${chatId}` : undefined}
        />
        <MessageOutline messages={messages} activeUserMessageId={activeUserMessageId} />
      </div>

      {/* 输入区域 - Floating Dock 贴底（透明背景，仅卡片悬浮） */}
      <div style={{
        flexShrink: 0,
        background: "transparent",
      }}>
        <ChatComposer
          value={input}
          onChange={setInput}
          onSend={handleSend}
          isSending={isSending}
          placeholder={t("chat.inputPlaceholder")}
          textareaRef={chatInputRef}
          draftKey={chatId ? `mfk_draft_${chatId}` : undefined}
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
          mode={mode}
          onModeChange={(m) => {
            setMode(m);
            if (chatId) {
              updateChat(chatId, { mode: m }).catch((err) =>
                console.error("Failed to persist mode:", err)
              );
            }
          }}
          onUploadFile={handleUploadFile}
          onSelectDirectory={handleSelectDirectory}
          onClearContext={handleClearContext}
          hasContext={contextFiles.length > 0}
          files={contextFiles}
          onRemoveFile={removeContextFile}
          projectName={currentProject?.name || null}
        />
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
