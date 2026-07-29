"use client";

import { useState } from "react";
import {
  Plus,
  Trash2,
  Brain,
} from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useMemory } from "@/hooks/useMemory";
import { useTranslation } from "@/hooks/useTranslation";
import { Panel } from "./Panel";

interface MemoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function MemoryPanel({ isOpen, onClose }: MemoryPanelProps) {
  const { agents } = useAgents();
  const { t } = useTranslation();
  const [selectedAgent, setSelectedAgent] = useState(agents[0]?.id || "");
  const { memories, loading, createMemory, deleteMemory } = useMemory(selectedAgent);

  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const handleCreate = async () => {
    if (!newKey.trim() || !newValue.trim() || isCreating) return;

    setIsCreating(true);
    try {
      await createMemory(newKey.trim(), newValue.trim());
      setNewKey("");
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

  return (
    <Panel isOpen={isOpen} onClose={onClose} title={t("memory.title")}>
      {/* Agent 选择 */}
      <div style={{ marginBottom: "20px" }}>
        <label style={{
          display: "block",
          fontSize: "13px",
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
                padding: "8px 12px",
                borderRadius: "var(--radius-full)",
                border: selectedAgent === agent.id ? "2px solid var(--color-primary)" : "1px solid var(--border-primary)",
                background: selectedAgent === agent.id ? "var(--color-primary-lighter)" : "var(--bg-level-2)",
                cursor: "pointer",
                fontSize: "13px",
                color: selectedAgent === agent.id ? "var(--color-primary)" : "var(--text-level-2)",
              }}
            >
              <span>{agent.avatar}</span>
              <span>{agent.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 添加记忆 */}
      <div style={{
        padding: "16px",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-level-2)",
        marginBottom: "20px",
      }}>
        <h3 style={{
          fontSize: "14px",
          fontWeight: "500",
          color: "var(--text-level-1)",
          margin: "0 0 12px 0",
        }}>{t("memory.addMemory")}</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <input
            type="text"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder={t("memory.keyPlaceholder")}
            style={{
              padding: "10px 12px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-1)",
              fontSize: "14px",
              color: "var(--text-level-2)",
              outline: "none",
            }}
          />
          <input
            type="text"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder={t("memory.valuePlaceholder")}
            style={{
              padding: "10px 12px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-1)",
              fontSize: "14px",
              color: "var(--text-level-2)",
              outline: "none",
            }}
          />
          <button
            onClick={handleCreate}
            disabled={!newKey.trim() || !newValue.trim() || isCreating}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
              padding: "10px 16px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: newKey.trim() && newValue.trim() && !isCreating ? "var(--color-primary)" : "var(--bg-level-3)",
              cursor: newKey.trim() && newValue.trim() && !isCreating ? "pointer" : "not-allowed",
              color: newKey.trim() && newValue.trim() && !isCreating ? "white" : "var(--text-level-3)",
              fontSize: "14px",
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
          fontSize: "14px",
          fontWeight: "500",
          color: "var(--text-level-1)",
          margin: "0 0 12px 0",
        }}>{t("memory.memoryList")}</h3>
        {loading ? (
          <p style={{ color: "var(--text-level-3)" }}>{t("common.loading")}</p>
        ) : memories.length === 0 ? (
          <div style={{
            padding: "24px",
            textAlign: "center",
            borderRadius: "var(--radius-md)",
            background: "var(--bg-level-2)",
          }}>
            <Brain style={{ width: "32px", height: "32px", color: "var(--text-level-4)", marginBottom: "8px" }} />
            <p style={{ fontSize: "13px", color: "var(--text-level-3)", margin: 0 }}>{t("memory.noMemories")}</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {memories.map((memory) => (
              <div
                key={memory.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--bg-level-2)",
                }}
              >
                <div>
                  <p style={{
                    fontSize: "13px",
                    fontWeight: "500",
                    color: "var(--text-level-1)",
                    margin: 0,
                  }}>{memory.key}</p>
                  <p style={{
                    fontSize: "12px",
                    color: "var(--text-level-3)",
                    margin: "2px 0 0 0",
                  }}>{memory.value}</p>
                </div>
                <button
                  onClick={() => handleDelete(memory.id)}
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
                  }}
                >
                  <Trash2 style={{ width: "14px", height: "14px" }} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </Panel>
  );
}
