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
import { Moon, Sun, Monitor, Plus, Trash2, Globe, ChevronDown, ChevronRight, Check } from "lucide-react";
import { PluginPanel } from "./PluginPanel";
import { ModelProvidersBasic } from "./ModelConfigSection";
import { SwitchButton } from "@/components/SwitchButton";
import type { Model } from "@/hooks/useModels";
import type { Agent } from "@/hooks/useAgents";

/** 设置导航项 id 联合类型（与 SettingsPanel 共享，保证 activeSection 类型安全） */
export type SettingSectionId = "general" | "model" | "ai" | "plugins" | "about";

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
  baichuan: "百川智能",
  siliconflow: "硅基流动",
  openai: "OpenAI",
};

/** 预设 Agent 排序优先级 */
const AGENT_ORDER = ["coder", "frontend_ui", "backend", "general", "analyst", "writer"];

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
      {/* 主题 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "18px" }}>
        <div>
          <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.general.theme.title")}
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
            {t("settings.general.theme.desc")}
          </p>
        </div>
        <div style={{ display: "flex", padding: "3px", borderRadius: "var(--radius-sm)", background: "var(--bg-level-2)" }}>
          {[
            { value: "light", label: t("settings.general.theme.light"), icon: Sun },
            { value: "dark", label: t("settings.general.theme.dark"), icon: Moon },
            { value: "system", label: t("settings.general.theme.system"), icon: Monitor },
          ].map((theme) => (
            <button
              key={theme.value}
              onClick={() => onUpdate("theme", theme.value)}
              disabled={saving === "theme"}
              style={{
                display: "flex", alignItems: "center", justifyContent: "center", flex: 1, gap: "6px",
                padding: "6px 14px", borderRadius: "var(--radius-xs)", border: "none",
                background: settings?.theme === theme.value ? "var(--bg-level-1)" : "transparent",
                cursor: "pointer", fontSize: "13px", whiteSpace: "nowrap",
                color: settings?.theme === theme.value ? "var(--text-level-1)" : "var(--text-level-3)",
                opacity: saving === "theme" ? 0.7 : 1,
              }}
            >
              <theme.icon style={{ width: "14px", height: "14px" }} />
              <span>{theme.label}</span>
            </button>
          ))}
        </div>
      </div>

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
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "18px" }}>
        <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
          {t("settings.general.font.title")}
        </h3>
        <select
          value={settings?.font_family || "system"}
          onChange={(e) => onUpdate("font_family", e.target.value)}
          disabled={saving === "font_family"}
          style={{ ...inputStyle, minWidth: "140px", padding: "6px 12px" }}
        >
          <option value="system">{t("settings.general.font.system")}</option>
          <option value="source-han-sans">{t("settings.general.font.source-han-sans")}</option>
          <option value="lxgw-wenkai">{t("settings.general.font.lxgw-wenkai")}</option>
          <option value="ibm-plex-sans">{t("settings.general.font.ibm-plex-sans")}</option>
        </select>
      </div>

      {/* 强调色主题（字段级边界：从高级上移到基础，通用 Tab 全量放出） */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "18px" }}>
        <div>
          <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.general.accentTheme.title")}
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
            {t("settings.general.accentTheme.desc")}
          </p>
        </div>
        <select
          value={settings?.accent_theme || "default"}
          onChange={(e) => onUpdate("accent_theme", e.target.value)}
          disabled={saving === "accent_theme"}
          style={{ ...inputStyle, opacity: saving === "accent_theme" ? 0.7 : 1, minWidth: "140px", padding: "6px 12px" }}
        >
          <option value="default">{t("settings.general.accentTheme.default")}</option>
          <option value="teal">{t("settings.general.accentTheme.teal")}</option>
          <option value="amber">{t("settings.general.accentTheme.amber")}</option>
          <option value="violet">{t("settings.general.accentTheme.violet")}</option>
          <option value="rose">{t("settings.general.accentTheme.rose")}</option>
          <option value="graphite">{t("settings.general.accentTheme.graphite")}</option>
        </select>
      </div>

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
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
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

  const currentName = models.find((m) => m.id === selectedId)?.name ?? selectedId ?? "—";

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

  // 按 provider 分组，保持 provider 原始出现顺序
  const providerGroups = useMemo(() => {
    const seen = new Set<string>();
    const groups: { providerId: string; providerName: string; models: Model[] }[] = [];
    for (const m of models) {
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
  }, [models]);

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
            models={models}
            selectedId={settings?.default_model || "qwen-flash"}
            onSelect={(id) => onUpdate("default_model", id)}
            disabled={saving === "default_model" || modelsLoading}
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

      {/* 默认人格 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
        <div>
          <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.ai.defaultPersonality.title")}
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
            {t("settings.ai.defaultPersonality.desc")}
          </p>
        </div>
        <span style={{ fontSize: "13px", color: "var(--text-level-2)" }}>
          {settings?.default_personality || "50"}
        </span>
      </div>
      <input
        type="range" min="0" max="100" step="25"
        value={settings?.default_personality || "50"}
        onChange={(e) => onUpdate("default_personality", e.target.value)}
        style={{ width: "100%" }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--text-level-4)", marginTop: "4px" }}>
        <span>{t("settings.ai.defaultPersonality.veryEmotional")}</span>
        <span>{t("settings.ai.defaultPersonality.balanced")}</span>
        <span>{t("settings.ai.defaultPersonality.veryRational")}</span>
      </div>
    </>
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
      return <AiBasic {...props} agents={props.agents} onManageAgents={props.onManageAgents!} />;
    case "plugins":
      return <PluginPanel />;
    case "about":
      return <AboutSection {...props} />;
    default:
      return null;
  }
}
