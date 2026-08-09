"use client";

/**
 * SettingsPanel —— 设置面板薄壳（字段级边界重构后）
 *
 * 设计说明：
 * - 5 个导航 Tab 完整展示，严禁隐藏 ai/plugins 顶级入口。
 * - 每个 section 渲染 BasicSettingsView（基础选项）；
 *   model/ai 额外直接渲染 AdvancedSettingsView（深水区参数），无折叠交互，全量展示。
 * - 统管 props 和单向数据流不变，子组件通过 props 消费。
 */
import { useState, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Monitor, Cpu, Brain, Info, Puzzle } from "lucide-react";
import { useSettingsStore } from "@/lib/store";
import { useTranslation } from "@/hooks/useTranslation";
import { useModels } from "@/hooks/useModels";
import { useAgents } from "@/hooks/useAgents";
import { Panel } from "./Panel";
import { AgentListPanel } from "./AgentListPanel";
import { BasicSettingsView, type SettingSectionId } from "./BasicSettingsView";
import { AdvancedSettingsView } from "./AdvancedSettingsView";

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

/** 设置面板内部视图状态机：主设置 / Agent 列表 / Agent 编辑 */
type ViewState = "main_settings" | "agent_list" | "agent_edit";

/** 含深水区参数的 section（model/ai）：基础区下方直接追加高级区，无折叠 */
const SECTIONS_WITH_ADVANCED: SettingSectionId[] = ["model", "ai"];

export function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const { settings, loading, fetchSettings, updateSetting } = useSettingsStore();
  const { t } = useTranslation();
  const { models, loading: modelsLoading } = useModels();
  const { agents } = useAgents();

  // ── 统管状态 ──
  const [saving, setSaving] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<SettingSectionId>("general");
  const [currentView, setCurrentView] = useState<ViewState>("main_settings");
  const [editingAgentId, setEditingAgentId] = useState<string | null>(null);
  const [direction, setDirection] = useState<1 | -1>(1);

  useEffect(() => {
    if (!settings) fetchSettings();
  }, [settings, fetchSettings]);

  const handleClose = () => {
    setCurrentView("main_settings");
    setEditingAgentId(null);
    onClose();
  };

  const handleUpdate = async (key: string, value: string) => {
    setSaving(key);
    try {
      await updateSetting(key, value);
    } catch (err) {
      console.error("Failed to update setting:", err);
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
    { id: "plugins", label: t("settings.plugins.title"), icon: Puzzle },
    { id: "about", label: t("settings.about.title"), icon: Info },
  ];

  const viewTitle =
    currentView === "main_settings"
      ? t("settings.title")
      : currentView === "agent_list"
        ? t("settings.ai.agents.title")
        : (agents.find((a) => a.id === editingAgentId)?.name ?? t("settings.ai.agents.title"));

  const goToMainSettings = () => {
    setDirection(-1);
    setEditingAgentId(null);
    setCurrentView("main_settings");
  };
  const goToAgentList = () => {
    setDirection(-1);
    setEditingAgentId(null);
    setCurrentView("agent_list");
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

  const hasAdvanced = SECTIONS_WITH_ADVANCED.includes(activeSection);

  return (
    <Panel isOpen={isOpen} onClose={handleClose} title={viewTitle} width="700px" height="min(680px, 82vh)" variant="center">
      <div style={{ position: "relative", height: "100%", overflow: "hidden" }}>
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
                  width: "140px", flexShrink: 0,
                  borderRight: "1px solid rgba(0, 0, 0, 0.06)",
                  paddingRight: "16px", marginRight: "16px",
                  height: "100%", overflow: "hidden",
                }}>
                  {navItems.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => setActiveSection(item.id)}
                      style={{
                        display: "flex", alignItems: "center", gap: "8px",
                        width: "100%", padding: "10px 12px",
                        borderRadius: "var(--radius-md)", border: "none",
                        background: activeSection === item.id ? "var(--bg-level-2)" : "transparent",
                        cursor: "pointer", fontSize: "14px",
                        color: activeSection === item.id ? "var(--text-level-1)" : "var(--text-level-3)",
                        textAlign: "left", marginBottom: "4px",
                      }}
                    >
                      <item.icon style={{ width: "16px", height: "16px" }} />
                      <span>{item.label}</span>
                    </button>
                  ))}
                </nav>

                {/* 右侧内容 - 独立滚动 */}
                <div style={{
                  flex: 1, minWidth: 0,
                  overflowY: "auto", overflowX: "hidden",
                  height: "100%", paddingRight: "4px",
                  scrollbarGutter: "stable",
                }}>
                  {/* 基础区块（默认展示） */}
                  <BasicSettingsView
                    {...viewProps}
                    activeSection={activeSection}
                    agents={agents}
                    onManageAgents={() => {
                      setDirection(1);
                      setCurrentView("agent_list");
                    }}
                  />

                  {/* 高级区块（model/ai 深水区参数，全量直接展示，无折叠） */}
                  {hasAdvanced && (
                    <div style={{ marginTop: "20px", paddingTop: "16px", borderTop: "1px solid var(--border-primary)" }}>
                      <AdvancedSettingsView
                        {...viewProps}
                        activeSection={activeSection}
                        agents={agents}
                        onManageAgents={() => {
                          setDirection(1);
                          setCurrentView("agent_list");
                        }}
                      />
                    </div>
                  )}
                </div>
              </div>
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
