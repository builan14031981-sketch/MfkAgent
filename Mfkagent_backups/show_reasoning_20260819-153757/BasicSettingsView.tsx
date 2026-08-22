"use client";
/**
 * BasicSettingsView —— 基础区块视图（字段级边界重构后）
 *
 * 职责：根据 activeSection 渲染对应 section 的"基础"部分。
 *
 * 字段级边界契约（V2 重构）：
 * - 通用(General) Tab：全部归属基础（主题/语言/字体/强调色/首页主题/首页台词），不再隐藏。
 * - 模型(Model) Tab：默认模型/默认推理程度 + Provider 卡片基础配置（API Key + 模型 Chip）。
 *   深水区参数（Base URL 覆盖/自定义模型/温度/备用识图）下沉到 AdvancedSettingsView。
 * - 本组件不持有业务状态，所有数据通过 props 注入（统管 props 单向数据流不变）。
 */
import { useState, useMemo, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Plus, Trash2, Globe, ChevronDown, ChevronRight, Check } from "lucide-react";
import { ExtensionPanel } from "./ExtensionPanel";
import { FeishuSettingsPanel } from "./FeishuSettingsPanel";
import { SecurityView } from "./security/SecurityView";
import { ModelProvidersBasic } from "./ModelConfigSection";
import { ProxySettingsSection } from "./ProxySettingsSection";
import { FALLBACK_MODEL_ID } from "@/lib/modelDefaults";
import { SwitchButton } from "@/components/SwitchButton";
import { FONT_FAMILY_MAP } from "@/components/providers";
import { useVisibleModels } from "@/hooks/useVisibleModels";
import type { Model } from "@/hooks/useModels";
import type { Agent } from "@/hooks/useAgents";

/** 设置导航项 id 联合类型（与 SettingsPanel 共享，保证 activeSection 类型安全） */
export type SettingSectionId = "general" | "model" | "ai" | "security" | "extensions" | "about" | "archive";

/** 统管状态注入 props（由 SettingsPanel 下发） */
export interface SettingsViewProps {
  settings: Record<string, string> | null;
  saving: string | null;
  onUpdate: (key: string, value: string) => void;
  models: Model[];
  modelsLoading: boolean;
  t: (key: string) => string;
}

/** AdvancedSettingsView 额外需要的 props */
export interface AdvancedSettingsViewProps extends SettingsViewProps {
  agents: Agent[];
  onManageAgents: () => void;
  onManageSubAgents?: () => void;
}

/** Provider ID → 中文展示名映射（与 ModelSelector 保持一致） */
const PROVIDER_NAMES: Record<string, string> = {
  deepseek: "DeepSeek",
  qwen: "通义千问",
  google: "Google Gemini",
  glm: "智谱 AI",
  moonshot: "Moonshot",
  freellmapi: "FreeLLMAPI",
  mimo: "小米 MiMo",
  wenxin: "百度文心",
  spark: "讯飞星火",
  minimax: "MiniMax",
  siliconflow: "硅基流动",
};

/** 预设 Agent 排序优先级 */
const AGENT_ORDER = ["coder", "frontend_ui", "backend", "general", "analyst", "writer"];

/**
 * V2 视觉主题定义（预览色为主题本体字面值，仅供设置页展示，
 * 运行时配色以 src/styles/tokens.css 为唯一权威源）。
 */
const VISUAL_THEMES: Array<{
  id: "studio-graphite" | "terminal" | "warm-minimal";
  nameKey: string;
  descKey: string;
  preview: { bg: string; surface: string; card: string; accent: string; text: string; border: string };
}> = [
  {
    id: "studio-graphite",
    nameKey: "settings.general.visualTheme.studioGraphite",
    descKey: "settings.general.visualTheme.studioGraphiteDesc",
    preview: { bg: "#ffffff", surface: "#f6f6f8", card: "#f7f7f9", accent: "#26282d", text: "#1a1b1e", border: "#e4e5e9" },
  },
  {
    id: "terminal",
    nameKey: "settings.general.visualTheme.terminal",
    descKey: "settings.general.visualTheme.terminalDesc",
    preview: { bg: "#1e1e1e", surface: "#252526", card: "#2d2d30", accent: "#3794ff", text: "#e7e7e7", border: "#3c3c40" },
  },
  {
    id: "warm-minimal",
    nameKey: "settings.general.visualTheme.warmMinimal",
    descKey: "settings.general.visualTheme.warmMinimalDesc",
    preview: { bg: "#faf8f5", surface: "#f2eee9", card: "#f5f1ec", accent: "#a56f45", text: "#2b2825", border: "#e5e0d8" },
  },
];

/** 单个主题预览卡：背景层级展示（侧边栏/主区/卡片）+ Accent 展示 */
function ThemePreviewCard({
  theme,
  selected,
  disabled,
  t,
  onSelect,
}: {
  theme: (typeof VISUAL_THEMES)[number];
  selected: boolean;
  disabled: boolean;
  t: (key: string) => string;
  onSelect: (id: string) => void;
}) {
  const p = theme.preview;
  return (
    <button
      onClick={() => onSelect(theme.id)}
      disabled={disabled}
      aria-pressed={selected}
      style={{
        flex: 1,
        minWidth: 0,
        padding: 0,
        borderRadius: "var(--radius-sm)",
        border: selected ? "1.5px solid var(--color-primary)" : "1px solid var(--border-primary)",
        background: "var(--bg-level-2)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.6 : 1,
        overflow: "hidden",
        textAlign: "left",
        transition: "border-color var(--transition-fast)",
      }}
    >
      {/* 预览区：层级结构示意（侧边栏 + 主区卡片 + accent 按钮/文字） */}
      <div style={{ display: "flex", height: 64, borderBottom: `1px solid ${p.border}` , background: p.bg }}>
        {/* 侧边栏层 */}
        <div style={{ width: "30%", background: p.surface, borderRight: `1px solid ${p.border}`, padding: "6px 5px", display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ height: 5, width: "85%", borderRadius: 2, background: p.card }} />
          <div style={{ height: 5, width: "65%", borderRadius: 2, background: selected ? p.accent : p.card, opacity: selected ? 0.9 : 1 }} />
          <div style={{ height: 5, width: "75%", borderRadius: 2, background: p.card }} />
        </div>
        {/* 主区层：卡片 + 文字行 + accent 按钮 */}
        <div style={{ flex: 1, padding: "7px 8px", display: "flex", flexDirection: "column", gap: 5 }}>
          <div style={{ height: 6, width: "55%", borderRadius: 2, background: p.text, opacity: 0.85 }} />
          <div style={{ flex: 1, borderRadius: 3, background: p.card, border: `1px solid ${p.border}` }} />
          <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
            <div style={{ height: 8, width: 26, borderRadius: 3, background: p.card, border: `1px solid ${p.border}` }} />
            <div style={{ height: 8, width: 26, borderRadius: 3, background: p.accent }} />
          </div>
        </div>
      </div>
      {/* 名称 + 适用场景说明 */}
      <div style={{ padding: "8px 10px", display: "flex", alignItems: "flex-start", gap: 6 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-level-1)", display: "flex", alignItems: "center", gap: 5 }}>
            {/* Accent 展示点 */}
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: p.accent, flexShrink: 0 }} />
            {t(theme.nameKey)}
          </div>
          <div style={{ fontSize: 11, color: "var(--text-level-3)", marginTop: 2, lineHeight: 1.4 }}>
            {t(theme.descKey)}
          </div>
        </div>
        {selected && (
          <span style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            width: 16, height: 16, borderRadius: "50%", flexShrink: 0,
            background: "var(--color-primary)", marginTop: 1,
          }}>
            <Check style={{ width: 10, height: 10, color: "var(--text-on-primary)" }} strokeWidth={2.5} />
          </span>
        )}
      </div>
    </button>
  );
}

