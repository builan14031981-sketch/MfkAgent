/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useAgents, Agent } from "@/hooks/useAgents";
import { useModels, Model } from "@/hooks/useModels";
import { useVisibleModels } from "@/hooks/useVisibleModels";
import { useChat } from "@/hooks/useChat";
import { useProjects } from "@/hooks/useProjects";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";
import { usePreferences } from "@/hooks/usePreferences";
import { apiGet } from "@/lib/api";
import { ChatComposer } from "@/components/ChatComposer";
import { useSkills, type SkillInfo } from "@/hooks/useSkills";
import type { ChatMode } from "@/components/ChatInput";
import type { PermissionMode } from "@/components/chat-input/PermissionSelector";
import { FileDropZone } from "@/components/FileDropZone";
import type { DroppedFile, Attachment } from "@/components/FileDropZone";
import { fileToAttachment, droppedFileToAttachment, mergeAttachments } from "@/components/FileDropZone";
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
  const { models } = useModels();
  // 2026-08-11 接入 useVisibleModels：与聊天页/弹窗/设置下拉用同一份可见模型
  const visibleModels = useVisibleModels(models);
  const { createChat } = useChat();
  const { createProject } = useProjects();
  const { skills: allSkills } = useSkills();
  const { settings, updateSetting } = useSettingsStore();
  // Phase 1.5：模型/推理强度偏好三级回落（localStorage → /api/settings → 默认 qwen-flash）
  // 2026-08-11：传 visibleModels，让偏好 modelId 跟下拉可见性一致（移除 qwen-max 后回落为 qwen-flash）
  const { modelId: prefModelId, reasoningEffort: prefReasoningEffort, hasLocalReasoning, prefsLoaded, setModel: setPrefModel, setReasoning: setPrefReasoning } = usePreferences(visibleModels, settings);
  const [welcome, setWelcome] = useState("");
  const [welcomeSubtext, setWelcomeSubtext] = useState("");
  // 全部台词类目（原始数据，builtin 模式从后端拉取）
  const [allQuoteCategories, setAllQuoteCategories] = useState<QuoteCategory[]>([]);
  const [greetingFavorites, setGreetingFavorites] = useState<string[]>([]);
  const [pendingProject, setPendingProject] = useState<Project | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<Attachment[]>([]);
  // 首页会话级 Skill：选中后随 URL 带给新会话，仅新会话生效，不写全局
  const [sessionSkills, setSessionSkills] = useState<SkillInfo[]>([]);
  // 初始值固定为 none（SSR/水合安全）；挂载后由下方初始化块按三级回落赋值
  const [reasoningEffort, setReasoningEffort] = useState<"none" | "high" | "max">("none");
  const [permissionMode, setPermissionMode] = useState<PermissionMode>(() => {
    const def = settings?.agent_permission_mode;
    return def === "safe" || def === "standard" || def === "autonomous" ? def : "standard";
  });
  const [mode, setMode] = useState<ChatMode>("build");
  // 初始随机抽取标记：防止收藏变化触发重新抽取（避免主页台词频繁跳变）
  const initialQuotePickedRef = useRef(false);

  useEffect(() => {
    initialQuotePickedRef.current = false; // 模式切换时重置，允许重新抽取
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

    // builtin 模式（默认）：从后端拉取全量分组文案
    // 初始随机抽取延后到 quoteCategories（派生后的收藏列表）就绪后执行，确保抽到的台词在菜单可见
    apiGet<{ categories?: QuoteCategory[] }>("/api/system/greetings")
      .then((data) => {
        if (cancelled) return;
        const categories = data?.categories ?? [];
        if (categories.length > 0) {
          setAllQuoteCategories(categories);
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
      updateSetting("greeting_favorites", JSON.stringify(next)).catch(() => {});
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

  // 初始随机抽取（builtin 模式）：从派生后的 quoteCategories（有收藏时仅收藏列表）中抽取
  // 确保：1) 不展示已隐藏（未收藏）的台词；2) 抽到的台词在 QuoteMenu 可见，高亮可生效
  // 仅首次数据就绪时执行一次，收藏变化不触发重新抽取（避免主页台词频繁跳变）
  useEffect(() => {
    const mode = settings?.greeting_mode ?? "builtin";
    if (mode !== "builtin") return;
    if (initialQuotePickedRef.current) return;
    if (!settings) return; // 等 settings 加载完（确保 greetingFavorites 已就绪）
    if (quoteCategories.length === 0) return;
    const all = quoteCategories.flatMap((c) => c.items);
    if (all.length === 0) return;
    const pick = all[Math.floor(Math.random() * all.length)];
    setWelcome(pick.text);
    setWelcomeSubtext(pick.subtext || "");
    initialQuotePickedRef.current = true;
  }, [settings, quoteCategories]);

  // 推理强度初始值：三级回落（localStorage → settings → none），仅首次就绪时应用一次，
  // 避免 settings 异步加载或用户手动切换后重复覆盖。
  // 采用 render 阶段"调整 state"模式（与 chat 页 reasoningInitForChatId 一致），规避 ref 读取告警。
  const [reasoningInitApplied, setReasoningInitApplied] = useState(false);
  if (!reasoningInitApplied && (prefsLoaded || hasLocalReasoning || settings)) {
    setReasoningInitApplied(true);
    setReasoningEffort(prefReasoningEffort);
  }

  const activeAgents = agents.filter((a) => a.status === "active");
  const currentAgent = selectedAgent || (settings?.default_agent ? activeAgents.find(a => a.id === settings.default_agent) || null : null) || activeAgents[0] || null;
  const currentModel = selectedModel || visibleModels.find((m) => m.id === prefModelId) || visibleModels[0] || null;

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
        pendingAttachments.map((a) => a.path || a.name),
        mode
      );

      const encodedMessage = encodeURIComponent(userMessage);
      // 首页选中了会话级 Skill：把它随 URL 带给新会话（聊天页据 skills 参数恢复会话级启用）
      const skillIds = sessionSkills.map((s) => s.id);
      const skillParam = skillIds.length > 0 ? `&skills=${encodeURIComponent(JSON.stringify(skillIds))}` : "";
      router.push(`/chat/${chat.id}?message=${encodedMessage}${skillParam}`);
    } catch (err) {
      console.error("Failed to create chat:", err);
      setIsCreating(false);
      setInput(userMessage);
    }
  };

  // 草稿预挂载：首页无 Chat 状态下附加文件 / 关联项目，创建会话时一并提交
  const handleAttachFile = useCallback((file: File) => {
    const att = fileToAttachment(file, pendingProject?.path);
    setPendingAttachments((prev) => mergeAttachments(prev, [att]));
  }, [pendingProject?.path]);

  // 全局拖拽：将拖入文件映射为附件并入草稿（首页无 Chat 状态，先挂 pending，创建会话时一并提交）
  const handleFilesDrop = useCallback((files: DroppedFile[]) => {
    const newAtts = files.map((f) => droppedFileToAttachment(f, pendingProject?.path));
    setPendingAttachments((prev) => mergeAttachments(prev, newAtts));
  }, [pendingProject?.path]);

  const handleLinkProject = useCallback(async (dirPath: string) => {
    const name = dirPath.split(/[\\/]/).filter(Boolean).pop() || dirPath;
    const project = await createProject(name, dirPath);
    setPendingProject(project);
    window.dispatchEvent(new Event("mfk-projects-changed"));
  }, [createProject]);

  const handleClearDraft = useCallback(() => {
    setPendingAttachments([]);
    setPendingProject(null);
    setSessionSkills([]);
  }, []);

  // 会话级启用 Skill（首页选中，随 URL 带给新会话）
  const handleApplySkill = useCallback((skill: SkillInfo) => {
    setSessionSkills((prev) => (prev.some((s) => s.id === skill.id) ? prev : [...prev, skill]));
  }, []);

  // 移除某个会话级 Skill
  const handleRemoveSkill = useCallback((skillId: string) => {
    setSessionSkills((prev) => prev.filter((s) => s.id !== skillId));
  }, []);

  const removePendingAttachment = useCallback((id: string) => {
    setPendingAttachments((prev) => prev.filter((a) => a.id !== id));
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

            {/* 底部输入区域容器：快捷指令 + 输入框 */}
      <div
        className="home-bottom-area"
        onMouseEnter={(e) => {
          const qs = e.currentTarget.querySelector('.home-quickstarts') as HTMLElement | null;
          if (qs) { qs.style.opacity = '1'; qs.style.transform = 'translateY(0)'; qs.style.pointerEvents = 'auto'; }
        }}
        onMouseLeave={(e) => {
          const qs = e.currentTarget.querySelector('.home-quickstarts') as HTMLElement | null;
          if (qs) { qs.style.opacity = '0'; qs.style.transform = 'translateY(8px)'; qs.style.pointerEvents = 'none'; }
        }}
        style={{
          width: "100%",
          // 2026-08-16：底部输入区随 ChatComposer 同步加宽，maxWidth 1400px，容器背景透明，仅输入卡片悬浮
          maxWidth: "1400px",
          margin: "0 auto",
          position: "relative",
        }}
      >
        {/* 快捷指令（非可交互主题时显示）：绝对定位在输入框上方，hover 时显示 */}
        {!interactiveTheme && quickStarts.length > 0 && (
          <div
            className="home-quickstarts"
            style={{
              position: "absolute",
              bottom: "100%",
              left: 0,
              right: 0,
              display: "flex",
              flexWrap: "wrap",
              gap: "8px",
              justifyContent: "center",
              padding: "8px 16px 12px",
              opacity: 0,
              transform: "translateY(8px)",
              pointerEvents: "none",
              transition: "opacity 0.2s ease, transform 0.2s ease",
            }}
          >
            {quickStarts.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => setInput(prompt)}
                style={{
                  padding: "8px 14px",
                  borderRadius: "var(--radius-full)",
                  border: "1px solid var(--border-primary)",
                  background: "var(--bg-level-2)",
                  cursor: "pointer",
                  fontSize: "12px",
                  color: "var(--text-level-2)",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
                  transition: "all 0.2s ease",
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

        {/* 渐变遮罩：内容区到输入区的平滑过渡 */}
        <div style={{
          height: "48px",
          background: "linear-gradient(to bottom, transparent, var(--bg-level-2))",
          position: "relative",
          marginTop: "-48px",
          pointerEvents: "none",
          zIndex: 1,
        }} />

        {/* 底部区域 - 贴底 ChatComposer（一级入口：允许 Agent 切换） */}
        <div style={{ position: "relative", zIndex: 2 }}>
          <ChatComposer
        value={input}
        onChange={setInput}
        onSend={handleSend}
        isSending={isCreating}
        placeholder={t("home.inputPlaceholder")}
        models={visibleModels}
        modelId={currentModel?.id || null}
        onModelChange={(id) => {
          const model = visibleModels.find(m => m.id === id);
          if (model) {
            setSelectedModel(model);
            setPrefModel(id);
          }
        }}
        reasoningEffort={reasoningEffort}
        onReasoningChange={(e) => {
          setReasoningEffort(e);
          setPrefReasoning(e);
        }}
        permissionMode={permissionMode}
        onPermissionChange={setPermissionMode}
        mode={mode}
        onModeChange={setMode}
        allowAgentChange
        agentId={currentAgent?.id ?? null}
        onAgentChange={handleAgentChange}
        onUploadFile={handleAttachFile}
        onSelectDirectory={handleLinkProject}
        onClearContext={handleClearDraft}
        hasContext={pendingAttachments.length > 0 || !!pendingProject || sessionSkills.length > 0}
        files={[]}
        onRemoveFile={() => {}}
        projectName={pendingProject?.name || null}
        onRemoveProject={() => setPendingProject(null)}
        attachments={pendingAttachments}
        onRemoveAttachment={removePendingAttachment}
        skills={allSkills}
        onApplySkill={handleApplySkill}
        activeSkillIds={new Set(sessionSkills.map((s) => s.id))}
        onRemoveSkill={handleRemoveSkill}
      />
        </div>
      </div>
      <FileDropZone onFilesDrop={handleFilesDrop} />
    </div>
  );
}




