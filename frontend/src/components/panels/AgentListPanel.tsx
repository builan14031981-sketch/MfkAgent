"use client";

import { useState, useEffect } from "react";
import { ChevronLeft, ChevronDown } from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useTranslation } from "@/hooks/useTranslation";
import { getSubAgents, type SubAgent } from "@/lib/api";
import { AgentIcon } from "../AgentIcon";

interface AgentListPanelProps {
  /** 当前编辑中的 Agent id；null 表示列表视图，非 null 表示详情视图 */
  editingAgentId: string | null;
  onSelectAgent: (id: string) => void;
  /** 返回设置（一级设置主界面） */
  onBackToSettings: () => void;
  /** 返回列表（Agent 列表） */
  onBackToList: () => void;
}

/** 表达风格取值 → 中文说明（Agent 内部字段，进程内映射） */
const EXPRESSION_MAP: Record<string, string> = {
  warm: "温暖",
  coder: "工程师",
  professional: "专业",
  companion: "伙伴",
  natural_companion: "自然陪伴",
  creative: "创意",
};

/** 人格强度 0-100 → 档位说明 */
function personalityLabel(v: number | null | undefined): string {
  if (v == null) return "默认";
  if (v >= 80) return `高（${v}）`;
  if (v >= 40) return `中（${v}）`;
  return `低（${v}）`;
}

