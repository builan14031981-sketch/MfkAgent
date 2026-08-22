"use client";

import { useState, useCallback, useEffect, useRef, startTransition } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { useAgents, triggerAgentsRefresh } from "@/hooks/useAgents";
import { useModels, Model, triggerModelsRefresh } from "@/hooks/useModels";
import { useVisibleModels } from "@/hooks/useVisibleModels";
import { useSettingsStore } from "@/lib/store";
import { useTranslation } from "@/hooks/useTranslation";
import { ChatInput } from "@/components/ChatInput";
import { AgentSelector } from "@/components/chat-input/AgentSelector";
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
 *
 * 数据同步契约（V77 修复）：
 * - 弹窗打开瞬间（project 从 null → 非 null）主动触发 triggerModelsRefresh
 *   + triggerAgentsRefresh，保证下拉里的列表是当下最新的。
 * - 监听 models / agents 变化：当前 selectedModel/agentId 若已不在最新列表
 *   里（被禁用/删除），自动置空让 fallback 链 (default → models[0]) 兜底，
 *   不会让用户看到一个指向不存在 model 的"幽灵选中"。
 * - Agent 选择只展示 status === "active" 的，与设置页 AiBasic 对齐。
 */
export function ProjectInitModal({ project, onClose, onCreated }: ProjectInitModalProps) {
  const router = useRouter();
  const { t } = useTranslation();
  const { createChat } = useChat();
  const { agents } = useAgents();
  const { models } = useModels();
  // 2026-08-11 接入 useVisibleModels：和聊天页/首页/设置默认模型下拉用同一份可见模型，
  // 避免用户在 ModelConfigSection 移出候选池后，此弹窗下拉仍能选到。
  const visibleModels = useVisibleModels(models);
  const { settings } = useSettingsStore();

  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [agentId, setAgentId] = useState<string | null>(() => settings?.default_agent || null);
  const [selectedModel, setSelectedModel] = useState<Model | null>(() => {
    const def = settings?.default_model;
    return def ? models.find(m => m.id === def) || null : null;
  });
  const [reasoningEffort, setReasoningEffort] = useState<"none" | "high" | "max">(() => {
    const def = settings?.default_reasoning_effort;
    return def === "high" || def === "max" ? def : "none";
  });
  const [permissionMode, setPermissionMode] = useState<PermissionMode>(() => {
    const def = settings?.agent_permission_mode;
    return def === "safe" || def === "standard" || def === "autonomous" ? def : "standard";
  });
  const [mode, setMode] = useState<"build" | "plan">("build");
  const [files, setFiles] = useState<string[]>([]);
  // 2026-08-11：Agent 选择器上提到标题行（会话创建后不可更改，与工具栏可改参数语义分离）
  const [agentOpen, setAgentOpen] = useState(false);

  const handleAttachFile = useCallback((file: File) => {
    const fileWithPath = file as File & { path?: string };
    const path = fileWithPath.path || file.name;
    setFiles((prev) => (prev.includes(path) ? prev : [...prev, path]));
  }, []);

  const projectId = project?.id;

  // ── 弹窗打开瞬间（project 从 null → 非 null）主动拉取最新数据 ──
  // 解决：在 settings 里改了 enabled_models / provider_disabled / agent 状态后，
  // 立即点击"新建项目"，弹窗仍展示旧数据的"幽灵选中"问题。
  const prevProjectIdRef = useRef<number | null>(null);
  useEffect(() => {
    const currentId = project?.id ?? null;
    const wasClosed = prevProjectIdRef.current === null;
    const isNowOpen = currentId !== null;
    if (wasClosed && isNowOpen) {
      // 弹窗刚打开：触发全局刷新（去抖交给底层 hook）
      triggerModelsRefresh();
      triggerAgentsRefresh();
    }
    prevProjectIdRef.current = currentId;
  }, [project?.id]);

  // ── selectedModel 失效回退 ──
  // 当 visibleModels 列表刷新后，若当前 selectedModel 已不在新列表里（被禁用/删除），
  // 置空让 (default_model → visibleModels[0]) fallback 链兜底。
  // 2026-08-11：改为监听 visibleModels，与下拉可见性保持一致
  useEffect(() => {
    if (selectedModel && !visibleModels.find((m) => m.id === selectedModel.id)) {
      setSelectedModel(null);
    }
  }, [visibleModels, selectedModel]);

  // ── agentId 失效回退 ──
  // 同上：当前选中的 agent 若已不在 active 列表里，置空让 fallback 兜底。
  // 只在弹窗打开期间生效（project 非 null），避免空跑。
  useEffect(() => {
    if (!project) return;
    if (!agentId) return;
    if (!agents.find((a) => a.id === agentId)) {
      setAgentId(null);
    }
  }, [agents, agentId, project]);

  // 内联过滤 active agents：与设置页 AiBasic.getSortedActiveAgents 对齐
  const activeAgents = agents.filter((a) => a.status === "active");

  const handleSend = useCallback(async () => {
    if (!input.trim() || isSending) return;
    const userMessage = input.trim();
    setIsSending(true);
    setInput("");
    try {
      const chat = await createChat(
        agentId || settings?.default_agent || activeAgents[0]?.id || "general",
        userMessage.slice(0, 50) || "New Chat",
        projectId,
        (selectedModel || (settings?.default_model ? visibleModels.find(m => m.id === settings.default_model) || null : null) || visibleModels[0] || null)?.id || null,
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
  }, [input, isSending, agentId, settings, activeAgents, selectedModel, visibleModels, projectId, files, mode, createChat, onCreated, onClose, router]);

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
        agentId || settings?.default_agent || activeAgents[0]?.id || "general",
        t("chat.projectInitDefaultTitle", { name: project.name }),
        projectId,
        (selectedModel || (settings?.default_model ? visibleModels.find(m => m.id === settings.default_model) || null : null) || visibleModels[0] || null)?.id || null,
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
  }, [isSending, agentId, settings, activeAgents, selectedModel, visibleModels, projectId, mode, project, createChat, onCreated, onClose, router, t]);

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
        background: "var(--overlay-modal)",
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
          gap: "8px",
          padding: "16px 20px 4px 20px",
        }}>
          <div style={{ minWidth: 0 }}>
            <h2 style={{
              fontSize: "16px",
              fontWeight: "600",
              color: "var(--text-level-1)",
              margin: "0 0 6px 0",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}>📂 {t("chat.projectInitTitle", { name: project.name })}</h2>
            <p style={{
              fontSize: "13px",
              color: "var(--text-level-3)",
              margin: 0,
            }}>{t("chat.projectInitDesc")}</p>
          </div>
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            flexShrink: 0,
          }}>
            {/* Agent 选择上提标题行：agent 在会话创建时绑定、之后不可更改，
                与工具栏里可随时修改的运行参数（模型/模式/权限）语义分离 */}
            <span title="会话创建后不可更改">
              <AgentSelector
                open={agentOpen}
                onToggle={() => setAgentOpen((o) => !o)}
                onClose={() => setAgentOpen(false)}
                selectedId={agentId || settings?.default_agent || activeAgents[0]?.id || "general"}
                onSelect={(id) => setAgentId(id)}
                hideDescription
              />
            </span>
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
        </div>

        {/* 弹窗内容：内置 ChatInput */}
        <div style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          padding: "4px 20px 12px 20px",
        }}>
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={handleSend}
            isSending={isSending}
            placeholder={t("chat.projectInitPlaceholder")}
            inputMinHeight={64}
            models={visibleModels}
            modelId={(selectedModel || (settings?.default_model ? visibleModels.find(m => m.id === settings.default_model) || null : null) || visibleModels[0] || null)?.id || null}
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
            agentId={agentId || settings?.default_agent || activeAgents[0]?.id || "general"}
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
              padding: "2px 0 0 0",
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
