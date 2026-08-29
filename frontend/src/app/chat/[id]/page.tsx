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
import { useStreamStore } from "@/lib/streamStore";
import { useTabStore } from "@/lib/tabStore";
import { usePreferences } from "@/hooks/usePreferences";
import { useVisibleModels } from "@/hooks/useVisibleModels";
import { compressMessages, apiDelete } from "@/lib/api";
import { useArtifactStore, artifactFileName } from "@/lib/artifactStore";
import { ProjectContextPanel } from "@/components/panels/ProjectContextPanel";
import { FileDropZone } from "@/components/FileDropZone";
import type { DroppedFile, Attachment } from "@/components/FileDropZone";
import { fileToAttachment, droppedFileToAttachment, mergeAttachments, toProjectRelative } from "@/components/FileDropZone";
import { ChatComposer } from "@/components/ChatComposer";
import { UserChoiceComposer } from "@/components/UserChoiceComposer";
import type { ChatMode } from "@/components/ChatInput";
import type { PermissionMode } from "@/components/chat-input/PermissionSelector";
import { MessageList } from "@/components/MessageList";
import { MessageOutline } from "@/components/MessageOutline";
import { ChatHeader } from "@/components/ChatHeader";
import { TaskProgressCard } from "@/components/TaskProgressCard";
import { ProjectPathContext } from "@/lib/projectPathContext";
import { useSkills, SkillInfo } from "@/hooks/useSkills";
import { selectDirectory } from "@/lib/selectDirectory";

