/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
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
import type { QuoteCategory, QuoteItem } from "@/components/hero/QuoteMenu";
import type { Project } from "@/hooks/useProjects";
import { INTERACTIVE_HERO_THEME_IDS } from "@/themes/registry";

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
  const { settings, updateSetting } = useSettingsStore();
  const [welcome, setWelcome] = useState("");
  const [welcomeSubtext, setWelcomeSubtext] = useState("");
  // 全部台词类目（原始数据，builtin 模式从后端拉取）
  const [allQuoteCategories, setAllQuoteCategories] = useState<QuoteCategory[]>([]);
  const [greetingFavorites, setGreetingFavorites] = useState<string[]>([]);
  const [pendingProject, setPendingProject] = useState<Project | null>(null);
  const [pendingFiles, setPendingFiles] = useState<string[]>([]);
  const [reasoningEffort, setReasoningEffort] = useState<"none" | "high" | "max">("none");
  const [mode, setMode] = useState<ChatMode>("build");

  useEffect(() => {
    let cancelled = false;
    const mode = settings?.greeting_mode ?? "builtin";

    // off 模式：不展示欢迎语，也不渲染台词小组件
    if (mode === "off") {
      setWelcome("");
      setWelcomeSubtext("");
      setAllQuoteCategories([]);
      return () => { cancelled = true; };
    }

    // custom 模式：从用户自定义台词（≤5 条）中随机取一条，作为独立数据源
    if (mode === "custom") {
      try {
        const parsed: unknown = JSON.parse(settings?.custom_greetings ?? "[]");
        if (Array.isArray(parsed)) {
          const list = parsed.filter((x): x is string => typeof x === "string" && x.trim() !== "");
          if (list.length > 0) {
            const pick = list[Math.floor(Math.random() * list.length)];
            setWelcome(pick);
            setWelcomeSubtext("");
            return () => { cancelled = true; };
          }
        }
      } catch {
        /* ignore malformed */
      }
      setWelcome("");
      setWelcomeSubtext("");
      return () => { cancelled = true; };
    }

    // builtin 模式（默认）：优先从后端欢迎语 API 获取全部分组文案，随机取一条做初始欢迎语
    apiGet<{ categories?: QuoteCategory[] }>("/api/system/greetings")
      .then((data) => {
        if (cancelled) return;
        const categories = data?.categories ?? [];
        if (categories.length > 0) {
          setAllQuoteCategories(categories);
          const all = categories.flatMap((c) => c.items);
          const pick = all[Math.floor(Math.random() * all.length)];
          if (pick) {
            setWelcome(pick.text);
            setWelcomeSubtext(pick.subtext || "");
            return;
          }
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
  }, [settings?.greeting_mode, settings?.custom_greetings, tArray]);

  // 台词菜单选中：切换首页欢迎语
  const handleSelectQuote = useCallback((item: QuoteItem) => {
    setWelcome(item.text);
    setWelcomeSubtext(item.subtext || "");
  }, []);

  // 收藏 key：类目 id + 分隔符 + 文本（203 条已验证唯一）
  const quoteFavKey = useCallback((catId: string, item: QuoteItem) => `${catId}\u0001${item.text}`, []);

  // 欢迎语收藏：从后端 Settings 加载（localStorage 不参与，权威源在后端，便于将来删除未收藏项）
  useEffect(() => {
    const raw = settings?.greeting_favorites;
    if (raw == null) return;
    try {
      const parsed: unknown = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        setGreetingFavorites(parsed.filter((x): x is string => typeof x === "string"));
      }
    } catch {
      /* ignore malformed */
    }
  }, [settings?.greeting_favorites]);

  // 切换单条欢迎语收藏：乐观更新本地 + 同步后端 Settings
  const toggleQuoteFavorite = useCallback((catId: string, item: QuoteItem) => {
    const key = quoteFavKey(catId, item);
    setGreetingFavorites((prev) => {
      const next = prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key];
      updateSetting("greeting_favorites", JSON.stringify(next));
      return next;
    });
  }, [quoteFavKey, updateSetting]);

  // 派生台词类目：有收藏时仅保留已收藏台词（未收藏的隐藏到后台），无收藏时展示全部（避免空白）
  const quoteCategories = useMemo(() => {
    if (greetingFavorites.length === 0) return allQuoteCategories;
    const favSet = new Set(greetingFavorites);
    return allQuoteCategories
      .map((c) => ({
        ...c,
        items: c.items.filter((item) => favSet.has(quoteFavKey(c.id, item))),
      }))
      .filter((c) => c.items.length > 0);
  }, [allQuoteCategories, greetingFavorites, quoteFavKey]);

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

  // 根据 Settings 默认推理强度预选（仅首次设置，避免覆盖用户手动切换）
  const defaultReasoningAppliedRef = useRef(false);
  useEffect(() => {
    if (defaultReasoningAppliedRef.current) return;
    const def = settings?.default_reasoning_effort;
    if (!def) return; // settings 未加载，等下一次变更
    defaultReasoningAppliedRef.current = true;
    if (def === "high" || def === "max") setReasoningEffort(def);
  }, [settings?.default_reasoning_effort]);

  const activeAgents = agents.filter((a) => a.status === "active");
  const currentAgent = selectedAgent || (settings?.default_agent ? activeAgents.find(a => a.id === settings.default_agent) || null : null) || activeAgents[0] || null;
  const currentModel = selectedModel || (settings?.default_model ? models.find(m => m.id === settings.default_model) || null : null) || models[0] || null;

  const handleAgentChange = useCallback((agentId: string) => {
    const agent = activeAgents.find((a) => a.id === agentId);
    if (agent) setSelectedAgent(agent);
  }, [activeAgents]);

  const handleSend = async () => {
    if (!input.trim() || !currentAgent || isCreating) return;

    const userMessage = input.trim();
    setIsCreating(true);
    setInput("");

    try {
      const chat = await createChat(
        currentAgent.id,
        userMessage.slice(0, 50) || "New Chat",
        pendingProject?.id ?? null,
        currentModel?.id || settings?.default_model || null,
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

  // 当前 hero 主题 id（HeroStage 上报）；可交互主题内已内置快捷入口，首页独立快捷指令行随之隐藏
  const [heroThemeId, setHeroThemeId] = useState<string | undefined>(undefined);
  const interactiveTheme = heroThemeId ? INTERACTIVE_HERO_THEME_IDS.has(heroThemeId) : false;

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
        <HeroStage
          welcome={welcome}
          subtext={welcomeSubtext}
          quoteCategories={quoteCategories}
          quoteFavorites={greetingFavorites}
          onToggleQuoteFavorite={toggleQuoteFavorite}
          onSelectQuote={handleSelectQuote}
          showQuoteWidget={(settings?.greeting_mode ?? "builtin") === "builtin"}
          onQuickAction={(prompt) => setInput(prompt)}
          onThemeChange={setHeroThemeId}
        />
      </div>

      {/* 快捷指令（非可交互主题时显示）：紧贴输入组合框上方，留轻微空隙 */}
      {!interactiveTheme && quickStarts.length > 0 && (
        <div style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "8px",
          justifyContent: "center",
          maxWidth: "768px",
          width: "100%",
          margin: "0 auto",
          padding: "0 16px 6px",
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
