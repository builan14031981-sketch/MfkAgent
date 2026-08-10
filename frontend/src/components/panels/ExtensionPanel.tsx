"use client";

/**
 * ExtensionPanel —— 扩展管理面板（V2）
 *
 * 定位：用户管理 AI 增强能力的入口。
 *
 * 页面结构（双区块 + 三级导航）：
 * - main_extensions（默认）
 *   - 区块 1: Skills（紧凑卡片，5 个内置 Skill）
 *   - 区块 2: Plugins（从 /api/plugins 拉取，紧凑卡片）
 * - skill_detail（点击 Skill 卡片后进入）
 *   - 头部卡 + 能力说明 + 适用场景 + 操作
 *
 * V1 原则：
 * - Skill：用户可启用/关闭
 * - Plugin：V1 只读显示（不暴露 CRUD），符合企划书 V4.0 红线
 *
 * 视觉规范：
 * - 紧凑卡片严格对齐 AgentListPanel 的 10×12 padding、单行布局
 * - 卡片高度目标 ~60px
 * - 三级导航复用 SettingsPanel 的 AnimatePresence 模式
 */

import { useState, useEffect, useMemo, type CSSProperties } from "react";
import { ChevronLeft, Sparkles, Presentation, Code2, Search, Palette, ShieldCheck, Globe, Terminal, FileText, Check } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { usePlugins, type PluginInfo } from "@/hooks/usePlugins";

// ── Skill 元数据（V1 静态） ──

export type SkillId = "ppt" | "python" | "research" | "ui" | "security";

interface SkillMeta {
  id: SkillId;
  icon: typeof Sparkles;
  i18nKey: SkillId;
}

const SKILL_META: SkillMeta[] = [
  { id: "ppt", icon: Presentation, i18nKey: "ppt" },
  { id: "python", icon: Code2, i18nKey: "python" },
  { id: "research", icon: Search, i18nKey: "research" },
  { id: "ui", icon: Palette, i18nKey: "ui" },
  { id: "security", icon: ShieldCheck, i18nKey: "security" },
];

const SKILL_STORAGE_KEY = "mfk_installed_skills";

/** 读取已安装 Skill 列表（SSR 安全） */
function readInstalledSkills(): Set<SkillId> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(SKILL_STORAGE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return new Set();
    return new Set(arr.filter((x): x is SkillId =>
      x === "ppt" || x === "python" || x === "research" || x === "ui" || x === "security"
    ));
  } catch {
    return new Set();
  }
}

function writeInstalledSkills(set: Set<SkillId>): void {
  try {
    localStorage.setItem(SKILL_STORAGE_KEY, JSON.stringify([...set]));
  } catch {
    /* 静默 */
  }
}

// ── Plugin 图标映射（与 usePlugins 后端数据 plugin_id 对应） ──

const PLUGIN_ICON_MAP: Record<string, typeof Globe> = {
  web_search: Globe,
  code_execution: Terminal,
  file_operations: FileText,
};

const PLUGIN_FALLBACK_ICON = Sparkles;

// ── 公共样式（紧凑卡片基线） ──

const COMPACT_CARD_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "10px",
  padding: "10px 12px",
  borderRadius: "var(--radius-md)",
  background: "var(--bg-level-2)",
  border: "1px solid var(--border-primary)",
  cursor: "pointer",
  transition: "background var(--transition-fast), border-color var(--transition-fast)",
  minHeight: "60px",
};

const SECTION_TITLE_STYLE: CSSProperties = {
  fontSize: "13px",
  fontWeight: "600",
  color: "var(--text-level-1)",
  margin: 0,
};

const SECTION_SUBTITLE_STYLE: CSSProperties = {
  fontSize: "12px",
  color: "var(--text-level-3)",
  margin: "2px 0 0 0",
  lineHeight: 1.4,
};

const SOFT_NOTE_STYLE: CSSProperties = {
  fontSize: "11px",
  color: "var(--text-level-4)",
  margin: "4px 0 10px 0",
  lineHeight: 1.55,
};

// ── 组件 ──

interface ExtensionPanelProps {
  /** 当前查看的 Skill id；null 表示扩展主页 */
  editingSkillId: SkillId | null;
  onSelectSkill: (id: SkillId) => void;
  onBackToList: () => void;
}

export function ExtensionPanel({ editingSkillId, onSelectSkill, onBackToList }: ExtensionPanelProps) {
  const { t } = useTranslation();

  // 详情页渲染优先级最高
  // 使用 key={editingSkillId} 强制 Remount：导航切换 Skill 时自然重新读取 localStorage，
  // 避免 useEffect+setState 同步触发带来的级联渲染风险。
  if (editingSkillId != null) {
    return (
      <SkillDetail
        key={editingSkillId}
        skillId={editingSkillId}
        onBack={onBackToList}
        t={t}
      />
    );
  }

  return <ExtensionList onSelectSkill={onSelectSkill} t={t} />;
}

