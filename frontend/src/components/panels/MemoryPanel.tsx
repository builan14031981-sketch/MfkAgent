"use client";

import { useState } from "react";
import {
  Plus,
  Trash2,
  Brain,
  Pencil,
  Check,
  X,
} from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useMemory, Memory } from "@/hooks/useMemory";
import { useTranslation } from "@/hooks/useTranslation";
import { Panel } from "./Panel";

interface MemoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
  /** 嵌入模式：渲染为内嵌内容（无 Panel 外壳），用于嵌入 SettingsPanel */
  embedded?: boolean;
}

type MemoryTab = "preference" | "project";

export function MemoryPanel({ isOpen, onClose, embedded = false }: MemoryPanelProps) {
  const { agents } = useAgents();
  const { t } = useTranslation();
  const [selectedAgent, setSelectedAgent] = useState(agents[0]?.id || "");
  const { memories, loading, createMemory, deleteMemory, updateMemory } = useMemory(selectedAgent);

  const [activeTab, setActiveTab] = useState<MemoryTab>("preference");
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editKey, setEditKey] = useState("");
  const [editValue, setEditValue] = useState("");
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  const filtered = memories.filter((m) => m.memory_type === activeTab);

  const resetNewForm = () => {
    setNewKey("");
    setNewValue("");
  };

  const handleCreate = async () => {
    if (!newKey.trim() || !newValue.trim() || isCreating) return;

    setIsCreating(true);
    try {
      await createMemory(newKey.trim(), newValue.trim(), activeTab);
      resetNewForm();
    } catch (err) {
      console.error("Failed to create memory:", err);
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteMemory(id);
      if (editingId === id) setEditingId(null);
    } catch (err) {
      console.error("Failed to delete memory:", err);
    }
  };

  const handleToggle = async (memory: Memory) => {
    try {
      await updateMemory(memory.id, { is_active: !memory.is_active });
    } catch (err) {
      console.error("Failed to toggle memory:", err);
    }
  };

  const startEdit = (memory: Memory) => {
    setEditingId(memory.id);
    setEditKey(memory.key);
    setEditValue(memory.value);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditKey("");
    setEditValue("");
  };

  const handleSaveEdit = async (id: number) => {
    if (!editKey.trim() || !editValue.trim() || isSavingEdit) return;

    setIsSavingEdit(true);
    try {
      await updateMemory(id, { key: editKey.trim(), value: editValue.trim() });
      cancelEdit();
    } catch (err) {
      console.error("Failed to update memory:", err);
    } finally {
      setIsSavingEdit(false);
    }
  };

  const content = (
    <>
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
              onClick={() => {
                setSelectedAgent(agent.id);
                cancelEdit();
              }}
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

      {/* 分类 Tab */}
      <div style={{
        display: "flex",
        gap: "8px",
        marginBottom: "16px",
      }}>
        {(["preference", "project"] as MemoryTab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              flex: 1,
              padding: "10px 12px",
              borderRadius: "var(--radius-md)",
              border: activeTab === tab ? "2px solid var(--color-primary)" : "1px solid var(--border-primary)",
              background: activeTab === tab ? "var(--color-primary-lighter)" : "var(--bg-level-2)",
              cursor: "pointer",
              fontSize: "14px",
              fontWeight: activeTab === tab ? "600" : "400",
              color: activeTab === tab ? "var(--color-primary)" : "var(--text-level-2)",
            }}
          >
            {tab === "preference" ? t("memory.preferences") : t("memory.project")}
          </button>
        ))}
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
        ) : filtered.length === 0 ? (
          <div style={{
            padding: "24px",
            textAlign: "center",
            borderRadius: "var(--radius-md)",
            background: "var(--bg-level-2)",
          }}>
            <Brain style={{ width: "32px", height: "32px", color: "var(--text-level-4)", marginBottom: "8px" }} />
            <p style={{ fontSize: "13px", color: "var(--text-level-3)", margin: 0 }}>
              {activeTab === "preference" ? t("memory.noPreferences") : t("memory.noProjectMemories")}
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {filtered.map((memory) => (
              <div
                key={memory.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--bg-level-2)",
                  opacity: memory.is_active ? 1 : 0.55,
                  border: "1px solid var(--border-secondary)",
                }}
              >
                {editingId === memory.id ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px", flex: 1 }}>
                    <input
                      type="text"
                      value={editKey}
                      onChange={(e) => setEditKey(e.target.value)}
                      style={{
                        padding: "8px 10px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-primary)",
                        background: "var(--bg-level-1)",
                        fontSize: "13px",
                        color: "var(--text-level-2)",
                        outline: "none",
                      }}
                    />
                    <input
                      type="text"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      style={{
                        padding: "8px 10px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-primary)",
                        background: "var(--bg-level-1)",
                        fontSize: "13px",
                        color: "var(--text-level-2)",
                        outline: "none",
                      }}
                    />
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        onClick={() => handleSaveEdit(memory.id)}
                        disabled={!editKey.trim() || !editValue.trim() || isSavingEdit}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "4px",
                          padding: "6px 12px",
                          borderRadius: "var(--radius-sm)",
                          border: "none",
                          background: editKey.trim() && editValue.trim() && !isSavingEdit ? "var(--color-primary)" : "var(--bg-level-3)",
                          cursor: editKey.trim() && editValue.trim() && !isSavingEdit ? "pointer" : "not-allowed",
                          color: editKey.trim() && editValue.trim() && !isSavingEdit ? "white" : "var(--text-level-3)",
                          fontSize: "12px",
                        }}
                      >
                        <Check style={{ width: "12px", height: "12px" }} />
                        <span>{t("memory.save")}</span>
                      </button>
                      <button
                        onClick={cancelEdit}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "4px",
                          padding: "6px 12px",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid var(--border-primary)",
                          background: "transparent",
                          cursor: "pointer",
                          color: "var(--text-level-2)",
                          fontSize: "12px",
                        }}
                      >
                        <X style={{ width: "12px", height: "12px" }} />
                        <span>{t("memory.cancel")}</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{
                        fontSize: "13px",
                        fontWeight: "500",
                        color: "var(--text-level-1)",
                        margin: 0,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}>{memory.key}</p>
                      <p style={{
                        fontSize: "12px",
                        color: "var(--text-level-3)",
                        margin: "2px 0 0 0",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}>{memory.value}</p>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
                      {/* 启用/禁用开关 */}
                      <button
                        onClick={() => handleToggle(memory)}
                        title={memory.is_active ? t("memory.disable") : t("memory.enable")}
                        style={{
                          position: "relative",
                          width: "34px",
                          height: "20px",
                          borderRadius: "var(--radius-full)",
                          border: "none",
                          background: memory.is_active ? "var(--color-primary)" : "var(--bg-level-3)",
                          cursor: "pointer",
                          transition: "background 0.15s ease",
                        }}
                      >
                        <span style={{
                          position: "absolute",
                          top: "2px",
                          left: memory.is_active ? "16px" : "2px",
                          width: "16px",
                          height: "16px",
                          borderRadius: "50%",
                          background: "white",
                          transition: "left 0.15s ease",
                        }} />
                      </button>
                      <button
                        onClick={() => startEdit(memory)}
                        title={t("memory.edit")}
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
                        <Pencil style={{ width: "14px", height: "14px" }} />
                      </button>
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
                        }}
                      >
                        <Trash2 style={{ width: "14px", height: "14px" }} />
                      </button>
                    </div>
                  </>
                )}
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
