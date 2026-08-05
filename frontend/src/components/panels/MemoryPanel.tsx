"use client";

import { useState } from "react";
import {
  Plus,
  Trash2,
  Brain,
} from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useProjects } from "@/hooks/useProjects";
import { useMemory, MemoryScope } from "@/hooks/useMemory";
import { useTranslation } from "@/hooks/useTranslation";
import { Panel } from "./Panel";
import { AgentIcon } from "../AgentIcon";

interface MemoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
  /** 嵌入模式：渲染为内嵌内容（无 Panel 外壳），用于嵌入 SettingsPanel */
  embedded?: boolean;
}

const SCOPE_OPTIONS: { value: MemoryScope; key: "scopeGlobal" | "scopeAgent" | "scopeProject" }[] = [
  { value: "global", key: "scopeGlobal" },
  { value: "agent", key: "scopeAgent" },
  { value: "project", key: "scopeProject" },
];

export function MemoryPanel({ isOpen, onClose, embedded = false }: MemoryPanelProps) {
  const { agents } = useAgents();
  const { projects } = useProjects();
  const { t } = useTranslation();
  const [scope, setScope] = useState<MemoryScope>("global");
  const [selectedAgent, setSelectedAgent] = useState(agents[0]?.id || "");
  const [selectedProject, setSelectedProject] = useState<number | null>(projects[0]?.id ?? null);
  const [newValue, setNewValue] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [composerFocused, setComposerFocused] = useState(false);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<number | null>(null);
  const { memories, loading, createMemory, deleteMemory } = useMemory(selectedAgent, selectedProject, scope);

  const agentScopeReady = scope !== "agent" || !!selectedAgent;
  const projectScopeReady = scope !== "project" || selectedProject != null;

  const handleCreate = async () => {
    const content = newValue.trim();
    if (!content || isCreating || !agentScopeReady || !projectScopeReady) return;
    setIsCreating(true);
    try {
      await createMemory(content, scope);
      setNewValue("");
    } catch (err) {
      console.error("Failed to create memory:", err);
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (confirmingDeleteId !== id) {
      setConfirmingDeleteId(id);
      // 自动取消确认态
      window.setTimeout(() => {
        setConfirmingDeleteId((cur) => (cur === id ? null : cur));
      }, 3000);
      return;
    }
    setConfirmingDeleteId(null);
    try {
      await deleteMemory(id);
    } catch (err) {
      console.error("Failed to delete memory:", err);
    }
  };

  /** scope → 标签文案 */
  const scopeLabel = (scopeVal: MemoryScope): string => {
    const opt = SCOPE_OPTIONS.find((o) => o.value === scopeVal);
    return opt ? t(`memory.${opt.key}`) : scopeVal;
  };

  /** 格式化创建时间：MM-DD HH:mm */
  const formatTime = (iso: string): string => {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  const content = (
    <>
      {/* 作用域切换（三 tab：全局 / Agent / 项目） */}
      <div style={{
        display: "flex",
        gap: "8px",
        marginBottom: "12px",
      }}>
        {SCOPE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setScope(opt.value)}
            style={{
              flex: 1,
              padding: "9px 12px",
              borderRadius: "var(--radius-md)",
              border: "1px solid",
              borderColor: scope === opt.value ? "var(--color-primary)" : "var(--border-primary)",
              background: scope === opt.value ? "var(--color-primary-lighter)" : "var(--bg-level-2)",
              cursor: "pointer",
              fontSize: "13px",
              fontWeight: scope === opt.value ? "600" : "400",
              color: scope === opt.value ? "var(--color-primary)" : "var(--text-level-2)",
            }}
          >
            {t(`memory.${opt.key}`)}
          </button>
        ))}
      </div>

      {/* Agent 选择（仅 agent 作用域） */}
      {scope === "agent" && (
        <div style={{ marginBottom: "12px" }}>
          <label style={{
            display: "block",
            fontSize: "12px",
            color: "var(--text-level-3)",
            marginBottom: "8px",
          }}>{t("memory.selectAgent")}</label>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {agents.map((agent) => (
              <button
                key={agent.id}
                onClick={() => setSelectedAgent(agent.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "6px 10px",
                  borderRadius: "var(--radius-full)",
                  border: "1px solid",
                  borderColor: selectedAgent === agent.id ? "var(--color-primary)" : "var(--border-primary)",
                  background: selectedAgent === agent.id ? "var(--color-primary-lighter)" : "var(--bg-level-2)",
                  cursor: "pointer",
                  fontSize: "12px",
                  color: selectedAgent === agent.id ? "var(--color-primary)" : "var(--text-level-2)",
                }}
              >
                <AgentIcon id={agent.id} size={13} style={{ color: selectedAgent === agent.id ? "var(--color-primary)" : "var(--text-level-3)" }} />
                <span>{agent.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 项目选择（仅 project 作用域） */}
      {scope === "project" && (
        <div style={{ marginBottom: "12px" }}>
          <label style={{
            display: "block",
            fontSize: "12px",
            color: "var(--text-level-3)",
            marginBottom: "8px",
          }}>{t("memory.selectProject")}</label>
          <select
            value={selectedProject ?? ""}
            onChange={(e) => setSelectedProject(e.target.value ? Number(e.target.value) : null)}
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-2)",
              fontSize: "13px",
              color: "var(--text-level-2)",
              outline: "none",
            }}
          >
            <option value="">{t("memory.selectProjectPlaceholder")}</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>{project.name}</option>
            ))}
          </select>
        </div>
      )}

      {/* 添加记忆：一体化容器（透明 textarea + 内置提交按钮，focus 整卡高亮） */}
      <div style={{ marginBottom: "12px" }}>
        <h3 style={{
          fontSize: "13px",
          fontWeight: "500",
          color: "var(--text-level-1)",
          margin: "0 0 8px 0",
        }}>{t("memory.addMemory")}</h3>
        <div
          style={{
            position: "relative",
            borderRadius: "var(--radius-md)",
            border: "1px solid",
            borderColor: composerFocused ? "var(--color-primary)" : "var(--border-primary)",
            background: "var(--bg-level-2)",
            transition: "border-color 0.15s ease",
          }}
        >
          <textarea
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            onFocus={() => setComposerFocused(true)}
            onBlur={() => setComposerFocused(false)}
            placeholder={t("memory.inputPlaceholder")}
            rows={3}
            style={{
              width: "100%",
              boxSizing: "border-box",
              display: "block",
              padding: "10px 12px 42px",
              background: "transparent",
              border: "none",
              outline: "none",
              fontSize: "14px",
              lineHeight: "1.5",
              color: "var(--text-level-2)",
              resize: "vertical",
              fontFamily: "inherit",
              minHeight: "88px",
            }}
          />
          <button
            onClick={handleCreate}
            disabled={!newValue.trim() || isCreating || !agentScopeReady || !projectScopeReady}
            style={{
              position: "absolute",
              bottom: "8px",
              right: "8px",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              height: "28px",
              padding: "0 12px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: newValue.trim() && !isCreating && agentScopeReady && projectScopeReady ? "var(--color-primary)" : "var(--bg-level-3)",
              cursor: newValue.trim() && !isCreating && agentScopeReady && projectScopeReady ? "pointer" : "not-allowed",
              color: newValue.trim() && !isCreating && agentScopeReady && projectScopeReady ? "white" : "var(--text-level-3)",
              fontSize: "12px",
              fontWeight: "500",
            }}
          >
            <Plus style={{ width: "13px", height: "13px" }} />
            <span>{t("memory.add")}</span>
          </button>
        </div>
      </div>

      {/* 记忆列表 */}
      <div>
        <h3 style={{
          fontSize: "13px",
          fontWeight: "500",
          color: "var(--text-level-1)",
          margin: "0 0 10px 0",
        }}>{t("memory.memoryList")}</h3>
        {loading && memories.length === 0 ? (
          <p style={{ color: "var(--text-level-3)" }}>{t("common.loading")}</p>
        ) : memories.length === 0 ? (
          <div style={{
            padding: "18px",
            textAlign: "center",
            borderRadius: "var(--radius-md)",
            background: "var(--bg-level-2)",
          }}>
            <Brain style={{ width: "30px", height: "30px", color: "var(--text-level-4)", marginBottom: "8px" }} />
            <p style={{ fontSize: "13px", color: "var(--text-level-3)", margin: 0 }}>
              {t("memory.noMemories")}
            </p>
            <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: "4px 0 0 0" }}>
              {t("memory.noMemoriesDesc")}
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {memories.map((memory) => {
              const isConfirming = confirmingDeleteId === memory.id;
              const createdTime = formatTime(memory.created_at);
              return (
                <div
                  key={memory.id}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "8px",
                    padding: "10px 12px",
                    borderRadius: "var(--radius-md)",
                    background: "var(--bg-level-2)",
                    border: "1px solid",
                    borderColor: isConfirming ? "var(--color-error)" : "var(--border-secondary)",
                    transition: "border-color 0.15s ease",
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {/* 元信息行：scope 标签 + 时间 */}
                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      marginBottom: "4px",
                    }}>
                      <span style={{
                        display: "inline-flex",
                        alignItems: "center",
                        padding: "1px 7px",
                        borderRadius: "var(--radius-full)",
                        background: "var(--color-primary-lighter)",
                        border: "1px solid var(--color-primary-light)",
                        fontSize: "10px",
                        fontWeight: 600,
                        lineHeight: 1.4,
                        color: "var(--color-primary)",
                      }}>{scopeLabel(memory.scope)}</span>
                      {createdTime && (
                        <span style={{
                          fontSize: "11px",
                          color: "var(--text-level-4)",
                        }}>{t("memory.createdAt")} {createdTime}</span>
                      )}
                    </div>
                    <div style={{
                      fontSize: "13px",
                      lineHeight: "1.5",
                      color: "var(--text-level-1)",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                    }}>
                      {memory.content}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(memory.id)}
                    title={isConfirming ? t("memory.deleteConfirm") : t("memory.delete")}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      height: "28px",
                      padding: isConfirming ? "0 10px" : "0",
                      borderRadius: "var(--radius-sm)",
                      border: isConfirming ? "1px solid var(--color-error)" : "none",
                      background: isConfirming ? "color-mix(in srgb, var(--color-error) 10%, var(--bg-level-2))" : "transparent",
                      cursor: "pointer",
                      color: isConfirming ? "var(--color-error)" : "var(--text-level-4)",
                      flexShrink: 0,
                      fontSize: "12px",
                      fontWeight: 500,
                      whiteSpace: "nowrap",
                      transition: "background 0.15s ease",
                    }}
                    onMouseEnter={(e) => {
                      if (!isConfirming) { e.currentTarget.style.background = "color-mix(in srgb, var(--color-error) 10%, var(--bg-level-2))"; e.currentTarget.style.color = "var(--color-error)"; }
                    }}
                    onMouseLeave={(e) => {
                      if (!isConfirming) { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-level-4)"; }
                    }}
                  >
                    {isConfirming ? (
                      <span>{t("memory.deleteConfirm")}</span>
                    ) : (
                      <Trash2 style={{ width: "14px", height: "14px" }} />
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );

  if (embedded) {
    return content;
  }

  return (
    <Panel isOpen={isOpen} onClose={onClose} title={t("memory.title")}>
      {content}
    </Panel>
  );
}