// ── 扩展主页 ──

type Translator = (key: string, params?: Record<string, string>) => string;

function ExtensionList({
  onSelectSkill,
  t,
}: {
  onSelectSkill: (id: SkillId) => void;
  t: Translator;
}) {
  const [installed, setInstalled] = useState<Set<SkillId>>(() => readInstalledSkills());

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === SKILL_STORAGE_KEY) setInstalled(readInstalledSkills());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const toggleSkill = (id: SkillId) => {
    setInstalled((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      writeInstalledSkills(next);
      return next;
    });
  };

  return (
    <div>
      {/* ── 区块 1: Skills ── */}
      <SectionHeader
        title={t("settings.extensions.skills.sectionTitle")}
        subtitle={t("settings.extensions.skills.sectionDesc")}
        counter={t("settings.extensions.skills.installedCount", {
          count: String(installed.size),
          total: String(SKILL_META.length),
        })}
      />

      <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "22px" }}>
        {SKILL_META.map(({ id, icon: Icon }) => {
          const isInstalled = installed.has(id);
          return (
            <SkillCompactCard
              key={id}
              id={id}
              icon={<Icon style={{ width: "18px", height: "18px", color: "var(--color-primary)" }} />}
              name={t(`settings.extensions.skillList.${id}.name`)}
              summary={t(`settings.extensions.skillList.${id}.summary`)}
              isInstalled={isInstalled}
              t={t}
              onClick={() => onSelectSkill(id)}
              onToggle={(e) => {
                e.stopPropagation();
                toggleSkill(id);
              }}
            />
          );
        })}
      </div>

      {/* ── 区块 2: Plugins ── */}
      <PluginSection t={t} />
    </div>
  );
}

// ── Skill 紧凑卡片（核心规格：60px 高，10×12 padding） ──

function SkillCompactCard({
  icon,
  name,
  summary,
  isInstalled,
  t,
  onClick,
  onToggle,
}: {
  id: SkillId;
  icon: React.ReactNode;
  name: string;
  summary: string;
  isInstalled: boolean;
  t: Translator;
  onClick: () => void;
  onToggle: (e: React.MouseEvent) => void;
}) {
  return (
    <div
      onClick={onClick}
      style={COMPACT_CARD_STYLE}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "var(--bg-level-3)";
        e.currentTarget.style.borderColor = "var(--text-level-4)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "var(--bg-level-2)";
        e.currentTarget.style.borderColor = "var(--border-primary)";
      }}
    >
      {icon}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{
          fontSize: "13px",
          fontWeight: "500",
          color: "var(--text-level-1)",
          margin: 0,
          lineHeight: 1.4,
        }}>
          {name}
        </p>
        <p style={{
          fontSize: "11px",
          color: "var(--text-level-3)",
          margin: "2px 0 0 0",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          lineHeight: 1.4,
        }}>
          {summary}
        </p>
      </div>
      <button
        onClick={onToggle}
        title={isInstalled ? t("settings.extensions.skills.disable") : t("settings.extensions.skills.install")}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "3px",
          padding: "5px 10px",
          borderRadius: "var(--radius-sm)",
          border: isInstalled ? "1px solid var(--border-primary)" : "1px solid var(--color-primary)",
          background: isInstalled ? "transparent" : "var(--color-primary-lighter, var(--bg-level-2))",
          cursor: "pointer",
          fontSize: "12px",
          fontWeight: "500",
          color: isInstalled ? "var(--text-level-2)" : "var(--color-primary)",
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        {isInstalled ? (
          <>
            <Check style={{ width: "11px", height: "11px" }} />
            {t("settings.extensions.skills.installed")}
          </>
        ) : (
          t("settings.extensions.skills.install")
        )}
      </button>
    </div>
  );
}

// ── Plugins 区块（V1 只读） ──

