"use client";
/**
 * AdvancedSettingsView —— 高级区块视图（VS Code 极简风格重构）
 *
 * 核心规矩：
 * - 移除内嵌的庞大 MemoryPanel，改为轻量入口行，点击直达独立记忆管理中心 (/memories)
 * - 智能体定制、子代理委派、记忆条目库三者统一为紧凑规范的入口行
 * - model 高级区展示自定义端点与模型深水区参数
 */
import { useRouter } from "next/navigation";
import { Bot, Workflow, Brain } from "lucide-react";
import { ModelAdvancedFields } from "./ModelConfigSection";
import type { AdvancedSettingsViewProps, SettingSectionId } from "./BasicSettingsView";

// ── model 高级区块：Base URL 覆盖 + 自定义模型 ──
function ModelAdvanced() {
  return <ModelAdvancedFields />;
}

// ── ai 高级区块：智能体定制 + 子代理 + 长期记忆库入口 ──
function AiAdvanced(props: AdvancedSettingsViewProps) {
  const router = useRouter();
  const { onManageAgents, onManageSubAgents, onClose, t } = props;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
      {/* 预设智能体配置 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "12px",
          padding: "10px 0",
          borderBottom: "1px solid var(--border-secondary)",
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <h4
            style={{
              fontSize: "13px",
              fontWeight: 500,
              color: "var(--text-level-1)",
              margin: 0,
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <Bot style={{ width: "15px", height: "15px", color: "var(--text-level-3)" }} />
            {t("settings.ai.agents.title")}
          </h4>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
            {t("settings.ai.agents.desc")}
          </p>
        </div>
        <button
          type="button"
          onClick={onManageAgents}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            height: "30px",
            padding: "0 12px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-2)",
            cursor: "pointer",
            fontSize: "12px",
            fontWeight: 500,
            color: "var(--text-level-2)",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
        >
          {t("settings.ai.agents.manage")} ›
        </button>
      </div>

      {/* 子代理委派 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "12px",
          padding: "10px 0",
          borderBottom: "1px solid var(--border-secondary)",
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <h4
            style={{
              fontSize: "13px",
              fontWeight: 500,
              color: "var(--text-level-1)",
              margin: 0,
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <Workflow style={{ width: "15px", height: "15px", color: "var(--text-level-3)" }} />
            {t("settings.ai.subAgents.title")}
          </h4>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
            {t("settings.ai.subAgents.desc")}
          </p>
        </div>
        <button
          type="button"
          onClick={onManageSubAgents}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            height: "30px",
            padding: "0 12px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-2)",
            cursor: "pointer",
            fontSize: "12px",
            fontWeight: 500,
            color: "var(--text-level-2)",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
        >
          {t("settings.ai.subAgents.manage")} ›
        </button>
      </div>

      {/* 长期记忆库入口行（该藏的藏在独立二级页，不再霸屏） */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "12px",
          padding: "10px 0",
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <h4
            style={{
              fontSize: "13px",
              fontWeight: 500,
              color: "var(--text-level-1)",
              margin: 0,
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <Brain style={{ width: "15px", height: "15px", color: "var(--text-level-3)" }} />
            长期记忆库 (Memory Hub)
          </h4>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
            集中查阅、检索与维护 AI 记录的用户偏好、事实知识与跨会话记忆条目。
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            if (props.onOpenMemoryManage) {
              props.onOpenMemoryManage();
            } else if (onClose) {
              onClose();
              router.push("/memories");
            }
          }}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            height: "30px",
            padding: "0 12px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-2)",
            cursor: "pointer",
            fontSize: "12px",
            fontWeight: 500,
            color: "var(--text-level-2)",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
        >
          管理记忆 ›
        </button>
      </div>
    </div>
  );
}

/** 高级区块视图入口 */
export function AdvancedSettingsView(
  props: AdvancedSettingsViewProps & { activeSection: SettingSectionId }
) {
  switch (props.activeSection) {
    case "general":
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
