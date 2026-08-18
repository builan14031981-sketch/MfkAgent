"use client";

/**
 * ExtensionPanel —— 扩展管理面板（V2）
 *
 * 定位：用户管理 AI 增强能力的入口。
 *
 * 页面结构（一级入口 + 二级管理 + 三级详情）：
 * - 一级 `home`（默认）：Skill / Plugins 两个入口卡，各带「管理」按钮
 * - 二级 `SKILL_MANAGE_VIEW`：全部内置 Skill 列表，可安装/卸载，点卡片进详情
 * - 二级 `PLUGIN_MANAGE_VIEW`：全部插件列表（V1 只读，展示运行状态）
 * - 三级：Skill 详情页（能力说明 + 适用场景 + 安装/关闭）
 *
 * Skill：用户可安装/卸载（后端持久化，卸载仅停用、可随时重装）
 * Plugin：V1 只读显示（不暴露 CRUD），符合企划书 V4.0 红线
 *
 * 视觉规范：
 * - 紧凑卡片严格对齐 AgentListPanel 的 10×12 padding、单行布局
 * - 卡片高度目标 ~60px
 */

import { useMemo, type CSSProperties, type ReactNode } from "react";
import {
  ChevronLeft,
  Sparkles,
  Code2,
  Terminal,
  FileText,
  Globe,
  Check,
  Database,
  Zap,
  ShieldCheck,
  Settings2 as Settings2Icon,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { useSkills } from "@/hooks/useSkills";
import { usePlugins, type PluginInfo, type PluginStatus } from "@/hooks/usePlugins";

/** 翻译函数类型（与 useTranslation 返回的 t 签名一致） */
type Translator = (key: string, params?: Record<string, string>) => string;

// ── Plugin 图标映射（与后端 plugin_id 对应） ──
const PLUGIN_ICON_MAP: Record<string, typeof Globe> = {
  web_search: Globe,
  code_execution: Terminal,
  file_operations: FileText,
  git: Code2,
  browser_ui: Globe,
  orchestration: Zap,
  core: ShieldCheck,
  browser_automation: Globe,
  system_control: Terminal,
  image_generation: Sparkles,
};

const PLUGIN_FALLBACK_ICON = Sparkles;

// ── Skill 图标映射（按后端 category 字段） ──

const SKILL_CATEGORY_ICON_MAP: Record<string, LucideIcon> = {
  开发: Code2,
  内容创作: FileText,
  数据分析: Database,
  办公效率: Zap,
  安全合规: ShieldCheck,
};

const SKILL_CATEGORY_FALLBACK_ICON = Sparkles;

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

const BACK_BUTTON_STYLE: CSSProperties = {
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
};

// ── 组件 ──

/** 二级「Skill 管理列表」的哨兵值（作为 editingSkillId 传入，表示非详情态） */
export const SKILL_MANAGE_VIEW = "__manage_skill__";
/** 二级「Plugin 管理列表」的哨兵值 */
export const PLUGIN_MANAGE_VIEW = "__manage_plugin__";

interface ExtensionPanelProps {
  /** 导航状态：null=扩展主页；SKILL_MANAGE_VIEW=Skill 列表；PLUGIN_MANAGE_VIEW=Plugin 列表；具体 id=Skill 详情 */
  editingSkillId: string | null;
  onSelectSkill: (id: string) => void;
  onBackToList: () => void;
}

export function ExtensionPanel({ editingSkillId, onSelectSkill, onBackToList }: ExtensionPanelProps) {
  const { t } = useTranslation();

  // 二级：Skill 管理列表
  if (editingSkillId === SKILL_MANAGE_VIEW) {
    return <ManageSkillList onSelectSkill={onSelectSkill} onBackToList={onBackToList} t={t} />;
  }

  // 二级：Plugin 管理列表
  if (editingSkillId === PLUGIN_MANAGE_VIEW) {
    return <ManagePluginList onBackToList={onBackToList} t={t} />;
  }

  // 三级：Skill 详情（返回 Skill 列表）
  if (editingSkillId != null) {
    return (
      <SkillDetail
        key={editingSkillId}
        skillId={editingSkillId}
        onBack={() => onSelectSkill(SKILL_MANAGE_VIEW)}
        t={t}
      />
    );
  }

  // 一级：扩展主页（Skill / Plugins 入口卡 + 管理按钮）
  return <ExtensionHome onSelectSkill={onSelectSkill} t={t} />;
}

// ── 扩展主页（一级）：Skill / Plugins 两个入口卡，各带「管理」按钮 ──

function ExtensionHome({
  onSelectSkill,
  t,
}: {
  onSelectSkill: (id: string) => void;
  t: Translator;
}) {
  const { skills, loading, error } = useSkills();
  const { plugins: allPlugins } = usePlugins();

  const installedCount = useMemo(
    () => skills.filter((s) => s.installed).length,
    [skills]
  );

  const pluginCount = useMemo(() => allPlugins.length, [allPlugins]);

  return (
    <div>
      <SectionHeader
        title={t("settings.extensions.title")}
        subtitle={t("settings.extensions.subtitle")}
      />

      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {/* 入口卡: Skill */}
        <EntryCard
          icon={<Sparkles style={{ width: "18px", height: "18px", color: "var(--color-primary)" }} />}
          name={t("settings.extensions.skills.sectionTitle")}
          summary={
            loading
              ? t("common.loading")
              : error
                ? error
                : t("settings.extensions.skills.sectionDesc")
          }
          meta={loading ? "" : t("settings.extensions.skills.installedCount", {
            count: String(installedCount),
            total: String(skills.length),
          })}
          actionLabel={t("settings.extensions.manage")}
          t={t}
          onManage={() => onSelectSkill(SKILL_MANAGE_VIEW)}
        />

        {/* 入口卡: Plugins（真能力：启用/停用决定该插件工具是否对 Agent 可见） */}
        <EntryCard
          icon={<Terminal style={{ width: "18px", height: "18px", color: "var(--color-primary)" }} />}
          name={t("settings.extensions.plugins.sectionTitle")}
          summary={t("settings.extensions.plugins.sectionDesc")}
          meta={pluginCount > 0 ? `${pluginCount} 个` : ""}
          actionLabel={t("settings.extensions.manage")}
          t={t}
          onManage={() => onSelectSkill(PLUGIN_MANAGE_VIEW)}
        />
      </div>
    </div>
  );
}

/** 一级入口卡：图标 + 名称 + 摘要 + 右侧「管理」按钮（同一容器内尺寸统一） */
function EntryCard({
  icon,
  name,
  summary,
  meta,
  actionLabel,
  t,
  onManage,
}: {
  icon: ReactNode;
  name: string;
  summary: string;
  meta: string;
  actionLabel: string;
  t: Translator;
  onManage: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "14px 12px",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-level-2)",
        border: "1px solid var(--border-primary)",
        minHeight: "64px",
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
          fontSize: "12px",
          color: "var(--text-level-3)",
          margin: "2px 0 0 0",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          lineHeight: 1.4,
        }}>
          {meta ? `${meta} · ${summary}` : summary}
        </p>
      </div>
      <span
        onClick={onManage}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onManage();
          }
        }}
        title={actionLabel}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "4px",
          padding: "6px 14px",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--color-primary)",
          background: "var(--color-primary-lighter, var(--bg-level-2))",
          cursor: "pointer",
          fontSize: "12px",
          fontWeight: "500",
          color: "var(--color-primary)",
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        <Settings2Icon style={{ width: "13px", height: "13px" }} />
        {actionLabel}
      </span>
    </div>
  );
}

