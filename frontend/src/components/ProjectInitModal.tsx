"use client";

import { useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { useAgents } from "@/hooks/useAgents";
import { useModels, Model } from "@/hooks/useModels";
import { useSettingsStore } from "@/lib/store";
import { useTranslation } from "@/hooks/useTranslation";
import { ChatInput } from "@/components/ChatInput";
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
  const [reasoningEffort, setReasoningEffort] = useState<"none" | "low" | "high">("none");
  const [mode, setMode] = useState<"build" | "plan">("build");
  const [files, setFiles] = useState<string[]>([]);

  const handleAttachFile = useCallback((file: File) => {
    const fileWithPath = file as File & { path?: string };
    const path = fileWithPath.path || file.name;
    setFiles((prev) => (prev.includes(path) ? prev : [...prev, path]));
  }, []);

  // 防空保护：project 缺失或字段不全时直接不渲染，防止崩溃
  if (!project || typeof project.id !== "number" || !project.name) {
    return null;
  }

  const currentAgent = agentId || settings?.default_agent || agents[0]?.id || "general";
  const currentModel = selectedModel || models[0] || null;

  const handleSend = async () => {
    if (!input.trim() || isSending) return;
    const userMessage = input.trim();
    setIsSending(true);
    setInput("");
    try {
      const personality = settings?.default_personality ? Number(settings.default_personality) : 50;
      const chat = await createChat(
        currentAgent,
        userMessage.slice(0, 50) || "New Chat",
        project.id,
        currentModel?.id || settings?.default_model || null,
        personality,
        files,
        mode
      );
      onCreated();
      onClose();
      const encoded = encodeURIComponent(userMessage);
      router.push(`/chat/${chat.id}?message=${encoded}`);
    } catch (err) {
      console.error("Failed to create chat from project init:", err);
      setInput(userMessage);
      setIsSending(false);
    }
  };

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
        background: "rgba(0, 0, 0, 0.4)",
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
        animation: "fadeIn 0.2s ease",
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: "672px",
          display: "flex",
          flexDirection: "column",
          background: "var(--bg-level-2)",
          borderRadius: "var(--radius-2xl)",
          boxShadow: "var(--shadow-lg), 0 0 0 1px var(--border-primary)",
          overflow: "hidden",
          animation: "panelCenterOpen 0.25s ease forwards",
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
        <div style={{ padding: "8px 24px 24px 24px" }}>
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={handleSend}
            isSending={isSending}
            placeholder={t("chat.projectInitPlaceholder")}
            models={models}
            modelId={currentModel?.id || null}
            onModelChange={(id) => {
              const model = models.find(m => m.id === id);
              if (model) setSelectedModel(model);
            }}
            reasoningEffort={reasoningEffort}
            onReasoningChange={setReasoningEffort}
            mode={mode}
            onModeChange={setMode}
            allowAgentChange
            agentId={currentAgent}
            onAgentChange={(id) => setAgentId(id)}
            onUploadFile={handleAttachFile}
            onSelectDirectory={() => {}}
            onClearContext={() => setFiles([])}
            hasContext={files.length > 0}
            files={files}
            onRemoveFile={(path) => setFiles((prev) => prev.filter((p) => p !== path))}
            projectName={project.name}
          />
        </div>
      </div>
    </div>
  );

  // Portal 挂载到 body，隔离事件冒泡，避免触发外层路由/点击
  if (typeof document === "undefined") return null;
  return createPortal(modal, document.body);
}
