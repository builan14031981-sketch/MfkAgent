"use client";
/**
 * AdvancedSettingsView —— 高级区块视图（字段级边界重构后）
 *
 * 职责：根据 activeSection 渲染对应 section 的"高级"部分（深水区参数）。
 *
 * 字段级边界契约（V2 重构）：
 * - general：无高级区块（全部上移到 BasicSettingsView），返回 null。
 * - model：Base URL 覆盖 + 自定义模型（含 model_id/api_base/temperature/max_tokens）+ 备用识图。
 * - ai：Agent 管理 + AI 长期记忆（保持不变）。
 * - plugins / about：无高级区块，返回 null。
 * - 本组件不持有业务状态，所有数据通过 props 注入（统管 props 单向数据流不变）。
 */
import { Bot, Workflow } from "lucide-react";
import { ModelAdvancedFields } from "./ModelConfigSection";
import { MemoryPanel } from "./MemoryPanel";
import type { AdvancedSettingsViewProps, SettingSectionId } from "./BasicSettingsView";

// ── model 高级区块：Base URL 覆盖 + 自定义模型 + 备用识图（深水区参数）──
function ModelAdvanced() {
  return <ModelAdvancedFields />;
}

// ── ai 高级区块：Agent 管理 + 子代理 + AI 长期记忆 ──
function AiAdvanced(props: AdvancedSettingsViewProps) {
  const { onManageAgents, onManageSubAgents, t } = props;
  return (
    <>
      {/* 预设 Agent：统一入口（列表在独立二级面板） */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "12px" }}>
        <div>
          <h3 style={{
            fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0,
            display: "flex", alignItems: "center", gap: "8px",
          }}>
            <Bot style={{ width: "16px", height: "16px" }} />
            {t("settings.ai.agents.title")}
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "4px 0 0 0" }}>
            {t("settings.ai.agents.desc")}
          </p>
        </div>
        <button
          onClick={onManageAgents}
          style={{
            display: "flex", alignItems: "center", gap: "6px", padding: "8px 14px",
            borderRadius: "var(--radius-md)", border: "1px solid var(--color-primary)",
            background: "var(--color-primary-lighter)", cursor: "pointer",
            fontSize: "13px", fontWeight: "500", color: "var(--color-primary)",
            whiteSpace: "nowrap", flexShrink: 0,
          }}
        >
          {t("settings.ai.agents.manage")} ›
        </button>
      </div>

      {/* 子代理：委派专用子任务给专门化子代理（独立二级面板） */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "12px", marginTop: "14px", paddingTop: "14px", borderTop: "1px solid var(--border-primary)" }}>
        <div>
          <h3 style={{
            fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0,
            display: "flex", alignItems: "center", gap: "8px",
          }}>
            <Workflow style={{ width: "16px", height: "16px" }} />
            {t("settings.ai.subAgents.title")}
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "4px 0 0 0" }}>
            {t("settings.ai.subAgents.desc")}
          </p>
        </div>
        <button
          onClick={onManageSubAgents}
          style={{
            display: "flex", alignItems: "center", gap: "6px", padding: "8px 14px",
            borderRadius: "var(--radius-md)", border: "1px solid var(--color-primary)",
            background: "var(--color-primary-lighter)", cursor: "pointer",
            fontSize: "13px", fontWeight: "500", color: "var(--color-primary)",
            whiteSpace: "nowrap", flexShrink: 0,
          }}
        >
          {t("settings.ai.subAgents.manage")} ›
        </button>
      </div>

      {/* AI 长期记忆（三作用域：全局 / Agent / 项目） */}
      <div style={{ marginTop: "24px" }}>
        <MemoryPanel embedded isOpen onClose={() => {}} />
      </div>
    </>
  );
}

/**
 * 高级区块视图入口：根据 activeSection 路由到对应 section 的高级部分。
 * general / extensions / about 无高级区块，返回 null。
 */
export function AdvancedSettingsView(
  props: AdvancedSettingsViewProps & { activeSection: SettingSectionId }
) {
  switch (props.activeSection) {
    case "general":
      // 字段级边界：General 全部上移到基础区，高级区无内容
      return null;
    case "model":
      return <ModelAdvanced />;
    case "ai":
      return <AiAdvanced {...props} />;
    case "extensions":
    case "about":
    default:
      return null;
  }
}
