"use client";

import { useState, useEffect } from "react";
import { ChevronLeft } from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useTranslation } from "@/hooks/useTranslation";
import { apiGet } from "@/lib/api";
import { AgentIcon } from "../AgentIcon";

interface AgentListPanelProps {
  /** 当前编辑中的 Agent id；null 表示列表视图，非 null 表示编辑视图 */
  editingAgentId: string | null;
  onSelectAgent: (id: string) => void;
  /** 返回设置（一级设置主界面） */
  onBackToSettings: () => void;
  /** 返回列表（Agent 列表） */
  onBackToList: () => void;
}

/** 预设 Agent 管理视图（列表 / 编辑 同一容器），由 SettingsPanel 以 ViewState 控制显隐与导航 */
export function AgentListPanel({ editingAgentId, onSelectAgent, onBackToSettings, onBackToList }: AgentListPanelProps) {
  const { agents, updateAgent } = useAgents();
  const { t } = useTranslation();
  const [capabilityTags, setCapabilityTags] = useState<Record<string, string>>({});
  const [editingCapabilities, setEditingCapabilities] = useState<string[] | null>(null);
  const [saving, setSaving] = useState(false);
  const activeAgent = editingAgentId ? agents.find((a) => a.id === editingAgentId) || null : null;

  // 获取领域能力标签词表
  useEffect(() => {
    apiGet<{ tags: Record<string, string> }>("/api/agents/capability-tags")
      .then((data) => setCapabilityTags(data.tags || {}))
      .catch(() => {});
  }, []);

  const handleSelectAgent = (id: string) => {
    setEditingCapabilities(null);
    onSelectAgent(id);
  };

  const visibleAgents = [...agents]
    .sort((a, b) => {
      const order = ["coder", "frontend_ui", "backend", "general", "analyst", "writer"];
      const ai = order.indexOf(a.id) === -1 ? 99 : order.indexOf(a.id);
      const bi = order.indexOf(b.id) === -1 ? 99 : order.indexOf(b.id);
      return ai - bi;
    })
    .filter((agent) => agent.status === "active");

  return (
    <>
      {/* 返回设置（视图右上角，一级设置时也显示） */}
      <div style={{
        display: "flex",
        justifyContent: "flex-end",
        marginBottom: "16px",
      }}>
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

      {activeAgent ? (
        <div>
          {/* 返回列表（仅编辑视图显示） */}
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
              <AgentIcon id={activeAgent.id} size={22} style={{ color: "var(--color-primary)", flexShrink: 0 }} />
              <div style={{ minWidth: 0 }}>
                <p style={{ fontSize: "14px", fontWeight: "600", color: "var(--text-level-1)", margin: 0 }}>{activeAgent.name}</p>
                <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>{activeAgent.description}</p>
              </div>
            </div>
          </div>

          {/* Block 2 系统指令（可滚动只读） */}
          <div style={{ marginTop: "16px" }}>
            <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: "0 0 8px 0" }}>
              {t("settings.ai.agents.systemPrompt")}
            </h4>
            <div style={{
              padding: "10px 12px",
              borderRadius: "var(--radius-sm)",
              background: "var(--bg-level-1)",
              border: "1px solid var(--border-primary)",
              fontSize: "12px",
              color: "var(--text-level-2)",
              fontFamily: "monospace",
              whiteSpace: "pre-wrap",
              maxHeight: "200px",
              overflowY: "auto",
              lineHeight: "1.5",
            }}>
              {activeAgent.system_prompt}
            </div>
          </div>

          {/* Block 3 其他参数配置 */}
          <div style={{ marginTop: "16px" }}>
            <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: "0 0 8px 0" }}>
              {t("settings.ai.agents.parameters")}
            </h4>
            <div style={{
              padding: "10px 12px",
              borderRadius: "var(--radius-sm)",
              background: "var(--bg-level-2)",
              border: "1px solid var(--border-primary)",
            }}>
              <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: 0 }}>
                {t("settings.ai.agents.modelGlobal")}
              </p>

              {/* 工具配置区域 */}
              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                  <span style={{ fontSize: "12px", color: "var(--text-level-4)" }}>
                    {t("settings.ai.agents.capabilities")}:
                  </span>
                  {editingCapabilities === null ? (
                    <button
                      onClick={() => setEditingCapabilities(activeAgent.capabilities || [])}
                      style={{
                        fontSize: "11px",
                        color: "var(--color-primary)",
                        background: "transparent",
                        border: "none",
                        cursor: "pointer",
                        padding: "2px 6px",
                      }}
                    >
                      {t("common.edit")}
                    </button>
                  ) : (
                    <div style={{ display: "flex", gap: "6px" }}>
                      <button
                        onClick={async () => {
                          if (!activeAgent) return;
                          setSaving(true);
                          try {
                            await updateAgent(activeAgent.id, { capabilities: editingCapabilities });
                            setEditingCapabilities(null);
                          } catch (err) {
                            console.error("Failed to update capabilities:", err);
                          } finally {
                            setSaving(false);
                          }
                        }}
                        disabled={saving}
                        style={{
                          fontSize: "11px",
                          color: "var(--color-primary)",
                          background: "transparent",
                          border: "none",
                          cursor: saving ? "not-allowed" : "pointer",
                          padding: "2px 6px",
                          opacity: saving ? 0.6 : 1,
                        }}
                      >
                        {t("common.save")}
                      </button>
                      <button
                        onClick={() => setEditingCapabilities(null)}
                        disabled={saving}
                        style={{
                          fontSize: "11px",
                          color: "var(--text-level-3)",
                          background: "transparent",
                          border: "none",
                          cursor: saving ? "not-allowed" : "pointer",
                          padding: "2px 6px",
                          opacity: saving ? 0.6 : 1,
                        }}
                      >
                        {t("common.cancel")}
                      </button>
                    </div>
                  )}
                </div>

                {editingCapabilities === null ? (
                  // 只读模式：显示领域标签 chip + 说明
                  <div style={{ margin: 0 }}>
                    {(activeAgent.capabilities || []).length > 0 ? (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "6px" }}>
                        {(activeAgent.capabilities || []).map((cap) => (
                          <span
                            key={cap}
                            title={capabilityTags[cap] || cap}
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              padding: "2px 8px",
                              borderRadius: "999px",
                              background: "var(--color-primary-lighter)",
                              color: "var(--color-primary)",
                              fontSize: "11px",
                              fontWeight: "500",
                              lineHeight: "1.5",
                            }}
                          >
                            {cap}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "0 0 6px 0" }}>-</p>
                    )}
                    <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: 0 }}>
                      {t("settings.ai.agents.capabilitiesHint")}
                    </p>
                  </div>
                ) : (
                  // 编辑模式：显示领域标签多选框
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "220px", overflowY: "auto" }}>
                    {Object.entries(capabilityTags).map(([key, desc]) => (
                      <label
                        key={key}
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          gap: "8px",
                          fontSize: "12px",
                          color: "var(--text-level-2)",
                          cursor: "pointer",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={editingCapabilities.includes(key)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setEditingCapabilities([...editingCapabilities, key]);
                            } else {
                              setEditingCapabilities(editingCapabilities.filter((n) => n !== key));
                            }
                          }}
                          style={{ marginTop: "2px" }}
                        />
                        <div>
                          <div style={{ fontWeight: "500" }}>{key}</div>
                          <div style={{ fontSize: "11px", color: "var(--text-level-4)", marginTop: "1px" }}>
                            {desc}
                          </div>
                        </div>
                      </label>
                    ))}
                    <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "2px 0 0 0" }}>
                      {t("settings.ai.agents.capabilitiesHint")}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {/* 研发核心三角置顶：代码审查 AI、前端 UI 设计 AI、后端 AI；仅展示 active Agent */}
          {visibleAgents.map((agent) => (
            <div
              key={agent.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "10px 12px",
                borderRadius: "var(--radius-md)",
                background: "var(--bg-level-2)",
                border: "1px solid var(--border-primary)",
              }}
            >
              <AgentIcon id={agent.id} size={18} style={{ color: "var(--color-primary)", flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{
                  fontSize: "13px",
                  fontWeight: "500",
                  color: "var(--text-level-1)",
                  margin: 0,
                }}>{agent.name}</p>
                <p style={{
                  fontSize: "11px",
                  color: "var(--text-level-3)",
                  margin: "1px 0 0 0",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}>{agent.description}</p>
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
      )}
    </>
  );
}