function PluginSection({ t }: { t: Translator }) {
  const { plugins, loading, error } = usePlugins();

  // 排序：active > installed > inactive > error
  const sortedPlugins = useMemo(() => {
    const order: Record<PluginInfo["status"], number> = {
      active: 0, installed: 1, inactive: 2, error: 3,
    };
    return [...plugins].sort((a, b) => order[a.status] - order[b.status]);
  }, [plugins]);

  const activeCount = useMemo(
    () => plugins.filter((p) => p.status === "active").length,
    [plugins]
  );

  return (
    <div>
      <SectionHeader
        title={t("settings.extensions.plugins.sectionTitle")}
        subtitle={t("settings.extensions.plugins.sectionDesc")}
        counter={t("settings.extensions.plugins.activeCount", {
          count: String(activeCount),
          total: String(plugins.length),
        })}
      />

      {/* 软说明文：自然融入，紧跟副标题下方 */}
      <p style={SOFT_NOTE_STYLE}>
        {t("settings.extensions.plugins.softNote")}
      </p>

      {loading ? (
        <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: 0 }}>{t("common.loading")}</p>
      ) : error ? (
        <p style={{ fontSize: "12px", color: "var(--color-error)", margin: 0 }}>{error}</p>
      ) : plugins.length === 0 ? (
        <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: 0 }}>
          {t("settings.extensions.plugins.empty")}
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {sortedPlugins.map((plugin) => {
            const Icon = PLUGIN_ICON_MAP[plugin.pluginId] ?? PLUGIN_FALLBACK_ICON;
            return (
              <PluginCompactCard
                key={plugin.pluginId}
                icon={<Icon style={{ width: "18px", height: "18px", color: "var(--color-primary)" }} />}
                name={plugin.name}
                version={`v${plugin.version}`}
                summary={plugin.description}
                status={plugin.status}
                t={t}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Plugin 紧凑卡片（同 Skill 卡片视觉，区分度在版本号 + 状态徽章） ──

function PluginCompactCard({
  icon,
  name,
  version,
  summary,
  status,
  t,
}: {
  icon: React.ReactNode;
  name: string;
  version: string;
  summary: string;
  status: PluginInfo["status"];
  t: Translator;
}) {
  return (
    <div style={COMPACT_CARD_STYLE}>
      {icon}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          lineHeight: 1.4,
        }}>
          <p style={{
            fontSize: "13px",
            fontWeight: "500",
            color: "var(--text-level-1)",
            margin: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}>
            {name}
          </p>
          <span style={{
            fontSize: "11px",
            color: "var(--text-level-4)",
            flexShrink: 0,
          }}>
            {version}
          </span>
          <StatusBadge status={status} t={t} />
        </div>
        <p style={{
          fontSize: "11px",
          color: "var(--text-level-3)",
          margin: "2px 0 0 0",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          lineHeight: 1.4,
        }}>
          {summary}
        </p>
      </div>
    </div>
  );
}

function StatusBadge({ status, t }: { status: PluginInfo["status"]; t: Translator }) {
  const colorMap: Record<PluginInfo["status"], { bg: string; fg: string }> = {
    active: { bg: "var(--color-primary-lighter, var(--bg-level-3))", fg: "var(--color-primary)" },
    installed: { bg: "var(--bg-level-3)", fg: "var(--text-level-3)" },
    inactive: { bg: "var(--bg-level-3)", fg: "var(--text-level-4)" },
    error: { bg: "var(--bg-level-3)", fg: "var(--color-error)" },
  };
  const labelMap: Record<PluginInfo["status"], string> = {
    active: "settings.extensions.plugins.statusActive",
    installed: "settings.extensions.plugins.statusInstalled",
    inactive: "settings.extensions.plugins.statusInactive",
    error: "settings.extensions.plugins.statusError",
  };
  const c = colorMap[status];
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      padding: "1px 6px",
      borderRadius: "var(--radius-full)",
      background: c.bg,
      color: c.fg,
      fontSize: "10px",
      fontWeight: "500",
      lineHeight: "14px",
      flexShrink: 0,
    }}>
      {t(labelMap[status])}
    </span>
  );
}

// ── Skill 详情页（仿 Agent 详情结构） ──

