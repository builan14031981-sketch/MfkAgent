"use client";

/**
 * AgentIconPreview —— Agent 图标三方案测试台（独立隔离，不修改任何生产组件）
 *
 * 用途：把 11 个 Agent 角色各自的 3 套方案（A 极简几何 / B 功能隐喻 / C 意象抽象）
 *       并排展示，并放入「助手切换胶囊 / 对话消息头像 / 侧边栏会话行」三个真实 UI 容器
 *       做小尺寸上身打样；支持一键切换明暗主题查看自适应。
 *
 * 规范：viewBox 24 · strokeWidth 1.5 · round · 纯线条 · currentColor（随主题自适应）。
 * 路由：/agent-icons-preview
 */

import { useEffect, useState } from "react";
import type { CSSProperties, ReactElement } from "react";
import { AGENT_IDS, AGENT_META, AGENT_ICON_SCHEMES } from "@/components/agent-icons";
import type { AgentIconScheme } from "@/components/agent-icons/base";

type IconComponent = () => ReactElement;

const SCHEME_LABEL: Record<AgentIconScheme, string> = {
  A: "A · 极简几何",
  B: "B · 功能隐喻",
  C: "C · 意象抽象",
};
const SCHEME_NOTE: Record<AgentIconScheme, string> = {
  A: "最克制的几何原型勾勒身份，小尺寸辨识度优先。",
  B: "用具象物件传递职责，语义直观、印象深刻。",
  C: "用弧线 / 轨道 / 节点表达气质，更灵动、更具个性。",
};

/* ── 场景容器：助手切换胶囊（24px 高） ─────────────────────── */
function Capsule({ Icon, name }: { Icon: IconComponent; name: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        height: 24,
        padding: "0 10px",
        borderRadius: 999,
        border: "1px solid var(--border-primary)",
        background: "var(--bg-level-3)",
        color: "var(--text-level-1)",
        fontSize: 12,
        whiteSpace: "nowrap",
      }}
    >
      <span style={{ color: "var(--text-level-2)", display: "inline-flex", fontSize: 15 }}>
        <Icon />
      </span>
      {name}
    </span>
  );
}

/* ── 场景容器：对话消息头像（16 / 20px） ───────────────────── */
function Avatar({ Icon, size }: { Icon: IconComponent; size: number }) {
  return (
    <span
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        border: "1px solid var(--border-primary)",
        background: "var(--bg-level-3)",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        color: "var(--text-level-2)",
        fontSize: size * 0.62,
      }}
    >
      <Icon />
    </span>
  );
}

/* ── 场景容器：侧边栏会话行前缀 ────────────────────────────── */
function SidebarRow({ Icon, name }: { Icon: IconComponent; name: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "4px 8px",
        borderRadius: 8,
        background: "var(--bg-level-2)",
        border: "1px solid var(--border-primary)",
        width: 128,
      }}
    >
      <span style={{ color: "var(--text-level-2)", display: "inline-flex", fontSize: 16 }}>
        <Icon />
      </span>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        <span style={{ fontSize: 11, color: "var(--text-level-1)", fontWeight: 600 }}>{name}</span>
        <span style={{ width: 60, height: 6, borderRadius: 3, background: "var(--bg-level-4)" }} />
      </div>
    </div>
  );
}

/* ── 单个方案列 ────────────────────────────────────────────── */
function SchemeCol({ scheme, Icon, name }: { scheme: AgentIconScheme; Icon: IconComponent; name: string }) {
  return (
    <div
      style={{
        flex: 1,
        minWidth: 0,
        border: "1px solid var(--border-primary)",
        borderRadius: "var(--radius-lg)",
        background: "var(--bg-level-2)",
        padding: 12,
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-level-1)" }}>{SCHEME_LABEL[scheme]}</div>
      {/* 大图 */}
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: 16,
          border: "1px solid var(--border-primary)",
          background: "var(--bg-level-1)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--color-primary)",
          fontSize: 44,
        }}
      >
        <Icon />
      </div>
      <p style={{ fontSize: 11, color: "var(--text-level-3)", lineHeight: 1.45, margin: 0 }}>{SCHEME_NOTE[scheme]}</p>

      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: "auto" }}>
        <Capsule Icon={Icon} name={name} />
        <div style={{ display: "flex", gap: 6 }}>
          <Avatar Icon={Icon} size={20} />
          <Avatar Icon={Icon} size={16} />
        </div>
        <SidebarRow Icon={Icon} name={name} />
      </div>
    </div>
  );
}

/* ── 页面 ──────────────────────────────────────────────────── */
export default function AgentIconPreviewPage() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    setDark(root.classList.contains("dark"));
  }, []);

  const toggleTheme = () => {
    const root = document.documentElement;
    const next = !dark;
    setDark(next);
    root.setAttribute("data-theme", next ? "midnight" : "studio-graphite");
    root.classList.remove("light", "dark");
    root.classList.add(next ? "dark" : "light");
  };

  return (
    <div
      style={{
        height: "100%",
        overflowY: "auto",
        lineHeight: 1.3,
        maxWidth: 1080,
        margin: "0 auto",
        padding: "20px 20px 48px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          marginBottom: 4,
        }}
      >
        <h1 style={{ fontSize: 18, fontWeight: 700, color: "var(--text-level-1)" }}>Agent 图标三方案测试台</h1>
        <button
          onClick={toggleTheme}
          style={{
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-3)",
            color: "var(--text-level-1)",
            fontSize: 12,
            fontWeight: 600,
            padding: "6px 12px",
            borderRadius: 999,
            cursor: "pointer",
          }}
        >
          {dark ? "☀️ 切到浅色" : "🌙 切到深色"}
        </button>
      </div>
      <p style={{ fontSize: 12, color: "var(--text-level-3)", marginBottom: 16 }}>
        viewBox 24 · strokeWidth 1.5 · round · 纯线条 · currentColor 随主题自适应 · 与生产组件隔离
      </p>

      {AGENT_IDS.map((id) => {
        const meta = AGENT_META[id];
        const schemes = AGENT_ICON_SCHEMES[id];
        return (
          <section
            key={id}
            style={{
              border: "1px solid var(--border-primary)",
              borderRadius: "var(--radius-lg)",
              background: "var(--bg-level-2)",
              padding: 14,
              marginBottom: 12,
            }}
          >
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 10 }}>
              <span style={{ fontSize: 14, fontWeight: 700, color: "var(--text-level-1)" }}>{meta.name}</span>
              <code style={{ fontSize: 11, color: "var(--text-level-3)", fontFamily: "var(--font-geist-mono), monospace" }}>
                {id}
              </code>
              <span style={{ fontSize: 12, color: "var(--text-level-2)" }}>{meta.desc}</span>
              <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--text-level-4)" }}>{meta.schemeNote}</span>
            </div>
            <div style={{ display: "flex", gap: 12, alignItems: "stretch" }}>
              {(Object.keys(schemes) as AgentIconScheme[]).map((s) => (
                <SchemeCol key={s} scheme={s} Icon={schemes[s]} name={meta.name} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}