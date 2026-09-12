"use client";
/**
 * BasicSettingsView —— 基础区块视图（VS Code 极简风格重构）
 *
 * 核心规范：
 * - 统一 SettingRow 规矩：左侧标题+副标题，右侧统一 32px 交互控件，1px 细分割线
 * - 统一 SettingSectionHeader：大写或加粗的小号浅灰分类标签
 * - 模型页整合 MultimodalConfigSection：生图与识图折叠聚合，解决页面冗长痛点
 * - 模型服务商去除嵌套折叠，已配置置顶
 * - 通用页主题与字体去除杂乱微缩图和突兀黑框，纯净高级
 */
import { useState, useMemo, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Plus, Trash2, ChevronDown, Check, Keyboard, Sparkles } from "lucide-react";
import { ExtensionPanel } from "./ExtensionPanel";
import { FeishuSettingsPanel } from "./FeishuSettingsPanel";
import { SecurityView } from "./security/SecurityView";
import { ModelProvidersBasic } from "./ModelConfigSection";
import { ProxySettingsSection } from "./ProxySettingsSection";
import { MultimodalConfigSection } from "./MultimodalConfigSection";
import { FALLBACK_MODEL_ID } from "@/lib/modelDefaults";
import { SwitchButton } from "@/components/SwitchButton";
import { FONT_FAMILY_MAP } from "@/components/providers";
import { useVisibleModels } from "@/hooks/useVisibleModels";
import type { Model } from "@/hooks/useModels";
import type { Agent } from "@/hooks/useAgents";

/** 设置导航项 id 联合类型 */
export type SettingSectionId = "general" | "model" | "ai" | "security" | "extensions" | "about" | "archive" | "shortcuts";

/** 统管状态注入 props */
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
  onOpenMemoryManage?: () => void;
  onClose?: () => void;
}

/** Provider ID → 中文展示名映射 */
const PROVIDER_NAMES: Record<string, string> = {
  deepseek: "DeepSeek",
  qwen: "通义千问",
  google: "Google Gemini",
  glm: "智谱 AI",
  moonshot: "Moonshot",
  freellmapi: "FreeLLMAPI",
  mimo: "小米 MiMo",
  wenxin: "百度文心",
  minimax: "MiniMax",
  siliconflow: "硅基流动",
  sensenova: "商汤日日新",
};

/** 预设 Agent 排序优先级 */
const AGENT_ORDER = ["general", "coder", "frontend_ui", "g", "pianai", "spark"];

/** 视觉主题定义 */
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

// ── VS Code 规范组件：设置行 ──
function SettingRow({
  title,
  desc,
  children,
  border = true,
}: {
  title: string;
  desc?: string;
  children: React.ReactNode;
  border?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "16px",
        padding: "12px 0",
        borderBottom: border ? "1px solid var(--border-secondary)" : "none",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <h4 style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-level-1)", margin: 0 }}>
          {title}
        </h4>
        {desc && (
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0", lineHeight: 1.4 }}>
            {desc}
          </p>
        )}
      </div>
      <div style={{ flexShrink: 0 }}>
        {children}
      </div>
    </div>
  );
}

// ── VS Code 规范组件：大类标题 ──
function SettingSectionHeader({ title, desc }: { title: string; desc?: string }) {
  return (
    <div style={{ margin: "18px 0 6px 0" }}>
      <h3 style={{
        fontSize: "11px",
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.06em",
        color: "var(--text-level-4)",
        margin: 0,
      }}>
        {title}
      </h3>
      {desc && (
        <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
          {desc}
        </p>
      )}
    </div>
  );
}

