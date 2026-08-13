"use client";

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Search,
  Trash2,
  Brain,
  Check,
  X,
  Pencil,
  Plus,
} from "lucide-react";
import { useAgents } from "@/hooks/useAgents";
import { useProjects } from "@/hooks/useProjects";
import { useMemory, MemoryScope } from "@/hooks/useMemory";
import type { MemoryItem, MemoryType } from "@/types/memory";
import { useTranslation } from "@/hooks/useTranslation";
import { AgentIcon } from "@/components/AgentIcon";

const SCOPE_OPTIONS: { value: MemoryScope; key: string }[] = [
  { value: "global", key: "memory.scopeGlobal" },
  { value: "agent", key: "memory.scopeAgent" },
  { value: "project", key: "memory.scopeProject" },
];

const TYPE_OPTIONS: { value: MemoryType; key: string }[] = [
  { value: "preference", key: "settings.memory.types.preference" },
  { value: "fact", key: "settings.memory.types.fact" },
  { value: "workflow", key: "settings.memory.types.workflow" },
  { value: "project", key: "settings.memory.types.project" },
  { value: "user_preference", key: "settings.memory.types.userPreference" },
  { value: "interaction_pattern", key: "settings.memory.types.interactionPattern" },
  { value: "relationship_note", key: "settings.memory.types.relationshipNote" },
  { value: "current_context", key: "settings.memory.types.currentContext" },
];

const TYPE_BADGE_META: Record<MemoryType, { color: string; key: string }> = {
  preference: { color: "var(--color-warning)", key: "settings.memory.types.preference" },
  fact: { color: "var(--color-info)", key: "settings.memory.types.fact" },
  workflow: { color: "var(--color-success)", key: "settings.memory.types.workflow" },
  project: { color: "var(--color-primary)", key: "settings.memory.types.project" },
  user_preference: { color: "var(--color-warning)", key: "settings.memory.types.userPreference" },
  interaction_pattern: { color: "var(--color-info)", key: "settings.memory.types.interactionPattern" },
  relationship_note: { color: "var(--color-error)", key: "settings.memory.types.relationshipNote" },
  current_context: { color: "var(--color-success)", key: "settings.memory.types.currentContext" },
};

const UNKNOWN_TYPE_META = { color: "var(--text-level-3)", key: "settings.memory.types.unknown" };

const PAGE_SIZE = 20;