/**
 * 实验主题定义（预览色为主题本体字面值，仅供设置页展示；
 * 运行时配色以 src/styles/tokens.css 为唯一权威源）。
 */
const EXPERIMENTAL_THEMES: Array<{
  id: string;
  nameKey: string;
  descKey: string;
  preview: {
    app: string; surface: string; card: string; elevated: string;
    text: string; textMuted: string; border: string; accent: string; onAccent: string;
    bubble: string; bubbleBorder: string;
  };
}> = [
  {
    id: "titanium",
    nameKey: "settings.general.experimentalTheme.titanium",
    descKey: "settings.general.experimentalTheme.titaniumDesc",
    preview: { app: "#e1e3e6", surface: "#d6d9dd", card: "#edeff1", elevated: "#f5f6f8", text: "#1f2328", textMuted: "#8b929c", border: "#c9cdd3", accent: "#4d6a8a", onAccent: "#ffffff", bubble: "#dde2e7", bubbleBorder: "rgba(77,106,138,0.22)" },
  },
  {
    id: "paper",
    nameKey: "settings.general.experimentalTheme.paper",
    descKey: "settings.general.experimentalTheme.paperDesc",
    preview: { app: "#f4f1ea", surface: "#ece8de", card: "#faf7f0", elevated: "#f0ebdf", text: "#2a2721", textMuted: "#948d7e", border: "#e0dacc", accent: "#9c422a", onAccent: "#fdf8f4", bubble: "#f2e9e0", bubbleBorder: "rgba(156,66,42,0.22)" },
  },
  {
    id: "midnight",
    nameKey: "settings.general.experimentalTheme.midnight",
    descKey: "settings.general.experimentalTheme.midnightDesc",
    preview: { app: "#0b0e14", surface: "#10141d", card: "#161b26", elevated: "#1d2331", text: "#dde3ec", textMuted: "#5c6577", border: "#232a3a", accent: "#6d8fbf", onAccent: "#f0f4fa", bubble: "#222b3b", bubbleBorder: "rgba(109,143,191,0.25)" },
  },
  {
    id: "mono",
    nameKey: "settings.general.experimentalTheme.mono",
    descKey: "settings.general.experimentalTheme.monoDesc",
    preview: { app: "#111112", surface: "#171718", card: "#1d1d1f", elevated: "#252527", text: "#e5e5e6", textMuted: "#636366", border: "#2a2a2d", accent: "#e5e5e6", onAccent: "#111112", bubble: "#2d2d2f", bubbleBorder: "rgba(229,229,230,0.25)" },
  },
  {
    id: "aurora",
    nameKey: "settings.general.experimentalTheme.aurora",
    descKey: "settings.general.experimentalTheme.auroraDesc",
    preview: { app: "#0d1210", surface: "#121815", card: "#18201c", elevated: "#1f2923", text: "#dfe7e2", textMuted: "#5d6961", border: "#24302a", accent: "#5fa893", onAccent: "#0e1412", bubble: "#21302a", bubbleBorder: "rgba(95,168,147,0.25)" },
  },
  // 2026-08-13 主题整理：原官方 obsidian / studio 降级至实验区；
  // Studio Accent 对比样张验收完毕，石墨（studio-graphite）转正，薰衣草/深蓝移除。
  {
    id: "obsidian",
    nameKey: "settings.general.visualTheme.obsidian",
    descKey: "settings.general.visualTheme.obsidianDesc",
    preview: { app: "#0f1114", surface: "#15181d", card: "#1b1f26", elevated: "#222732", text: "#e8eaed", textMuted: "#6a7180", border: "#262b34", accent: "#5e6ad2", onAccent: "#f2f5f9", bubble: "#222732", bubbleBorder: "rgba(94,106,210,0.35)" },
  },
  {
    id: "studio",
    nameKey: "settings.general.visualTheme.studio",
    descKey: "settings.general.visualTheme.studioDesc",
    preview: { app: "#ffffff", surface: "#f6f6f8", card: "#f7f7f9", elevated: "#efeff2", text: "#1a1b1e", textMuted: "#8a8f98", border: "#e4e5e9", accent: "#0a6cd6", onAccent: "#ffffff", bubble: "#ededef", bubbleBorder: "rgba(10,108,214,0.18)" },
  },
  // 2026-08-13 第三方候选（对比预览，验收后筛选转正）：Clay / Indigo / Graphite Dark
  {
    id: "clay",
    nameKey: "settings.general.experimentalTheme.clay",
    descKey: "settings.general.experimentalTheme.clayDesc",
    preview: { app: "#f5f4ed", surface: "#ece9df", card: "#faf9f5", elevated: "#e8e5da", text: "#1a191b", textMuted: "#87867f", border: "#ddd9cc", accent: "#c96442", onAccent: "#fdfcf9", bubble: "#e9e2d4", bubbleBorder: "rgba(201,100,66,0.22)" },
  },
  {
    id: "indigo",
    nameKey: "settings.general.experimentalTheme.indigo",
    descKey: "settings.general.experimentalTheme.indigoDesc",
    preview: { app: "#08090a", surface: "#101113", card: "#141516", elevated: "#1b1c1d", text: "#f7f8f8", textMuted: "#6d7076", border: "#26272b", accent: "#5e6ad2", onAccent: "#ffffff", bubble: "#22262b", bubbleBorder: "rgba(94,106,210,0.30)" },
  },
  {
    id: "graphite-dark",
    nameKey: "settings.general.experimentalTheme.graphiteDark",
    descKey: "settings.general.experimentalTheme.graphiteDarkDesc",
    preview: { app: "#0e0f10", surface: "#131416", card: "#18191b", elevated: "#1f2023", text: "#e7e7e8", textMuted: "#6a6c70", border: "#26272a", accent: "#3a3d43", onAccent: "#ffffff", bubble: "#222327", bubbleBorder: "rgba(255,255,255,0.12)" },
  },
];