// ── Skill 管理列表（二级）：按分类分组展示，可安装/卸载，点卡片进详情 ──

/** 分类展示顺序（与后端 SKILL_CATALOG 的 5 大意图分类对齐） */
const SKILL_CATEGORY_ORDER = ["开发", "内容创作", "数据分析", "办公效率", "安全合规"];

function ManageSkillList({
  onSelectSkill,
  onBackToList,
  t,
}: {
  onSelectSkill: (id: string) => void;
  onBackToList: () => void;
  t: Translator;
}) {
  const { skills, loading, error, installSkill, uninstallSkill } = useSkills();

  const installedCount = useMemo(
    () => skills.filter((s) => s.installed).length,
    [skills]
  );

  /** 按分类顺序分组：未知分类归入末尾 */
  const grouped = useMemo(() => {
    const map = new Map<string, typeof skills>();
    for (const s of skills) {
      const cat = s.category || "其他";
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(s);
    }
    const ordered = SKILL_CATEGORY_ORDER.filter((c) => map.has(c));
    const rest = [...map.keys()].filter((c) => !SKILL_CATEGORY_ORDER.includes(c));
    return [...ordered, ...rest].map((cat) => ({ category: cat, list: map.get(cat)! }));
  }, [skills]);

  // 加入/移出 Skill 库：安装语义 = 出现在输入框 + 号「调用 Skill」列表，供用户在当前会话激活
  const toggleLibrary = async (id: string) => {
    const s = skills.find((x) => x.id === id);
    if (!s) return;
    if (s.installed) await uninstallSkill(s.id);
    else await installSkill(s.id);
  };

  return (
    <div>
      {/* 返回扩展主页 */}
      <button onClick={onBackToList} style={BACK_BUTTON_STYLE}>
        <ChevronLeft style={{ width: "14px", height: "14px" }} />
        {t("settings.extensions.manageBackHome")}
      </button>

      <SectionHeader
        title={t("settings.extensions.skills.sectionTitle")}
        subtitle={t("settings.extensions.skills.sectionDesc")}
        counter={t("settings.extensions.skills.installedCount", {
          count: String(installedCount),
          total: String(skills.length),
        })}
      />

      {/* 会话级说明：告知 Skill 如何开启，消除「安装=全局生效」误解 */}
      <p style={{
        fontSize: "11px",
        color: "var(--text-level-4)",
        margin: "4px 0 10px 0",
        lineHeight: 1.55,
      }}>
        {t("settings.extensions.skills.usageNote")}
      </p>

      {loading ? (
        <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: 0 }}>{t("common.loading")}</p>
      ) : error ? (
        <p style={{ fontSize: "12px", color: "var(--color-error)", margin: 0 }}>{error}</p>
      ) : skills.length === 0 ? (
        <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: 0 }}>{t("common.noData")}</p>
      ) : (
        grouped.map(({ category, list }) => (
          <div key={category} style={{ marginBottom: "14px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                margin: "0 0 8px 0",
              }}
            >
              <span
                style={{
                  fontSize: "12px",
                  fontWeight: "600",
                  color: "var(--text-level-2)",
                  margin: 0,
                }}
              >
                {category}
              </span>
              <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>
                {t("settings.extensions.skills.categoryCount", { count: String(list.length) })}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {list.map((skill) => {
                const Icon = SKILL_CATEGORY_ICON_MAP[skill.category] ?? SKILL_CATEGORY_FALLBACK_ICON;
                return (
                  <SkillCompactCard
                    key={skill.id}
                    icon={<Icon style={{ width: "18px", height: "18px", color: "var(--color-primary)" }} />}
                    name={skill.name}
                    summary={skill.description}
                    inLibrary={skill.installed}
                    t={t}
                    onClick={() => onSelectSkill(skill.id)}
                    onToggleLibrary={() => toggleLibrary(skill.id)}
                  />
                );
              })}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// ── Skill 紧凑卡片（核心规格：60px 高，10×12 padding）──

function SkillCompactCard({
  icon,
  name,
  summary,
  inLibrary,
  t,
  onClick,
  onToggleLibrary,
}: {
  icon: ReactNode;
  name: string;
  summary: string;
  inLibrary: boolean;
  t: Translator;
  onClick: () => void;
  onToggleLibrary: () => void;
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
      {inLibrary && (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "1px 7px",
            borderRadius: "var(--radius-full)",
            background: "var(--color-primary-lighter, var(--bg-level-3))",
            color: "var(--color-primary)",
            fontSize: "10px",
            fontWeight: "500",
            lineHeight: "14px",
            flexShrink: 0,
          }}
        >
          {t("settings.extensions.skills.installed")}
        </span>
      )}
      <span
        role="button"
        tabIndex={0}
        onClick={(e) => { e.stopPropagation(); onToggleLibrary(); }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            e.stopPropagation();
            onToggleLibrary();
          }
        }}
        title={inLibrary ? t("settings.extensions.skills.removeFromLibrary") : t("settings.extensions.skills.install")}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "3px",
          padding: "5px 10px",
          borderRadius: "var(--radius-sm)",
          border: inLibrary ? "1px solid var(--border-primary)" : "1px solid var(--color-primary)",
          background: inLibrary ? "transparent" : "var(--color-primary)",
          cursor: "pointer",
          fontSize: "12px",
          fontWeight: "500",
          color: inLibrary ? "var(--text-level-2)" : "#fff",
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        {inLibrary ? t("settings.extensions.skills.removeFromLibrary") : t("settings.extensions.skills.install")}
      </span>
      <span
        role="button"
        tabIndex={0}
        onClick={(e) => { e.stopPropagation(); onClick(); }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            e.stopPropagation();
            onClick();
          }
        }}
        title={t("settings.extensions.skills.detail")}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "3px",
          padding: "5px 10px",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-primary)",
          background: "transparent",
          cursor: "pointer",
          fontSize: "12px",
          fontWeight: "500",
          color: "var(--text-level-2)",
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        {t("settings.extensions.skills.detail")}
      </span>
    </div>
  );
}

