"use client";

/**
 * SubAgentPanel —— 子代理（角色模板）管理视图
 *
 * 子代理即角色模板：身份提示词 + 工具白名单，持久化于 agents 表。
 * 主 Agent 通过 delegate_sub_agent 委派子任务，编排按模板 spawn 用完即弃实例。
 * 本面板提供角色模板的列表 / 编辑 / 新建，供专业用户配置模板的
 * 身份提示词与工具白名单（allowed_tools）。
 *
 * 视觉规范复用 AgentListPanel（紧凑卡片、小字号、无大间隙）。
 */
import { useState, useEffect, useCallback } from "react";
import { ChevronLeft, Plus, Trash2, Save, Bot, SlidersHorizontal } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import {
  getSubAgents,
  getSubAgentAvailableTools,
  createSubAgent,
  updateSubAgent,
  deleteSubAgent,
  type SubAgent,
} from "@/lib/api";
import { AgentIcon } from "../AgentIcon";

interface SubAgentPanelProps {
  /** 当前编辑中的角色模板 id；null = 列表；"__create__" = 新建 */
  editingId: string | null;
  onSelect: (id: string) => void;
  onBackToSettings: () => void;
  onBackToList: () => void;
  onRefresh: () => void;
}

type View = "list" | "edit" | "create";

const inputStyle: React.CSSProperties = {
  padding: "7px 10px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-primary)",
  background: "var(--bg-level-2)",
  fontSize: "13px",
  color: "var(--text-level-2)",
  outline: "none",
};

const primaryBtn: React.CSSProperties = {
  padding: "6px 14px",
  borderRadius: "var(--radius-sm)",
  border: "none",
  background: "var(--color-primary)",
  color: "var(--text-on-primary)",
  cursor: "pointer",
  fontSize: "12px",
  fontWeight: 500,
};

const ghostBtn: React.CSSProperties = {
  padding: "5px 10px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-primary)",
  background: "transparent",
  cursor: "pointer",
  fontSize: "12px",
  color: "var(--text-level-2)",
};