/**
 * 微型工作台预览：完整渲染 Sidebar / Chat / Input 三区域整体效果，
 * 供实验主题选择时展示（色值均为预览专用字面值）。
 */
function MiniWorkspacePreview({ p }: { p: (typeof EXPERIMENTAL_THEMES)[number]["preview"] }) {
  return (
    <div style={{ display: "flex", height: 116, background: p.app, overflow: "hidden" }}>
      {/* Sidebar 效果 */}
      <div style={{ width: "32%", background: p.surface, borderRight: `1px solid ${p.border}`, padding: "7px 6px", display: "flex", flexDirection: "column", gap: 4, flexShrink: 0 }}>
        <div style={{ height: 9, borderRadius: 3, background: p.card, marginBottom: 3 }} />
        <div style={{ height: 7, borderRadius: 3, background: p.card }} />
        {/* 激活会话行：左侧 accent 指示条 */}
        <div style={{ height: 7, borderRadius: 3, background: p.elevated, position: "relative", overflow: "hidden" }}>
          <span style={{ position: "absolute", left: 1, top: 1, bottom: 1, width: 2, borderRadius: 1, background: p.accent }} />
        </div>
        <div style={{ height: 7, borderRadius: 3, background: p.card }} />
        <div style={{ flex: 1 }} />
        <div style={{ height: 7, width: "60%", borderRadius: 3, background: p.card }} />
      </div>
      {/* Chat + Input 效果 */}
      <div style={{ flex: 1, minWidth: 0, padding: "8px 9px 7px", display: "flex", flexDirection: "column", gap: 6 }}>
        {/* 用户消息（右对齐 tint 气泡，与运行时 tokens.css 方案B 一致） */}
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <div style={{ width: "46%", height: 14, borderRadius: 5, background: p.bubble, border: `1px solid ${p.bubbleBorder}`, padding: "3px 5px" }}>
            <div style={{ height: 3, width: "75%", borderRadius: 1.5, background: p.text, opacity: 0.75 }} />
            <div style={{ height: 3, width: "45%", borderRadius: 1.5, background: p.text, opacity: 0.75, marginTop: 2 }} />
          </div>
        </div>
        {/* AI 回复（无气泡平铺文字行） */}
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          <div style={{ height: 3, width: "30%", borderRadius: 1.5, background: p.textMuted }} />
          <div style={{ height: 3, width: "88%", borderRadius: 1.5, background: p.text, opacity: 0.75 }} />
          <div style={{ height: 3, width: "72%", borderRadius: 1.5, background: p.text, opacity: 0.75 }} />
          <div style={{ height: 16, width: "58%", borderRadius: 3, background: p.card, border: `1px solid ${p.border}`, marginTop: 2 }} />
        </div>
        <div style={{ flex: 1 }} />
        {/* Input 输入区 */}
        <div style={{ height: 22, borderRadius: 5, background: p.card, border: `1px solid ${p.border}`, display: "flex", alignItems: "center", padding: "0 5px", gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", border: `1px solid ${p.textMuted}`, flexShrink: 0 }} />
          <div style={{ flex: 1, height: 3, width: "40%", borderRadius: 1.5, background: p.textMuted, opacity: 0.7 }} />
          <span style={{ width: 13, height: 13, borderRadius: 3, background: p.accent, flexShrink: 0 }} />
        </div>
      </div>
    </div>
  );
}

/**
 * 实验主题选择器（字体选择式交互）：
 * 收起态 = 类 select 字段（展示当前实验主题）；
 * 点击展开 = 完整工作台预览卡列表，点击即切换。
 */
function ExperimentalThemePicker({
  currentThemeId,
  saving,
  t,
  onSelect,
}: {
  currentThemeId: string;
  saving: boolean;
  t: (key: string) => string;
  onSelect: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(() => {
    try {
      return localStorage.getItem("mfk_theme_picker_expanded") === "true";
    } catch {
      return false;
    }
  });
  const toggleExpanded = () => {
    setExpanded((prev) => {
      const next = !prev;
      try { localStorage.setItem("mfk_theme_picker_expanded", String(next)); } catch { /* noop */ }
      return next;
    });
  };
  const current = EXPERIMENTAL_THEMES.find((theme) => theme.id === currentThemeId);

  return (
    <div>
      {/* 触发字段：仿字体选择的 select 外观，点击展开/收起 */}
      <button
        onClick={toggleExpanded}
        disabled={saving}
        style={{
          width: "100%",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
          padding: "8px 12px",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-primary)",
          background: "var(--bg-level-2)",
          cursor: saving ? "not-allowed" : "pointer",
          fontSize: "13px",
          color: current ? "var(--text-level-2)" : "var(--text-level-4)",
          opacity: saving ? 0.7 : 1,
          transition: "border-color var(--transition-fast)",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          {current && (
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: current.preview.accent, flexShrink: 0, border: "1px solid var(--border-primary)" }} />
          )}
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {current ? t(current.nameKey) : t("settings.general.experimentalTheme.placeholder")}
          </span>
        </span>
        <ChevronDown style={{
          width: 14, height: 14, flexShrink: 0, color: "var(--text-level-4)",
          transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform var(--transition-fast)",
        }} />
      </button>

      {/* 展开区：完整预览卡（2 列），点击切换 */}
      {expanded && (
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10,
          marginTop: 10, animation: "fadeIn 0.2s ease",
        }}>
          {EXPERIMENTAL_THEMES.map((theme) => {
            const selected = theme.id === currentThemeId;
            return (
              <button
                key={theme.id}
                onClick={() => onSelect(theme.id)}
                disabled={saving}
                aria-pressed={selected}
                style={{
                  padding: 0,
                  borderRadius: "var(--radius-sm)",
                  border: selected ? "1.5px solid var(--color-primary)" : "1px solid var(--border-primary)",
                  background: "var(--bg-level-2)",
                  cursor: saving ? "not-allowed" : "pointer",
                  opacity: saving ? 0.6 : 1,
                  overflow: "hidden",
                  textAlign: "left",
                  transition: "border-color var(--transition-fast)",
                }}
              >
                <MiniWorkspacePreview p={theme.preview} />
                <div style={{ padding: "7px 10px", display: "flex", alignItems: "flex-start", gap: 6, borderTop: `1px solid var(--border-secondary)` }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-level-1)" }}>{t(theme.nameKey)}</div>
                    <div style={{ fontSize: 11, color: "var(--text-level-3)", marginTop: 2, lineHeight: 1.4 }}>{t(theme.descKey)}</div>
                  </div>
                  {selected && (
                    <span style={{
                      display: "flex", alignItems: "center", justifyContent: "center",
                      width: 16, height: 16, borderRadius: "50%", flexShrink: 0,
                      background: "var(--color-primary)", marginTop: 1,
                    }}>
                      <Check style={{ width: 10, height: 10, color: "var(--text-on-primary)" }} strokeWidth={2.5} />
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* 实验主题激活时：提供返回官方主题的快捷入口 */}
      {current && (
        <button
          onClick={() => onSelect("studio-graphite")}
          disabled={saving}
          style={{
            marginTop: 8, padding: "4px 0", border: "none", background: "transparent",
            cursor: "pointer", fontSize: 12, color: "var(--text-level-3)",
            textDecoration: "underline", textUnderlineOffset: 3,
          }}
        >
          {t("settings.general.experimentalTheme.backToOfficial")}
        </button>
      )}
    </div>
  );
}

function getSortedActiveAgents(agents: { id: string; name: string; status: string }[]) {
  return [...agents]
    .sort((a, b) => {
      const ai = AGENT_ORDER.indexOf(a.id);
      const bi = AGENT_ORDER.indexOf(b.id);
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    })
    .filter((agent) => agent.status === "active");
}

const inputStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-primary)",
  background: "var(--bg-level-2)",
  fontSize: "13px",
  color: "var(--text-level-2)",
  outline: "none",
};

/** 字体选项：displayFont 用于以本尊字体渲染选项名（原生 <select> 的 option 在 Windows 上无法设字体） */
const FONT_OPTIONS: Array<{ value: string; labelKey: string }> = [
  { value: "system", labelKey: "settings.general.font.system" },
  { value: "source-han-sans", labelKey: "settings.general.font.source-han-sans" },
  { value: "lxgw-wenkai", labelKey: "settings.general.font.lxgw-wenkai" },
  { value: "ibm-plex-sans", labelKey: "settings.general.font.ibm-plex-sans" },
];

/** 字体选择器：自定义下拉，每个选项名用对应字体渲染（所见即所得） */
function FontFamilyDropdown({
  value,
  onSelect,
  disabled,
  t,
}: {
  value: string;
  onSelect: (value: string) => void;
  disabled: boolean;
  t: (key: string) => string;
}) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 });
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  const current = FONT_OPTIONS.find((o) => o.value === value) ?? FONT_OPTIONS[0];

  // 预载霞鹜文楷 webfont（仅供选项预览；其余字体已本地自托管：fontsource 包 + public/fonts）
  useEffect(() => {
    if (document.getElementById("font-preview-cdn")) return;
    const link = document.createElement("link");
    link.id = "font-preview-cdn";
    link.rel = "stylesheet";
    link.href = "https://cdn.jsdelivr.net/npm/lxgw-wenkai-webfont@1.7.0/style.css";
    document.head.appendChild(link);
  }, []);

  // 计算下拉位置（向下弹出）
  useEffect(() => {
    if (!open || !btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    setPos({ top: rect.bottom + 4, left: rect.left, width: Math.max(rect.width, 220) });
  }, [open]);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (popRef.current?.contains(target)) return;
      if (btnRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Esc 关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        style={{
          ...inputStyle,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "8px",
          minWidth: "160px",
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.6 : 1,
        }}
      >
        <span
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            fontFamily: FONT_FAMILY_MAP[current.value],
          }}
        >
          {t(current.labelKey)}
        </span>
        <ChevronDown style={{ width: "14px", height: "14px", color: "var(--text-level-4)", flexShrink: 0 }} />
      </button>

      {open && createPortal(
        <div
          ref={popRef}
          data-portal-popover
          style={{
            position: "fixed",
            top: pos.top,
            left: pos.left,
            width: pos.width,
            padding: "6px",
            borderRadius: "var(--radius-xl)",
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-secondary)",
            boxShadow: "var(--shadow-lg)",
            zIndex: 9999,
          }}
        >
          {FONT_OPTIONS.map((opt) => {
            const active = opt.value === value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  onSelect(opt.value);
                  setOpen(false);
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  width: "100%",
                  padding: "7px 10px",
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  fontSize: "13px",
                  fontWeight: active ? 600 : 400,
                  color: active ? "var(--color-primary)" : "var(--text-level-2)",
                  borderRadius: "var(--radius-sm)",
                  textAlign: "left",
                  fontFamily: FONT_FAMILY_MAP[opt.value],
                }}
              >
                <span style={{ width: "14px", flexShrink: 0 }}>
                  {active && <Check style={{ width: "14px", height: "14px" }} />}
                </span>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {t(opt.labelKey)}
                </span>
              </button>
            );
          })}
        </div>,
        document.body
      )}
    </>
  );
}