/** 预设 Agent 管理视图（分组列表 / 详情 同一容器），由 SettingsPanel 以 ViewState 控制显隐与导航 */
export function AgentListPanel({ editingAgentId, onSelectAgent, onBackToSettings, onBackToList }: AgentListPanelProps) {
  const { agents } = useAgents();
  const { t } = useTranslation();
  const [subAgents, setSubAgents] = useState<SubAgent[]>([]);
  const [promptExpanded, setPromptExpanded] = useState(false);

  // 获取子代理列表
  useEffect(() => {
    getSubAgents()
      .then(setSubAgents)
      .catch(() => {});
  }, []);

  // 详情目标：优先主 Agent，找不到再匹配子代理
  const activeMain = editingAgentId ? agents.find((a) => a.id === editingAgentId) || null : null;
  const activeSub = editingAgentId && !activeMain ? subAgents.find((s) => s.id === editingAgentId) || null : null;
  const active = activeMain || activeSub;

  const handleSelectAgent = (id: string) => {
    setPromptExpanded(false);
    onSelectAgent(id);
  };

  // 后端已按 AGENT_ORDER 排序，直接按 group 分组，不重复排序
  const activeAgents = agents.filter((a) => a.status === "active");
  const coreAgents = activeAgents.filter((a) => a.group !== "sub" && a.group !== "assist");
  const assistAgents = activeAgents.filter((a) => a.group === "assist");
  const activeSubs = subAgents.filter((s) => s.status === "active");

  /** 分组渲染列表 */
  const renderGroup = (
    title: string,
    desc: string,
    list: Array<{ id: string; name: string; description: string; subdesc?: string }>
  ) => {
    if (list.length === 0) return null;
    return (
      <div>
        <div style={{ margin: "0 0 6px 0" }}>
          <p style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-level-1)", margin: 0 }}>{title}</p>
          <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "1px 0 0 0" }}>{desc}</p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          {list.map((agent) => (
            <div
              key={agent.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "9px 12px",
                borderRadius: "var(--radius-md)",
                background: "var(--bg-level-2)",
                border: "1px solid var(--border-primary)",
              }}
            >
              <AgentIcon id={agent.id} size={18} style={{ color: "var(--color-primary)", flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
                  {agent.name}
                </p>
                <p style={{
                  fontSize: "11px",
                  color: "var(--text-level-3)",
                  margin: "1px 0 0 0",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}>{agent.description}</p>
                {agent.subdesc && (
                  <p style={{ fontSize: "10px", color: "var(--text-level-4)", margin: "2px 0 0 0" }}>{agent.subdesc}</p>
                )}
              </div>
              <button
                onClick={() => handleSelectAgent(agent.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  padding: "5px 10px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-primary)",
                  background: "transparent",
                  cursor: "pointer",
                  fontSize: "12px",
                  color: "var(--text-level-2)",
                  flexShrink: 0,
                }}
              >
                {t("settings.ai.agents.detail")} ›
              </button>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <>
      {/* 返回设置（视图右上角，一级设置时也显示） */}
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "16px" }}>
        <button
          onClick={onBackToSettings}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            padding: "6px 12px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-2)",
            cursor: "pointer",
            fontSize: "13px",
            fontWeight: "500",
            color: "var(--text-level-1)",
          }}
        >
          <ChevronLeft style={{ width: "15px", height: "15px" }} />
          {t("settings.ai.agents.backToSettings")}
        </button>
      </div>

      {active ? (
        <div>
          {/* 返回列表（仅详情视图显示） */}
          <button
            onClick={() => onBackToList()}
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
            {t("settings.ai.agents.backToAgentList")}
          </button>

          {/* Block 1 基本信息 */}
          <div style={{
            padding: "12px",
            borderRadius: "var(--radius-md)",
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-primary)",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <AgentIcon id={active.id} size={22} style={{ color: "var(--color-primary)", flexShrink: 0 }} />
              <div style={{ minWidth: 0 }}>
                <p style={{ fontSize: "14px", fontWeight: "600", color: "var(--text-level-1)", margin: 0 }}>
                  {active.name}
                </p>
                <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
                  {active.description}
                </p>
              </div>
            </div>
          </div>

          {/* Block 2 人格配置（仅主 Agent） */}
          {activeMain && (
            <div style={{ marginTop: "16px" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: "0 0 8px 0" }}>
                {t("settings.ai.agents.personality")}
              </h4>
              <div style={{
                padding: "10px 12px",
                borderRadius: "var(--radius-sm)",
                background: "var(--bg-level-2)",
                border: "1px solid var(--border-primary)",
                display: "flex",
                flexDirection: "column",
                gap: "10px",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "12px", color: "var(--text-level-4)", width: 64, flexShrink: 0 }}>
                    {t("settings.ai.agents.expressionProfile")}
                  </span>
                  <span style={{ fontSize: "13px", color: "var(--text-level-1)", fontWeight: 500 }}>
                    {activeMain.expression_profile ? EXPRESSION_MAP[activeMain.expression_profile] || activeMain.expression_profile : "默认"}
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "12px", color: "var(--text-level-4)", width: 64, flexShrink: 0 }}>
                    {t("settings.ai.agents.personalityLevel")}
                  </span>
                  <div style={{ flex: 1, display: "flex", alignItems: "center", gap: "8px" }}>
                    <div style={{
                      flex: 1,
                      height: 4,
                      borderRadius: "999px",
                      background: "var(--bg-level-1)",
                      overflow: "hidden",
                    }}>
                      <div style={{
                        height: "100%",
                        width: `${activeMain.default_personality_level ?? 0}%`,
                        background: "var(--color-primary)",
                        borderRadius: "999px",
                      }} />
                    </div>
                    <span style={{ fontSize: "12px", color: "var(--text-level-2)", whiteSpace: "nowrap" }}>
                      {personalityLabel(activeMain.default_personality_level)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Block 4 身份设定 / 系统指令（默认折叠，可展开看全） */}
          <div style={{ marginTop: "16px" }}>
            <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: "0 0 8px 0" }}>
              {activeMain ? t("settings.ai.agents.systemPrompt") : t("settings.ai.agents.identity")}
            </h4>
            <div style={{
              padding: "10px 12px",
              borderRadius: "var(--radius-sm)",
              background: "var(--bg-level-1)",
              border: "1px solid var(--border-primary)",
            }}>
              <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "0 0 6px 0" }}>
                {t("settings.ai.agents.systemPromptHint")}
              </p>
              <div style={{
                fontSize: "12px",
                color: "var(--text-level-2)",
                fontFamily: "monospace",
                whiteSpace: "pre-wrap",
                lineHeight: "1.5",
                maxHeight: promptExpanded ? "none" : "120px",
                overflowY: promptExpanded ? "visible" : "hidden",
                position: "relative",
              }}>
                {activeMain ? activeMain.system_prompt : activeSub?.identity || ""}
                {!promptExpanded && (
                  <div style={{
                    position: "absolute",
                    left: 0,
                    right: 0,
                    bottom: 0,
                    height: 40,
                    background: "linear-gradient(to top, var(--bg-level-1), transparent)",
                    pointerEvents: "none",
                  }} />
                )}
              </div>
              <button
                onClick={() => setPromptExpanded((v) => !v)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  padding: "4px 8px",
                  marginTop: "6px",
                  borderRadius: "var(--radius-sm)",
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  fontSize: "11px",
                  color: "var(--color-primary)",
                }}
              >
                {promptExpanded ? t("settings.ai.agents.foldPrompt") : t("settings.ai.agents.expandPrompt")}
                <ChevronDown
                  style={{
                    width: "13px",
                    height: "13px",
                    transform: promptExpanded ? "rotate(180deg)" : "none",
                    transition: "transform .15s ease",
                  }}
                />
              </button>
            </div>
          </div>

          {/* Block 4 工具白名单（仅子代理） */}
          {activeSub && (
            <div style={{ marginTop: "16px" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: "0 0 8px 0" }}>
                {t("settings.ai.agents.toolsHint")}
              </h4>
              <div style={{
                padding: "10px 12px",
                borderRadius: "var(--radius-sm)",
                background: "var(--bg-level-2)",
                border: "1px solid var(--border-primary)",
              }}>
                {(activeSub.allowed_tools || []).length > 0 ? (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                    {(activeSub.allowed_tools || []).map((tool) => (
                      <span
                        key={tool}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          padding: "2px 8px",
                          borderRadius: "999px",
                          background: "var(--bg-level-1)",
                          border: "1px solid var(--border-primary)",
                          color: "var(--text-level-2)",
                          fontSize: "11px",
                          lineHeight: "1.5",
                        }}
                      >
                        {tool}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: 0 }}>-</p>
                )}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {renderGroup(
            t("settings.ai.agents.groups.core"),
            t("settings.ai.agents.groupCoreDesc"),
            coreAgents.map((a) => ({ id: a.id, name: a.name, description: a.description }))
          )}
          {renderGroup(
            t("settings.ai.agents.groups.assist"),
            t("settings.ai.agents.groupAssistDesc"),
            assistAgents.map((a) => ({ id: a.id, name: a.name, description: a.description }))
          )}
          {renderGroup(
            t("settings.ai.agents.groups.sub"),
            t("settings.ai.agents.groupSubDesc"),
            activeSubs.map((s) => ({
              id: s.id,
              name: s.name,
              description: s.description,
              subdesc: s.allowed_tools.length > 0 ? `${t("settings.ai.agents.toolsHint")} ${s.allowed_tools.length} 项` : undefined,
            }))
          )}
        </div>
      )}
    </>
  );
}