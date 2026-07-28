"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Plus,
  Trash2,
  Brain,
} from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useMemory } from "@/hooks/useMemory";

export default function MemoryPage() {
  const router = useRouter();
  const { agents } = useAgents();
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
    <div style={{
      display: "flex",
      height: "100vh",
      background: "var(--bg-level-2)",
    }}>
      {/* 左侧 Sidebar */}
      <aside style={{
        width: "280px",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        borderRight: "1px solid var(--border-primary)",
        background: "var(--bg-level-1)",
      }}>
        {/* 返回按钮 */}
        <div style={{ padding: "16px" }}>
          <button
            onClick={() => router.back()}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 16px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "var(--bg-level-3)",
              cursor: "pointer",
              fontSize: "14px",
              width: "100%",
            }}
          >
            <ArrowLeft style={{ width: "16px", height: "16px" }} />
            <span>返回</span>
          </button>
        </div>

        {/* Agent 选择 */}
        <div style={{ padding: "0 16px", marginBottom: "16px" }}>
          <p style={{
            padding: "0 12px",
            marginBottom: "8px",
            fontSize: "12px",
            fontWeight: "600",
            color: "var(--text-level-4)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}>Agent</p>
          {agents.map((agent) => (
            <button
              key={agent.id}
              onClick={() => setSelectedAgent(agent.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "10px 12px",
                borderRadius: "var(--radius-md)",
                border: "none",
                background: selectedAgent === agent.id ? "var(--bg-level-3)" : "transparent",
                cursor: "pointer",
                fontSize: "14px",
                color: "var(--text-level-2)",
                width: "100%",
                marginBottom: "2px",
              }}
            >
              <span style={{ fontSize: "14px" }}>{agent.avatar}</span>
              <span>{agent.name}</span>
            </button>
          ))}
        </div>
      </aside>

      {/* 右侧内容区 */}
      <main style={{
        flex: 1,
        overflowY: "auto",
        padding: "32px 48px",
      }}>
        <h1 style={{
          fontSize: "24px",
          fontWeight: "600",
          color: "var(--text-level-1)",
          margin: "0 0 32px 0",
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}>
          <Brain style={{ width: "24px", height: "24px" }} />
          记忆管理
        </h1>

        {/* 添加新记忆 */}
        <div style={{
          padding: "20px",
          borderRadius: "var(--radius-lg)",
          background: "var(--bg-level-1)",
          marginBottom: "24px",
        }}>
          <h2 style={{
            fontSize: "16px",
            fontWeight: "600",
            color: "var(--text-level-1)",
            margin: "0 0 16px 0",
          }}>添加记忆</h2>
          <div style={{
            display: "flex",
            gap: "12px",
            alignItems: "flex-end",
          }}>
            <div style={{ flex: 1 }}>
              <label style={{
                display: "block",
                fontSize: "12px",
                color: "var(--text-level-3)",
                marginBottom: "4px",
              }}>键</label>
              <input
                type="text"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                placeholder="例如: 喜欢简洁回答"
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-primary)",
                  background: "var(--bg-level-2)",
                  fontSize: "14px",
                  color: "var(--text-level-2)",
                  outline: "none",
                }}
              />
            </div>
            <div style={{ flex: 1 }}>
              <label style={{
                display: "block",
                fontSize: "12px",
                color: "var(--text-level-3)",
                marginBottom: "4px",
              }}>值</label>
              <input
                type="text"
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                placeholder="例如: 是"
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-primary)",
                  background: "var(--bg-level-2)",
                  fontSize: "14px",
                  color: "var(--text-level-2)",
                  outline: "none",
                }}
              />
            </div>
            <button
              onClick={handleCreate}
              disabled={!newKey.trim() || !newValue.trim() || isCreating}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "10px 16px",
                borderRadius: "var(--radius-md)",
                border: "none",
                background: newKey.trim() && newValue.trim() && !isCreating ? "var(--color-primary)" : "var(--bg-level-3)",
                cursor: newKey.trim() && newValue.trim() && !isCreating ? "pointer" : "not-allowed",
                color: newKey.trim() && newValue.trim() && !isCreating ? "white" : "var(--text-level-3)",
                fontSize: "14px",
                flexShrink: 0,
              }}
            >
              <Plus style={{ width: "14px", height: "14px" }} />
              添加
            </button>
          </div>
        </div>

        {/* 记忆列表 */}
        <div>
          <h2 style={{
            fontSize: "16px",
            fontWeight: "600",
            color: "var(--text-level-1)",
            margin: "0 0 16px 0",
          }}>记忆列表</h2>
          {loading ? (
            <p style={{ color: "var(--text-level-3)" }}>加载中...</p>
          ) : memories.length === 0 ? (
            <div style={{
              padding: "32px",
              textAlign: "center",
              borderRadius: "var(--radius-lg)",
              background: "var(--bg-level-1)",
            }}>
              <Brain style={{ width: "48px", height: "48px", color: "var(--text-level-4)", marginBottom: "16px" }} />
              <p style={{ fontSize: "14px", color: "var(--text-level-3)", margin: 0 }}>暂无记忆</p>
              <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: "4px 0 0 0" }}>添加记忆让 AI 更了解你</p>
            </div>
          ) : (
            <div style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
            }}>
              {memories.map((memory) => (
                <div
                  key={memory.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px 16px",
                    borderRadius: "var(--radius-md)",
                    background: "var(--bg-level-1)",
                  }}
                >
                  <div>
                    <p style={{
                      fontSize: "14px",
                      fontWeight: "500",
                      color: "var(--text-level-1)",
                      margin: 0,
                    }}>{memory.key}</p>
                    <p style={{
                      fontSize: "13px",
                      color: "var(--text-level-3)",
                      margin: "4px 0 0 0",
                    }}>{memory.value}</p>
                  </div>
                  <button
                    onClick={() => handleDelete(memory.id)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "32px",
                      height: "32px",
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
      </main>
    </div>
  );
}