/** 自定义台词编辑器：最多 5 条，逐条输入/删除，保存时以 JSON 数组写入设置 */
function GreetingCustomEditor({
  value,
  saving,
  onSave,
  t,
}: {
  value: string;
  saving: boolean;
  onSave: (key: string, value: string) => void;
  t: (key: string) => string;
}) {
  const [draft, setDraft] = useState<string[]>(() => {
    try {
      const parsed: unknown = JSON.parse(value);
      if (Array.isArray(parsed)) return parsed.filter((x): x is string => typeof x === "string");
    } catch {
      /* ignore malformed */
    }
    return [];
  });

  const MAX_CHARS = 50;
  const clean = draft.map((s) => s.trim()).filter(Boolean);

  const handleChange = (index: number, text: string) => {
    setDraft((prev) => prev.map((s, i) => (i === index ? text.slice(0, MAX_CHARS) : s)));
  };
  const handleAdd = () => {
    if (clean.length >= 5) return;
    setDraft((prev) => [...prev, ""]);
  };
  const handleRemove = (index: number) => {
    setDraft((prev) => prev.filter((_, i) => i !== index));
  };
  const handleSave = () => {
    onSave("custom_greetings", JSON.stringify(clean.map((s) => s.slice(0, MAX_CHARS))));
  };

  return (
    <div>
      {draft.length === 0 && (
        <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: "0 0 8px 0" }}>
          {t("settings.general.greeting.customEmpty")}
        </p>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginBottom: "10px" }}>
        {draft.map((item, index) => (
          <div key={index} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <input
              value={item}
              onChange={(e) => handleChange(index, e.target.value)}
              maxLength={50}
              placeholder={t("settings.general.greeting.customPlaceholder")}
              style={{
                flex: 1, padding: "7px 10px", borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
                fontSize: "13px", color: "var(--text-level-2)", outline: "none",
              }}
            />
            <button
              onClick={() => handleRemove(index)}
              title={t("common.delete")}
              style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                width: 28, height: 28, borderRadius: "var(--radius-sm)", border: "none",
                background: "transparent", cursor: "pointer", color: "var(--text-level-4)",
              }}
            >
              <Trash2 style={{ width: 14, height: 14 }} />
            </button>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <button
          onClick={handleAdd}
          disabled={clean.length >= 5}
          style={{
            display: "flex", alignItems: "center", gap: "5px", padding: "6px 12px",
            borderRadius: "var(--radius-sm)", border: "1px dashed var(--border-primary)",
            background: "transparent", cursor: clean.length >= 5 ? "not-allowed" : "pointer",
            fontSize: "12px", color: "var(--text-level-3)", opacity: clean.length >= 5 ? 0.5 : 1,
          }}
        >
          <Plus style={{ width: 13, height: 13 }} />
          {t("settings.general.greeting.customAdd")}
        </button>
        <button
          onClick={handleSave}
          disabled={saving || JSON.stringify(clean) === value}
          style={{
            padding: "6px 16px", borderRadius: "var(--radius-sm)", border: "none",
            background: "var(--color-primary)", color: "#fff",
            cursor: saving ? "not-allowed" : "pointer", fontSize: "12px", fontWeight: 500,
            opacity: saving ? 0.7 : 1,
          }}
        >
          {saving ? t("common.saving") : t("common.save")}
        </button>
        <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>{clean.length}/5</span>
      </div>
    </div>
  );
}

