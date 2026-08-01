"use client";

import { useState } from "react";
import {
  Plus,
  Trash2,
  Brain,
} from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
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

export function MemoryPanel({ isOpen, onClose, embedded = false }: MemoryPanelProps) {
  const { agents } = useAgents();
  const { t } = useTranslation();
  const [selectedAgent, setSelectedAgent] = useState(agents[0]?.id || "");
  const [scope, setScope] = useState<MemoryScope>("agent");
  const [newValue, setNewValue] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const { memories, loading, createMemory, deleteMemory } = useMemory(selectedAgent);

  const filtered = memories.filter((m) =>
    scope === "project" ? m.memory_type === "project" : ["user", "preference"].includes(m.memory_type)
  );

  const handleCreate = async () => {
    const content = newValue.trim();
    if (!content || isCreating) return;
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
    try {
      await deleteMemory(id);
    } catch (err) {
      console.error("Failed to delete memory:", err);
    }
  };

  const scopeOptions: { value: MemoryScope; label: string }[] = [
    { value: "agent", label: t("memory.scopeAgent") },
    { value: "project", label: t("memory.scopeProject") },
  ];

  const content = (
    <>
      {/* Agent 选择 */}
      <div style={{ marginBottom: "16px" }}>
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

      {/* 作用域切换 */}
      <div style={{
        display: "flex",
        gap: "8px",
        marginBottom: "16px",
      }}>
        {scopeOptions.map((opt) => (
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
            {opt.label}
          </button>
        ))}
      </div>

      {/* 添加记忆：单输入，直接写大白话 */}
      <div style={{
        padding: "14px",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-level-2)",
        marginBottom: "20px",
      }}>
        <h3 style={{
          fontSize: "13px",
          fontWeight: "500",
          color: "var(--text-level-1)",
          margin: "0 0 10px 0",
        }}>{t("memory.addMemory")}</h3>
        <textarea
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
          placeholder={t("memory.inputPlaceholder")}
          rows={3}
          style={{
            width: "100%",
            boxSizing: "border-box",
            padding: "10px 12px",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-1)",
            fontSize: "14px",
            lineHeight: "1.5",
            color: "var(--text-level-2)",
            outline: "none",
            resize: "vertical",
            fontFamily: "inherit",
            minHeight: "76px",
          }}
        />
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "8px" }}>
          <button
            onClick={handleCreate}
            disabled={!newValue.trim() || isCreating}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "8px 18px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: newValue.trim() && !isCreating ? "var(--color-primary)" : "var(--bg-level-3)",
              cursor: newValue.trim() && !isCreating ? "pointer" : "not-allowed",
              color: newValue.trim() && !isCreating ? "white" : "var(--text-level-3)",
              fontSize: "13px",
              fontWeight: "500",
            }}
          >
            <Plus style={{ width: "14px", height: "14px" }} />
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
        ) : filtered.length === 0 ? (
          <div style={{
            padding: "24px",
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
            {filtered.map((memory) => (
              <div
                key={memory.id}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "8px",
                  padding: "10px 12px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--bg-level-2)",
                  border: "1px solid var(--border-secondary)",
                }}
              >
                <div style={{
                  flex: 1,
                  minWidth: 0,
                  fontSize: "13px",
                  lineHeight: "1.5",
                  color: "var(--text-level-1)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}>
                  {memory.value}
                </div>
                <button
                  onClick={() => handleDelete(memory.id)}
                  title={t("memory.delete")}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: "28px",
                    height: "28px",
                    borderRadius: "var(--radius-sm)",
                    border: "none",
                    background: "transparent",
                    cursor: "pointer",
                    color: "var(--text-level-4)",
                    flexShrink: 0,
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "var(--color-error-lighter)"; e.currentTarget.style.color = "var(--color-error)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-level-4)"; }}
                >
                  <Trash2 style={{ width: "14px", height: "14px" }} />
                </button>
              </div>
            ))}
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