// ── Plugin 管理列表（二级，真能力：启用/停用决定该插件工具是否对 Agent 可见） ──

const PLUGIN_STATUS_COLOR: Record<string, string> = {
  active: "var(--color-primary)",
  installed: "var(--text-level-3)",
  inactive: "var(--text-level-4)",
  error: "var(--color-error)",
};

function ManagePluginList({ onBackToList, t }: { onBackToList: () => void; t: Translator }) {
  const { plugins, loading, setPluginActive } = usePlugins();

  const activeCount = useMemo(
    () => plugins.filter((p) => p.status === "active").length,
    [plugins]
  );

  const toggle = async (p: PluginInfo) => {
    const next = p.status !== "active";
    try {
      await setPluginActive(p.pluginId, next);
    } catch (err) {
      console.error("Failed to toggle plugin:", err);
    }
  };

  return (
    <div>
      {/* 返回扩展主页 */}
      <button onClick={onBackToList} style={BACK_BUTTON_STYLE}>
        <ChevronLeft style={{ width: "14px", height: "14px" }} />
        {t("settings.extensions.manageBackHome")}
      </button>

      <SectionHeader
        title={t("settings.extensions.plugins.sectionTitle")}
        subtitle={t("settings.extensions.plugins.sectionDesc")}
        counter={t("settings.extensions.plugins.activeCount", {
          count: String(activeCount),
          total: String(plugins.length),
        })}
      />

      <p style={{
        fontSize: "11px",
        color: "var(--text-level-4)",
        margin: "4px 0 10px 0",
        lineHeight: 1.55,
      }}>
        {t("settings.extensions.plugins.softNote")}
      </p>

      {loading ? (
        <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: 0 }}>{t("common.loading")}</p>
      ) : plugins.length === 0 ? (
        <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: 0 }}>{t("settings.extensions.plugins.empty")}</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {plugins.map((p) => {
            const active = p.status === "active";
            const Icon = PLUGIN_ICON_MAP[p.pluginId] ?? PLUGIN_FALLBACK_ICON;
            const statusLabel =
              p.status === "active"
                ? t("settings.extensions.plugins.statusActive")
                : p.status === "inactive"
                  ? t("settings.extensions.plugins.statusInactive")
                  : p.status === "installed"
                    ? t("settings.extensions.plugins.statusInstalled")
                    : t("settings.extensions.plugins.statusError");
            return (
              <div
                key={p.pluginId}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  padding: "10px 12px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--bg-level-2)",
                  border: "1px solid var(--border-primary)",
                  minHeight: "60px",
                }}
              >
                <Icon style={{ width: "18px", height: "18px", color: "var(--color-primary)", flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)" }}>{p.name}</span>
                    <span style={{
                      fontSize: "10px",
                      color: PLUGIN_STATUS_COLOR[p.status] ?? "var(--text-level-3)",
                      background: "var(--bg-level-3)",
                      borderRadius: "var(--radius-full)",
                      padding: "1px 7px",
                      lineHeight: "14px",
                    }}>
                      {statusLabel}
                    </span>
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
                    {p.description}
                  </p>
                </div>
                <button
                  onClick={() => toggle(p)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "3px",
                    padding: "5px 10px",
                    borderRadius: "var(--radius-sm)",
                    border: active ? "1px solid var(--border-primary)" : "1px solid var(--color-primary)",
                    background: active ? "transparent" : "var(--color-primary)",
                    cursor: "pointer",
                    fontSize: "12px",
                    fontWeight: "500",
                    color: active ? "var(--text-level-2)" : "#fff",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                  }}
                >
                  {active && <Check style={{ width: "12px", height: "12px" }} />}
                  {active ? t("settings.extensions.plugins.disable") : t("settings.extensions.plugins.enable")}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Skill 详情页（仿 Agent 详情结构） ──

function SkillDetail({
  skillId,
  onBack,
  t,
}: {
  skillId: string;
  onBack: () => void;
  t: Translator;
}) {
  const { skills, loading, installSkill, uninstallSkill } = useSkills();
  const skill = skills.find((s) => s.id === skillId);

  if (loading && !skill) {
    return (
      <p style={{ fontSize: "13px", color: "var(--text-level-3)" }}>
        {t("common.loading")}
      </p>
    );
  }

  if (!skill) {
    return (
      <p style={{ fontSize: "13px", color: "var(--text-level-3)" }}>
        {t("settings.extensions.skillDetail.notFound")}
      </p>
    );
  }

  const Icon = SKILL_CATEGORY_ICON_MAP[skill.category] ?? SKILL_CATEGORY_FALLBACK_ICON;
  const isInstalled = skill.installed;

  // 加入/移出 Skill 库：安装语义 = 出现在输入框 + 号「调用 Skill」列表
  const toggleLibrary = async () => {
    if (!skill) return;
    if (skill.installed) await uninstallSkill(skill.id);
    else await installSkill(skill.id);
  };

  return (
    <div>
      {/* 返回 Skill 列表 */}
      <button onClick={onBack} style={BACK_BUTTON_STYLE}>
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
                {skill.name}
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
              {skill.description}
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
          {skill.description}
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
          {skill.tags.length > 0 ? skill.tags.join("、") : "-"}
        </div>
      </div>

      {/* Block 4: 加入/移出 Skill 库（加入后出现在输入框 + 号「调用 Skill」列表） */}
      <div style={{ marginTop: "16px", display: "flex", justifyContent: "flex-end", gap: "8px", alignItems: "center" }}>
        <span style={{ fontSize: "11px", color: "var(--text-level-4)", marginRight: "auto", lineHeight: 1.5, maxWidth: "300px" }}>
          {t("settings.extensions.skills.usageNote")}
        </span>
        <button
          onClick={toggleLibrary}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "7px 16px",
            borderRadius: "var(--radius-sm)",
            border: isInstalled ? "1px solid var(--border-primary)" : "1px solid var(--color-primary)",
            background: isInstalled ? "transparent" : "var(--color-primary)",
            cursor: "pointer",
            fontSize: "12px",
            fontWeight: "500",
            color: isInstalled ? "var(--text-level-2)" : "#fff",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
        >
          {isInstalled && <Check style={{ width: "13px", height: "13px" }} />}
          {isInstalled ? t("settings.extensions.skills.removeFromLibrary") : t("settings.extensions.skills.install")}
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
  counter?: string;
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
        <h4 style={{
          fontSize: "13px",
          fontWeight: "600",
          color: "var(--text-level-1)",
          margin: 0,
        }}>{title}</h4>
        <p style={{
          fontSize: "12px",
          color: "var(--text-level-3)",
          margin: "2px 0 0 0",
          lineHeight: 1.4,
        }}>{subtitle}</p>
      </div>
      {counter && (
        <span style={{
          fontSize: "11px",
          color: "var(--text-level-4)",
          fontVariantNumeric: "tabular-nums",
          flexShrink: 0,
          paddingTop: "2px",
        }}>
          {counter}
        </span>
      )}
    </div>
  );
}