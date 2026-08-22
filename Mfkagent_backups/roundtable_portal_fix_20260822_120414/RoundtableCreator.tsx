"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAgents } from "@/hooks/useAgents";
import { useChat } from "@/hooks/useChat";
import { useModels } from "@/hooks/useModels";
import { useVisibleModels } from "@/hooks/useVisibleModels";
import { useSettingsStore } from "@/lib/store";
import { Panel } from "@/components/panels/Panel";
import { AgentIcon } from "@/components/AgentIcon";
import {
  Users,
  Play,
  ChevronDown,
  ChevronUp,
  Loader2,
  Check,
  MessageSquare,
  Wrench,
  Zap,
  Cpu,
} from "lucide-react";

interface RoundtableCreatorProps {
  onClose: () => void;
  initialContent?: string;
  initialAgentId?: string;
}

type RoundtableMode = "discussion" | "collaboration";

/**
 * 圆桌讨论创建面板 —— 对标 SettingsPanel 规范
 * 使用项目统管 Panel 容器，支持主题适配、防误触、无虚化、无透明闪烁
 */
export function RoundtableCreator({
  onClose,
  initialContent = "",
  initialAgentId,
}: RoundtableCreatorProps) {
  const router = useRouter();
  const { agents, loading: agentsLoading } = useAgents();
  const { models } = useModels();
  const visibleModels = useVisibleModels(models);
  const { createChat } = useChat();
  const { settings } = useSettingsStore();

  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>(
    initialAgentId ? [initialAgentId] : []
  );
  const [agentModels, setAgentModels] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<RoundtableMode>("discussion");
  const [maxRounds, setMaxRounds] = useState(2);
  const [needSummary, setNeedSummary] = useState(true);
  const [concurrentFirstRound, setConcurrentFirstRound] = useState(true);
  const [content, setContent] = useState(initialContent);
  const [creating, setCreating] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  const availableAgents = agents.filter(
    (a) => a.status === "active" && !a.id.startsWith("sub_")
  );

  const toggleAgent = (agentId: string) => {
    setSelectedAgentIds((prev) =>
      prev.includes(agentId)
        ? prev.filter((id) => id !== agentId)
        : [...prev, agentId]
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
      const defaultModel =
        visibleModels.find((m) => m.id === settings?.default_model) ||
        visibleModels[0];

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
    <Panel
      isOpen={true}
      onClose={onClose}
      title="圆桌讨论"
      width="580px"
      variant="center"
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          flex: 1,
          minHeight: 0,
          background: "var(--bg-level-1)",
        }}
      >
        {/* 滚动内容区 */}
        <div
          style={{
            padding: "20px 24px",
            overflowY: "auto",
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: "18px",
          }}
        >
          {/* 讨论主题 */}
          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 600,
                marginBottom: "8px",
                display: "block",
                color: "var(--text-level-2)",
              }}
            >
              讨论主题
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="输入你想讨论的问题、方案或多专家会诊任务..."
              rows={3}
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-2)",
                color: "var(--text-level-1)",
                fontSize: "13px",
                lineHeight: "1.5",
                resize: "vertical",
                fontFamily: "inherit",
                boxSizing: "border-box",
                outline: "none",
                transition: "border-color var(--transition-fast)",
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = "var(--color-primary)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = "var(--border-primary)";
              }}
            />
          </div>

          {/* 讨论模式 */}
          <div>
            <label
              style={{
                fontSize: "12px",
                fontWeight: 600,
                marginBottom: "8px",
                display: "block",
                color: "var(--text-level-2)",
              }}
            >
              讨论模式
            </label>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "10px",
              }}
            >
              {/* 探讨模式 */}
              <button
                type="button"
                onClick={() => setMode("discussion")}
                style={{
                  padding: "12px 14px",
                  borderRadius: "var(--radius-md)",
                  border: `1px solid ${
                    mode === "discussion"
                      ? "var(--color-primary)"
                      : "var(--border-primary)"
                  }`,
                  background:
                    mode === "discussion"
                      ? "color-mix(in srgb, var(--color-primary) 10%, var(--bg-level-2))"
                      : "var(--bg-level-2)",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "all var(--transition-fast)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    marginBottom: "4px",
                  }}
                >
                  <MessageSquare
                    size={15}
                    style={{
                      color:
                        mode === "discussion"
                          ? "var(--color-primary)"
                          : "var(--text-level-3)",
                    }}
                  />
                  <span
                    style={{
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "var(--text-level-1)",
                    }}
                  >
                    探讨模式
                  </span>
                </div>
                <div
                  style={{
                    fontSize: "11px",
                    color: "var(--text-level-3)",
                    lineHeight: "1.4",
                  }}
                >
                  多专家多轮辩论，最后汇总观点，不生成子任务
                </div>
              </button>

              {/* 协作模式 */}
              <button
                type="button"
                onClick={() => setMode("collaboration")}
                style={{
                  padding: "12px 14px",
                  borderRadius: "var(--radius-md)",
                  border: `1px solid ${
                    mode === "collaboration"
                      ? "var(--color-primary)"
                      : "var(--border-primary)"
                  }`,
                  background:
                    mode === "collaboration"
                      ? "color-mix(in srgb, var(--color-primary) 10%, var(--bg-level-2))"
                      : "var(--bg-level-2)",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "all var(--transition-fast)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    marginBottom: "4px",
                  }}
                >
                  <Wrench
                    size={15}
                    style={{
                      color:
                        mode === "collaboration"
                          ? "var(--color-primary)"
                          : "var(--text-level-3)",
                    }}
                  />
                  <span
                    style={{
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "var(--text-level-1)",
                    }}
                  >
                    协作模式
                  </span>
                </div>
                <div
                  style={{
                    fontSize: "11px",
                    color: "var(--text-level-3)",
                    lineHeight: "1.4",
                  }}
                >
                  专家讨论分工 + 自动生成可执行任务清单
                </div>
              </button>
            </div>
          </div>

          {/* 选择参与 Agent */}
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "8px",
              }}
            >
              <label
                style={{
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "var(--text-level-2)",
                  margin: 0,
                }}
              >
                参与讨论的 Agent（至少 2 个）
              </label>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 500,
                  color:
                    selectedAgentIds.length >= 2
                      ? "var(--color-primary)"
                      : "var(--text-level-4)",
                }}
              >
                已选 {selectedAgentIds.length} 个
              </span>
            </div>

            {agentsLoading ? (
              <div
                style={{
                  padding: "24px",
                  textAlign: "center",
                  color: "var(--text-level-3)",
                  fontSize: "12px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "6px",
                  background: "var(--bg-level-2)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <Loader2
                  size={16}
                  style={{ animation: "spin 1s linear infinite" }}
                />
                加载 Agent 列表中...
              </div>
            ) : availableAgents.length === 0 ? (
              <div
                style={{
                  padding: "24px",
                  textAlign: "center",
                  color: "var(--text-level-3)",
                  fontSize: "12px",
                  background: "var(--bg-level-2)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                暂无可用 Agent
              </div>
            ) : (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                  maxHeight: "220px",
                  overflowY: "auto",
                  padding: "2px",
                }}
              >
                {availableAgents.map((agent) => {
                  const selected = selectedAgentIds.includes(agent.id);
                  const expanded = expandedAgent === agent.id;

                  return (
                    <div
                      key={agent.id}
                      style={{
                        borderRadius: "var(--radius-md)",
                        border: `1px solid ${
                          selected
                            ? "var(--color-primary)"
                            : "var(--border-primary)"
                        }`,
                        background: "var(--bg-level-2)",
                        overflow: "hidden",
                        transition: "border-color var(--transition-fast)",
                      }}
                    >
                      <div
                        onClick={() => toggleAgent(agent.id)}
                        style={{
                          width: "100%",
                          padding: "8px 12px",
                          background: selected
                            ? "color-mix(in srgb, var(--color-primary) 8%, var(--bg-level-2))"
                            : "transparent",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          boxSizing: "border-box",
                          userSelect: "none",
                        }}
                      >
                        {/* 选中标记 */}
                        <div
                          style={{
                            width: "18px",
                            height: "18px",
                            borderRadius: "var(--radius-xs)",
                            border: `1px solid ${
                              selected
                                ? "var(--color-primary)"
                                : "var(--border-primary)"
                            }`,
                            background: selected
                              ? "var(--color-primary)"
                              : "var(--bg-level-1)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexShrink: 0,
                            transition: "all var(--transition-fast)",
                          }}
                        >
                          {selected && <Check size={12} color="#ffffff" />}
                        </div>

                        {/* Agent 图标 */}
                        <AgentIcon id={agent.id} size={18} />

                        {/* Agent 名称与简介 */}
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div
                            style={{
                              fontSize: "12px",
                              fontWeight: 600,
                              color: "var(--text-level-1)",
                              lineHeight: "1.3",
                            }}
                          >
                            {agent.name}
                          </div>
                          <div
                            style={{
                              fontSize: "11px",
                              color: "var(--text-level-3)",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                              marginTop: "2px",
                            }}
                          >
                            {agent.description ||
                              agent.identity?.slice(0, 40) ||
                              "专业 Agent"}
                          </div>
                        </div>

                        {/* 独立模型配置按钮 */}
                        {selected && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setExpandedAgent(expanded ? null : agent.id);
                            }}
                            title="配置该 Agent 独立模型"
                            style={{
                              background: "transparent",
                              border: "none",
                              cursor: "pointer",
                              padding: "4px 6px",
                              color: expanded
                                ? "var(--color-primary)"
                                : "var(--text-level-3)",
                              display: "flex",
                              alignItems: "center",
                              gap: "2px",
                              borderRadius: "var(--radius-sm)",
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.background =
                                "var(--bg-level-3)";
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = "transparent";
                            }}
                          >
                            <Cpu size={13} />
                            {expanded ? (
                              <ChevronUp size={12} />
                            ) : (
                              <ChevronDown size={12} />
                            )}
                          </button>
                        )}
                      </div>

                      {/* 展开：独立模型选择 */}
                      {selected && expanded && (
                        <div
                          style={{
                            padding: "8px 12px 10px 40px",
                            background: "var(--bg-level-3)",
                            borderTop: "1px solid var(--border-secondary)",
                          }}
                        >
                          <div
                            style={{
                              fontSize: "11px",
                              color: "var(--text-level-3)",
                              marginBottom: "4px",
                            }}
                          >
                            专属模型（留空则继承全局模型）:
                          </div>
                          <select
                            value={agentModels[agent.id] || ""}
                            onChange={(e) =>
                              setAgentModel(agent.id, e.target.value)
                            }
                            style={{
                              width: "100%",
                              padding: "6px 8px",
                              borderRadius: "var(--radius-sm)",
                              border: "1px solid var(--border-primary)",
                              background: "var(--bg-level-2)",
                              color: "var(--text-level-1)",
                              fontSize: "12px",
                              outline: "none",
                              boxSizing: "border-box",
                            }}
                          >
                            <option value="">继承全局默认模型</option>
                            {visibleModels.map((m) => (
                              <option key={m.id} value={m.id}>
                                {m.name || m.id}
                              </option>
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

          {/* 高级设置折叠区 */}
          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: "0",
                fontSize: "12px",
                fontWeight: 500,
                color: "var(--text-level-3)",
                display: "flex",
                alignItems: "center",
                gap: "4px",
                marginBottom: showAdvanced ? "10px" : "0",
              }}
            >
              {showAdvanced ? (
                <ChevronUp size={14} />
              ) : (
                <ChevronDown size={14} />
              )}
              <span>高级设置</span>
            </button>

            {showAdvanced && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "12px",
                  padding: "14px",
                  background: "var(--bg-level-2)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-primary)",
                }}
              >
                {/* 讨论轮次 */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div>
                    <div
                      style={{
                        fontSize: "12px",
                        fontWeight: 500,
                        color: "var(--text-level-1)",
                      }}
                    >
                      讨论轮次
                    </div>
                    <div
                      style={{
                        fontSize: "11px",
                        color: "var(--text-level-3)",
                      }}
                    >
                      每个 Agent 在圆桌中的最大发言轮数
                    </div>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => setMaxRounds(Math.max(1, maxRounds - 1))}
                      style={{
                        width: "26px",
                        height: "26px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-primary)",
                        background: "var(--bg-level-3)",
                        cursor: "pointer",
                        fontSize: "14px",
                        color: "var(--text-level-2)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      -
                    </button>
                    <span
                      style={{
                        fontSize: "13px",
                        fontWeight: 600,
                        minWidth: "20px",
                        textAlign: "center",
                        color: "var(--text-level-1)",
                      }}
                    >
                      {maxRounds}
                    </span>
                    <button
                      type="button"
                      onClick={() => setMaxRounds(Math.min(5, maxRounds + 1))}
                      style={{
                        width: "26px",
                        height: "26px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-primary)",
                        background: "var(--bg-level-3)",
                        cursor: "pointer",
                        fontSize: "14px",
                        color: "var(--text-level-2)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      +
                    </button>
                  </div>
                </div>

                {/* 第一轮并发 */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <Zap size={14} style={{ color: "var(--text-level-3)" }} />
                    <div>
                      <div
                        style={{
                          fontSize: "12px",
                          fontWeight: 500,
                          color: "var(--text-level-1)",
                        }}
                      >
                        首轮并发回答
                      </div>
                      <div
                        style={{
                          fontSize: "11px",
                          color: "var(--text-level-3)",
                        }}
                      >
                        所有专家同时给出第一轮初始分析
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      setConcurrentFirstRound(!concurrentFirstRound)
                    }
                    style={{
                      width: "40px",
                      height: "22px",
                      borderRadius: "11px",
                      border: "none",
                      background: concurrentFirstRound
                        ? "var(--color-primary)"
                        : "var(--bg-level-4)",
                      cursor: "pointer",
                      position: "relative",
                      transition: "background var(--transition-fast)",
                      flexShrink: 0,
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        top: "2px",
                        left: concurrentFirstRound ? "20px" : "2px",
                        width: "18px",
                        height: "18px",
                        borderRadius: "50%",
                        background: "white",
                        boxShadow: "0 1px 2px rgba(0,0,0,0.2)",
                        transition: "left var(--transition-fast)",
                      }}
                    />
                  </button>
                </div>

                {/* 最终总结 */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div>
                    <div
                      style={{
                        fontSize: "12px",
                        fontWeight: 500,
                        color: "var(--text-level-1)",
                      }}
                    >
                      生成最终综合报告
                    </div>
                    <div
                      style={{
                        fontSize: "11px",
                        color: "var(--text-level-3)",
                      }}
                    >
                      由主持人 Agent 最终汇总各专家结论
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setNeedSummary(!needSummary)}
                    style={{
                      width: "40px",
                      height: "22px",
                      borderRadius: "11px",
                      border: "none",
                      background: needSummary
                        ? "var(--color-primary)"
                        : "var(--bg-level-4)",
                      cursor: "pointer",
                      position: "relative",
                      transition: "background var(--transition-fast)",
                      flexShrink: 0,
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        top: "2px",
                        left: needSummary ? "20px" : "2px",
                        width: "18px",
                        height: "18px",
                        borderRadius: "50%",
                        background: "white",
                        boxShadow: "0 1px 2px rgba(0,0,0,0.2)",
                        transition: "left var(--transition-fast)",
                      }}
                    />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 底部操作栏 */}
        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid var(--border-secondary)",
            display: "flex",
            justifyContent: "flex-end",
            gap: "10px",
            background: "var(--bg-level-1)",
            flexShrink: 0,
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "7px 16px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-2)",
              cursor: "pointer",
              fontSize: "13px",
              color: "var(--text-level-2)",
              transition: "all var(--transition-fast)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-level-3)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "var(--bg-level-2)";
            }}
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleCreate}
            disabled={
              creating || selectedAgentIds.length < 2 || !content.trim()
            }
            style={{
              padding: "7px 20px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background:
                selectedAgentIds.length >= 2 && content.trim()
                  ? "var(--color-primary)"
                  : "var(--bg-level-3)",
              color:
                selectedAgentIds.length >= 2 && content.trim()
                  ? "white"
                  : "var(--text-level-4)",
              cursor:
                selectedAgentIds.length >= 2 && content.trim() && !creating
                  ? "pointer"
                  : "not-allowed",
              fontSize: "13px",
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: "6px",
              boxShadow:
                selectedAgentIds.length >= 2 && content.trim()
                  ? "0 2px 8px rgba(0, 113, 227, 0.25)"
                  : "none",
              transition: "all var(--transition-fast)",
            }}
          >
            {creating ? (
              <>
                <Loader2
                  size={14}
                  style={{ animation: "spin 1s linear infinite" }}
                />
                <span>创建圆桌中...</span>
              </>
            ) : (
              <>
                <Play size={14} fill="currentColor" />
                <span>
                  开始{mode === "collaboration" ? "协作" : "讨论"}
                </span>
              </>
            )}
          </button>
        </div>
      </div>
    </Panel>
  );
}