// 2026-08-11：项目上下文面板开关态持久化 key（与侧边栏 mfk_sidebar_collapsed 同一模式）
const PROJECT_CONTEXT_OPEN_KEY = "mfk_project_context_open";

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
  const { skills: allSkills } = useSkills();
  // 会话级 Skill：只在当前会话生效，刷新即失效（不写入全局 enabled，不污染其他会话）
  const [sessionSkills, setSessionSkills] = useState<SkillInfo[]>([]);
  const { models } = useModels();
  // 三层漏斗过滤：Provider 总开关 → API Key 检查 → 模型白名单（按 provider 独立）
  // 抽到 useVisibleModels hook 统一 4 个入口行为（2026-08-11）
  // 兜底：过滤后为空时显示全部，避免首屏空白或老用户升级后模型消失
  const visibleModels = useVisibleModels(models);
  const { projects, createProject } = useProjects();
  const { chats, createChat, updateChat } = useChat();
  const { messages, setMessages, sendMessageStream, deleteMessagesFrom, refetch, appendMessage, invalidateMessagesCache } = useMessages(chatId);
  const { settings } = useSettingsStore();
  // Phase 1.5：模型/推理强度偏好三级回落（localStorage → /api/settings → 默认 qwen-flash）
  const { modelId: prefModelId, reasoningEffort: prefReasoningEffort, hasLocalReasoning, prefsLoaded, setModel: setPrefModel, setReasoning: setPrefReasoning } = usePreferences(models, settings);

  // 当前会话关联的 Agent / 项目（产出物收集需 projectPath 反查 projectId，故在 useChatStream 前解析）
  const currentChat = chats.find((c) => c.id === chatId);
  const currentAgent = agents.find((a) => a.id === currentChat?.agent_id);
  const currentProject = (currentChat?.project_id ? projects.find(p => p.id === currentChat.project_id) : null) ?? null;

  // 当前圆桌参会 Agent 席位列表（供输入框 @mention 优先联想展示）
  const roundtableAttendees = useMemo(() => {
    if (!currentChat || currentChat.mode !== "roundtable" || !currentChat.roundtable_config) {
      return undefined;
    }
    const config = currentChat.roundtable_config;
    const agentIds: string[] = [];
    if (Array.isArray(config.agent_ids)) {
      agentIds.push(...config.agent_ids);
    }
    if (agentIds.length === 0) return undefined;
    const attendeeSet = new Set(agentIds);
    return agents.filter((a) => attendeeSet.has(a.id));
  }, [currentChat, agents]);

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
  } = useChatStream({ chatId, sendMessageStream, appendMessage, refetch, projectPath: currentProject?.path ?? null });

  // 全局活跃会话同步：后台流结束时的通知判定依赖它（组件卸载→置 null，
  // 修复“离开聊天页后 ref 冻结导致永远不弹通知”的缺陷）
  useEffect(() => {
    if (chatId == null) return;
    useStreamStore.getState().setActiveChatId(chatId);
    return () => {
      useStreamStore.getState().setActiveChatId(null);
    };
  }, [chatId]);

  // 从 URL skills 参数恢复会话级 Skill：首页选中后随 ?skills=[...] 带给新会话
  useEffect(() => {
    if (allSkills.length === 0 || chatId == null) return;
    try {
      const raw = searchParams.get("skills");
      if (!raw) return;
      const ids: string[] = JSON.parse(raw);
      if (!Array.isArray(ids)) return;
      setSessionSkills((prev) => {
        const existing = new Set(prev.map((s) => s.id));
        const toAdd = allSkills.filter((s) => ids.includes(s.id) && !existing.has(s.id));
        return toAdd.length ? [...prev, ...toAdd] : prev;
      });
    } catch {
      /* 非法 JSON 忽略 */
    }
    // 只在挂载时读一次，避免搜索参数变化时反复触发
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allSkills, chatId]);

  // 稳定引用：避免每次 render 新建对象导致 memo(MessageList) 失效
  const currentAgentView = useMemo(
    () => (currentAgent ? { id: currentAgent.id, name: currentAgent.name } : null),
    [currentAgent]
  );
  // 发送模型：本次页面内临时选择 > 会话快照 model（原样透传，查不到列表也不放弃、不兜底）；
  // 未绑定则为 null，交给后端 settings.default_model 决定。绝不参与偏好/列表首项兜底，
  // 防止"用户选的模型被静默替换"（2026-08-14 根治）。
  const sendModelId = selectedModel?.id ?? currentChat?.model ?? null;
  // 下拉显示模型：仅影响 UI 高亮，永不进入发送。优先级：临时选择 > 会话快照 > 全局默认 > 偏好 > 可见列表首项。
  const displayModel = selectedModel
    ?? (currentChat?.model ? visibleModels.find(m => m.id === currentChat.model) ?? null : null)
    ?? (settings?.default_model ? visibleModels.find(m => m.id === settings.default_model) ?? null : null)
    ?? visibleModels.find(m => m.id === prefModelId)
    ?? visibleModels[0]
    ?? null;

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
  const [permissionMode, setPermissionMode] = useState<PermissionMode>("standard");
  const [permissionInitForChatId, setPermissionInitForChatId] = useState<number | null>(null);
  const [mode, setMode] = useState<ChatMode>("build");
  const [modeInitForChatId, setModeInitForChatId] = useState<number | null>(null);
  const [projectContextOpen, setProjectContextOpenState] = useState(false);
  // 2026-08-11：项目上下文面板开关态持久化（此前纯内存，刷新即关）
  useEffect(() => {
    try {
      setProjectContextOpenState(window.localStorage.getItem(PROJECT_CONTEXT_OPEN_KEY) === "1");
    } catch { /* localStorage 不可用时保持关闭 */ }
  }, []);
  const setProjectContextOpen = useCallback(
    (updater: boolean | ((prev: boolean) => boolean)) => {
      setProjectContextOpenState((prev) => {
        const next = typeof updater === "function" ? updater(prev) : updater;
        try { window.localStorage.setItem(PROJECT_CONTEXT_OPEN_KEY, next ? "1" : "0"); } catch { /* noop */ }
        return next;
      });
    },
    []
  );
  const [activeUserMessageId, setActiveUserMessageId] = useState<number | null>(null);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [contextInitForChatId, setContextInitForChatId] = useState<number | null>(null);
  const [isCompressing, setIsCompressing] = useState(false);

  // 当前需要抉择的请求（最新一条未解决的 user_choice），用于"无感替换输入框"
  const activeChoice = useMemo(() => {
    const session = chatId != null ? useStreamStore.getState().sessions[chatId] : undefined;
    if (!session) return null;
    for (let i = session.timeline.length - 1; i >= 0; i--) {
      const seg = session.timeline[i];
      if (seg.type === "user_choice" && seg.choice.resolvedAction == null) {
        return seg.choice;
      }
    }
    return null;
  }, [chatId, timeline]);

  // 存储 File 对象的映射（attachment.id → File），供发送时读取文件内容拼接 Content 前缀
  const fileMapRef = useRef<Map<string, File>>(new Map());

  // 推理强度初始值：三级回落（localStorage → settings.default_reasoning_effort → none），
  // 会话切换时重置；本地偏好读取完成（prefsLoaded）或 settings 就绪后再初始化，避免 settings 未加载时过早置 none
  if (reasoningInitForChatId !== chatId && (prefsLoaded || hasLocalReasoning || settings)) {
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

  // 权限模式初始值：读会话快照 currentChat.permission_mode（会话级，无全局默认），切换会话时重置
  if (permissionInitForChatId !== chatId && currentChat) {
    setPermissionInitForChatId(chatId);
    const mode = currentChat.permission_mode;
    setPermissionMode(mode === "safe" || mode === "standard" || mode === "autonomous" ? mode : "standard");
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

  // 右上角「关联项目」胶囊：直接打开目录选择器（不经过加号菜单）
  const handleOpenDirectoryPicker = useCallback(async () => {
    const dir = await selectDirectory();
    if (dir) await handleSelectDirectory(dir);
  }, [handleSelectDirectory]);

  // 关联已有项目：直接从已注册列表中选择
  const handleSelectExistingProject = useCallback(async (projectId: number) => {
    if (!chatId) return;
    try {
      await updateChat(chatId, { project_id: projectId });
    } catch (err) {
      console.error("Failed to link existing project:", err);
    }
  }, [chatId, updateChat]);

  // 切换项目（ChatHeader 下拉）
  const handleSwitchProject = useCallback(async (projectId: number) => {
    if (!chatId) return;
    try {
      await updateChat(chatId, { project_id: projectId });
      // 切换后清空附件（旧项目上下文文件不再适用）
      setAttachments([]);
      fileMapRef.current.clear();
    } catch (err) {
      console.error("Failed to switch project:", err);
    }
  }, [chatId, updateChat]);

  // 解绑项目
  const handleUnbindProject = useCallback(async () => {
    if (!chatId) return;
    try {
      await updateChat(chatId, { unbind_project: true });
      setAttachments([]);
      fileMapRef.current.clear();
    } catch (err) {
      console.error("Failed to unbind project:", err);
    }
  }, [chatId, updateChat]);

  // 清除上下文：真实清空当前会话的对话历史（含会话级 Skill），并清附件
  const handleClearContext = useCallback(async () => {
    if (!chatId) return;
    try {
      await apiDelete(`/api/v1/chat/${chatId}/messages`);
    } catch (err) {
      console.error("Failed to clear chat history:", err);
    }
    setMessages([]);
    invalidateMessagesCache();
    setSessionSkills([]);
    setAttachments([]);
    fileMapRef.current.clear();
  }, [chatId, setMessages, invalidateMessagesCache]);

  // 会话级启用 Skill：把其 prompt 说明书作为文档喂给当前会话（不写全局 enabled）
  const handleApplySkill = useCallback((skill: SkillInfo) => {
    setSessionSkills((prev) => (prev.some((s) => s.id === skill.id) ? prev : [...prev, skill]));
  }, []);

  // 移除某个会话级 Skill
  const handleRemoveSkill = useCallback((skillId: string) => {
    setSessionSkills((prev) => prev.filter((s) => s.id !== skillId));
  }, []);

  // 粘贴剪贴板：文本追加到输入框；图片作为附件上传（复用 onUploadFile 需 File，故走文件流）
  const handlePasteClipboard = useCallback(async () => {
    try {
      if (!navigator.clipboard) {
        setInput((v) => v + (v ? "\n" : "") + "[系统] 当前环境不支持剪贴板读取");
        return;
      }
      const items = await navigator.clipboard.read();
      for (const item of items) {
        const imgType = item.types.find((t) => t.startsWith("image/"));
        if (imgType) {
          const blob = await item.getType(imgType);
          const file = new File([blob], `clipboard-${Date.now()}.png`, { type: imgType });
          handleUploadFile(file);
          return;
        }
      }
      const text = await navigator.clipboard.readText();
      if (text) setInput((v) => v + (v ? "\n" : "") + text);
    } catch (err) {
      console.warn("[handlePasteClipboard] 读取剪贴板失败:", err);
    }
  }, [handleUploadFile]);

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
    await sendStream(userMsg.content, { modelId: sendModelId, personalityLevel, reasoningEffort, permissionMode, appendUserMessage: false });
  }, [isSending, messages, sendStream, sendModelId, personalityLevel, reasoningEffort, permissionMode]);

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
    await sendStream(userMsg.content, { modelId: sendModelId, personalityLevel, reasoningEffort, permissionMode, appendUserMessage: false });
  }, [isSending, messages, deleteMessagesFrom, sendStream, sendModelId, personalityLevel, reasoningEffort, permissionMode]);

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

      // 从 URL 参数恢复从首页随新建会话传递的附件（如屏幕截图）
      const attachmentsParam = searchParams.get("attachments");
      let urlAttachments = attachments;
      if (attachmentsParam) {
        try {
          const parsed = JSON.parse(decodeURIComponent(attachmentsParam));
          if (Array.isArray(parsed) && parsed.length > 0) {
            urlAttachments = parsed;
            setAttachments(parsed);
          }
        } catch (e) {
          console.warn("Failed to parse attachments from URL param:", e);
        }
      }

      // 清除URL参数
      const newUrl = `/chat/${chatId}`;
      window.history.replaceState({}, "", newUrl);

      // 自动发送消息（复用统一流式管线，携带 attachments）
      sendStream(userMessage, {
        modelId: sendModelId,
        personalityLevel,
        reasoningEffort,
        permissionMode,
        attachments: urlAttachments,
      });
    }
  }, [searchParams, hasAutoSent, chatId, messages, isSending, sendStream, personalityLevel, reasoningEffort, permissionMode, sendModelId, attachments]);

  const handleSend = useCallback(async (screenshots?: Array<{ id: string; dataUrl: string; file: File }>) => {
    // 允许只发文字、只发附件、或只发截图
    if ((!input.trim() && attachments.length === 0 && (!screenshots || screenshots.length === 0)) || isSending) return;

    const userMessage = input.trim() || "[图片]";

    // 收集所有附件：已有附件 + 截图附件（手动收集，不依赖 React 异步状态更新）
    const sentAttachments = [...attachments];
    const sentFileMap = new Map(fileMapRef.current);

    // 上传截图并加到 sentAttachments（直接调用 uploadAttachment，确保附件对象被收集）
    if (screenshots && screenshots.length > 0 && chatId) {
      for (const item of screenshots) {
        try {
          const uploaded = await uploadAttachment(chatId, item.file);
          if (uploaded) {
            sentAttachments.push(uploaded);
            sentFileMap.set(uploaded.id, item.file);
          }
        } catch (err) {
          console.error("[Screenshot] upload failed in handleSend:", err);
        }
      }
    }

    // 上传完成后再清空输入框和附件，避免重新渲染干扰 fetch
    setInput("");
    setAttachments([]);
    fileMapRef.current.clear();

    // buildContent：读取 text 附件内容 + 会话级 Skill 说明书，拼接到用户消息前
    const buildContent = async (content: string): Promise<string> => {
      let prefix = "";

      // 会话级 Skill：把启用 Skill 的说明书作为【强制行为契约】喂给当前会话（只在本会话生效）
      if (sessionSkills.length > 0) {
        const skillSection = sessionSkills
          .map((s) => `<skill name="${s.name}">\n${s.prompt ?? s.description}\n</skill>`)
          .join("\n\n");
        prefix += (
          `【本会话已启用 Skill 行为契约】\n` +
          `以下 Skill 是当前会话的【强制执行规范】，不是参考文档。处理用户请求时必须逐条严格遵循，` +
          `包括其中的输出格式、必含字段、禁止项与自查清单。若 Skill 要求输出某字段/清单/对照表，` +
          `缺一项即视为未完成任务，必须补齐后再交付。\n\n` +
          `${skillSection}\n\n---\n\n`
        );
      }

      if (sentAttachments.length === 0) return prefix ? `${prefix}${content}` : content;

      for (const att of sentAttachments) {
        if (att.kind !== "text") continue;
        const file = sentFileMap.get(att.id);
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
        return `${prefix}---\n\n${content}`;
      }
      return content;
    };

    // 后端 context_builder 已接管附件处理：
    // - text 类：后端主动读取文件内容注入 Prompt 第 ⑨ 层
    // - image 类：后端填入 vision_context（待后端修复 AgentRuntime 传递断裂）
    // - binary 类：后端注入元数据说明
    // 前端 buildContent 作为兜底：即使后端未注入，AI 也能从用户消息中看到文件内容
    await sendStream(userMessage, {
      modelId: sendModelId,
      personalityLevel,
      reasoningEffort,
      permissionMode,
      buildContent,
      attachments: sentAttachments,
    });
  }, [input, isSending, sendStream, sendModelId, personalityLevel, reasoningEffort, permissionMode, attachments, sessionSkills, chatId]);

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
        invalidateMessagesCache(); // 压缩后缓存已变化，失效旧缓存
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
              color: "var(--text-on-primary)",
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
    const newTitle = editTitle.trim();
    try {
      await updateChat(chatId, { title: newTitle });
      useTabStore.getState().updateTabTitle(chatId, newTitle);
      setIsEditingTitle(false);
    } catch (err) {
      console.error("Failed to update title:", err);
    }
  };

  // 浏览器式多标签：进入对话自动入驻顶部 TabBar 并激活
  useEffect(() => {
    if (chatId) {
      useTabStore.getState().openTab({
        chatId,
        title: currentChat?.title || "新对话",
        agentId: currentAgent?.id || currentChat?.agent_id,
        projectId: currentProject?.id ?? currentChat?.project_id ?? null,
      });
    }
  }, [chatId, currentChat?.title, currentChat?.agent_id, currentChat?.project_id, currentAgent?.id, currentProject?.id]);

  // 新建对话（聊天头部 + 按钮 + 快捷键联动）
  const handleNewChat = useCallback(async () => {
    const agent = currentAgent || agents[0];
    if (!agent) {
      router.push("/");
      return;
    }
    try {
      const chat = await createChat(
        agent.id,
        "新对话",
        currentProject?.id ?? null,
        selectedModel?.id || settings?.default_model || null,
        [],
        currentChat?.mode || "build",
        currentChat?.permission_mode || "standard"
      );
      router.push(`/chat/${chat.id}`);
    } catch (err) {
      console.error("Failed to create chat:", err);
    }
  }, [currentAgent, agents, currentProject, selectedModel, settings, currentChat, createChat, router]);

  return (
    <ProjectPathContext.Provider value={currentChat?.project_path ?? currentProject?.path ?? null}>
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
        projects={projects}
        onSwitchProject={handleSwitchProject}
        onUnbindProject={handleUnbindProject}
        onSelectDirectory={handleOpenDirectoryPicker}
        onNewChat={handleNewChat}
      />

      {/* 消息列表（智能吸底滚动 + Markdown 渲染 + 代码块折叠）+ 对话大纲悬浮导航 */}
      <div data-zoomable="message-list" style={{
        position: "relative",
        flex: 1,
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
      }}>
        <MessageList
          messages={messages}
          timeline={timeline}
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

      {/* 多 Agent 任务进度面板：输入框上方，与 ChatComposer 等宽对齐，两侧各留 100px 空隙（不顶满；移动端 mf-x-100 收紧为 12px） */}
      <div className="mf-x-100" style={{ maxWidth: "1400px", margin: "0 auto", width: "100%" }}>
        <TaskProgressCard tasks={tasks ?? []} chatId={chatId} live={isSending} />
      </div>

      {/* 输入区域 - Floating Dock 贴底（透明背景，仅卡片悬浮）
          有看待抉择请求时，输入框整体被选择框替换（无感，不打断）
          mf-safe-bottom：移动端手势条避让（globals.css ≤768px 生效） */}
      <div data-zoomable="composer" className="mf-safe-bottom" style={{
        flexShrink: 0,
        background: "transparent",
      }}>
        {activeChoice && chatId != null ? (
          <UserChoiceComposer choice={activeChoice} chatId={chatId} />
        ) : (
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
            modelId={displayModel?.id || null}
            onModelChange={handleModelChange}
            reasoningEffort={reasoningEffort}
            onReasoningChange={(e) => {
              setReasoningEffort(e);
              setPrefReasoning(e);
            }}
            permissionMode={permissionMode}
            onPermissionChange={(mode) => {
              setPermissionMode(mode);
              if (chatId != null) {
                updateChat(chatId, { permission_mode: mode }).catch((err) =>
                  console.error("Failed to persist permission mode:", err)
                );
              }
            }}
            mode={mode}
            onModeChange={handleModeChange}
            onUploadFile={handleUploadFile}
            onSelectDirectory={handleSelectDirectory}
            onClearContext={handleClearContext}
            hasContext={messages.length > 0 || sessionSkills.length > 0}
            projects={projects}
            onSelectExistingProject={handleSelectExistingProject}
            skills={allSkills}
            onApplySkill={handleApplySkill}
            activeSkillIds={new Set(sessionSkills.map((s) => s.id))}
            onRemoveSkill={handleRemoveSkill}
            onPasteClipboard={handlePasteClipboard}
            files={[]}
            onRemoveFile={() => {}}
            projectName={currentProject?.name || null}
            attachments={attachments}
            onRemoveAttachment={removeAttachment}
            roundtableAttendees={roundtableAttendees}
          />
        )}
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
    </ProjectPathContext.Provider>
  );
}
