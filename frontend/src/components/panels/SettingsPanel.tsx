"use client";

/**
 * SettingsPanel —— 设置面板薄壳（字段级边界重构后）
 *
 * 设计说明：
 * - 6 个导航 Tab 完整展示，严禁隐藏 ai/extensions 顶级入口。
 * - 每个 section 渲染 BasicSettingsView（基础选项）；
 *   model/ai 额外直接渲染 AdvancedSettingsView（深水区参数），无折叠交互，全量展示。
 * - 统管 props 和单向数据流不变，子组件通过 props 消费。
 */
import { useState, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Monitor, Cpu, Brain, Info, Blocks, ShieldAlert, Database, Keyboard, Search, X, Smartphone } from "lucide-react";
import { useRouter } from "next/navigation";
import { useSettingsStore } from "@/lib/store";
import { useTranslation } from "@/hooks/useTranslation";
import { useModels } from "@/hooks/useModels";
import { useAgents } from "@/hooks/useAgents";
import { SETTINGS_SEARCH_INDEX } from "@/lib/settingsSearchIndex";
import { useSettingsToast, errorMessage } from "@/lib/toastStore";
import { SettingsToast } from "@/components/SettingsToast";
import { Panel } from "./Panel";
import { AgentListPanel } from "./AgentListPanel";
import { SubAgentPanel } from "./SubAgentPanel";
import { ArchivePanel } from "./ArchivePanel";
import { BasicSettingsView, type SettingSectionId } from "./BasicSettingsView";
import { AdvancedSettingsView } from "./AdvancedSettingsView";
import { SwitchButton } from "@/components/SwitchButton";
import { getSubAgents, type SubAgent } from "@/lib/api";

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

/** 设置面板内部视图状态机：主设置 / Agent 列表 / Agent 编辑 / 子代理列表 / 子代理编辑 / 子代理新建 */
type ViewState = "main_settings" | "agent_list" | "agent_edit" | "sub_agent_list" | "sub_agent_edit" | "sub_agent_create";

/** 含深水区参数的 section（model/ai）：基础区下方直接追加高级区，无折叠 */
const SECTIONS_WITH_ADVANCED: SettingSectionId[] = ["model", "ai"];

