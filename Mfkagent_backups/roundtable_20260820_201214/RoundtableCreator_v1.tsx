"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAgents, type Agent } from "@/hooks/useAgents";
import { useChat } from "@/hooks/useChat";
import { useModels } from "@/hooks/useModels";
import { useVisibleModels } from "@/hooks/useVisibleModels";
import { useSettingsStore } from "@/lib/store";
import { X, Users, Play, ChevronDown, ChevronUp } from "lucide-react";

interface RoundtableCreatorProps {
  onClose: () => void;
  initialContent?: string;
}

/** 圆桌模式创建器：多选 Agent、设置轮次、创建圆桌会话 */
export function RoundtableCreator({ onClose, initialContent = "" }: RoundtableCreatorProps) {
  const router = useRouter();
  const { agents } = useAgents();
  const { models } = useModels();
  const visibleModels = useVisibleModels(models);
  const { createChat } = useChat();
  const { settings } = useSettingsStore();

  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>([]);
  const [maxRounds, setMaxRounds] = useState(2);
  const [needSummary, setNeedSummary] = useState(true);
  const [content, setContent] = useState(initialContent);
  const [creating, setCreating] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const toggleAgent = (agentId: string) => {
    setSelectedAgentIds((prev) =>
      prev.includes(agentId) ? prev.filter((id) => id !== agentId) : [...prev, agentId]
    );
  };

  const handleCreate = async () => {
    if (selectedAgentIds.length < 2) {
      alert("请至少选择 2 个 Agent 参与圆桌讨论");
      return;
    }
    if (!content.trim()) {
      alert("请输入讨论主题");
      return;
    }

    setCreating(true);
    try {
      const defaultModel = visibleModels.find((m) => m.id === settings?.default_model) || visibleModels[0];
      const chat = await createChat(
        selectedAgentIds[0], // 主 Agent 用第一个
        content.slice(0, 50) || "圆桌讨论",
        null,
        defaultModel?.id || null,
        [],
        "roundtable",
        "standard",
        {
          agent_ids: selectedAgentIds,
          max_rounds: maxRounds,
          need_summary: needSummary,
          moderator_id: selectedAgentIds[selectedAgentIds.length - 1],
          strategy: "round_robin",
        }
      );

      const encodedMessage = encodeURIComponent(content);
      router.push(`/chat/${chat.id}?message=${encodedMessage}`);
      onClose();
    } catch (err) {
      console.error("Failed to create roundtable chat:", err);
      alert("创建圆桌会话失败，请重试");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.5)",
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--bg-level-1)",
          borderRadius: "12px",
          width: "100%",
          maxWidth: "560px",
          maxHeight: "85vh",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          border: "1px solid var(--border-color)",
          boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
        }}
      >
        {/* 头部 */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border-color)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Users size={20} style={{ color: "var(--accent-color)" }} />
            <span style={{ fontSize: "16px", fontWeight: 600 }}>圆桌讨论</span>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "4px",
              color: "var(--text-level-3)",
              borderRadius: "4px",
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* 内容 */}
        <div style={{ padding: "20px", overflowY: "auto", flex: 1 }}>
          {/* 讨论主题 */}
          <div style={{ marginBottom: "20px" }}>
            <label style={{ fontSize: "13px", fontWeight: 500, marginBottom: "8px", display: "block" }}>
              讨论主题
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="输入你想讨论的问题或任务..."
              rows={3}
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: "8px",
                border: "1px solid var(--border-color)",
                background: "var(--bg-level-2)",
                color: "var(--text-level-1)",
                fontSize: "14px",
                resize: "vertical",
                fontFamily: "inherit",
              }}
            />
          </div>

          {/* 选择 Agent */}
          <div style={{ marginBottom: "20px" }}>
            <label style={{ fontSize: "13px", fontWeight: 500, marginBottom: "8px", display: "block" }}>
              参与讨论的 Agent（至少 2 个，已选 {selectedAgentIds.length}）
            </label>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, 1fr)",
                gap: "8px",
                maxHeight: "240px",
                overflowY: "auto",
                padding: "4px",
              }}
            >
              {agents.map((agent) => {
                const selected = selectedAgentIds.includes(agent.id);
                return (
                  <button
                    key={agent.id}
                    onClick={() => toggleAgent(agent.id)}
                    style={{
                      padding: "10px 12px",
                      borderRadius: "8px",
                      border: `1px solid ${selected ? "var(--accent-color)" : "var(--border-color)"}`,
                      background: selected ? "var(--accent-color)" + "15" : "var(--bg-level-2)",
                      cursor: "pointer",
                      textAlign: "left",
                      transition: "all 0.15s",
                    }}
                  >
                    <div style={{ fontSize: "13px", fontWeight: 500, marginBottom: "2px" }}>
                      {agent.name}
                    </div>
                    <div
                      style={{
                        fontSize: "11px",
                        color: "var(--text-level-3)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {agent.description || agent.identity?.slice(0, 30) || ""}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 高级设置 */}
          <div>
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: "0",
                fontSize: "13px",
                color: "var(--text-level-3)",
                display: "flex",
                alignItems: "center",
                gap: "4px",
                marginBottom: showAdvanced ? "12px" : "0",
              }}
            >
              {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              高级设置
            </button>

            {showAdvanced && (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: "13px" }}>讨论轮次</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <button
                      onClick={() => setMaxRounds(Math.max(1, maxRounds - 1))}
                      style={{
                        width: "28px",
                        height: "28px",
                        borderRadius: "6px",
                        border: "1px solid var(--border-color)",
                        background: "var(--bg-level-2)",
                        cursor: "pointer",
                        fontSize: "16px",
                      }}
                    >
                      -
                    </button>
                    <span style={{ fontSize: "14px", fontWeight: 500, minWidth: "24px", textAlign: "center" }}>
                      {maxRounds}
                    </span>
                    <button
                      onClick={() => setMaxRounds(Math.min(5, maxRounds + 1))}
                      style={{
                        width: "28px",
                        height: "28px",
                        borderRadius: "6px",
                        border: "1px solid var(--border-color)",
                        background: "var(--bg-level-2)",
                        cursor: "pointer",
                        fontSize: "16px",
                      }}
                    >
                      +
                    </button>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: "13px" }}>最终总结</span>
                  <button
                    onClick={() => setNeedSummary(!needSummary)}
                    style={{
                      width: "44px",
                      height: "24px",
                      borderRadius: "12px",
                      border: "none",
                      background: needSummary ? "var(--accent-color)" : "var(--bg-level-3)",
                      cursor: "pointer",
                      position: "relative",
                      transition: "background 0.2s",
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        top: "2px",
                        left: needSummary ? "22px" : "2px",
                        width: "20px",
                        height: "20px",
                        borderRadius: "50%",
                        background: "white",
                        transition: "left 0.2s",
                      }}
                    />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 底部 */}
        <div
          style={{
            padding: "16px 20px",
            borderTop: "1px solid var(--border-color)",
            display: "flex",
            justifyContent: "flex-end",
            gap: "10px",
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              border: "1px solid var(--border-color)",
              background: "var(--bg-level-2)",
              cursor: "pointer",
              fontSize: "14px",
            }}
          >
            取消
          </button>
          <button
            onClick={handleCreate}
            disabled={creating || selectedAgentIds.length < 2}
            style={{
              padding: "8px 20px",
              borderRadius: "8px",
              border: "none",
              background: selectedAgentIds.length >= 2 ? "var(--accent-color)" : "var(--bg-level-3)",
              color: selectedAgentIds.length >= 2 ? "white" : "var(--text-level-3)",
              cursor: selectedAgentIds.length >= 2 && !creating ? "pointer" : "not-allowed",
              fontSize: "14px",
              fontWeight: 500,
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            {creating ? "创建中..." : (
              <>
                <Play size={14} />
                开始讨论
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
