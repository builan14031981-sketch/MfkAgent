"use client";

import { useState, useEffect } from "react";
import { ChevronLeft } from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useTranslation } from "@/hooks/useTranslation";
import { apiGet } from "@/lib/api";
import { Panel } from "./Panel";
import { AgentIcon } from "../AgentIcon";

interface AgentListPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

interface Tool {
  name: string;
  description: string;
}

/** 预设 Agent 二级面板：主列表 + 详情（Master-Detail），左上角返回设置 */
export function AgentListPanel({ isOpen, onClose }: AgentListPanelProps) {
  const { agents, updateAgent } = useAgents();
  const { t } = useTranslation();
  const [activeAgentId, setActiveAgentId] = useState<string | null>(null);
  const [availableTools, setAvailableTools] = useState<Tool[]>([]);
  const [editingCapabilities, setEditingCapabilities] = useState<string[] | null>(null);
  const [saving, setSaving] = useState(false);
  const activeAgent = activeAgentId ? agents.find((a) => a.id === activeAgentId) || null : null;

  // 获取可用工具列表
  useEffect(() => {
    apiGet<{ tools: Tool[] }>("/api/tools")
      .then((data) => setAvailableTools(data.tools))
      .catch(() => {});
  }, []);

  // 切换 Agent 时重置编辑状态
  useEffect(() => {
    setEditingCapabilities(null);
  }, [activeAgentId]);

  const visibleAgents = [...agents]
    .sort((a, b) => {
      const order = ["coder", "frontend_ui", "backend", "general", "analyst", "writer"];
      const ai = order.indexOf(a.id) === -1 ? 99 : order.indexOf(a.id);
      const bi = order.indexOf(b.id) === -1 ? 99 : order.indexOf(b.id);
      return ai - bi;
    })
    .filter((agent) => !["warm", "rational"].includes(agent.id));

  const content = (
    <>
      {/* 返回设置（左上角，明显） */}
      <button
        onClick={onClose}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          padding: "6px 12px",
          marginBottom: "16px",
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

      {activeAgent ? (
        <div>
          {/* 返回列表 */}
          <button
            onClick={() => setActiveAgentId(null)}
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
              <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "0 0 12px 0" }}>
                <span style={{ color: "var(--text-level-4)" }}>{t("settings.ai.agents.model")}: </span>
                {activeAgent.default_model || "-"}
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
                  // 只读模式：显示已选工具
                  <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: 0 }}>
                    {(activeAgent.capabilities || []).length > 0
                      ? (activeAgent.capabilities || []).join("、")
                      : "-"}
                  </p>
                ) : (
                  // 编辑模式：显示多选框
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    {availableTools.map((tool) => (
                      <label
                        key={tool.name}
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
                          checked={editingCapabilities.includes(tool.name)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setEditingCapabilities([...editingCapabilities, tool.name]);
                            } else {
                              setEditingCapabilities(editingCapabilities.filter((n) => n !== tool.name));
                            }
                          }}
                          style={{ marginTop: "2px" }}
                        />
                        <div>
                          <div style={{ fontWeight: "500" }}>{tool.name}</div>
                          <div style={{ fontSize: "11px", color: "var(--text-level-4)", marginTop: "1px" }}>
                            {tool.description}
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {/* 研发核心三角置顶：代码审查 AI、前端 UI 设计 AI、后端 AI；旧预设 warm/rational 不展示 */}
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
                onClick={() => setActiveAgentId(agent.id)}
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

  return (
    <Panel
      isOpen={isOpen}
      onClose={onClose}
      title={t("settings.ai.agents.title")}
      width="460px"
      variant="bottom-left"
    >
      {content}
    </Panel>
  );
}