/** 单个主题质感卡片：纯净色环 + 标题 + 说明 */
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
      type="button"
      onClick={() => onSelect(theme.id)}
      disabled={disabled}
      aria-pressed={selected}
      style={{
        flex: 1,
        minWidth: 0,
        padding: "10px 12px",
        borderRadius: "var(--radius-sm)",
        border: `1.5px solid ${selected ? "var(--color-primary)" : "var(--border-primary)"}`,
        background: selected ? "color-mix(in srgb, var(--color-primary) 4%, var(--bg-level-2))" : "var(--bg-level-2)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.6 : 1,
        textAlign: "left",
        display: "flex",
        flexDirection: "column",
        gap: "6px",
        transition: "all var(--transition-fast)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {/* 色板小色轮 */}
          <div style={{ display: "flex", alignItems: "center", gap: "3px" }}>
            <span style={{ width: 9, height: 9, borderRadius: "50%", background: p.bg, border: `1px solid ${p.border}` }} />
            <span style={{ width: 9, height: 9, borderRadius: "50%", background: p.surface, border: `1px solid ${p.border}` }} />
            <span style={{ width: 9, height: 9, borderRadius: "50%", background: p.accent }} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-level-1)" }}>
            {t(theme.nameKey)}
          </span>
        </div>
        {selected && (
          <span style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            width: 16, height: 16, borderRadius: "50%",
            background: "var(--color-primary)", color: "#fff",
          }}>
            <Check style={{ width: 10, height: 10 }} strokeWidth={2.5} />
          </span>
        )}
      </div>
      <div style={{ fontSize: 11, color: "var(--text-level-3)", lineHeight: 1.4 }}>
        {t(theme.descKey)}
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
  height: "32px",
  padding: "0 10px",
  borderRadius: "var(--radius-sm)",
  background: "var(--bg-level-2)",
  border: "1px solid var(--border-primary)",
  fontSize: "12px",
  color: "var(--text-level-2)",
  outline: "none",
  boxSizing: "border-box",
};

/** 字体选项 */
const FONT_OPTIONS: Array<{ value: string; labelKey: string }> = [
  { value: "system", labelKey: "settings.general.font.system" },
  { value: "source-han-sans", labelKey: "settings.general.font.source-han-sans" },
  { value: "lxgw-wenkai", labelKey: "settings.general.font.lxgw-wenkai" },
  { value: "ibm-plex-sans", labelKey: "settings.general.font.ibm-plex-sans" },
];

/** 字体选择器：自定义下拉，选项名用对应字体渲染（所见即所得） */
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

  useEffect(() => {
    if (document.getElementById("font-preview-cdn")) return;
    const link = document.createElement("link");
    link.id = "font-preview-cdn";
    link.rel = "stylesheet";
    link.href = "https://cdn.jsdelivr.net/npm/lxgw-wenkai-webfont@1.7.0/style.css";
    document.head.appendChild(link);
  }, []);

  useEffect(() => {
    if (!open || !btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    setPos({ top: rect.bottom + 4, left: rect.left, width: Math.max(rect.width, 180) });
  }, [open]);

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
        <ChevronDown style={{ width: "13px", height: "13px", color: "var(--text-level-4)", flexShrink: 0 }} />
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
            padding: "4px",
            borderRadius: "var(--radius-sm)",
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-secondary)",
            boxShadow: "var(--shadow-md)",
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
                className={active ? "mf-dropdown-item is-active" : "mf-dropdown-item"}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  width: "100%",
                  padding: "6px 8px",
                  border: "none",
                  background: active ? "var(--bg-level-3)" : "transparent",
                  cursor: "pointer",
                  fontSize: "12px",
                  fontWeight: active ? 600 : 400,
                  color: active ? "var(--color-primary)" : "var(--text-level-2)",
                  borderRadius: "var(--radius-xs)",
                  textAlign: "left",
                  fontFamily: FONT_FAMILY_MAP[opt.value],
                }}
              >
                <span style={{ width: "14px", flexShrink: 0 }}>
                  {active && <Check style={{ width: "13px", height: "13px" }} />}
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

