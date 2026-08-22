"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAgents, type Agent } from "@/hooks/useAgents";
import { useChat } from "@/hooks/useChat";
import { useModels } from "@/hooks/useModels";
import { useVisibleModels } from "@/hooks/useVisibleModels";
import { useSettingsStore } from "@/lib/store";
import { X, Users, Play, ChevronDown, ChevronUp, Loader2, Check, MessageSquare, Wrench, Zap, Cpu } from "lucide-react";

interface RoundtableCreatorProps {
  onClose: () => void;
  initialContent?: string;
  initialAgentId?: string;
}

type RoundtableMode = "discussion" | "collaboration";

/** 圆桌模式创建器 V2：多选 Agent、模式选择、每Agent模型、并发、创建圆桌会话 */
export function RoundtableCreator({ onClose, initialContent = "", initialAgentId }: RoundtableCreatorProps) {
  const router = useRouter();
  const { agents, loading: agentsLoading } = useAgents();
  const { models } = useModels();
  const visibleModels = useVisibleModels(models);
  const { createChat } = useChat();
  const { settings } = useSettingsStore();

  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>(initialAgentId ? [initialAgentId] : []);
  const [agentModels, setAgentModels] = useState<Record<string, string>>({}); // agent_id -> model_id (空=继承全局)
  const [mode, setMode] = useState<RoundtableMode>("discussion");
  const [maxRounds, setMaxRounds] = useState(2);
  const [needSummary, setNeedSummary] = useState(true);
  const [concurrentFirstRound, setConcurrentFirstRound] = useState(true);
  const [content, setContent] = useState(initialContent);
  const [creating, setCreating] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  const availableAgents = agents.filter((a) => a.status === "active" && !a.id.startsWith("sub_"));

  const toggleAgent = (agentId: string) => {
    setSelectedAgentIds((prev) =>
      prev.includes(agentId) ? prev.filter((id) => id !== agentId) : [...prev, agentId]
    );
  };

  const setAgentModel = (agentId: string, modelId: string) => {
    setAgentModels((prev) => {
      const next = { ...prev };
      if (modelId) next[agentId] = modelId;
      else delete next[agentId];
      return next;
    });
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

      // V2: agents 格式，每Agent可独立模型
      const agentsConfig = selectedAgentIds.map((aid) => {
        const seat: Record<string, any> = { agent_id: aid };
        if (agentModels[aid]) seat.model = agentModels[aid];
        return seat;
      });

      const roundtableConfig: Record<string, any> = {
        mode,
        agents: agentsConfig,
        max_rounds: maxRounds,
        need_summary: needSummary,
        moderator_id: selectedAgentIds[selectedAgentIds.length - 1],
        concurrent_first_round: concurrentFirstRound,
      };
      if (mode === "collaboration") {
        roundtableConfig.generate_tasks = true;
      }

      const chat = await createChat(
        selectedAgentIds[0],
        content.slice(0, 50) || "圆桌讨论",
        null,
        defaultModel?.id || null,
        [],
        "roundtable",
        "standard",
        roundtableConfig
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
    <>
      <div
        style={{
          position: "fixed",
          inset: 0,
          background: "var(--overlay-modal)",
          zIndex: 999,
        }}
        onClick={onClose}
      />
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          background: "#ffffff",
          borderRadius: "12px",
          width: "100%",
          maxWidth: "560px",
          maxHeight: "88vh",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          border: "1px solid #e4e5e9",
          boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
          zIndex: 1000,
        }}
      >
        {/* 头部 */}
        <div
          style={{
            padding: "14px 18px",
            borderBottom: "1px solid var(--border-primary)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Users size={18} style={{ color: "var(--color-primary)" }} />
            <span style={{ fontSize: "15px", fontWeight: 600 }}>圆桌讨论</span>
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
              display: "flex",
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* 内容 */}
        <div style={{ padding: "16px 18px", overflowY: "auto", flex: 1 }}>
          {/* 讨论主题 */}
          <div style={{ marginBottom: "14px" }}>
            <label style={{ fontSize: "12px", fontWeight: 500, marginBottom: "6px", display: "block", color: "var(--text-level-2)" }}>
              讨论主题
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="输入你想讨论的问题或任务..."
              rows={2}
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: "8px",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-2)",
                color: "var(--text-level-1)",
                fontSize: "13px",
                resize: "vertical",
                fontFamily: "inherit",
                boxSizing: "border-box",
              }}
            />
          </div>

          {/* 模式选择 */}
          <div style={{ marginBottom: "14px" }}>
            <label style={{ fontSize: "12px", fontWeight: 500, marginBottom: "6px", display: "block", color: "var(--text-level-2)" }}>
              讨论模式
            </label>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
              <button
                onClick={() => setMode("discussion")}
                style={{
                  padding: "10px 12px",
                  borderRadius: "8px",
                  border: `1px solid ${mode === "discussion" ? "var(--color-primary)" : "var(--border-primary)"}`,
                  background: mode === "discussion" ? "color-mix(in srgb, var(--color-primary) 10%, transparent)" : "var(--bg-level-2)",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "all 0.15s",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "3px" }}>
                  <MessageSquare size={14} style={{ color: mode === "discussion" ? "var(--color-primary)" : "var(--text-level-3)" }} />
                  <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-level-1)" }}>探讨模式</span>
                </div>
                <div style={{ fontSize: "10px", color: "var(--text-level-3)", lineHeight: 1.3 }}>
                  多专家讨论，最后出总结，不生成任务
                </div>
              </button>
              <button
                onClick={() => setMode("collaboration")}
                style={{
                  padding: "10px 12px",
                  borderRadius: "8px",
                  border: `1px solid ${mode === "collaboration" ? "var(--color-primary)" : "var(--border-primary)"}`,
                  background: mode === "collaboration" ? "color-mix(in srgb, var(--color-primary) 10%, transparent)" : "var(--bg-level-2)",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "all 0.15s",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "3px" }}>
                  <Wrench size={14} style={{ color: mode === "collaboration" ? "var(--color-primary)" : "var(--text-level-3)" }} />
                  <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-level-1)" }}>协作模式</span>
                </div>
                <div style={{ fontSize: "10px", color: "var(--text-level-3)", lineHeight: 1.3 }}>
                  讨论 + 生成可执行任务清单
                </div>
              </button>
            </div>
          </div>

          {/* 选择 Agent */}
          <div style={{ marginBottom: "14px" }}>
            <label style={{ fontSize: "12px", fontWeight: 500, marginBottom: "6px", display: "block", color: "var(--text-level-2)" }}>
              参与讨论的 Agent（至少 2 个，已选 <span style={{ color: "var(--color-primary)" }}>{selectedAgentIds.length}</span>）
            </label>
            {agentsLoading ? (
              <div style={{ padding: "20px", textAlign: "center", color: "var(--text-level-3)", fontSize: "12px" }}>
                <Loader2 size={16} style={{ animation: "spin 1s linear infinite", marginRight: "6px" }} />
                加载 Agent 列表...
              </div>
            ) : availableAgents.length === 0 ? (
              <div style={{ padding: "20px", textAlign: "center", color: "var(--text-level-3)", fontSize: "12px" }}>
                暂无可用 Agent
              </div>
            ) : (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                  maxHeight: "240px",
                  overflowY: "auto",
                  padding: "2px",
                }}
              >
                {availableAgents.map((agent) => {
                  const selected = selectedAgentIds.includes(agent.id);
                  const expanded = expandedAgent === agent.id;
                  return (
                    <div key={agent.id}>
                      <button
                        onClick={() => toggleAgent(agent.id)}
                        style={{
                          width: "100%",
                          padding: "8px 10px",
                          borderRadius: "8px",
                          border: `1px solid ${selected ? "var(--color-primary)" : "var(--border-primary)"}`,
                          background: selected ? "color-mix(in srgb, var(--color-primary) 12%, transparent)" : "var(--bg-level-2)",
                          cursor: "pointer",
                          textAlign: "left",
                          transition: "all 0.15s",
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                          position: "relative",
                          boxSizing: "border-box",
                        }}
                      >
                        {selected && (
                          <div style={{
                            width: "16px",
                            height: "16px",
                            borderRadius: "50%",
                            background: "var(--color-primary)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexShrink: 0,
                          }}>
                            <Check size={10} color="white" />
                          </div>
                        )}
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: "12px", fontWeight: 500, color: "var(--text-level-1)" }}>
                            {agent.name}
                          </div>
                          <div style={{
                            fontSize: "10px",
                            color: "var(--text-level-3)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}>
                            {agent.description || agent.identity?.slice(0, 40) || "专业专家"}
                          </div>
                        </div>
                        {selected && (
                          <button
                            onClick={(e) => { e.stopPropagation(); setExpandedAgent(expanded ? null : agent.id); }}
                            style={{
                              background: "none",
                              border: "none",
                              cursor: "pointer",
                              padding: "2px 4px",
                              color: "var(--text-level-3)",
                              display: "flex",
                              alignItems: "center",
                            }}
                          >
                            <Cpu size={13} />
                            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                          </button>
                        )}
                      </button>
                      {/* 展开：模型选择 */}
                      {selected && expanded && (
                        <div style={{
                          padding: "8px 10px 8px 34px",
                          background: "var(--bg-level-1)",
                          borderRadius: "0 0 8px 8px",
                          border: "1px solid var(--border-primary)",
                          borderTop: "none",
                          marginTop: "-2px",
                        }}>
                          <div style={{ fontSize: "10px", color: "var(--text-level-3)", marginBottom: "4px" }}>
                            模型（留空=继承全局）
                          </div>
                          <select
                            value={agentModels[agent.id] || ""}
                            onChange={(e) => setAgentModel(agent.id, e.target.value)}
                            style={{
                              width: "100%",
                              padding: "5px 8px",
                              borderRadius: "6px",
                              border: "1px solid var(--border-primary)",
                              background: "var(--bg-level-2)",
                              color: "var(--text-level-1)",
                              fontSize: "11px",
                              boxSizing: "border-box",
                            }}
                          >
                            <option value="">继承全局模型</option>
                            {visibleModels.map((m) => (
                              <option key={m.id} value={m.id}>{m.name || m.id}</option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
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
                fontSize: "12px",
                color: "var(--text-level-3)",
                display: "flex",
                alignItems: "center",
                gap: "4px",
                marginBottom: showAdvanced ? "10px" : "0",
              }}
            >
              {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              高级设置
            </button>

            {showAdvanced && (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px", padding: "12px", background: "var(--bg-level-2)", borderRadius: "8px" }}>
                {/* 轮次 */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: "12px", color: "var(--text-level-2)" }}>讨论轮次</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <button
                      onClick={() => setMaxRounds(Math.max(1, maxRounds - 1))}
                      style={{
                        width: "26px", height: "26px", borderRadius: "6px",
                        border: "1px solid var(--border-color)",
                        background: "var(--bg-level-1)", cursor: "pointer",
                        fontSize: "14px", color: "var(--text-level-2)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}
                    >-</button>
                    <span style={{ fontSize: "13px", fontWeight: 500, minWidth: "20px", textAlign: "center", color: "var(--text-level-1)" }}>
                      {maxRounds}
                    </span>
                    <button
                      onClick={() => setMaxRounds(Math.min(5, maxRounds + 1))}
                      style={{
                        width: "26px", height: "26px", borderRadius: "6px",
                        border: "1px solid var(--border-color)",
                        background: "var(--bg-level-1)", cursor: "pointer",
                        fontSize: "14px", color: "var(--text-level-2)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}
                    >+</button>
                  </div>
                </div>

                {/* 第一轮并发 */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <Zap size={13} style={{ color: "var(--text-level-3)" }} />
                    <span style={{ fontSize: "12px", color: "var(--text-level-2)" }}>第一轮并发</span>
                  </div>
                  <button
                    onClick={() => setConcurrentFirstRound(!concurrentFirstRound)}
                    style={{
                      width: "40px", height: "22px", borderRadius: "11px",
                      border: "none",
                      background: concurrentFirstRound ? "var(--color-primary)" : "var(--bg-level-3)",
                      cursor: "pointer", position: "relative",
                      transition: "background 0.2s", flexShrink: 0,
                    }}
                  >
                    <div style={{
                      position: "absolute", top: "2px",
                      left: concurrentFirstRound ? "20px" : "2px",
                      width: "18px", height: "18px", borderRadius: "50%",
                      background: "white", transition: "left 0.2s",
                    }} />
                  </button>
                </div>

                {/* 最终总结 */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: "12px", color: "var(--text-level-2)" }}>最终总结</span>
                  <button
                    onClick={() => setNeedSummary(!needSummary)}
                    style={{
                      width: "40px", height: "22px", borderRadius: "11px",
                      border: "none",
                      background: needSummary ? "var(--color-primary)" : "var(--bg-level-3)",
                      cursor: "pointer", position: "relative",
                      transition: "background 0.2s", flexShrink: 0,
                    }}
                  >
                    <div style={{
                      position: "absolute", top: "2px",
                      left: needSummary ? "20px" : "2px",
                      width: "18px", height: "18px", borderRadius: "50%",
                      background: "white", transition: "left 0.2s",
                    }} />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 底部 */}
        <div
          style={{
            padding: "12px 18px",
            borderTop: "1px solid var(--border-primary)",
            display: "flex",
            justifyContent: "flex-end",
            gap: "8px",
            flexShrink: 0,
          }}
        >
          <button
            onClick={onClose}
            style={{
              padding: "7px 16px", borderRadius: "8px",
              border: "1px solid var(--border-color)",
              background: "var(--bg-level-2)", cursor: "pointer",
              fontSize: "13px", color: "var(--text-level-2)",
            }}
          >取消</button>
          <button
            onClick={handleCreate}
            disabled={creating || selectedAgentIds.length < 2 || !content.trim()}
            style={{
              padding: "7px 18px", borderRadius: "8px", border: "none",
              background: selectedAgentIds.length >= 2 && content.trim() ? "var(--color-primary)" : "var(--bg-level-3)",
              color: selectedAgentIds.length >= 2 && content.trim() ? "white" : "var(--text-level-3)",
              cursor: selectedAgentIds.length >= 2 && content.trim() && !creating ? "pointer" : "not-allowed",
              fontSize: "13px", fontWeight: 500,
              display: "flex", alignItems: "center", gap: "6px",
            }}
          >
            {creating ? (
              <><Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} />创建中...</>
            ) : (
              <><Play size={14} />开始{mode === "collaboration" ? "协作" : "讨论"}</>
            )}
          </button>
        </div>
      </div>
    </>
  );
}