/** 独立记忆管理二级页：三作用域 + 搜索 + 类型筛选 + 分页 + 编辑/删除/批量删除/新建 */
export default function MemoryManagerPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const { agents } = useAgents();
  const { projects } = useProjects();

  const [scope, setScope] = useState<MemoryScope>("global");
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [selectedProject, setSelectedProject] = useState<number | null>(projects[0]?.id ?? null);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [typeFilter, setTypeFilter] = useState<MemoryType | "all">("all");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirmBatch, setConfirmBatch] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editContent, setEditContent] = useState("");
  const [editType, setEditType] = useState<MemoryType>("fact");
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createContent, setCreateContent] = useState("");
  const [createType, setCreateType] = useState<MemoryType>("fact");
  const [isCreating, setIsCreating] = useState(false);

  const { memories, loading, createMemory, updateMemory, deleteMemory, deleteMemories } =
    useMemory(selectedAgent, selectedProject, scope, search);

  // 搜索输入防抖（500ms）
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSearch(searchInput.trim()), 500);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [searchInput]);

  // 切换作用域/筛选时回到第一页 + 清除选中（render 阶段调整，避免 set-state-in-effect）
  const prevFilterKey = `${scope}|${selectedAgent}|${selectedProject}|${typeFilter}|${search}`;
  const [lastFilterKey, setLastFilterKey] = useState(prevFilterKey);
  if (lastFilterKey !== prevFilterKey) {
    setLastFilterKey(prevFilterKey);
    setPage(1);
    setSelected(new Set());
  }

  const filteredMemories = useMemo(() => {
    let list = memories;
    if (typeFilter !== "all") list = list.filter((m) => (m.memory_type || "fact") === typeFilter);
    return list;
  }, [memories, typeFilter]);

  const pageMemories = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filteredMemories.slice(start, start + PAGE_SIZE);
  }, [filteredMemories, page]);

  const totalPages = Math.max(1, Math.ceil(filteredMemories.length / PAGE_SIZE));

  const scopeLabel = useCallback((s: MemoryScope) => {
    const opt = SCOPE_OPTIONS.find((o) => o.value === s);
    return opt ? t(opt.key) : s;
  }, [t]);

  const formatTime = useCallback((iso: string) => {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }, []);

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    const pageIds = pageMemories.map((m) => m.id);
    setSelected((prev) => {
      const next = new Set(prev);
      const allOnPage = pageIds.every((id) => next.has(id));
      pageIds.forEach((id) => {
        if (allOnPage) next.delete(id);
        else next.add(id);
      });
      return next;
    });
  };

  const startEdit = (m: MemoryItem) => {
    setEditingId(m.id);
    setEditContent(m.content);
    setEditType((m.memory_type || "fact") as MemoryType);
  };

  const saveEdit = async () => {
    if (editingId == null) return;
    const content = editContent.trim();
    if (!content) return;
    try {
      await updateMemory(editingId, { content, memory_type: editType });
      setEditingId(null);
    } catch (err) {
      console.error("Failed to update memory:", err);
    }
  };

  const handleDelete = async (id: number) => {
    if (confirmingDeleteId !== id) {
      setConfirmingDeleteId(id);
      window.setTimeout(() => {
        setConfirmingDeleteId((cur) => (cur === id ? null : cur));
      }, 3000);
      return;
    }
    setConfirmingDeleteId(null);
    try { await deleteMemory(id); } catch (err) { console.error("Failed to delete memory:", err); }
  };

  const handleBatchDelete = async () => {
    if (selected.size === 0) return;
    if (!confirmBatch) { setConfirmBatch(true); return; }
    setConfirmBatch(false);
    try {
      await deleteMemories([...selected]);
      setSelected(new Set());
    } catch (err) { console.error("Failed to batch delete:", err); }
  };

  const handleCreate = async () => {
    const content = createContent.trim();
    if (!content || isCreating) return;
    setIsCreating(true);
    try {
      await createMemory(content, scope);
      setCreateContent("");
      setShowCreate(false);
    } catch (err) {
      console.error("Failed to create memory:", err);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <>
      {/* 顶部栏 */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "16px",
        padding: "14px 24px",
        borderBottom: "1px solid var(--border-primary)",
        background: "var(--bg-level-1)",
        flexShrink: 0,
      }}>
        <button
          onClick={() => router.back()}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "6px 12px",
            borderRadius: "var(--radius-md)",
            border: "none",
            background: "var(--bg-level-3)",
            cursor: "pointer",
            fontSize: "13px",
            color: "var(--text-level-2)",
          }}
        >
          <ArrowLeft style={{ width: "14px", height: "14px" }} />
          <span>{t("memory.back")}</span>
        </button>

        <div style={{ display: "flex", alignItems: "center", gap: "8px", flex: 1, minWidth: 0 }}>
          <Brain style={{ width: "18px", height: "18px", color: "var(--color-primary)", flexShrink: 0 }} />
          <div style={{ minWidth: 0 }}>
            <h1 style={{
              fontSize: "16px", fontWeight: "600", color: "var(--text-level-1)", margin: 0, lineHeight: 1.2,
            }}>{t("memory.manageTitle")}</h1>
            <p style={{
              fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0", lineHeight: 1.3,
            }}>{t("memory.manageDesc")}</p>
          </div>
        </div>

        {/* 统计 */}
        <span style={{
          fontSize: "12px",
          color: "var(--text-level-3)",
          padding: "4px 12px",
          borderRadius: "var(--radius-full)",
          background: "var(--bg-level-3)",
          whiteSpace: "nowrap",
        }}>{t("memory.totalCount", { count: String(filteredMemories.length) })}</span>
      </div>

      {/* 工具栏 */}
      <div style={{
        padding: "16px 24px 12px",
        borderBottom: "1px solid var(--border-secondary)",
        background: "var(--bg-level-2)",
        flexShrink: 0,
      }}>
        {/* 作用域 tabs */}
        <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
          {SCOPE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setScope(opt.value)}
              style={{
                padding: "7px 16px",
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
              {t(opt.key)}
            </button>
          ))}
        </div>

        {/* Agent 选择（agent 作用域） */}
        {scope === "agent" && (
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "12px", alignItems: "center" }}>
            <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>{t("memory.selectAgent")}</span>
            <button
              onClick={() => setSelectedAgent("")}
              style={{
                padding: "5px 12px",
                borderRadius: "var(--radius-full)",
                border: "1px solid",
                borderColor: selectedAgent === "" ? "var(--color-primary)" : "var(--border-primary)",
                background: selectedAgent === "" ? "var(--color-primary-lighter)" : "var(--bg-level-2)",
                cursor: "pointer",
                fontSize: "12px",
                color: selectedAgent === "" ? "var(--color-primary)" : "var(--text-level-2)",
              }}
            >{t("memory.types.all")}</button>
            {agents.map((agent) => (
              <button
                key={agent.id}
                onClick={() => setSelectedAgent(agent.id)}
                style={{
                  display: "flex", alignItems: "center", gap: "6px",
                  padding: "5px 12px",
                  borderRadius: "var(--radius-full)",
                  border: "1px solid",
                  borderColor: selectedAgent === agent.id ? "var(--color-primary)" : "var(--border-primary)",
                  background: selectedAgent === agent.id ? "var(--color-primary-lighter)" : "var(--bg-level-2)",
                  cursor: "pointer",
                  fontSize: "12px",
                  color: selectedAgent === agent.id ? "var(--color-primary)" : "var(--text-level-2)",
                }}
              >
                <AgentIcon id={agent.id} size={13} />
                <span>{agent.name}</span>
              </button>
            ))}
          </div>
        )}

        {/* 项目选择（project 作用域） */}
        {scope === "project" && (
          <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "12px" }}>
            <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>{t("memory.selectProject")}</span>
            <select
              value={selectedProject ?? ""}
              onChange={(e) => setSelectedProject(e.target.value ? Number(e.target.value) : null)}
              style={{
                padding: "7px 12px",
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

        {/* 搜索 + 类型筛选 + 批量删除 */}
        <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
          <div style={{
            flex: 1,
            minWidth: "200px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "9px 12px",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-1)",
          }}>
            <Search style={{ width: "15px", height: "15px", color: "var(--text-level-3)", flexShrink: 0 }} />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder={t("memory.searchPlaceholder")}
              style={{
                flex: 1,
                border: "none",
                outline: "none",
                background: "transparent",
                fontSize: "13px",
                color: "var(--text-level-2)",
              }}
            />
            {searchInput && (
              <button
                onClick={() => setSearchInput("")}
                style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--text-level-4)", padding: 0, display: "flex" }}
              >
                <X style={{ width: "14px", height: "14px" }} />
              </button>
            )}
          </div>

          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as MemoryType | "all")}
            style={{
              padding: "9px 12px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-1)",
              fontSize: "13px",
              color: "var(--text-level-2)",
              outline: "none",
            }}
          >
            <option value="all">{t("settings.memory.types.all")}</option>
            {TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{t(opt.key)}</option>
            ))}
          </select>

          {selected.size > 0 && (
            <button
              onClick={handleBatchDelete}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "9px 14px",
                borderRadius: "var(--radius-md)",
                border: confirmBatch ? "1px solid var(--color-error)" : "none",
                background: confirmBatch ? "color-mix(in srgb, var(--color-error) 10%, var(--bg-level-2))" : "var(--color-error)",
                cursor: "pointer",
                fontSize: "12px",
                fontWeight: "500",
                color: confirmBatch ? "var(--color-error)" : "#fff",
                whiteSpace: "nowrap",
              }}
            >
              <Trash2 style={{ width: "13px", height: "13px" }} />
              <span>{confirmBatch
                ? t("memory.confirmBatchDelete", { count: String(selected.size) })
                : t("memory.batchDelete")}</span>
            </button>
          )}

          <button
            onClick={() => setShowCreate((v) => !v)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "9px 14px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-primary)",
              background: "var(--color-primary-lighter)",
              cursor: "pointer",
              fontSize: "12px",
              fontWeight: "500",
              color: "var(--color-primary)",
              whiteSpace: "nowrap",
            }}
          >
            <Plus style={{ width: "13px", height: "13px" }} />
            <span>{t("memory.addMemory")}</span>
          </button>
        </div>

        {/* 新建记忆内联输入 */}
        {showCreate && (
          <div style={{
            marginTop: "12px",
            padding: "12px",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-primary)",
            background: "var(--bg-level-1)",
          }}>
            <textarea
              value={createContent}
              onChange={(e) => setCreateContent(e.target.value)}
              rows={2}
              autoFocus
              placeholder={t("memory.inputPlaceholder")}
              style={{
                width: "100%", boxSizing: "border-box", padding: "8px 10px",
                borderRadius: "var(--radius-sm)", border: "1px solid var(--border-primary)",
                background: "var(--bg-level-2)", outline: "none", fontSize: "13px",
                lineHeight: "1.5", color: "var(--text-level-1)", resize: "vertical",
                fontFamily: "inherit",
              }}
            />
            <div style={{ display: "flex", gap: "8px", alignItems: "center", marginTop: "8px", flexWrap: "wrap" }}>
              <select
                value={createType}
                onChange={(e) => setCreateType(e.target.value as MemoryType)}
                style={{
                  padding: "6px 10px", borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-primary)", background: "var(--bg-level-1)",
                  fontSize: "12px", color: "var(--text-level-2)", outline: "none",
                }}
              >
                {TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{t(opt.key)}</option>
                ))}
              </select>
              <button
                onClick={handleCreate}
                disabled={!createContent.trim() || isCreating}
                style={{
                  display: "inline-flex", alignItems: "center", gap: "5px",
                  padding: "6px 14px", borderRadius: "var(--radius-md)", border: "none",
                  background: createContent.trim() && !isCreating ? "var(--color-primary)" : "var(--bg-level-3)",
                  color: createContent.trim() && !isCreating ? "#fff" : "var(--text-level-3)",
                  cursor: createContent.trim() && !isCreating ? "pointer" : "not-allowed",
                  fontSize: "12px", fontWeight: 500,
                }}
              >
                <Check style={{ width: "13px", height: "13px" }} />
                {t("memory.add")}
              </button>
              <button
                onClick={() => setShowCreate(false)}
                style={{
                  display: "inline-flex", alignItems: "center", gap: "5px",
                  padding: "6px 12px", borderRadius: "var(--radius-md)", border: "none",
                  background: "var(--bg-level-3)", color: "var(--text-level-3)", cursor: "pointer",
                  fontSize: "12px",
                }}
              >
                {t("memory.cancel")}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 列表区 */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 24px 24px" }}>
        {loading && filteredMemories.length === 0 ? (
          <p style={{ color: "var(--text-level-3)" }}>{t("common.loading")}</p>
        ) : filteredMemories.length === 0 ? (
          <div style={{
            padding: "48px",
            textAlign: "center",
            borderRadius: "var(--radius-lg)",
            background: "var(--bg-level-1)",
          }}>
            <Brain style={{ width: "40px", height: "40px", color: "var(--text-level-4)", marginBottom: "12px" }} />
            <p style={{ fontSize: "14px", color: "var(--text-level-3)", margin: 0 }}>
              {search || typeFilter !== "all"
                ? t("memory.noSearchResults")
                : t("memory.noMemories")}
            </p>
            <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: "4px 0 0 0" }}>
              {search || typeFilter !== "all"
                ? t("memory.noSearchResultsDesc")
                : t("memory.noMemoriesDesc")}
            </p>
          </div>
        ) : (
          <>
            <div style={{ borderRadius: "var(--radius-lg)", border: "1px solid var(--border-primary)", overflow: "hidden" }}>
              {/* 表头 */}
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                padding: "10px 16px",
                background: "var(--bg-level-3)",
                borderBottom: "1px solid var(--border-primary)",
              }}>
                <button
                  onClick={toggleAll}
                  title="select all on page"
                  style={{
                    width: "18px", height: "18px", borderRadius: "var(--radius-xs)",
                    border: "1px solid var(--border-primary)", background: "var(--bg-level-1)",
                    cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                    color: "var(--color-primary)", flexShrink: 0, padding: 0,
                  }}
                >
                  {pageMemories.every((m) => selected.has(m.id)) && (
                    <Check style={{ width: "12px", height: "12px" }} />
                  )}
                </button>
                <span style={{ flex: 1, fontSize: "11px", fontWeight: 600, color: "var(--text-level-4)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  {t("memory.memoryList")}
                </span>
                <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--text-level-4)", textTransform: "uppercase", letterSpacing: "0.5px", width: "90px", textAlign: "right" }}>
                  {t("memory.confirm")}
                </span>
              </div>

              {pageMemories.map((memory) => {
                const isEditing = editingId === memory.id;
                const isConfirming = confirmingDeleteId === memory.id;
                const isSelected = selected.has(memory.id);
                const memType: MemoryType = memory.memory_type || "fact";
                const typeMeta = TYPE_BADGE_META[memType] ?? UNKNOWN_TYPE_META;
                return (
                  <div
                    key={memory.id}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "12px",
                      padding: "12px 16px",
                      background: isSelected ? "var(--color-primary-lighter)" : "var(--bg-level-2)",
                      borderBottom: "1px solid var(--border-secondary)",
                      transition: "background 0.15s ease",
                    }}
                  >
                    <button
                      onClick={() => toggleSelect(memory.id)}
                      style={{
                        width: "18px", height: "18px", marginTop: "3px", borderRadius: "var(--radius-xs)",
                        border: "1px solid var(--border-primary)", background: "var(--bg-level-1)",
                        cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                        color: "var(--color-primary)", flexShrink: 0, padding: 0,
                      }}
                    >
                      {isSelected && <Check style={{ width: "12px", height: "12px" }} />}
                    </button>

                    <div style={{ flex: 1, minWidth: 0 }}>
                      {/* 元信息行 */}
                      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "6px", flexWrap: "wrap" }}>
                        <span style={{
                          display: "inline-flex", alignItems: "center", padding: "1px 7px",
                          borderRadius: "var(--radius-full)", background: "var(--color-primary-lighter)",
                          border: "1px solid var(--color-primary-light)", fontSize: "10px", fontWeight: 600,
                          lineHeight: 1.4, color: "var(--color-primary)",
                        }}>{scopeLabel(memory.scope)}</span>
                        <span style={{
                          display: "inline-flex", alignItems: "center", padding: "1px 7px",
                          borderRadius: "var(--radius-full)",
                          background: `color-mix(in srgb, ${typeMeta.color} 12%, transparent)`,
                          border: `1px solid color-mix(in srgb, ${typeMeta.color} 32%, transparent)`,
                          fontSize: "10px", fontWeight: 600, lineHeight: 1.4, color: typeMeta.color,
                        }}>{t(typeMeta.key)}</span>
                        {memory.agent_id && (
                          <span style={{ fontSize: "10px", color: "var(--text-level-4)" }}>
                            {agents.find((a) => a.id === memory.agent_id)?.name || memory.agent_id}
                          </span>
                        )}
                        <span style={{ fontSize: "10px", color: "var(--text-level-4)" }}>
                          {t("memory.createdAt")} {formatTime(memory.created_at)}
                        </span>
                        {memory.source_chat_id != null && (
                          <span style={{ fontSize: "10px", color: "var(--text-level-4)" }}>
                            #{memory.source_chat_id}
                          </span>
                        )}
                      </div>

                      {/* 内容 / 编辑态 */}
                      {isEditing ? (
                        <div>
                          <textarea
                            value={editContent}
                            onChange={(e) => setEditContent(e.target.value)}
                            rows={2}
                            autoFocus
                            style={{
                              width: "100%", boxSizing: "border-box", padding: "8px 10px",
                              borderRadius: "var(--radius-sm)", border: "1px solid var(--color-primary)",
                              background: "var(--bg-level-1)", outline: "none", fontSize: "13px",
                              lineHeight: "1.5", color: "var(--text-level-1)", resize: "vertical",
                              fontFamily: "inherit",
                            }}
                          />
                          <div style={{ display: "flex", gap: "8px", alignItems: "center", marginTop: "8px", flexWrap: "wrap" }}>
                            <select
                              value={editType}
                              onChange={(e) => setEditType(e.target.value as MemoryType)}
                              style={{
                                padding: "6px 10px", borderRadius: "var(--radius-sm)",
                                border: "1px solid var(--border-primary)", background: "var(--bg-level-1)",
                                fontSize: "12px", color: "var(--text-level-2)", outline: "none",
                              }}
                            >
                              {TYPE_OPTIONS.map((opt) => (
                                <option key={opt.value} value={opt.value}>{t(opt.key)}</option>
                              ))}
                            </select>
                            <button
                              onClick={saveEdit}
                              style={{
                                display: "inline-flex", alignItems: "center", gap: "5px",
                                padding: "6px 14px", borderRadius: "var(--radius-md)", border: "none",
                                background: "var(--color-primary)", color: "#fff", cursor: "pointer",
                                fontSize: "12px", fontWeight: 500,
                              }}
                            >
                              <Check style={{ width: "13px", height: "13px" }} />
                              {t("memory.save")}
                            </button>
                            <button
                              onClick={() => setEditingId(null)}
                              style={{
                                display: "inline-flex", alignItems: "center", gap: "5px",
                                padding: "6px 12px", borderRadius: "var(--radius-md)", border: "none",
                                background: "var(--bg-level-3)", color: "var(--text-level-3)", cursor: "pointer",
                                fontSize: "12px",
                              }}
                            >
                              {t("memory.cancel")}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div style={{
                          fontSize: "13px", lineHeight: "1.5", color: "var(--text-level-1)",
                          whiteSpace: "pre-wrap", wordBreak: "break-word",
                        }}>
                          {memory.content}
                        </div>
                      )}
                    </div>

                    {/* 右侧：置信度 + 操作 */}
                    <div style={{
                      display: "flex", flexDirection: "column", alignItems: "flex-end",
                      gap: "6px", width: "90px", flexShrink: 0,
                    }}>
                      <span style={{
                        fontSize: "12px", color: "var(--text-level-3)", fontWeight: 500,
                      }}>{Math.round((memory.confidence ?? 0.8) * 100)}%</span>
                      <div style={{ display: "flex", gap: "4px" }}>
                        <button
                          onClick={() => startEdit(memory)}
                          title={t("memory.edit")}
                          style={{
                            display: "flex", alignItems: "center", justifyContent: "center",
                            width: "28px", height: "28px", borderRadius: "var(--radius-sm)",
                            border: "none", background: "transparent", cursor: "pointer",
                            color: "var(--text-level-4)",
                          }}
                          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; e.currentTarget.style.color = "var(--color-primary)"; }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-level-4)"; }}
                        >
                          <Pencil style={{ width: "14px", height: "14px" }} />
                        </button>
                        <button
                          onClick={() => handleDelete(memory.id)}
                          title={isConfirming ? t("memory.deleteConfirm") : t("memory.delete")}
                          style={{
                            display: "flex", alignItems: "center", justifyContent: "center",
                            height: "28px", padding: isConfirming ? "0 10px" : "0", borderRadius: "var(--radius-sm)",
                            border: isConfirming ? "1px solid var(--color-error)" : "none",
                            background: isConfirming ? "color-mix(in srgb, var(--color-error) 10%, var(--bg-level-2))" : "transparent",
                            cursor: "pointer", color: isConfirming ? "var(--color-error)" : "var(--text-level-4)",
                            fontSize: "11px", fontWeight: 500, whiteSpace: "nowrap",
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
                    </div>
                  </div>
                );
              })}
            </div>

            {/* 分页 */}
            {totalPages > 1 && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px", padding: "16px 0 4px" }}>
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  style={{
                    padding: "6px 14px", borderRadius: "var(--radius-md)", border: "1px solid var(--border-primary)",
                    background: "var(--bg-level-2)", cursor: page <= 1 ? "not-allowed" : "pointer",
                    fontSize: "12px", color: "var(--text-level-3)", opacity: page <= 1 ? 0.5 : 1,
                  }}
                >‹</button>
                <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  style={{
                    padding: "6px 14px", borderRadius: "var(--radius-md)", border: "1px solid var(--border-primary)",
                    background: "var(--bg-level-2)", cursor: page >= totalPages ? "not-allowed" : "pointer",
                    fontSize: "12px", color: "var(--text-level-3)", opacity: page >= totalPages ? 0.5 : 1,
                  }}
                >›</button>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
