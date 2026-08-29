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
import { Plus, Trash2, Globe, ChevronDown, ChevronRight, Check, Keyboard } from "lucide-react";
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
export type SettingSectionId = "general" | "model" | "ai" | "security" | "extensions" | "about" | "archive" | "shortcuts";

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
  /** 关闭设置面板（用于跳转独立页面时自动关闭） */
  onClose?: () => void;
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
  sensenova: "商汤日日新",
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

function getSortedActiveAgents(agents: { id: string; name: string; status: string }[]) {
  return [...agents]
    .sort((a, b) => {
      const ai = AGENT_ORDER.indexOf(a.id);
      const bi = AGENT_ORDER.indexOf(b.id);
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    })
    .filter((agent) => agent.status === "active" && !agent.id.startsWith("sub_"));
}

const inputStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: "var(--radius-sm)",
  background: "var(--bg-level-2)",
  fontSize: "13px",
  color: "var(--text-level-2)",
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
        className="mf-input"
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
          className="mf-pop"
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
          className="mf-btn-primary"
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

// ── 键盘快捷键一览（仅展示，不可编辑）──
// 静态快照：与 AppLayout / CommandPalette / ChatInput / Dock 的 keydown handler 保持一致。
const KEYBOARD_SHORTCUTS: { action: string; keys: string[] }[] = [
  { action: "打开命令面板", keys: ["Cmd/Ctrl", "K"] },
  { action: "切换终端面板", keys: ["Cmd/Ctrl", "`"] },
  { action: "新建对话", keys: ["Cmd/Ctrl", "T"] },
  { action: "切换标签", keys: ["Cmd/Ctrl", "Tab"] },
  { action: "跳到第 N 个标签", keys: ["Alt", "1-9"] },
  { action: "缩放内容（75% - 150%）", keys: ["Ctrl", "滚轮"] },
  { action: "发送消息", keys: ["Enter"] },
  { action: "消息内换行", keys: ["Shift", "Enter"] },
  { action: "关闭弹层/面板", keys: ["Esc"] },
];

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
              className={settings?.language === lang.value ? "mf-seg-btn is-active" : "mf-seg-btn"}
              style={{
                flex: 1, padding: "6px 14px", borderRadius: "var(--radius-xs)", border: "none",
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
                className={(settings?.hero_random_scope || "all") === opt.value ? "mf-seg-btn is-active" : "mf-seg-btn"}
                style={{
                  flex: 1, padding: "6px 14px", borderRadius: "var(--radius-xs)", border: "none",
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
                className={active ? "mf-seg-btn is-active" : "mf-seg-btn"}
                style={{
                  flex: 1, padding: "6px 14px", borderRadius: "var(--radius-xs)", border: "none",
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

      {/* 浏览器主页：右侧浏览器标签的默认打开网址 */}
      <div style={{ marginBottom: "18px" }}>
        <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: "0 0 6px 0" }}>
          {t("settings.general.browserHomepage.title")}
        </h3>
        <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: "0 0 8px 0" }}>
          {t("settings.general.browserHomepage.desc")}
        </p>
        <input
          type="text"
          value={settings?.browser_homepage ?? ""}
          onChange={(e) => onUpdate("browser_homepage", e.target.value)}
          placeholder="https://example.com"
          spellCheck={false}
          style={{
            width: "100%", padding: "7px 10px", borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
            fontSize: "13px", color: "var(--text-level-2)", outline: "none",
          }}
        />
      </div>
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
        className="mf-input"
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
          className="mf-pop"
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
            className="mf-input"
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

      {/* 显示思考过程 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "18px" }}>
        <div>
          <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.model.showReasoning.title")}
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
            {t("settings.model.showReasoning.desc")}
          </p>
        </div>
        <SwitchButton
          checked={settings?.show_reasoning !== "false"}
          disabled={saving === "show_reasoning"}
          onChange={(v) => onUpdate("show_reasoning", v ? "true" : "false")}
        />
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
            className="mf-input"
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
          className="mf-input"
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

      {/* 人格快捷预设：理性 / 平衡 / 感性 一键设定（映射 0 / 50 / 100） */}
      <div style={{ display: "flex", gap: 6, marginBottom: "14px" }}>
        {[
          { label: "理性", value: "0" },
          { label: "平衡", value: "50" },
          { label: "感性", value: "100" },
        ].map((p) => {
          const active = String(settings?.default_personality ?? 50) === p.value;
          return (
            <button
              key={p.value}
              onClick={() => onUpdate("default_personality", p.value)}
              disabled={saving === "default_personality"}
              style={{
                padding: "4px 14px",
                borderRadius: "var(--radius-full)",
                border: "1px solid",
                borderColor: active ? "var(--color-primary)" : "var(--border-primary)",
                background: active ? "var(--color-primary-lighter)" : "var(--bg-level-2)",
                color: active ? "var(--color-primary)" : "var(--text-level-3)",
                fontSize: "12px",
                fontWeight: active ? 500 : 400,
                cursor: "pointer",
                opacity: saving === "default_personality" ? 0.6 : 1,
                transition: "border-color var(--transition-fast), background var(--transition-fast)",
              }}
            >{p.label}</button>
          );
        })}
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

// ── shortcuts 区块：键盘快捷键一览（独立 Tab，Codex 风格顶级分区；仅展示，不可编辑） ──
function ShortcutsSection() {
  return (
    <div>
      <div style={{ marginBottom: "12px" }}>
        <h3 style={{ fontSize: 14, fontWeight: 500, color: "var(--text-level-1)", margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
          <Keyboard style={{ width: 15, height: 15 }} />
          键盘快捷键
        </h3>
        <p style={{ fontSize: 12, color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
          常用操作一览
        </p>
      </div>
      <div style={{
        border: "1px solid var(--border-primary)",
        borderRadius: "var(--radius-sm)",
        background: "var(--bg-level-2)",
        overflow: "hidden",
      }}>
        {KEYBOARD_SHORTCUTS.map((s, i) => (
          <div key={s.action} style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            padding: "9px 12px",
            borderBottom: i === KEYBOARD_SHORTCUTS.length - 1 ? "none" : "1px solid var(--border-primary)",
          }}>
            <span style={{ fontSize: 12, color: "var(--text-level-2)" }}>{s.action}</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
              {s.keys.map((k, ki) => (
                <span key={ki} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  {ki > 0 && <span style={{ fontSize: 11, color: "var(--text-level-4)" }}>+</span>}
                  <kbd style={{
                    fontFamily: "var(--font-geist-mono), var(--font-family)",
                    fontSize: 11,
                    padding: "2px 7px",
                    borderRadius: 4,
                    border: "1px solid var(--border-primary)",
                    background: "var(--bg-level-1)",
                    color: "var(--text-level-2)",
                    lineHeight: 1.4,
                    whiteSpace: "nowrap",
                  }}>{k}</kbd>
                </span>
              ))}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

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
    case "shortcuts":
      return <ShortcutsSection />;
    default:
      return null;
  }
}
