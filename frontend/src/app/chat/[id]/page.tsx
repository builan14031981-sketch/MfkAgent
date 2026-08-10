"use client";

import { useState, useEffect, useRef, useCallback, useMemo, Suspense } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { useAgents } from "@/hooks/useAgents";
import { useModels, Model } from "@/hooks/useModels";
import { useProjects } from "@/hooks/useProjects";
import { useChat } from "@/hooks/useChat";
import { useMessages } from "@/hooks/useMessages";
import type { Message } from "@/hooks/useMessages";
import { uploadAttachment } from "@/hooks/useMessages";
import { useChatStream } from "@/hooks/useChatStream";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";
import { usePreferences } from "@/hooks/usePreferences";
import { useProviderConfig } from "@/hooks/useProviderConfig";
import { compressMessages } from "@/lib/api";
import { ProjectContextPanel } from "@/components/panels/ProjectContextPanel";
import { FileDropZone } from "@/components/FileDropZone";
import type { DroppedFile, Attachment } from "@/components/FileDropZone";
import { fileToAttachment, droppedFileToAttachment, mergeAttachments, toProjectRelative } from "@/components/FileDropZone";
import { ChatComposer } from "@/components/ChatComposer";
import type { ChatMode } from "@/components/ChatInput";
import type { PermissionMode } from "@/components/chat-input/PermissionSelector";
import { MessageList } from "@/components/MessageList";
import { MessageOutline } from "@/components/MessageOutline";
import { ChatHeader } from "@/components/ChatHeader";
import { AgentStatusCard } from "@/components/AgentStatusCard";

// 静态导出：动态路由需在 [id]/layout.tsx 提供 generateStaticParams（占位参数）。
export default function ChatPage() {
  return (
    <Suspense fallback={null}>
      <ChatPageInner />
    </Suspense>
  );
}