export function SubAgentPanel({ editingId, onSelect, onBackToSettings, onBackToList, onRefresh }: SubAgentPanelProps) {
  const { t } = useTranslation();
  const [subAgents, setSubAgents] = useState<SubAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [availableTools, setAvailableTools] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  // 编辑态草稿
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [identity, setIdentity] = useState("");
  const [allowedTools, setAllowedTools] = useState<string[]>([]);
  const [agentId, setAgentId] = useState("");

  const view: View = editingId === "__create__" ? "create" : editingId ? "edit" : "list";

  const loadSubAgents = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getSubAgents();
      setSubAgents(data);
    } catch {
      /* 忽略加载错误，保持空列表 */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSubAgents();
    getSubAgentAvailableTools()
      .then((d) => setAvailableTools(d.tools || []))
      .catch(() => {});
  }, [loadSubAgents]);

  // 进入编辑态时填充草稿
  useEffect(() => {
    if (view === "edit") {
      const a = subAgents.find((s) => s.id === editingId);
      if (a) {
        setName(a.name);
        setDescription(a.description || "");
        setIdentity(a.identity || "");
        setAllowedTools(a.allowed_tools || []);
      }
    } else if (view === "create") {
      setName("");
      setDescription("");
      setIdentity("");
      setAllowedTools([]);
      setAgentId("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editingId, view]);

  const active = view === "edit" ? subAgents.find((s) => s.id === editingId) || null : null;

  const toggleTool = (tool: string) => {
    setAllowedTools((prev) => (prev.includes(tool) ? prev.filter((x) => x !== tool) : [...prev, tool]));
  };

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      if (view === "create") {
        if (!agentId.trim()) return;
        await createSubAgent({
          agent_id: agentId.trim(),
          name: name.trim(),
          description: description.trim(),
          identity,
          allowed_tools: allowedTools,
        });
      } else if (active) {
        await updateSubAgent(active.id, {
          name: name.trim(),
          description: description.trim(),
          identity,
          allowed_tools: allowedTools,
        });
      }
      await loadSubAgents();
      onRefresh();
      onBackToList();
    } catch (err) {
      console.error("Failed to save sub-agent:", err);
      alert(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm(`确定删除角色模板「${subAgents.find((s) => s.id === id)?.name ?? id}」？`)) return;
    try {
      await deleteSubAgent(id);
      await loadSubAgents();
      onRefresh();
      onBackToList();
    } catch (err) {
      console.error("Failed to delete sub-agent:", err);
      alert(err instanceof Error ? err.message : "删除失败");
    }
  };

  return (
    <>
      {/* 返回设置 */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <button onClick={onBackToSettings} style={{ ...ghostBtn, display: "flex", alignItems: "center", gap: "4px" }}>
          <ChevronLeft style={{ width: "15px", height: "15px" }} />
          {t("settings.ai.agents.backToSettings")}
        </button>
        {view === "list" && (
          <button
            onClick={() => onSelect("__create__")}
            style={{ ...primaryBtn, display: "flex", alignItems: "center", gap: "5px" }}
          >
            <Plus style={{ width: "13px", height: "13px" }} />
            新建角色模板
          </button>
        )}
      </div>

      {view !== "list" && (
        <button onClick={onBackToList} style={{ ...ghostBtn, display: "flex", alignItems: "center", gap: "4px", marginBottom: "12px" }}>
          <ChevronLeft style={{ width: "14px", height: "14px" }} />
          {t("settings.ai.agents.backToAgentList")}
        </button>
      )}

      {view === "list" ? (
        loading ? (
          <p style={{ fontSize: "12px", color: "var(--text-level-3)" }}>{t("common.loading")}</p>
        ) : subAgents.length === 0 ? (
          <div style={{ padding: "16px", borderRadius: "var(--radius-md)", background: "var(--bg-level-2)", border: "1px solid var(--border-primary)" }}>
            <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: 0 }}>
              暂无角色模板。点击右上角「新建角色模板」创建，主 Agent 即可通过 delegate_sub_agent 工具按模板 spawn 执行子任务。
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {subAgents.map((s) => (
              <div
                key={s.id}
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
                <AgentIcon id={s.id} size={18} style={{ color: "var(--color-primary)", flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <p style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>{s.name}</p>
                    {s.is_builtin && (
                      <span style={{
                        fontSize: "10px", padding: "1px 6px", borderRadius: "999px",
                        background: "var(--color-primary-lighter)", color: "var(--color-primary)",
                        whiteSpace: "nowrap",
                      }}>
                        内置
                      </span>
                    )}
                  </div>
                  <p style={{
                    fontSize: "11px", color: "var(--text-level-3)", margin: "1px 0 0 0",
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                  }}>
                    {s.description}
                  </p>
                  <p style={{ fontSize: "10px", color: "var(--text-level-4)", margin: "2px 0 0 0" }}>
                    {s.allowed_tools.length > 0 ? `工具 ${s.allowed_tools.length} 项` : "不限工具"}
                  </p>
                </div>
                <button onClick={() => onSelect(s.id)} style={{ ...ghostBtn, flexShrink: 0 }}>
                  编辑 ›
                </button>
                {!s.is_builtin && (
                  <button
                    onClick={() => handleDelete(s.id)}
                    title="删除"
                    style={{
                      display: "flex", alignItems: "center", justifyContent: "center",
                      width: 28, height: 28, borderRadius: "var(--radius-sm)", border: "none",
                      background: "transparent", cursor: "pointer", color: "var(--text-level-4)", flexShrink: 0,
                    }}
                  >
                    <Trash2 style={{ width: 14, height: 14 }} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          {/* 基本信息 */}
          <div style={{ padding: "12px", borderRadius: "var(--radius-md)", background: "var(--bg-level-2)", border: "1px solid var(--border-primary)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "10px" }}>
              <Bot style={{ width: "14px", height: "14px", color: "var(--color-primary)" }} />
              <span style={{ fontSize: "12px", fontWeight: 500, color: "var(--text-level-1)" }}>基本信息</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {view === "create" && (
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <label style={{ fontSize: "12px", color: "var(--text-level-3)", width: 70, flexShrink: 0 }}>ID</label>
                  <input
                    value={agentId}
                    onChange={(e) => setAgentId(e.target.value)}
                    placeholder="sub_xxx（唯一标识）"
                    style={{ ...inputStyle, flex: 1 }}
                  />
                </div>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <label style={{ fontSize: "12px", color: "var(--text-level-3)", width: 70, flexShrink: 0 }}>名称</label>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="角色模板名称" style={{ ...inputStyle, flex: 1 }} />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <label style={{ fontSize: "12px", color: "var(--text-level-3)", width: 70, flexShrink: 0 }}>描述</label>
                <input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="一句话说明角色模板职责"
                  style={{ ...inputStyle, flex: 1 }}
                />
              </div>
            </div>
          </div>

          {/* 身份提示词 */}
          <div style={{ padding: "12px", borderRadius: "var(--radius-md)", background: "var(--bg-level-2)", border: "1px solid var(--border-primary)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
              <SlidersHorizontal style={{ width: "14px", height: "14px", color: "var(--color-primary)" }} />
              <span style={{ fontSize: "12px", fontWeight: 500, color: "var(--text-level-1)" }}>身份提示词</span>
            </div>
            <textarea
              value={identity}
              onChange={(e) => setIdentity(e.target.value)}
              placeholder="定义角色模板的身份、职责、行为约束与输出格式。实例仅看到此提示词与委派任务，看不到主会话历史，请写得自包含。"
              rows={6}
              style={{
                ...inputStyle,
                width: "100%",
                resize: "vertical",
                fontFamily: "monospace",
                lineHeight: 1.5,
              }}
            />
          </div>

          {/* 工具白名单 */}
          <div style={{ padding: "12px", borderRadius: "var(--radius-md)", background: "var(--bg-level-2)", border: "1px solid var(--border-primary)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Bot style={{ width: "14px", height: "14px", color: "var(--color-primary)" }} />
                <span style={{ fontSize: "12px", fontWeight: 500, color: "var(--text-level-1)" }}>工具白名单</span>
              </div>
              <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>
                {allowedTools.length > 0 ? `已选 ${allowedTools.length} 项` : "未限制"}
              </span>
            </div>
            {availableTools.length === 0 ? (
              <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: 0 }}>暂无可选工具</p>
            ) : (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", maxHeight: "180px", overflowY: "auto" }}>
                {availableTools.map((tool) => {
                  const checked = allowedTools.includes(tool);
                  return (
                    <label
                      key={tool}
                      style={{
                        display: "inline-flex", alignItems: "center", gap: "5px",
                        padding: "3px 8px", borderRadius: "999px", cursor: "pointer",
                        background: checked ? "var(--color-primary-lighter)" : "var(--bg-level-1)",
                        border: checked ? "1px solid var(--color-primary)" : "1px solid var(--border-primary)",
                        fontSize: "11px", color: checked ? "var(--color-primary)" : "var(--text-level-2)",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleTool(tool)}
                        style={{ margin: 0, accentColor: "var(--color-primary)" }}
                      />
                      {tool}
                    </label>
                  );
                })}
              </div>
            )}
            <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "8px 0 0 0" }}>
              实例仅能使用白名单内的工具。留空 = 不限制（继承主会话工具目录）。
            </p>
          </div>

          {/* 操作按钮 */}
          <div style={{ display: "flex", gap: "8px" }}>
            <button onClick={handleSave} disabled={saving || !name.trim()} style={{ ...primaryBtn, display: "flex", alignItems: "center", gap: "5px", opacity: saving || !name.trim() ? 0.6 : 1 }}>
              <Save style={{ width: "13px", height: "13px" }} />
              {saving ? "保存中…" : "保存"}
            </button>
            <button onClick={onBackToList} style={ghostBtn}>取消</button>
          </div>
        </div>
      )}
    </>
  );
}