function SkillDetail({
  skillId,
  onBack,
  t,
}: {
  skillId: SkillId;
  onBack: () => void;
  t: Translator;
}) {
  const meta = SKILL_META.find((s) => s.id === skillId);
  // 初始值懒加载即可：父组件已用 key={skillId} 强制 Remount，
  // 每次进入都是全新实例，state 重新初始化天然反映最新 localStorage。
  const [installed, setInstalled] = useState<Set<SkillId>>(() => readInstalledSkills());

  if (!meta) {
    return (
      <p style={{ fontSize: "13px", color: "var(--text-level-3)" }}>
        {t("settings.extensions.skillDetail.notFound")}
      </p>
    );
  }

  const Icon = meta.icon;
  const isInstalled = installed.has(skillId);
  const baseKey = `settings.extensions.skillList.${skillId}`;

  const toggle = () => {
    setInstalled((prev) => {
      const next = new Set(prev);
      if (next.has(skillId)) next.delete(skillId);
      else next.add(skillId);
      writeInstalledSkills(next);
      return next;
    });
  };

  return (
    <div>
      {/* 返回列表 */}
      <button
        onClick={onBack}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          padding: "5px 10px",
          marginBottom: "12px",
          borderRadius: "var(--radius-sm)",
          border: "none",
          background: "transparent",
          cursor: "pointer",
          fontSize: "12px",
          color: "var(--text-level-3)",
        }}
      >
        <ChevronLeft style={{ width: "14px", height: "14px" }} />
        {t("settings.extensions.skillDetail.backToList")}
      </button>

      {/* Block 1: 头部卡（对齐 Agent 详情） */}
      <div style={{
        padding: "12px",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-level-2)",
        border: "1px solid var(--border-primary)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "32px",
            height: "32px",
            borderRadius: "var(--radius-sm)",
            background: "var(--color-primary-lighter, var(--bg-level-3))",
            color: "var(--color-primary)",
            flexShrink: 0,
          }}>
            <Icon style={{ width: "18px", height: "18px" }} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <p style={{ fontSize: "14px", fontWeight: "600", color: "var(--text-level-1)", margin: 0 }}>
                {t(`${baseKey}.name`)}
              </p>
              {isInstalled && (
                <span style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "3px",
                  fontSize: "11px",
                  padding: "1px 8px",
                  borderRadius: "var(--radius-full)",
                  background: "var(--color-primary-lighter, var(--bg-level-3))",
                  color: "var(--color-primary)",
                  lineHeight: "16px",
                }}>
                  <Check style={{ width: "10px", height: "10px" }} />
                  {t("settings.extensions.skills.installed")}
                </span>
              )}
            </div>
            <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
              {t(`${baseKey}.summary`)}
            </p>
          </div>
        </div>
      </div>

      {/* Block 2: 能力说明 */}
      <div style={{ marginTop: "16px" }}>
        <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: "0 0 6px 0" }}>
          {t("settings.extensions.skills.capabilities")}
        </h4>
        <div style={{
          padding: "10px 12px",
          borderRadius: "var(--radius-sm)",
          background: "var(--bg-level-1)",
          border: "1px solid var(--border-primary)",
          fontSize: "12px",
          color: "var(--text-level-2)",
          lineHeight: 1.6,
        }}>
          {t(`${baseKey}.capabilities`)}
        </div>
      </div>

      {/* Block 3: 适用场景 */}
      <div style={{ marginTop: "12px" }}>
        <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: "0 0 6px 0" }}>
          {t("settings.extensions.skills.scenarios")}
        </h4>
        <div style={{
          padding: "10px 12px",
          borderRadius: "var(--radius-sm)",
          background: "var(--bg-level-1)",
          border: "1px solid var(--border-primary)",
          fontSize: "12px",
          color: "var(--text-level-2)",
          lineHeight: 1.6,
        }}>
          {t(`${baseKey}.scenarios`)}
        </div>
      </div>

      {/* Block 4: 操作按钮 */}
      <div style={{ marginTop: "16px", display: "flex", justifyContent: "flex-end", gap: "8px" }}>
        <button
          onClick={toggle}
          style={{
            padding: "7px 20px",
            borderRadius: "var(--radius-sm)",
            border: isInstalled ? "1px solid var(--border-primary)" : "1px solid var(--color-primary)",
            background: isInstalled ? "transparent" : "var(--color-primary)",
            color: isInstalled ? "var(--text-level-1)" : "#fff",
            cursor: "pointer",
            fontSize: "13px",
            fontWeight: "500",
          }}
        >
          {isInstalled ? t("settings.extensions.skills.disable") : t("settings.extensions.skills.install")}
        </button>
      </div>
    </div>
  );
}

// ── 区块头部（标题 + 副标题 + 右上计数器） ──

function SectionHeader({
  title,
  subtitle,
  counter,
}: {
  title: string;
  subtitle: string;
  counter: string;
}) {
  return (
    <div style={{
      display: "flex",
      alignItems: "baseline",
      justifyContent: "space-between",
      marginBottom: "8px",
      gap: "12px",
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <h4 style={SECTION_TITLE_STYLE}>{title}</h4>
        <p style={SECTION_SUBTITLE_STYLE}>{subtitle}</p>
      </div>
      <span style={{
        fontSize: "11px",
        color: "var(--text-level-4)",
        fontVariantNumeric: "tabular-nums",
        flexShrink: 0,
        paddingTop: "2px",
      }}>
        {counter}
      </span>
    </div>
  );
}