// ── general 基础区块：主题 / 语言 / 字体 / 强调色 / 首页主题 / 首页台词（全量上移）──
function GeneralBasic(props: SettingsViewProps) {
  const { settings, saving, onUpdate, t } = props;
  return (
    <>
      {/* 视觉主题（V2：专业主题预览卡，替代 light/dark/system 分段开关） */}
      <div style={{ marginBottom: "18px" }}>
        <div style={{ marginBottom: "10px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.general.theme.title")}
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
            {t("settings.general.visualTheme.desc")}
          </p>
        </div>
        <div style={{ display: "flex", gap: "10px" }}>
          {VISUAL_THEMES.map((theme) => (
            <ThemePreviewCard
              key={theme.id}
              theme={theme}
              selected={(settings?.visual_theme || "studio-graphite") === theme.id}
              disabled={saving === "visual_theme"}
              t={t}
              onSelect={(id) => onUpdate("visual_theme", id)}
            />
          ))}
        </div>
      </div>

      {/* 实验主题（探索阶段，完整工作台预览，点击展开切换） */}
      <div style={{ marginBottom: "18px" }}>
        <div style={{ marginBottom: "10px" }}>
          <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.general.experimentalTheme.title")}
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
            {t("settings.general.experimentalTheme.desc")}
          </p>
        </div>
        <ExperimentalThemePicker
          currentThemeId={settings?.visual_theme || "studio-graphite"}
          saving={saving === "visual_theme"}
          t={t}
          onSelect={(id) => onUpdate("visual_theme", id)}
        />
      </div>

      {/* 网络代理（可配置化：auto/manual/off + 测试） */}
      <ProxySettingsSection
        settings={settings}
        saving={saving}
        onUpdate={onUpdate}
        t={t}
      />

      {/* 语言 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "18px" }}>
        <div>
          <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.general.language.title")}
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
            {t("settings.general.language.desc")}
          </p>
        </div>
        <div style={{ display: "flex", padding: "3px", borderRadius: "var(--radius-sm)", background: "var(--bg-level-2)" }}>
          {[
            { value: "zh-CN", label: t("settings.general.language.zh-CN") },
            { value: "en-US", label: t("settings.general.language.en-US") },
          ].map((lang) => (
            <button
              key={lang.value}
              onClick={() => onUpdate("language", lang.value)}
              disabled={saving === "language"}
              style={{
                flex: 1, padding: "6px 14px", borderRadius: "var(--radius-xs)", border: "none",
                background: settings?.language === lang.value ? "var(--bg-level-1)" : "transparent",
                cursor: "pointer", fontSize: "13px", whiteSpace: "nowrap",
                color: settings?.language === lang.value ? "var(--text-level-1)" : "var(--text-level-3)",
                opacity: saving === "language" ? 0.7 : 1,
              }}
            >
              {lang.label}
            </button>
          ))}
        </div>
      </div>

      {/* 字体风格 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
        <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
          {t("settings.general.font.title")}
        </h3>
        <FontFamilyDropdown
          value={settings?.font_family || "system"}
          onSelect={(v) => onUpdate("font_family", v)}
          disabled={saving === "font_family"}
          t={t}
        />
      </div>

      {/* 字体实时预览：以当前所选字体渲染 */}
      <div
        style={{
          marginBottom: "18px",
          padding: "12px 14px",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-primary)",
          background: "var(--bg-level-2)",
          fontFamily: FONT_FAMILY_MAP[settings?.font_family || "system"],
          color: "var(--text-level-2)",
        }}
      >
        <div style={{ fontSize: "15px", lineHeight: 1.6 }}>
          The quick brown fox jumps over the lazy dog 0123456789
        </div>
        <div style={{ fontSize: "14px", lineHeight: 1.6, color: "var(--text-level-3)" }}>
          你好，世界！字体预览 Font Preview
        </div>
      </div>

      {/* 强调色多选已于 V2.0 废除：每个视觉主题自带唯一 accent，见上方主题选择。 */}

      {/* 首页启动主题（规则控制；主题管理/切换留在首页） */}
      <div style={{ marginBottom: "18px" }}>
        <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
          {t("settings.general.heroTheme.title")}
        </h3>
        <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 12px 0" }}>
          {t("settings.general.heroTheme.desc")}
        </p>

        {/* 启用首页主题入口 */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
          <div>
            <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
              {t("settings.general.heroTheme.entry")}
            </h4>
            <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "1px 0 0 0" }}>
              {t("settings.general.heroTheme.entryDesc")}
            </p>
          </div>
          <SwitchButton
            checked={settings?.hero_entry !== "0"}
            disabled={saving === "hero_entry"}
            onChange={(v) => onUpdate("hero_entry", v ? "1" : "0")}
          />
        </div>

        {/* 启动时随机主题 */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
          <div>
            <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
              {t("settings.general.heroTheme.random")}
            </h4>
            <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "1px 0 0 0" }}>
              {t("settings.general.heroTheme.randomDesc")}
            </p>
          </div>
          <SwitchButton
            checked={settings?.hero_random !== "0"}
            disabled={saving === "hero_random"}
            onChange={(v) => onUpdate("hero_random", v ? "1" : "0")}
          />
        </div>

        {/* 随机范围 */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
              {t("settings.general.heroTheme.scope")}
            </h4>
            <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "1px 0 0 0" }}>
              {t("settings.general.heroTheme.scopeDesc")}
            </p>
          </div>
          <div style={{ display: "flex", padding: "3px", borderRadius: "var(--radius-sm)", background: "var(--bg-level-2)" }}>
            {[
              { value: "all", label: t("settings.general.heroTheme.scopeAll") },
              { value: "favorites", label: t("settings.general.heroTheme.scopeFavorites") },
            ].map((opt) => (
              <button
                key={opt.value}
                onClick={() => onUpdate("hero_random_scope", opt.value)}
                disabled={saving === "hero_random_scope"}
                style={{
                  flex: 1, padding: "6px 14px", borderRadius: "var(--radius-xs)", border: "none",
                  background: (settings?.hero_random_scope || "all") === opt.value ? "var(--bg-level-1)" : "transparent",
                  cursor: "pointer", fontSize: "13px", whiteSpace: "nowrap",
                  color: (settings?.hero_random_scope || "all") === opt.value ? "var(--text-level-1)" : "var(--text-level-3)",
                  opacity: saving === "hero_random_scope" ? 0.7 : 1,
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 首页台词（欢迎语）规则 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "18px" }}>
        <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
          {t("settings.general.greeting.title")}
        </h3>
        <div style={{ display: "flex", padding: "3px", borderRadius: "var(--radius-sm)", background: "var(--bg-level-2)" }}>
          {([
            { value: "builtin", label: t("settings.general.greeting.builtin") },
            { value: "custom", label: t("settings.general.greeting.custom") },
            { value: "off", label: t("settings.general.greeting.off") },
          ] as const).map((opt) => {
            const active = (settings?.greeting_mode ?? "builtin") === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => onUpdate("greeting_mode", opt.value)}
                disabled={saving === "greeting_mode"}
                style={{
                  flex: 1, padding: "6px 14px", borderRadius: "var(--radius-xs)", border: "none",
                  background: active ? "var(--bg-level-1)" : "transparent",
                  cursor: "pointer", fontSize: "13px", whiteSpace: "nowrap",
                  color: active ? "var(--text-level-1)" : "var(--text-level-3)",
                  opacity: saving === "greeting_mode" ? 0.7 : 1,
                }}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 自定义台词编辑（仅 custom 模式显示） */}
      {(settings?.greeting_mode ?? "builtin") === "custom" && (
        <div style={{ marginBottom: "18px" }}>
          <GreetingCustomEditor
            value={settings?.custom_greetings ?? "[]"}
            saving={saving === "custom_greetings"}
            onSave={onUpdate}
            t={t}
          />
        </div>
      )}
    </>
  );
}

/** 按 provider 分组的自定义模型下拉（与聊天页 ModelSelector 视觉一致） */
function GroupedModelDropdown({
  models,
  selectedId,
  onSelect,
  disabled,
  loading,
}: {
  models: Model[];
  selectedId: string;
  onSelect: (id: string) => void;
  disabled: boolean;
  loading: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 });
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem("mfk_model_dropdown_collapsed");
      return saved ? new Set(JSON.parse(saved)) : new Set();
    } catch {
      return new Set();
    }
  });
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  const groups = useMemo(() => {
    const seen = new Set<string>();
    const list: { providerId: string; providerName: string; models: Model[] }[] = [];
    for (const m of models) {
      if (!seen.has(m.provider)) {
        seen.add(m.provider);
        list.push({ providerId: m.provider, providerName: PROVIDER_NAMES[m.provider] || m.provider, models: [] });
      }
      const g = list.find((x) => x.providerId === m.provider);
      if (g) g.models.push(m);
    }
    return list;
  }, [models]);

  // 2026-08-11 增强：当前选中的 model 不在列表中（已从候选池移除）时，
  // 补一个"未启用"提示，避免用户看到裸 ID 误以为下拉坏了。
  const currentModel = models.find((m) => m.id === selectedId);
  const currentName = currentModel?.name
    ?? (selectedId ? `${selectedId}（未启用）` : "—");

  // 计算下拉位置（向下弹出）
  useEffect(() => {
    if (!open || !btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    setPos({ top: rect.bottom + 4, left: rect.left, width: Math.max(rect.width, 200) });
  }, [open]);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (popRef.current?.contains(target)) return;
      if (btnRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        style={{
          ...inputStyle,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "8px",
          minWidth: "160px",
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.6 : 1,
        }}
      >
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {loading ? "Loading..." : currentName}
        </span>
        <ChevronDown style={{ width: "14px", height: "14px", color: "var(--text-level-4)", flexShrink: 0 }} />
      </button>

      {open && !loading && createPortal(
        <div
          ref={popRef}
          data-portal-popover
          style={{
            position: "fixed",
            top: pos.top,
            left: pos.left,
            width: pos.width,
            maxHeight: 320,
            overflowY: "auto",
            padding: "6px",
            borderRadius: "var(--radius-xl)",
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-secondary)",
            boxShadow: "var(--shadow-lg)",
            zIndex: 9999,
          }}
        >
          {groups.map((group, gi) => {
            const isCollapsed = collapsed.has(group.providerId);
            return (
              <div key={group.providerId}>
                {gi > 0 && (
                  <div style={{ height: "1px", margin: "4px 8px", background: "var(--border-primary)", opacity: 0.5 }} />
                )}
                <div
                  onClick={() => {
                    setCollapsed((prev) => {
                      const next = new Set(prev);
                      if (next.has(group.providerId)) next.delete(group.providerId);
                      else next.add(group.providerId);
                      try { localStorage.setItem("mfk_model_dropdown_collapsed", JSON.stringify([...next])); } catch { /* noop */ }
                      return next;
                    });
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                    padding: "5px 10px 3px",
                    fontSize: "10px",
                    fontWeight: 600,
                    color: "var(--text-level-4)",
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                    cursor: "pointer",
                    userSelect: "none",
                  }}
                >
                  {isCollapsed ? (
                    <ChevronRight style={{ width: "10px", height: "10px", opacity: 0.5, flexShrink: 0 }} />
                  ) : (
                    <ChevronDown style={{ width: "10px", height: "10px", opacity: 0.5, flexShrink: 0 }} />
                  )}
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {group.providerName}
                  </span>
                </div>
                {!isCollapsed && group.models.map((model) => {
                  const active = model.id === selectedId;
                  return (
                    <button
                      key={model.id}
                      type="button"
                      onClick={() => {
                        onSelect(model.id);
                        setOpen(false);
                      }}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        width: "100%",
                        padding: "6px 10px 6px 24px",
                        border: "none",
                        background: "transparent",
                        cursor: "pointer",
                        fontSize: "12px",
                        fontWeight: active ? 600 : 400,
                        color: active ? "var(--color-primary)" : "var(--text-level-2)",
                        borderRadius: "var(--radius-sm)",
                        textAlign: "left",
                        outline: "none",
                        whiteSpace: "nowrap",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                    >
                      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {model.name}
                      </span>
                      {active && <Check style={{ width: "14px", height: "14px", color: "var(--color-primary)", flexShrink: 0 }} />}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>,
        document.body
      )}
    </>
  );
}

// ── model 基础区块：默认模型 / 默认推理程度 + Provider 卡片基础配置 ──
function ModelBasic(props: SettingsViewProps) {
  const { settings, saving, onUpdate, models, modelsLoading, t } = props;
  // 2026-08-11：默认模型下拉按候选池过滤，与全站下拉保持一致
  const visibleModels = useVisibleModels(models);

  // 按 provider 分组，保持 provider 原始出现顺序（基于可见模型）
  const providerGroups = useMemo(() => {
    const seen = new Set<string>();
    const groups: { providerId: string; providerName: string; models: Model[] }[] = [];
    for (const m of visibleModels) {
      if (!seen.has(m.provider)) {
        seen.add(m.provider);
        groups.push({
          providerId: m.provider,
          providerName: PROVIDER_NAMES[m.provider] || m.provider,
          models: [],
        });
      }
      const group = groups.find((g) => g.providerId === m.provider);
      if (group) group.models.push(m);
    }
    return groups;
  }, [visibleModels]);

  return (
    <>
      {/* 默认模型 */}
      <div style={{ marginBottom: "18px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
              {t("settings.model.defaultModel.title")}
            </h3>
            <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
              {t("settings.model.defaultModel.desc")}
            </p>
          </div>
          <GroupedModelDropdown
            models={visibleModels}
            selectedId={settings?.default_model || FALLBACK_MODEL_ID}
            onSelect={(id) => onUpdate("default_model", id)}
            // 2026-08-11 修复：只有 visibleModels 为空且仍在 loading 时才禁用，
            // 避免 enabled_models 改后 useModels 重 fetch 期间下拉被锁死（1-2s 窗口）。
            // loading 态仍然以 "Loading..." 文本提示，不静默。
            disabled={saving === "default_model" || (modelsLoading && visibleModels.length === 0)}
            loading={modelsLoading}
          />
        </div>
      </div>

      {/* 默认推理程度 */}
      <div style={{ marginBottom: "18px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
              {t("settings.model.reasoningEffort.title")}
            </h3>
            <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
              {t("settings.model.reasoningEffort.desc")}
            </p>
          </div>
          <select
            value={settings?.default_reasoning_effort || "none"}
            onChange={(e) => onUpdate("default_reasoning_effort", e.target.value)}
            disabled={saving === "default_reasoning_effort"}
            style={inputStyle}
          >
            <option value="none">{t("chat.reasoning.off")}</option>
            <option value="high">{t("chat.reasoning.fast")}</option>
            <option value="max">{t("chat.reasoning.deep")}</option>
          </select>
        </div>
      </div>

      {/* 文生图模型（Phase H：AI 生成图片使用的千问图像模型，复用通义千问 API Key） */}
      <div style={{ marginBottom: "18px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
              {t("settings.model.imageGen.title")}
            </h3>
            <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
              {t("settings.model.imageGen.desc")}
            </p>
          </div>
          <select
            value={settings?.image_gen_model || "qwen-image-3.0-pro"}
            onChange={(e) => onUpdate("image_gen_model", e.target.value)}
            disabled={saving === "image_gen_model"}
            style={{ ...inputStyle, minWidth: "200px" }}
          >
            <option value="qwen-image-3.0-pro">{t("settings.model.imageGen.pro")}</option>
            <option value="qwen-image-3.0">{t("settings.model.imageGen.flash")}</option>
          </select>
        </div>
      </div>

      {/* 字段级边界：Provider 卡片基础配置（API Key + 模型 Chip + 连通性 + 远程拉取）
          Base URL 覆盖输入框在此处隐藏，下沉到 AdvancedSettingsView。
          新手绝不会看到 Base URL 这种复杂的输入框。 */}
      <div style={{ marginTop: "8px", paddingTop: "16px", borderTop: "1px solid var(--border-primary)" }}>
        <ModelProvidersBasic />
      </div>
    </>
  );
}

// ── ai 基础区块：默认 Agent / 默认人格 ──
function AiBasic(props: AdvancedSettingsViewProps) {
  const { settings, saving, onUpdate, agents, t } = props;
  // 人格档位：底层 0..100（25 步进）→ 展示 -2..+2，平衡点 0
  const personalityNum = Number(settings?.default_personality ?? 50);
  const personalityDisplay = Math.round((personalityNum - 50) / 25);
  return (
    <>
      {/* 默认 Agent */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "18px" }}>
        <div>
          <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.ai.defaultAgent.title")}
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
            {t("settings.ai.defaultAgent.desc")}
          </p>
        </div>
        <select
          value={settings?.default_agent || "general"}
          onChange={(e) => onUpdate("default_agent", e.target.value)}
          disabled={saving === "default_agent"}
          style={{ ...inputStyle, minWidth: "140px" }}
        >
          {getSortedActiveAgents(agents).map((agent) => (
            <option key={agent.id} value={agent.id}>{agent.name}</option>
          ))}
        </select>
      </div>

      {/* 默认人格：短滑块 + 数值，与标题同行；条色固定低饱和蓝，不随主题 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "16px", marginBottom: "10px" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.ai.defaultPersonality.title")}
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
            {t("settings.ai.defaultPersonality.desc")}
          </p>
        </div>
        <div style={{ flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <input
              type="range" min="0" max="100" step="25"
              value={settings?.default_personality || "50"}
              onChange={(e) => onUpdate("default_personality", e.target.value)}
              style={{ width: "150px", accentColor: "#8494a9", cursor: "pointer" }}
            />
            <span style={{ fontSize: "13px", color: "var(--text-level-2)", minWidth: "2ch", textAlign: "right" }}>
              {personalityDisplay > 0 ? `+${personalityDisplay}` : `${personalityDisplay}`}
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "var(--text-level-4)", width: "150px", marginTop: "2px" }}>
            <span>{t("settings.ai.defaultPersonality.veryEmotional")}</span>
            <span>{t("settings.ai.defaultPersonality.balanced")}</span>
            <span>{t("settings.ai.defaultPersonality.veryRational")}</span>
          </div>
        </div>
      </div>

      {/* 记忆治理三开关：读闸 / 写闸 / 保存提示（memory_* 键与后端 DEFAULT_SETTINGS 对齐） */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
        <div>
          <h3 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.ai.memoryRead.title")}
          </h3>
          <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "1px 0 0 0" }}>
            {t("settings.ai.memoryRead.desc")}
          </p>
        </div>
        <SwitchButton
          checked={settings?.memory_read_enabled !== "false"}
          disabled={saving === "memory_read_enabled"}
          onChange={(v) => onUpdate("memory_read_enabled", v ? "true" : "false")}
        />
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
        <div>
          <h3 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.ai.memoryWrite.title")}
          </h3>
          <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "1px 0 0 0" }}>
            {t("settings.ai.memoryWrite.desc")}
          </p>
        </div>
        <SwitchButton
          checked={settings?.memory_write_enabled !== "false"}
          disabled={saving === "memory_write_enabled"}
          onChange={(v) => onUpdate("memory_write_enabled", v ? "true" : "false")}
        />
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h3 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.ai.memoryAlert.title")}
          </h3>
          <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "1px 0 0 0" }}>
            {t("settings.ai.memoryAlert.desc")}
          </p>
        </div>
        <SwitchButton
          checked={settings?.memory_alert !== "false"}
          disabled={saving === "memory_alert"}
          onChange={(v) => onUpdate("memory_alert", v ? "true" : "false")}
        />
      </div>
    </>
  );
}

// ── security 区块：移入 security/SecurityView.tsx（紧凑安全中心）

// ── about 区块 ──
function AboutSection(props: SettingsViewProps) {
  const { t } = props;
  return (
    <div>
      <div style={{ padding: "16px", borderRadius: "var(--radius-md)", background: "var(--bg-level-2)" }}>
        <p style={{ fontSize: "15px", fontWeight: "600", color: "var(--text-level-1)", margin: "0 0 8px 0" }}>MfkAgent</p>
        <p style={{ fontSize: "13px", color: "var(--text-level-3)", margin: "0 0 4px 0" }}>{t("settings.about.version")}</p>
        <p style={{ fontSize: "13px", color: "var(--text-level-3)", margin: "0 0 12px 0" }}>{t("settings.about.description")}</p>
        <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: 0 }}>{t("settings.about.aiMayError")}</p>
      </div>
    </div>
  );
}

/**
 * 基础区块视图入口：根据 activeSection 路由到对应 section 的基础部分。
 * ai section 需要 agents，通过可选 props 传入。
 */
export function BasicSettingsView(
  props: SettingsViewProps & {
    activeSection: SettingSectionId;
    agents?: Agent[];
    onManageAgents?: () => void;
    onManageSubAgents?: () => void;
    editingSkillId?: string | null;
    onSelectSkill?: (id: string) => void;
    onBackToExtensionList?: () => void;
  }
) {
  switch (props.activeSection) {
    case "general":
      return <GeneralBasic {...props} />;
    case "model":
      return <ModelBasic {...props} />;
    case "ai":
      // ai 基础区块需要 agents；未传入时安全降级为 null
      if (!props.agents) return null;
      return <AiBasic {...props} agents={props.agents} onManageAgents={props.onManageAgents!} onManageSubAgents={props.onManageSubAgents} />;
    case "security":
      return <SecurityView {...props} />;
    case "extensions":
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          <FeishuSettingsPanel />
          <ExtensionPanel
            editingSkillId={(props.editingSkillId ?? null) as never}
            onSelectSkill={(id) => props.onSelectSkill?.(id)}
            onBackToList={() => props.onBackToExtensionList?.()}
          />
        </div>
      );
    case "about":
      return <AboutSection {...props} />;
    default:
      return null;
  }
}