function ChatPageInner() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const chatId = params.id ? Number(params.id) : null;
  const { t } = useTranslation();

  const [input, setInput] = useState("");
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const [personalityLevel, setPersonalityLevel] = useState(50);
  const [personalityInitForChatId, setPersonalityInitForChatId] = useState<number | null>(null);

  const { agents } = useAgents();
  const { models } = useModels();
  // 三层漏斗过滤：Provider 总开关 → API Key 检查 → 模型白名单（按 provider 独立）
  // 兜底：过滤后为空时显示全部，避免首屏空白或老用户升级后模型消失
  const providerConfig = useProviderConfig();
  const visibleModels = useMemo(() => {
    const loaded = !providerConfig.loading && providerConfig.settings != null;
    if (!loaded) return models;
    const filtered = models.filter((m) => {
      // 第1层：Provider 总开关（禁用则隐藏该 provider 下所有模型）
      if (providerConfig.isProviderDisabled(m.provider)) return false;
      // 第2层：API Key 检查（未配置 Key 则隐藏）
      if (!providerConfig.hasProviderKey(m.provider)) return false;
      // 第3层：模型白名单（按 provider 独立判断；空列表=全部可见）
      const providerEnabled = providerConfig.getEnabled(m.provider);
      return providerEnabled.length === 0 || providerEnabled.includes(m.id);
    });
    return filtered.length > 0 ? filtered : models;
  }, [models, providerConfig]);
  const { projects, createProject } = useProjects();
  const { chats, updateChat } = useChat();
  const { messages, setMessages, sendMessageStream, deleteMessagesFrom, refetch, appendMessage } = useMessages(chatId);
  const { settings } = useSettingsStore();
  // Phase 1.5：模型/推理强度偏好三级回落（localStorage → /api/settings → 默认 qwen-flash）
  const { modelId: prefModelId, reasoningEffort: prefReasoningEffort, hasLocalReasoning, setModel: setPrefModel, setReasoning: setPrefReasoning } = usePreferences(models, settings);

  const {
    isSending,
    timeline,
    tasks,
    tokenUsage,
    setTokenUsage,
    orbStage,
    streamingError,
    sendStream,
    resolveApproval,
    currentAgentState,
    reasoningActive,
    stop,
  } = useChatStream({ chatId, sendMessageStream, appendMessage, refetch });

  const currentChat = chats.find((c) => c.id === chatId);
  const currentAgent = agents.find((a) => a.id === currentChat?.agent_id);
  // 稳定引用：避免每次 render 新建对象导致 memo(MessageList) 失效
  const currentAgentView = useMemo(
    () => (currentAgent ? { id: currentAgent.id, name: currentAgent.name } : null),
    [currentAgent]
  );
  const currentProject = (currentChat?.project_id ? projects.find(p => p.id === currentChat.project_id) : null) ?? null;
  // 模型优先级：会话内手动选择 > 会话快照 model > 偏好（localStorage→settings→qwen-flash）> 模型列表兜底
  const currentModel = selectedModel || (currentChat?.model ? visibleModels.find(m => m.id === currentChat.model) || models.find(m => m.id === currentChat.model) || null : null) || visibleModels.find(m => m.id === prefModelId) || models.find(m => m.id === prefModelId) || visibleModels[0] || models[0] || null;

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
  const [reasoningInitForChatId, setReasoningInitForChatId] = useState<number | null>(null);
  const [permissionMode, setPermissionMode] = useState<PermissionMode>("strict");
  const [mode, setMode] = useState<ChatMode>("build");
  const [modeInitForChatId, setModeInitForChatId] = useState<number | null>(null);
  const [projectContextOpen, setProjectContextOpen] = useState(false);
  const [activeUserMessageId, setActiveUserMessageId] = useState<number | null>(null);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [contextInitForChatId, setContextInitForChatId] = useState<number | null>(null);
  const [isCompressing, setIsCompressing] = useState(false);

  // 存储 File 对象的映射（attachment.id → File），供发送时读取文件内容拼接 Content 前缀
  const fileMapRef = useRef<Map<string, File>>(new Map());

  // 推理强度初始值：三级回落（localStorage → settings.default_reasoning_effort → none），
  // 会话切换时重置；localStorage 已有偏好或 settings 就绪后再初始化，避免 settings 未加载时过早置 none
  if (reasoningInitForChatId !== chatId && (hasLocalReasoning || settings)) {
    setReasoningInitForChatId(chatId);
    setReasoningEffort(prefReasoningEffort);
  }

  // 上下文文件初始值：读会话快照 currentChat.context_files（首页草稿预挂载时随创建请求一起提交）。
  // 路径列表转为 Attachment（无 size/mime，按扩展名推断 kind）
  if (contextInitForChatId !== chatId && currentChat) {
    setContextInitForChatId(chatId);
    const paths: string[] = currentChat.context_files || [];
    const initialAtts: Attachment[] = paths.map((p) => droppedFileToAttachment({ name: p.split(/[\\/]/).pop() || p, path: p }, currentProject?.path));
    setAttachments(initialAtts);
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

  // 拖入文件：项目内文件直接构造 Attachment，项目外文件走 upload 端点（需已绑定项目）
  // 无项目绑定时：仍然保存 File 对象到 fileMapRef，发送时通过 buildContent 读取内容拼接
  const handleFilesDrop = useCallback(async (files: DroppedFile[]) => {
    if (!chatId) return;
    const newAtts: Attachment[] = [];
    for (const f of files) {
      const relPath = toProjectRelative(f.path, currentProject?.path);
      if (relPath) {
        // 项目内文件：直接构造（后端 context_builder 可安全读取）
        const att = droppedFileToAttachment(f, currentProject?.path);
        if (f.file) fileMapRef.current.set(att.id, f.file);
        newAtts.push(att);
      } else if (f.file && currentProject) {
        // 项目外文件 + 已绑定项目：上传到 .mfkagent/uploads/
        const uploaded = await uploadAttachment(chatId, f.file);
        if (uploaded) {
          fileMapRef.current.set(uploaded.id, f.file);
          newAtts.push(uploaded);
        }
      } else if (f.file && !currentProject) {
        // 无项目：仍然加入附件列表（path 为 null），发送时通过 buildContent 读取 File 内容拼接
        const att = fileToAttachment(f.file, null);
        fileMapRef.current.set(att.id, f.file);
        newAtts.push(att);
      } else if (!currentProject) {
        // 无项目且无 File 对象（如 DroppedFile 无 file 字段）：无法处理
        console.warn("未关联项目，且文件无 File 对象，无法添加附件。请先关联项目再拖入文件。");
      }
    }
    if (newAtts.length > 0) {
      setAttachments((prev) => mergeAttachments(prev, newAtts));
    }
  }, [chatId, currentProject]);

  const removeAttachment = useCallback((id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
    fileMapRef.current.delete(id);
  }, []);

  // 上传按钮/卡片拖拽：项目内文件直接构造，项目外文件走 upload 端点
  // 无项目绑定时：仍然保存 File 对象到 fileMapRef，发送时通过 buildContent 读取内容拼接
  const handleUploadFile = useCallback(async (file: File) => {
    if (!chatId) return;
    const fileWithPath = file as File & { path?: string };
    const absPath = fileWithPath.path || file.name;
    const relPath = toProjectRelative(absPath, currentProject?.path);
    if (relPath) {
      // 项目内文件
      const att = fileToAttachment(file, currentProject?.path);
      fileMapRef.current.set(att.id, file);
      setAttachments((prev) => mergeAttachments(prev, [att]));
    } else {
      // 项目外文件或无项目关联：统一走上传 API（后端已支持无项目关联的全局上传目录）
      const uploaded = await uploadAttachment(chatId, file);
      if (uploaded) {
        fileMapRef.current.set(uploaded.id, file);
        setAttachments((prev) => mergeAttachments(prev, [uploaded]));
      }
    }
  }, [chatId, currentProject]);

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
    setAttachments([]);
    fileMapRef.current.clear();
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
    await sendStream(userMsg.content, { modelId: currentModel?.id, personalityLevel, reasoningEffort, permissionMode, appendUserMessage: false });
  }, [isSending, messages, sendStream, currentModel?.id, personalityLevel, reasoningEffort, permissionMode]);

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
    await sendStream(userMsg.content, { modelId: currentModel?.id, personalityLevel, reasoningEffort, permissionMode, appendUserMessage: false });
  }, [isSending, messages, deleteMessagesFrom, sendStream, currentModel?.id, personalityLevel, reasoningEffort, permissionMode]);

  // 切换会话时重置输入框：避免上一会话的多行内容（引用/编辑/草稿）残留导致 textarea 保持变高
  // render 阶段调整 state（非 effect），符合 React 官方推荐模式
  const prevChatIdRef = useRef<number | null>(null);
  if (prevChatIdRef.current !== chatId) {
    prevChatIdRef.current = chatId;
    setInput("");
  }

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

      // 自动发送消息（复用统一流式管线，携带从 chat.context_files 恢复的 attachments）
      sendStream(userMessage, {
        modelId: currentModel?.id || "qwen-flash",
        personalityLevel,
        reasoningEffort,
        permissionMode,
        attachments,
      });
    }
  }, [searchParams, hasAutoSent, chatId, messages, isSending, sendStream, personalityLevel, reasoningEffort, permissionMode, currentModel?.id, attachments]);

  const handleSend = useCallback(async () => {
    if (!input.trim() || isSending) return;

    const userMessage = input.trim();
    setInput("");
    // 发送后立即清空附件，避免已发送的附件残留在输入框
    setAttachments([]);
    fileMapRef.current.clear();

    // 【调试】打印发送前的 attachments 状态
    console.log("[handleSend] attachments count:", attachments.length);
    if (attachments.length > 0) {
      console.log("[handleSend] attachments:", attachments.map(a => ({ id: a.id, name: a.name, path: a.path, kind: a.kind, hasFile: fileMapRef.current.has(a.id) })));
    } else {
      console.warn("[handleSend] attachments 为空！文件可能未正确添加。");
    }

    // buildContent：读取 text 附件内容，拼接到用户消息前（前端兜底，保障 AI 一定看到文件内容）
    const buildContent = async (content: string): Promise<string> => {
      if (attachments.length === 0) return content;

      const fileMap = fileMapRef.current;
      let prefix = "";
      for (const att of attachments) {
        if (att.kind !== "text") continue;
        const file = fileMap.get(att.id);
        if (file) {
          try {
            const text = await file.text();
            prefix += `[文件: ${att.name}] (${att.path || "未关联项目"})\n${text}\n\n`;
          } catch (err) {
            console.warn(`[handleSend] 读取文件 ${att.name} 失败:`, err);
            prefix += `[文件: ${att.name}] (${att.path || "未关联项目"})\n（无法读取文件内容）\n\n`;
          }
        } else if (att.path) {
          // 无 File 对象但有路径（如 context_files 恢复的附件）：标记路径，依赖后端读取
          prefix += `[文件: ${att.name}] (${att.path})\n（文件内容由后端注入）\n\n`;
        }
      }

      if (prefix) {
        const finalContent = `${prefix}---\n\n${content}`;
        console.log("[handleSend] buildContent 拼接完成，前缀长度:", prefix.length);
        return finalContent;
      }
      return content;
    };

    // 后端 context_builder 已接管附件处理：
    // - text 类：后端主动读取文件内容注入 Prompt 第 ⑨ 层
    // - image 类：后端填入 vision_context（待后端修复 AgentRuntime 传递断裂）
    // - binary 类：后端注入元数据说明
    // 前端 buildContent 作为兜底：即使后端未注入，AI 也能从用户消息中看到文件内容
    await sendStream(userMessage, {
      modelId: currentModel?.id || "qwen-flash",
      personalityLevel,
      reasoningEffort,
      permissionMode,
      buildContent,
      attachments,
    });
  }, [input, isSending, sendStream, currentModel?.id, personalityLevel, reasoningEffort, permissionMode, attachments, currentProject]);

  // 语音意图无缝衔接：语音小球转写成功后自动拉起 Agent 流程
  // 复用 handleSend 同款参数（模型/人格/推理/权限/附件），语音视为一次"语音版发送"
  const handleVoicePrompt = useCallback(async (text: string) => {
    const prompt = text.trim();
    if (!prompt || isSending) return;
    // 清空输入框（ChatInput 已用 onChange 填入文本，这里发送后清空）
    setInput("");
    // 语音发送同样清空已暂存附件（与 handleSend 行为一致）
    const sentAttachments = attachments;
    setAttachments([]);
    fileMapRef.current.clear();

    // buildContent：与 handleSend 一致的 text 附件兜底（语音可能配合已拖入的文件）
    const buildContent = async (content: string): Promise<string> => {
      if (sentAttachments.length === 0) return content;
      const fileMap = fileMapRef.current;
      let prefix = "";
      for (const att of sentAttachments) {
        if (att.kind !== "text") continue;
        const file = fileMap.get(att.id);
        if (file) {
          try {
            const t = await file.text();
            prefix += `[文件: ${att.name}] (${att.path || "未关联项目"})\n${t}\n\n`;
          } catch {
            prefix += `[文件: ${att.name}] (${att.path || "未关联项目"})\n（无法读取文件内容）\n\n`;
          }
        } else if (att.path) {
          prefix += `[文件: ${att.name}] (${att.path})\n（文件内容由后端注入）\n\n`;
        }
      }
      return prefix ? `${prefix}---\n\n${content}` : content;
    };

    await sendStream(prompt, {
      modelId: currentModel?.id || "qwen-flash",
      personalityLevel,
      reasoningEffort,
      permissionMode,
      buildContent,
      attachments: sentAttachments,
    });
  }, [isSending, sendStream, currentModel?.id, personalityLevel, reasoningEffort, permissionMode, attachments]);

  // 模型切换：本地选中 + 持久化到会话快照 + 同步到偏好（localStorage）
  const handleModelChange = useCallback((id: string) => {
    const model = models.find((m) => m.id === id);
    if (model) {
      setSelectedModel(model);
      setPrefModel(id);
      if (chatId) {
        updateChat(chatId, { model: model.id }).catch((err) =>
          console.error("Failed to persist model:", err)
        );
      }
    }
  }, [models, chatId, updateChat, setPrefModel]);

  // 工作模式切换：本地选中 + 持久化到会话快照
  const handleModeChange = useCallback((m: ChatMode) => {
    setMode(m);
    if (chatId) {
      updateChat(chatId, { mode: m }).catch((err) =>
        console.error("Failed to persist mode:", err)
      );
    }
  }, [chatId, updateChat]);

  // 压缩会话：G6-B 压缩引擎 — 将冗长历史提炼为摘要
  // 注意：useCallback 必须在 if(!chatId) early return 之前，否则违反 rules-of-hooks
  const handleCompress = useCallback(async () => {
    if (!chatId || isCompressing) return;
    setIsCompressing(true);
    try {
      const result = await compressMessages(chatId, 4);
      if (result.compressed) {
        setMessages(result.messages as Message[]);
        setTokenUsage(null);
      }
    } catch (err) {
      console.error("Compression failed:", err);
    } finally {
      setIsCompressing(false);
    }
  }, [chatId, isCompressing, setMessages, setTokenUsage]);

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
      {/* 聊天头部（memo：流式期间跳过重渲染） */}
      <ChatHeader
        chat={currentChat}
        agent={currentAgent}
        project={currentProject}
        streamingStage={orbStage}
        tokenUsage={tokenUsage}
        onCompress={handleCompress}
        isCompressing={isCompressing}
        isEditingTitle={isEditingTitle}
        editTitle={editTitle}
        onEditTitleChange={setEditTitle}
        onStartEditTitle={handleStartEditTitle}
        onSaveTitle={handleSaveTitle}
        onCancelEditTitle={() => setIsEditingTitle(false)}
        onOpenProjectContext={() => setProjectContextOpen((v) => !v)}
      />

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
          timeline={timeline}
          tasks={tasks}
          streamingError={streamingError}
          isStreaming={isSending}
          streamingStage={orbStage}
          reasoningActive={reasoningActive}
          currentAgent={currentAgentView}
          onQuote={handleQuote}
          onRegenerate={handleRegenerate}
          onRetry={handleRetry}
          onEdit={handleEdit}
          onApproveApproval={(id, toolCallId) => resolveApproval(id, "approve", toolCallId)}
          onDenyApproval={(id, toolCallId) => resolveApproval(id, "deny", toolCallId)}
          onActiveUserMessageChange={setActiveUserMessageId}
          scrollPersistenceKey={chatId ? `mfk_chat_scroll_${chatId}` : undefined}
        />
        <MessageOutline messages={messages} activeUserMessageId={activeUserMessageId} />
      </div>

      {/* 动态 Agent 状态名片：仅 currentAgentState 非 null 时渲染（输入框上方专属区域） */}
      <AgentStatusCard state={currentAgentState} />

      {/* 输入区域 - Floating Dock 贴底（透明背景，仅卡片悬浮） */}
      <div style={{
        flexShrink: 0,
        background: "transparent",
      }}>
        <ChatComposer
          value={input}
          onChange={setInput}
          onSend={handleSend}
          onStop={stop}
          isSending={isSending}
          placeholder={t("chat.inputPlaceholder")}
          textareaRef={chatInputRef}
          draftKey={chatId ? `mfk_draft_${chatId}` : undefined}
          models={visibleModels}
          modelId={currentModel?.id || null}
          onModelChange={handleModelChange}
          reasoningEffort={reasoningEffort}
          onReasoningChange={(e) => {
            setReasoningEffort(e);
            setPrefReasoning(e);
          }}
          permissionMode={permissionMode}
          onPermissionChange={setPermissionMode}
          mode={mode}
          onModeChange={handleModeChange}
          onUploadFile={handleUploadFile}
          onSelectDirectory={handleSelectDirectory}
          onClearContext={handleClearContext}
          hasContext={attachments.length > 0}
          files={[]}
          onRemoveFile={() => {}}
          projectName={currentProject?.name || null}
          attachments={attachments}
          onRemoveAttachment={removeAttachment}
          onVoicePrompt={handleVoicePrompt}
        />
      </div>

      {/* 全屏文件拖拽感知 */}
      <FileDropZone onFilesDrop={handleFilesDrop} />

      {/* Project Context Panel */}
      <ProjectContextPanel
        isOpen={projectContextOpen}
        onClose={() => setProjectContextOpen(false)}
        project={currentProject}
        selectedFiles={attachments.map((a) => a.path || a.name)}
        onToggleFile={(path) => {
          setAttachments((prev) => {
            const exists = prev.some((a) => (a.path || a.name) === path);
            if (exists) return prev.filter((a) => (a.path || a.name) !== path);
            return mergeAttachments(prev, [droppedFileToAttachment({ name: path.split(/[\\/]/).pop() || path, path }, currentProject?.path)]);
          });
        }}
        onClearFiles={() => setAttachments([])}
      />
    </>
  );
}
