"use client";

import { useState, useCallback, startTransition } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { useAgents } from "@/hooks/useAgents";
import { useModels, Model } from "@/hooks/useModels";
import { useSettingsStore } from "@/lib/store";
import { useTranslation } from "@/hooks/useTranslation";
import { ChatInput } from "@/components/ChatInput";
import type { PermissionMode } from "@/components/chat-input/PermissionSelector";
import type { Project } from "@/hooks/useProjects";

interface ProjectInitModalProps {
  project: Project | null;
  onClose: () => void;
  onCreated: () => void;
}

/**
 * 项目初始化向导：项目创建成功后弹出，置顶于全屏正中央。
 * 内置一体化 ChatInput（Agent / 模型 / 思考模式 / 附件），
 * 发送后自动创建会话并无缝跳转至 Chat 页。
 */
export function ProjectInitModal({ project, onClose, onCreated }: ProjectInitModalProps) {
  const router = useRouter();
  const { t } = useTranslation();
  const { createChat } = useChat();
  const { agents } = useAgents();
  const { models } = useModels();
  const { settings } = useSettingsStore();

  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [agentId, setAgentId] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const [reasoningEffort, setReasoningEffort] = useState<"none" | "high" | "max">("none");
  const [permissionMode, setPermissionMode] = useState<PermissionMode>("strict");
  const [mode, setMode] = useState<"build" | "plan">("build");
  const [files, setFiles] = useState<string[]>([]);

  const handleAttachFile = useCallback((file: File) => {
    const fileWithPath = file as File & { path?: string };
    const path = fileWithPath.path || file.name;
    setFiles((prev) => (prev.includes(path) ? prev : [...prev, path]));
  }, []);

  const projectId = project?.id;

  const handleSend = useCallback(async () => {
    if (!input.trim() || isSending) return;
    const userMessage = input.trim();
    setIsSending(true);
    setInput("");
    try {
      const chat = await createChat(
        agentId || settings?.default_agent || agents[0]?.id || "general",
        userMessage.slice(0, 50) || "New Chat",
        projectId,
        (selectedModel || (settings?.default_model ? models.find(m => m.id === settings.default_model) || null : null) || models[0] || null)?.id || null,
        files,
        mode
      );
      // 1. 立即先关闭弹窗并跳转路由（给用户最快的 UI 响应）
      onClose();
      startTransition(() => {
        router.push(`/chat/${chat.id}?message=${encodeURIComponent(userMessage)}`);
      });
      // 2. 将侧边栏刷新逻辑延迟到下一帧，脱离跳转卡顿区
      setTimeout(() => {
        onCreated();
      }, 100);
    } catch (err) {
      console.error("Failed to create chat from project init:", err);
      setInput(userMessage);
      setIsSending(false);
    }
  }, [input, isSending, agentId, settings, agents, selectedModel, models, projectId, files, mode, createChat, onCreated, onClose, router]);

  /**
   * 跳过：创建关联当前 project 的空会话（无 ?message 参数，不触发自动发送），
   * 并跳转至 chat 页。复用 isSending 锁，避免与 handleSend 竞争。
   * 标题采用 i18n 文案 "{name} 的新对话"。
   */
  const handleSkip = useCallback(async () => {
    if (isSending || !project) return;
    setIsSending(true);
    try {
      const chat = await createChat(
        agentId || settings?.default_agent || agents[0]?.id || "general",
        t("chat.projectInitDefaultTitle", { name: project.name }),
        projectId,
        (selectedModel || (settings?.default_model ? models.find(m => m.id === settings.default_model) || null : null) || models[0] || null)?.id || null,
        [],
        mode
      );
      // 1. 立即先关闭弹窗并跳转路由（给用户最快的 UI 响应）
      onClose();
      startTransition(() => {
        router.push(`/chat/${chat.id}`);
      });
      // 2. 将侧边栏刷新逻辑延迟到下一帧，脱离跳转卡顿区
      setTimeout(() => {
        onCreated();
      }, 100);
    } catch (err) {
      console.error("Failed to create chat on skip:", err);
      setIsSending(false);
    }
  }, [isSending, agentId, settings, agents, selectedModel, models, projectId, mode, project, createChat, onCreated, onClose, router, t]);

  // 防空保护：project 缺失或字段不全时直接不渲染，防止崩溃
  if (!project || typeof project.id !== "number" || !project.name) {
    return null;
  }

  const modal = (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
        background: "rgba(0, 0, 0, 0.3)",
        backdropFilter: "blur(2px)",
        WebkitBackdropFilter: "blur(2px)",
        animation: "fadeIn 0.2s ease",
      }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: "672px",
          maxHeight: "calc(100vh - 32px)",
          display: "flex",
          flexDirection: "column",
          background: "var(--bg-level-2)",
          borderRadius: "var(--radius-2xl)",
          boxShadow: "var(--shadow-lg), 0 0 0 1px var(--border-primary)",
          overflow: "hidden",
          animation: "panelOpen 0.25s ease forwards",
          outline: "none",
        }}
      >
        {/* 弹窗头部：标题 + 右上角关闭 */}
        <div style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          padding: "20px 24px 8px 24px",
        }}>
          <div>
            <h2 style={{
              fontSize: "16px",
              fontWeight: "600",
              color: "var(--text-level-1)",
              margin: "0 0 6px 0",
            }}>📂 {t("chat.projectInitTitle", { name: project.name })}</h2>
            <p style={{
              fontSize: "13px",
              color: "var(--text-level-3)",
              margin: 0,
            }}>{t("chat.projectInitDesc")}</p>
          </div>
          <button
            onClick={onClose}
            title={t("common.close")}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "26px",
              height: "26px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              color: "var(--text-level-4)",
              flexShrink: 0,
              outline: "none",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
              e.currentTarget.style.color = "var(--text-level-1)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--text-level-4)";
            }}
          >
            <X style={{ width: "15px", height: "15px" }} />
          </button>
        </div>

        {/* 弹窗内容：内置 ChatInput */}
        <div style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          padding: "8px 24px 24px 24px",
        }}>
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={handleSend}
            isSending={isSending}
            placeholder={t("chat.projectInitPlaceholder")}
            inputMinHeight={97}
            models={models}
            modelId={(selectedModel || (settings?.default_model ? models.find(m => m.id === settings.default_model) || null : null) || models[0] || null)?.id || null}
            onModelChange={(id) => {
              const model = models.find(m => m.id === id);
              if (model) setSelectedModel(model);
            }}
            reasoningEffort={reasoningEffort}
            onReasoningChange={setReasoningEffort}
            permissionMode={permissionMode}
            onPermissionChange={setPermissionMode}
            mode={mode}
            onModeChange={setMode}
            allowAgentChange
            agentId={agentId || settings?.default_agent || agents[0]?.id || "general"}
            onAgentChange={(id) => setAgentId(id)}
            onUploadFile={handleAttachFile}
            onSelectDirectory={() => {}}
            onClearContext={() => setFiles([])}
            hasContext={files.length > 0}
            files={files}
            onRemoveFile={(path) => setFiles((prev) => prev.filter((p) => p !== path))}
            projectName={project.name}
          />
          <button
            onClick={handleSkip}
            disabled={isSending}
            style={{
              display: "block",
              width: "100%",
              padding: "6px 0 2px 0",
              border: "none",
              background: "transparent",
              cursor: isSending ? "not-allowed" : "pointer",
              fontSize: "12px",
              color: "var(--text-level-4)",
              textAlign: "center",
              outline: "none",
              opacity: isSending ? 0.5 : 1,
            }}
            onMouseEnter={(e) => { if (!isSending) e.currentTarget.style.color = "var(--text-level-2)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-level-4)"; }}
          >
            {t("chat.projectInitSkip")}
          </button>
        </div>
      </div>
    </div>
  );

  // Portal 挂载到 body，隔离事件冒泡，避免触发外层路由/点击
  if (typeof document === "undefined") return null;
  return createPortal(modal, document.body);
}
