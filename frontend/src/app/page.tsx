/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAgents, Agent } from "@/hooks/useAgents";
import { useModels, Model } from "@/hooks/useModels";
import { useChat } from "@/hooks/useChat";
import { useProjects } from "@/hooks/useProjects";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";
import { apiGet } from "@/lib/api";
import { ChatComposer } from "@/components/ChatComposer";
import type { ChatMode } from "@/components/ChatInput";
import { HeroStage } from "@/components/hero/HeroStage";
import type { Project } from "@/hooks/useProjects";

export default function Home() {
  const router = useRouter();
  const { t, tArray } = useTranslation();
  const [input, setInput] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [selectedModel, setSelectedModel] = useState<Model | null>(null);
  const { agents } = useAgents();
  const { models, loading: modelsLoading } = useModels();
  const { createChat } = useChat();
  const { createProject } = useProjects();
  const { settings } = useSettingsStore();
  const [welcome, setWelcome] = useState("");
  const [welcomeSubtext, setWelcomeSubtext] = useState("");
  const [comboPersonality, setComboPersonality] = useState<number | null>(null);
  const [pendingProject, setPendingProject] = useState<Project | null>(null);
  const [pendingFiles, setPendingFiles] = useState<string[]>([]);
  const [reasoningEffort, setReasoningEffort] = useState<"none" | "low" | "high">("none");
  const [mode, setMode] = useState<ChatMode>("build");

  useEffect(() => {
    let cancelled = false;
    // 优先从后端欢迎语 API 获取随机极客文案
    apiGet<{ text?: string; subtext?: string }>("/api/system/greeting")
      .then((data) => {
        if (cancelled) return;
        if (data?.text) {
          setWelcome(data.text);
          setWelcomeSubtext(data.subtext || "");
          return;
        }
        throw new Error("empty greeting");
      })
      .catch(() => {
        if (cancelled) return;
        // 回退本地语言资源
        const messages = tArray("home.welcome");
        setWelcome(messages[Math.floor(Math.random() * messages.length)] || "");
        setWelcomeSubtext("");
      });
    return () => { cancelled = true; };
  }, [tArray]);

  // 根据 Settings 默认模型预选
  useEffect(() => {
    if (!modelsLoading && models.length > 0 && !selectedModel) {
      const defaultModelId = settings?.default_model;
      if (defaultModelId) {
        const found = models.find((m) => m.id === defaultModelId);
        if (found) setSelectedModel(found);
      }
    }
  }, [modelsLoading, models, settings?.default_model, selectedModel]);

  const currentAgent = selectedAgent || (settings?.default_agent ? agents.find(a => a.id === settings.default_agent) || null : null) || agents[0] || null;
  const currentModel = selectedModel || models[0] || null;

  const handleAgentChange = useCallback((agentId: string, personality: number) => {
    const agent = agents.find((a) => a.id === agentId);
    if (agent) setSelectedAgent(agent);
    setComboPersonality(personality);
  }, [agents]);

  const handleSend = async () => {
    if (!input.trim() || !currentAgent || isCreating) return;

    const userMessage = input.trim();
    setIsCreating(true);
    setInput("");

    try {
      const personalityLevel = comboPersonality ?? (settings?.default_personality ? Number(settings.default_personality) : 50);
      const chat = await createChat(
        currentAgent.id,
        userMessage.slice(0, 50) || "New Chat",
        pendingProject?.id ?? null,
        currentModel?.id || settings?.default_model || null,
        personalityLevel,
        pendingFiles,
        mode
      );

      const encodedMessage = encodeURIComponent(userMessage);
      router.push(`/chat/${chat.id}?message=${encodedMessage}`);
    } catch (err) {
      console.error("Failed to create chat:", err);
      setIsCreating(false);
      setInput(userMessage);
    }
  };

  // 草稿预挂载：首页无 Chat 状态下附加文件 / 关联项目，创建会话时一并提交
  const handleAttachFile = useCallback((file: File) => {
    const fileWithPath = file as File & { path?: string };
    const path = fileWithPath.path || file.name;
    setPendingFiles((prev) => (prev.includes(path) ? prev : [...prev, path]));
  }, []);

  const handleLinkProject = useCallback(async (dirPath: string) => {
    const name = dirPath.split(/[\\/]/).filter(Boolean).pop() || dirPath;
    const project = await createProject(name, dirPath);
    setPendingProject(project);
    window.dispatchEvent(new Event("mfk-projects-changed"));
  }, [createProject]);

  const handleClearDraft = useCallback(() => {
    setPendingFiles([]);
    setPendingProject(null);
  }, []);

  const removePendingFile = useCallback((path: string) => {
    setPendingFiles((prev) => prev.filter((p) => p !== path));
  }, []);

  const quickStarts = tArray("home.quickStarts");

  return (
    <div style={{
      flex: 1,
      display: "flex",
      flexDirection: "column",
      minHeight: 0,
      overflow: "hidden",
    }}>
      {/* 顶部/中部区域 - 舒展居中 */}
      <div style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "0 16px",
        minHeight: 0,
        overflowY: "auto",
      }}>
        {/* 启动主题舞台（Hero Theme 系统） */}
        <HeroStage welcome={welcome} subtext={welcomeSubtext} />

        {/* 快捷指令 */}
        {quickStarts.length > 0 && (
          <div style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "8px",
            justifyContent: "center",
            maxWidth: "480px",
          }}>
            {quickStarts.map((prompt) => (
              <button
                key={prompt}
                onClick={() => {
                  setInput(prompt);
                }}
                style={{
                  padding: "8px 14px",
                  borderRadius: "var(--radius-full)",
                  border: "1px solid var(--border-primary)",
                  background: "var(--bg-level-2)",
                  cursor: "pointer",
                  fontSize: "12px",
                  color: "var(--text-level-2)",
                  transition: "all var(--transition-fast)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "var(--color-primary)";
                  e.currentTarget.style.color = "var(--color-primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--border-primary)";
                  e.currentTarget.style.color = "var(--text-level-2)";
                }}
              >{prompt}</button>
            ))}
          </div>
        )}
      </div>

      {/* 底部区域 - 贴底 ChatComposer（一级入口：允许 Agent 切换） */}
      <ChatComposer
        value={input}
        onChange={setInput}
        onSend={handleSend}
        isSending={isCreating}
        placeholder={t("home.inputPlaceholder")}
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
        agentId={currentAgent?.id ?? null}
        onAgentChange={handleAgentChange}
        onUploadFile={handleAttachFile}
        onSelectDirectory={handleLinkProject}
        onClearContext={handleClearDraft}
        hasContext={pendingFiles.length > 0 || !!pendingProject}
        files={pendingFiles}
        onRemoveFile={removePendingFile}
        projectName={pendingProject?.name || null}
        onRemoveProject={() => setPendingProject(null)}
      />
    </div>
  );
}