/** 自定义台词编辑器 */
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
      /* ignore */
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
      <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginBottom: "8px" }}>
        {draft.map((item, index) => (
          <div key={index} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <input
              value={item}
              onChange={(e) => handleChange(index, e.target.value)}
              maxLength={50}
              placeholder={t("settings.general.greeting.customPlaceholder")}
              style={{
                flex: 1, height: "30px", padding: "0 8px", borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
                fontSize: "12px", color: "var(--text-level-2)", outline: "none",
              }}
            />
            <button
              onClick={() => handleRemove(index)}
              title={t("common.delete")}
              style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                width: 26, height: 26, borderRadius: "var(--radius-sm)", border: "none",
                background: "transparent", cursor: "pointer", color: "var(--text-level-4)",
              }}
            >
              <Trash2 style={{ width: "13px", height: "13px" }} />
            </button>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <button
          onClick={handleAdd}
          disabled={clean.length >= 5}
          style={{
            display: "flex", alignItems: "center", gap: "4px", padding: "4px 10px",
            borderRadius: "var(--radius-sm)", border: "1px dashed var(--border-primary)",
            background: "transparent", cursor: clean.length >= 5 ? "not-allowed" : "pointer",
            fontSize: "11px", color: "var(--text-level-3)", opacity: clean.length >= 5 ? 0.5 : 1,
          }}
        >
          <Plus style={{ width: "12px", height: "12px" }} />
          {t("settings.general.greeting.customAdd")}
        </button>
        <button
          onClick={handleSave}
          disabled={saving || JSON.stringify(clean) === value}
          style={{
            padding: "4px 12px", borderRadius: "var(--radius-sm)", border: "none",
            background: "var(--color-primary)", color: "#fff",
            cursor: saving ? "not-allowed" : "pointer", fontSize: "11px", fontWeight: 500,
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

// ── 键盘快捷键一览 ──
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

// ── General 基础区块（VS Code 规矩风格）──
function GeneralBasic(props: SettingsViewProps) {
  const { settings, saving, onUpdate, t } = props;
  return (
    <div>
      {/* ── 外观与界面 ── */}
      <SettingSectionHeader title="界面外观 (Appearance)" />

      {/* 视觉主题 */}
      <div style={{ padding: "8px 0 14px", borderBottom: "1px solid var(--border-secondary)" }}>
        <div style={{ marginBottom: "10px" }}>
          <h4 style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.general.theme.title")}
          </h4>
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

      {/* 语言 */}
      <SettingRow
        title={t("settings.general.language.title")}
        desc={t("settings.general.language.desc")}
      >
        <div style={{ display: "flex", padding: "2px", borderRadius: "var(--radius-sm)", background: "var(--bg-level-2)", border: "1px solid var(--border-secondary)" }}>
          {[
            { value: "zh-CN", label: t("settings.general.language.zh-CN") },
            { value: "en-US", label: t("settings.general.language.en-US") },
          ].map((lang) => (
            <button
              key={lang.value}
              type="button"
              onClick={() => onUpdate("language", lang.value)}
              disabled={saving === "language"}
              style={{
                padding: "4px 12px",
                borderRadius: "var(--radius-xs)",
                border: "none",
                cursor: "pointer",
                fontSize: "12px",
                whiteSpace: "nowrap",
                background: settings?.language === lang.value ? "var(--bg-level-1)" : "transparent",
                color: settings?.language === lang.value ? "var(--text-level-1)" : "var(--text-level-3)",
                fontWeight: settings?.language === lang.value ? 600 : 400,
                boxShadow: settings?.language === lang.value ? "var(--shadow-xs)" : "none",
              }}
            >
              {lang.label}
            </button>
          ))}
        </div>
      </SettingRow>

      {/* 字体风格 */}
      <SettingRow
        title={t("settings.general.font.title")}
        desc="选择应用渲染的主要字体风格"
      >
        <FontFamilyDropdown
          value={settings?.font_family || "system"}
          onSelect={(v) => onUpdate("font_family", v)}
          disabled={saving === "font_family"}
          t={t}
        />
      </SettingRow>

      {/* ── 网络连接 ── */}
      <SettingSectionHeader title="网络代理 (Network & Proxy)" />
      <ProxySettingsSection
        settings={settings}
        saving={saving}
        onUpdate={onUpdate}
        t={t}
      />

      {/* ── 常规偏好 ── */}
      <SettingSectionHeader title="偏好与启动 (Preferences)" />

      {/* 首页台词 */}
      <SettingRow
        title={t("settings.general.greeting.title")}
        desc={t("settings.general.greeting.desc")}
      >
        <div style={{ display: "flex", padding: "2px", borderRadius: "var(--radius-sm)", background: "var(--bg-level-2)", border: "1px solid var(--border-secondary)" }}>
          {([
            { value: "builtin", label: t("settings.general.greeting.builtin") },
            { value: "custom", label: t("settings.general.greeting.custom") },
            { value: "off", label: t("settings.general.greeting.off") },
          ] as const).map((opt) => {
            const active = (settings?.greeting_mode ?? "builtin") === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => onUpdate("greeting_mode", opt.value)}
                disabled={saving === "greeting_mode"}
                style={{
                  padding: "4px 12px",
                  borderRadius: "var(--radius-xs)",
                  border: "none",
                  cursor: "pointer",
                  fontSize: "12px",
                  whiteSpace: "nowrap",
                  background: active ? "var(--bg-level-1)" : "transparent",
                  color: active ? "var(--text-level-1)" : "var(--text-level-3)",
                  fontWeight: active ? 600 : 400,
                  boxShadow: active ? "var(--shadow-xs)" : "none",
                }}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </SettingRow>

      {/* 自定义台词编辑（仅 custom 模式显示） */}
      {(settings?.greeting_mode ?? "builtin") === "custom" && (
        <div style={{ padding: "8px 0 12px", borderBottom: "1px solid var(--border-secondary)" }}>
          <GreetingCustomEditor
            value={settings?.custom_greetings ?? "[]"}
            saving={saving === "custom_greetings"}
            onSave={onUpdate}
            t={t}
          />
        </div>
      )}

      {/* 浏览器主页 */}
      <SettingRow
        title={t("settings.general.browserHomepage.title")}
        desc={t("settings.general.browserHomepage.desc")}
        border={false}
      >
        <input
          type="text"
          value={settings?.browser_homepage ?? ""}
          onChange={(e) => onUpdate("browser_homepage", e.target.value)}
          placeholder="https://example.com"
          spellCheck={false}
          style={{
            width: "240px",
            height: "32px",
            padding: "0 10px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-2)",
            fontSize: "12px",
            color: "var(--text-level-2)",
            outline: "none",
            boxSizing: "border-box",
          }}
        />
      </SettingRow>
    </div>
  );
}

/** 按 provider 分组的自定义模型下拉 */
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

  const currentModel = models.find((m) => m.id === selectedId);
  const currentName = currentModel?.name ?? (selectedId ? `${selectedId}（未激活）` : "—");

  useEffect(() => {
    if (!open || !btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    setPos({ top: rect.bottom + 4, left: rect.left, width: Math.max(rect.width, 220) });
  }, [open]);

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
          minWidth: "180px",
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.6 : 1,
        }}
      >
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {loading ? "Loading..." : currentName}
        </span>
        <ChevronDown style={{ width: "13px", height: "13px", color: "var(--text-level-4)", flexShrink: 0 }} />
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
            padding: "4px",
            borderRadius: "var(--radius-sm)",
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-secondary)",
            boxShadow: "var(--shadow-md)",
            zIndex: 9999,
          }}
        >
          {groups.map((group, gi) => {
            const isCollapsed = collapsed.has(group.providerId);
            return (
              <div key={group.providerId}>
                {gi > 0 && (
                  <div style={{ height: "1px", margin: "4px 6px", background: "var(--border-secondary)" }} />
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
                    justifyContent: "space-between",
                    padding: "4px 8px",
                    cursor: "pointer",
                    fontSize: "11px",
                    fontWeight: 600,
                    color: "var(--text-level-3)",
                    userSelect: "none",
                  }}
                >
                  <span>{group.providerName}</span>
                  <ChevronDown
                    style={{
                      width: "11px",
                      height: "11px",
                      transform: isCollapsed ? "rotate(-90deg)" : "rotate(0deg)",
                      transition: "transform 0.15s ease",
                    }}
                  />
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
                        padding: "5px 8px 5px 16px",
                        border: "none",
                        background: active ? "var(--bg-level-3)" : "transparent",
                        cursor: "pointer",
                        fontSize: "12px",
                        fontWeight: active ? 600 : 400,
                        color: active ? "var(--color-primary)" : "var(--text-level-2)",
                        borderRadius: "var(--radius-xs)",
                        textAlign: "left",
                        outline: "none",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
                      onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = "transparent"; }}
                    >
                      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {model.name}
                      </span>
                      {active && <Check style={{ width: "13px", height: "13px", color: "var(--color-primary)", flexShrink: 0 }} />}
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

// ── Model 基础区块（VS Code 规矩风格）──
function ModelBasic(props: SettingsViewProps) {
  const { settings, saving, onUpdate, models, modelsLoading, t } = props;
  const visibleModels = useVisibleModels(models);

  return (
    <div>
      {/* ── 默认模型与推理 ── */}
      <SettingSectionHeader title="推理偏好 (Model & Inference)" />

      {/* 默认模型 */}
      <SettingRow
        title={t("settings.model.defaultModel.title")}
        desc={t("settings.model.defaultModel.desc")}
      >
        <GroupedModelDropdown
          models={visibleModels}
          selectedId={settings?.default_model || FALLBACK_MODEL_ID}
          onSelect={(id) => onUpdate("default_model", id)}
          disabled={saving === "default_model" || (modelsLoading && visibleModels.length === 0)}
          loading={modelsLoading}
        />
      </SettingRow>

      {/* 默认推理程度 */}
      <SettingRow
        title={t("settings.model.reasoningEffort.title")}
        desc={t("settings.model.reasoningEffort.desc")}
      >
        <select
          value={settings?.default_reasoning_effort || "none"}
          className="mf-input"
          onChange={(e) => onUpdate("default_reasoning_effort", e.target.value)}
          disabled={saving === "default_reasoning_effort"}
          style={{
            ...inputStyle,
            minWidth: "160px",
          }}
        >
          <option value="none">{t("chat.reasoning.off")}</option>
          <option value="high">{t("chat.reasoning.fast")}</option>
          <option value="max">{t("chat.reasoning.deep")}</option>
        </select>
      </SettingRow>

      {/* 显示思考过程 */}
      <SettingRow
        title={t("settings.model.showReasoning.title")}
        desc={t("settings.model.showReasoning.desc")}
        border={false}
      >
        <SwitchButton
          checked={settings?.show_reasoning !== "false"}
          disabled={saving === "show_reasoning"}
          onChange={(v) => onUpdate("show_reasoning", v ? "true" : "false")}
        />
      </SettingRow>

      {/* ── 多模态扩展能力（生图与识图折叠组件）── */}
      <SettingSectionHeader title="多模态扩展 (Multimodal)" desc="管理 AI 的图像生成模型与视觉识图 (BYOK) 回退通道" />
      <div style={{ marginBottom: "14px" }}>
        <MultimodalConfigSection
          settings={settings}
          saving={saving}
          onUpdate={onUpdate}
        />
      </div>

      {/* ── 模型服务商管理 ── */}
      <SettingSectionHeader title="模型服务商管理 (Providers)" />
      <div style={{ marginTop: "4px" }}>
        <ModelProvidersBasic />
      </div>
    </div>
  );
}

// ── AI 基础区块（VS Code 规矩风格）──
function AiBasic(props: AdvancedSettingsViewProps) {
  const { settings, saving, onUpdate, agents, t } = props;
  const personalityNum = Number(settings?.default_personality ?? 50);
  const personalityDisplay = Math.round((personalityNum - 50) / 25);

  return (
    <div>
      {/* ── 智能体偏好 ── */}
      <SettingSectionHeader title="智能体偏好 (Agent Preferences)" />

      {/* 默认 Agent */}
      <SettingRow
        title={t("settings.ai.defaultAgent.title")}
        desc={t("settings.ai.defaultAgent.desc")}
      >
        <select
          value={settings?.default_agent || "general"}
          className="mf-input"
          onChange={(e) => onUpdate("default_agent", e.target.value)}
          disabled={saving === "default_agent"}
          style={{ ...inputStyle, minWidth: "160px" }}
        >
          {getSortedActiveAgents(agents).map((agent) => (
            <option key={agent.id} value={agent.id}>{agent.name}</option>
          ))}
        </select>
      </SettingRow>

      {/* 默认人格倾向 */}
      <SettingRow
        title={t("settings.ai.defaultPersonality.title")}
        desc={t("settings.ai.defaultPersonality.desc")}
        border={false}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {/* 快捷按钮 */}
          <div style={{ display: "flex", padding: "2px", borderRadius: "var(--radius-sm)", background: "var(--bg-level-2)", border: "1px solid var(--border-secondary)" }}>
            {[
              { label: "理性", value: "0" },
              { label: "平衡", value: "50" },
              { label: "感性", value: "100" },
            ].map((p) => {
              const active = String(settings?.default_personality ?? 50) === p.value;
              return (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => onUpdate("default_personality", p.value)}
                  disabled={saving === "default_personality"}
                  style={{
                    padding: "3px 10px",
                    borderRadius: "var(--radius-xs)",
                    border: "none",
                    cursor: "pointer",
                    fontSize: "12px",
                    background: active ? "var(--bg-level-1)" : "transparent",
                    color: active ? "var(--color-primary)" : "var(--text-level-3)",
                    fontWeight: active ? 600 : 400,
                  }}
                >
                  {p.label}
                </button>
              );
            })}
          </div>

          {/* 滑块 */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <input
              type="range" min="0" max="100" step="25"
              value={settings?.default_personality || "50"}
              onChange={(e) => onUpdate("default_personality", e.target.value)}
              style={{ width: "90px", accentColor: "var(--color-primary)", cursor: "pointer" }}
            />
            <span style={{ fontSize: "12px", color: "var(--text-level-2)", minWidth: "2ch", textAlign: "right" }}>
              {personalityDisplay > 0 ? `+${personalityDisplay}` : `${personalityDisplay}`}
            </span>
          </div>
        </div>
      </SettingRow>

      {/* ── 记忆治理 ── */}
      <SettingSectionHeader title="长期记忆治理 (Memory Governance)" desc="控制会话对长期记忆的读取、记录与主动提示行为" />

      {/* 记忆读取 */}
      <SettingRow
        title={t("settings.ai.memoryRead.title")}
        desc={t("settings.ai.memoryRead.desc")}
      >
        <SwitchButton
          checked={settings?.memory_read_enabled !== "false"}
          disabled={saving === "memory_read_enabled"}
          onChange={(v) => onUpdate("memory_read_enabled", v ? "true" : "false")}
        />
      </SettingRow>

      {/* 记忆写入 */}
      <SettingRow
        title={t("settings.ai.memoryWrite.title")}
        desc={t("settings.ai.memoryWrite.desc")}
      >
        <SwitchButton
          checked={settings?.memory_write_enabled !== "false"}
          disabled={saving === "memory_write_enabled"}
          onChange={(v) => onUpdate("memory_write_enabled", v ? "true" : "false")}
        />
      </SettingRow>

      {/* 记忆提示 */}
      <SettingRow
        title={t("settings.ai.memoryAlert.title")}
        desc={t("settings.ai.memoryAlert.desc")}
        border={false}
      >
        <SwitchButton
          checked={settings?.memory_alert !== "false"}
          disabled={saving === "memory_alert"}
          onChange={(v) => onUpdate("memory_alert", v ? "true" : "false")}
        />
      </SettingRow>
    </div>
  );
}

// ── Shortcuts 快捷键一览（VS Code 规矩风格）──
function ShortcutsSection() {
  return (
    <div>
      <SettingSectionHeader title="全局快捷键 (Keybindings)" desc="桌面端常用键盘快捷操作一览" />
      <div style={{
        border: "1px solid var(--border-primary)",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-level-2)",
        overflow: "hidden",
        marginTop: "8px",
      }}>
        {KEYBOARD_SHORTCUTS.map((s, i) => (
          <div key={s.action} style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            padding: "10px 14px",
            borderBottom: i === KEYBOARD_SHORTCUTS.length - 1 ? "none" : "1px solid var(--border-secondary)",
          }}>
            <span style={{ fontSize: 13, color: "var(--text-level-2)" }}>{s.action}</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
              {s.keys.map((k, ki) => (
                <span key={ki} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  {ki > 0 && <span style={{ fontSize: 11, color: "var(--text-level-4)" }}>+</span>}
                  <kbd style={{
                    fontFamily: "var(--font-geist-mono), var(--font-family)",
                    fontSize: 11,
                    padding: "3px 8px",
                    borderRadius: "4px",
                    border: "1px solid var(--border-primary)",
                    background: "var(--bg-level-1)",
                    color: "var(--text-level-1)",
                    lineHeight: 1.4,
                    whiteSpace: "nowrap",
                    boxShadow: "0 1px 1px rgba(0,0,0,0.05)",
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

// ── About 关于区块（VS Code 规矩风格）──
function AboutSection(props: SettingsViewProps) {
  const { t } = props;
  return (
    <div>
      <SettingSectionHeader title="关于 MfkAgent (About)" desc="客户端版本与版权说明" />
      <div style={{
        padding: "18px 20px",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-level-2)",
        border: "1px solid var(--border-primary)",
        marginTop: "8px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
          <span style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-level-1)" }}>MfkAgent</span>
          <span style={{
            fontSize: "11px",
            padding: "2px 8px",
            borderRadius: "999px",
            background: "color-mix(in srgb, var(--color-primary) 12%, transparent)",
            color: "var(--color-primary)",
            fontWeight: 600,
          }}>
            {t("settings.about.version")}
          </span>
        </div>
        <p style={{ fontSize: "13px", color: "var(--text-level-3)", margin: "0 0 12px 0", lineHeight: 1.5 }}>
          {t("settings.about.description")}
        </p>
        <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: 0 }}>
          {t("settings.about.aiMayError")}
        </p>
      </div>
    </div>
  );
}

/** 基础区块视图入口 */
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
      if (!props.agents) return null;
      return <AiBasic {...props} agents={props.agents} onManageAgents={props.onManageAgents!} onManageSubAgents={props.onManageSubAgents} />;
    case "security":
      return <SecurityView {...props} />;
    case "extensions":
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
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