export function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const { settings, loading, fetchSettings, updateSetting } = useSettingsStore();
  const { t } = useTranslation();
  const { models, loading: modelsLoading } = useModels();
  const { agents } = useAgents();
  const { showToast } = useSettingsToast();
  const pairRouter = useRouter(); // 安卓端 M1：跳转 /pair 连接手机页

  // ── 统管状态 ──
  const [saving, setSaving] = useState<string | null>(null);
  // 设置搜索框（导航级过滤，索引见 lib/settingsSearchIndex.ts）
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSection, setActiveSection] = useState<SettingSectionId>(() => {
    try {
      const saved = localStorage.getItem("mfk_settings_active_section");
      return (saved as SettingSectionId) || "general";
    } catch {
      return "general";
    }
  });
  // 开发者模式：默认关（小白视图只显示基础区）；开 = 全量展示深水区参数（Base URL/自定义模型/子代理等）。
  // 借鉴 Codex Developer mode / Windsurf Advanced Settings 的行业做法，localStorage 持久化。
  const [developerMode, setDeveloperMode] = useState(() => {
    try { return localStorage.getItem("mfk_settings_developer_mode") === "1"; }
    catch { return false; }
  });
  const handleDeveloperMode = (v: boolean) => {
    setDeveloperMode(v);
    try { localStorage.setItem("mfk_settings_developer_mode", v ? "1" : "0"); } catch { /* noop */ }
  };
  const [currentView, setCurrentView] = useState<ViewState>("main_settings");
  const [editingAgentId, setEditingAgentId] = useState<string | null>(null);
  // 子代理三级导航：子代理列表 / 编辑 / 新建（"__create__" = 新建）
  const [editingSubAgentId, setEditingSubAgentId] = useState<string | null>(null);
  // 子代理列表快照（用于编辑视图标题显示名称）
  const [subAgentsList, setSubAgentsList] = useState<SubAgent[]>([]);
  // 三级导航：Skill 详情（在扩展区点击 Skill 卡片后进入）
  const [editingSkillId, setEditingSkillId] = useState<string | null>(null);
  const [direction, setDirection] = useState<1 | -1>(1);

  useEffect(() => {
    if (!settings) fetchSettings();
  }, [settings, fetchSettings]);

  // 进入子代理视图时拉取列表快照（标题需要名称）
  useEffect(() => {
    if (currentView.startsWith("sub_agent")) {
      getSubAgents().then(setSubAgentsList).catch(() => {});
    }
  }, [currentView]);

  const handleClose = () => {
    setCurrentView("main_settings");
    setEditingAgentId(null);
    setEditingSubAgentId(null);
    setEditingSkillId(null);
    onClose();
  };

  const handleUpdate = async (key: string, value: string) => {
    setSaving(key);
    try {
      await updateSetting(key, value);
      showToast(t("common.saved"), "success");
    } catch (err) {
      console.error("Failed to update setting:", err);
      showToast(errorMessage(err) || t("common.saved"), "error");
    } finally {
      setSaving(null);
    }
  };

  if (loading) {
    return (
      <Panel isOpen={isOpen} onClose={handleClose} title={t("settings.title")}>
        <p style={{ color: "var(--text-level-3)" }}>{t("common.loading")}</p>
      </Panel>
    );
  }

  const navItems: { id: SettingSectionId; label: string; icon: typeof Monitor }[] = [
    { id: "general", label: t("settings.general.title"), icon: Monitor },
    { id: "model", label: t("settings.model.title"), icon: Cpu },
    { id: "ai", label: t("settings.ai.title"), icon: Brain },
    { id: "security", label: t("settings.security.title"), icon: ShieldAlert },
    { id: "extensions", label: t("settings.extensions.title"), icon: Blocks },
    { id: "archive", label: t("settings.archive.title"), icon: Database },
    { id: "about", label: t("settings.about.title"), icon: Info },
    { id: "shortcuts", label: t("settings.shortcuts.title"), icon: Keyboard },
  ];

  // ── 设置搜索：过滤左侧导航 + 命中字段计数（导航级，不侵入字段渲染）──
  const q = searchQuery.trim().toLowerCase();
  const matchFields = (sectionId: string) => {
    if (!q) return [];
    const entry = SETTINGS_SEARCH_INDEX.find((e) => e.section === sectionId);
    if (!entry) return [];
    return entry.fields.filter(
      (f) =>
        f.label.toLowerCase().includes(q) ||
        (f.aliases ?? []).some((a) => a.toLowerCase().includes(q)),
    );
  };
  const isSectionMatched = (sectionId: string) => {
    if (!q) return true;
    const labelKey = navItems.find((n) => n.id === sectionId)?.label ?? "";
    if (labelKey && labelKey.toLowerCase().includes(q)) return true;
    return matchFields(sectionId).length > 0;
  };
  const filteredNav = q ? navItems.filter((n) => isSectionMatched(n.id)) : navItems;
  const activeHits = q ? matchFields(activeSection) : [];

  // 搜索词变化时（onChange 事件内）：若当前 tab 不在命中集，自动跳到第一个命中 tab
  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    const nq = value.trim().toLowerCase();
    if (!nq) return;
    const matched = navItems.filter((n) => {
      const entry = SETTINGS_SEARCH_INDEX.find((e) => e.section === n.id);
      const titleOk = n.label.toLowerCase().includes(nq);
      const fieldsOk = entry
        ? entry.fields.some(
            (f) =>
              f.label.toLowerCase().includes(nq) ||
              (f.aliases ?? []).some((a) => a.toLowerCase().includes(nq)),
          )
        : false;
      return titleOk || fieldsOk;
    });
    if (matched.length > 0 && !matched.some((n) => n.id === activeSection)) {
      setActiveSection(matched[0].id as SettingSectionId);
    }
  };

  const viewTitle =
    currentView === "main_settings"
      ? t("settings.title")
      : currentView === "agent_list"
        ? t("settings.ai.agents.title")
        : currentView === "sub_agent_list"
          ? t("settings.ai.subAgents.title")
          : currentView === "sub_agent_create"
            ? t("settings.ai.subAgents.create")
            : currentView === "sub_agent_edit"
              ? (subAgentsList.find((s) => s.id === editingSubAgentId)?.name ?? t("settings.ai.subAgents.title"))
              : (agents.find((a) => a.id === editingAgentId)?.name ?? t("settings.ai.agents.title"));

  const goToMainSettings = () => {
    setDirection(-1);
    setEditingAgentId(null);
    setEditingSubAgentId(null);
    setCurrentView("main_settings");
  };
  const goToAgentList = () => {
    setDirection(-1);
    setEditingAgentId(null);
    setCurrentView("agent_list");
  };
  const goToSubAgentList = () => {
    setDirection(-1);
    setEditingSubAgentId(null);
    setCurrentView("sub_agent_list");
  };

  const viewVariants = {
    enter: (dir: number) => ({ opacity: 0, x: dir * 24 }),
    center: { opacity: 1, x: 0 },
    exit: (dir: number) => ({ opacity: 0, x: dir * -24 }),
  };
  const viewTransition = { duration: 0.2, ease: "easeInOut" as const };

  // 子组件共享 props（统管状态下发）
  const viewProps = {
    settings,
    saving,
    onUpdate: handleUpdate,
    models,
    modelsLoading,
    t,
  };

  // 含深水区参数的 section（model/ai）：基础区下方追加高级区；仅在开发者模式下渲染
  const hasAdvanced = SECTIONS_WITH_ADVANCED.includes(activeSection) && developerMode;

  return (
    <Panel isOpen={isOpen} onClose={handleClose} title={viewTitle} width="700px" height="min(680px, 82vh)" variant="center"
      headerExtra={
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          <span style={{ fontSize: 12, color: developerMode ? "var(--color-primary)" : "var(--text-level-3)", fontWeight: developerMode ? 500 : 400, userSelect: "none" }}>
            {t("settings.developerMode")}
          </span>
          <SwitchButton checked={developerMode} onChange={handleDeveloperMode} />
        </div>
      }
    >
      <div style={{ position: "relative", height: "100%", overflow: "hidden" }}>
        <SettingsToast />
        <AnimatePresence mode="popLayout" initial={false} custom={direction}>
          {currentView === "main_settings" ? (
            <motion.div
              key="main_settings"
              custom={direction}
              variants={viewVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={viewTransition}
              style={{ height: "100%" }}
            >
              <div style={{ display: "flex", gap: "24px", minHeight: "400px", height: "100%", overflow: "hidden" }}>
                {/* 左侧导航 - 固定不滚动 */}
                <nav style={{
                  width: "168px", flexShrink: 0,
                  borderRight: "1px solid var(--border-primary)",
                  paddingRight: "16px", marginRight: "16px",
                  height: "100%", overflow: "hidden",
                  display: "flex", flexDirection: "column",
                }}>
                  {/* 设置搜索框：导航级过滤 */}
                  <div style={{ position: "relative", marginBottom: "10px", flexShrink: 0 }}>
                    <Search style={{
                      position: "absolute", left: "9px", top: "50%", transform: "translateY(-50%)",
                      width: "13px", height: "13px", color: "var(--text-level-4)", pointerEvents: "none",
                    }} />
                    <input
                      value={searchQuery}
                      onChange={(e) => handleSearchChange(e.target.value)}
                      placeholder={t("settings.searchPlaceholder")}
                      className="mf-input"
                      style={{
                        width: "100%", padding: "7px 26px 7px 28px", boxSizing: "border-box",
                        borderRadius: "var(--radius-sm)",
                        background: "var(--bg-level-2)",
                        fontSize: "12px", color: "var(--text-level-2)",
                      }}
                    />
                    {searchQuery && (
                      <button
                        onClick={() => setSearchQuery("")}
                        aria-label="clear search"
                        className="mf-icon-btn"
                        style={{
                          position: "absolute", right: "6px", top: "50%", transform: "translateY(-50%)",
                          border: "none", cursor: "pointer",
                          color: "var(--text-level-4)", padding: "2px", display: "inline-flex",
                        }}
                      >
                        <X style={{ width: "12px", height: "12px" }} />
                      </button>
                    )}
                  </div>
                  {q && filteredNav.length === 0 && (
                    <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "4px 0 0 0", flexShrink: 0 }}>
                      {t("settings.searchNoResult")}
                    </p>
                  )}
                  <div style={{ flex: 1, overflowY: "auto", overflowX: "hidden", scrollbarGutter: "stable" }}>
                  {filteredNav.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => {
                        setActiveSection(item.id);
                        // 切 Tab 时重置 Skill 详情，返回扩展主页
                        setEditingSkillId(null);
                        try { localStorage.setItem("mfk_settings_active_section", item.id); } catch { /* noop */ }
                      }}
                      className={activeSection === item.id ? "mf-nav-item is-active" : "mf-nav-item"}
                      style={{
                        display: "flex", alignItems: "center", gap: "8px",
                        width: "100%", padding: "10px 12px",
                        borderRadius: "var(--radius-md)", border: "none",
                        cursor: "pointer", fontSize: "14px",
                        color: activeSection === item.id ? "var(--text-level-1)" : "var(--text-level-3)",
                        textAlign: "left", marginBottom: "4px",
                      }}
                    >
                      <item.icon
                        style={{
                          width: "16px", height: "16px",
                          color: activeSection === item.id ? "var(--color-primary)" : "currentColor",
                          transition: "color var(--transition-fast)",
                        }}
                      />
                      <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.label}</span>
                      {q && matchFields(item.id).length > 0 && (
                        <span style={{ fontSize: "10px", color: "var(--color-primary)", flexShrink: 0 }}>
                          {matchFields(item.id).length}
                        </span>
                      )}
                    </button>
                  ))}
                  {/* 安卓端 M1：连接手机入口（独立页面 /pair，不走 section 状态机） */}
                  <button
                    onClick={() => pairRouter.push("/pair")}
                    className="mf-nav-item"
                    style={{
                      display: "flex", alignItems: "center", gap: "8px",
                      width: "100%", padding: "10px 12px",
                      borderRadius: "var(--radius-md)", border: "none",
                      cursor: "pointer", fontSize: "14px",
                      color: "var(--text-level-3)",
                      textAlign: "left", marginBottom: "4px",
                    }}
                  >
                    <Smartphone
                      style={{
                        width: "16px", height: "16px",
                        color: "currentColor",
                        transition: "color var(--transition-fast)",
                      }}
                    />
                    <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>连接手机</span>
                  </button>
                  </div>
                </nav>

                {/* 右侧内容 - 独立滚动 */}
                <div style={{
                  flex: 1, minWidth: 0,
                  overflowY: "auto", overflowX: "hidden",
                  height: "100%", paddingRight: "4px",
                  scrollbarGutter: "stable",
                }}>
                  {/* 搜索命中提示（导航级计数，不侵入字段渲染） */}
                  {q && activeHits.length > 0 && (
                    <div style={{
                      padding: "8px 12px", marginBottom: "12px",
                      borderRadius: "var(--radius-sm)",
                      background: "color-mix(in srgb, var(--color-primary) 8%, transparent)",
                      border: "1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)",
                      fontSize: "12px", color: "var(--text-level-2)",
                    }}>
                      {t("settings.searchHits", { count: String(activeHits.length) })}：{activeHits.map((f) => f.label).join("、")}
                    </div>
                  )}
                  {/* 归档 Tab：独立面板（归档列表 + 归档目录配置） */}
                  {activeSection === "archive" ? (
                    <ArchivePanel />
                  ) : (
                    <>
                      {/* 基础区块（默认展示） */}
                      <BasicSettingsView
                        {...viewProps}
                        activeSection={activeSection}
                        agents={agents}
                        onManageAgents={() => {
                          setDirection(1);
                          setCurrentView("agent_list");
                        }}
                        onManageSubAgents={() => {
                          setDirection(1);
                          setCurrentView("sub_agent_list");
                        }}
                        editingSkillId={editingSkillId}
                        onSelectSkill={(id) => setEditingSkillId(id)}
                        onBackToExtensionList={() => setEditingSkillId(null)}
                      />

                      {/* 高级区块（model/ai 深水区参数，全量直接展示，无折叠） */}
                      {hasAdvanced && (
                        <div style={{ marginTop: "20px", paddingTop: "16px", borderTop: "1px solid var(--border-primary)" }}>
                          <AdvancedSettingsView
                            {...viewProps}
                            activeSection={activeSection}
                            agents={agents}
                            onClose={onClose}
                            onManageAgents={() => {
                              setDirection(1);
                              setCurrentView("agent_list");
                            }}
                            onManageSubAgents={() => {
                              setDirection(1);
                              setCurrentView("sub_agent_list");
                            }}
                          />
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </motion.div>
          ) : currentView.startsWith("sub_agent") ? (
            <motion.div
              key={currentView}
              custom={direction}
              variants={viewVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={viewTransition}
              style={{ height: "100%", overflowY: "auto", overflowX: "hidden" }}
            >
              <SubAgentPanel
                editingId={editingSubAgentId}
                onSelect={(id) => {
                  setDirection(1);
                  setEditingSubAgentId(id);
                  setCurrentView(id === "__create__" ? "sub_agent_create" : "sub_agent_edit");
                }}
                onBackToSettings={goToMainSettings}
                onBackToList={goToSubAgentList}
                onRefresh={() => getSubAgents().then(setSubAgentsList).catch(() => {})}
              />
            </motion.div>
          ) : (
            <motion.div
              key={editingAgentId ? "agent_edit" : "agent_list"}
              custom={direction}
              variants={viewVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={viewTransition}
              style={{ height: "100%", overflowY: "auto", overflowX: "hidden" }}
            >
              <AgentListPanel
                editingAgentId={editingAgentId}
                onSelectAgent={(id) => {
                  setDirection(1);
                  setEditingAgentId(id);
                  setCurrentView("agent_edit");
                }}
                onBackToSettings={goToMainSettings}
                onBackToList={goToAgentList}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </Panel>
  );
}
