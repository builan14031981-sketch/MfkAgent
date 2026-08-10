"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import { Search, X, Plus, Check, Loader2, Zap, AlertCircle } from "lucide-react";
import type { RemoteModelInfo } from "@/hooks/useProviderConfig";

/** 格式化上下文窗口为可读字符串 */
function formatContextWindow(tokens: number | null): string {
  if (tokens === null || tokens === undefined) return "";
  if (tokens >= 1_000_000) {
    const m = tokens / 1_000_000;
    return m === Math.floor(m) ? `${m}M` : `${m.toFixed(1)}M`;
  }
  if (tokens >= 1_000) {
    const k = tokens / 1_000;
    return k === Math.floor(k) ? `${k}K` : `${k.toFixed(0)}K`;
  }
  return `${tokens}`;
}

export interface RemoteModelPickerProps {
  /** Provider ID（用于日志/标识） */
  providerId: string;
  /** 已拉取的远程模型列表（由父组件 fetch 后传入） */
  models: RemoteModelInfo[];
  /** 该 provider 下已启用的模型 id 集合（用于标记"已添加"） */
  enabledSet: Set<string>;
  /** 选中某模型时触发（父组件负责实际添加到 enabled_models） */
  onAdd: (modelId: string) => void;
  /** 关闭弹层 */
  onClose: () => void;
  /** 加载态 */
  loading: boolean;
  /** 拉取错误信息（无则 null） */
  error: string | null;
}

/**
 * 远程模型搜索选择器（防爆设计）。
 *
 * 核心解决问题：上游 provider（如硅基流动）可能返回几百个模型，
 * 绝不能平铺成 Chip 撑爆 UI。改用"搜索框 + 滚动视窗 + 逐项添加"模式。
 *
 * 防爆策略：
 * 1. 搜索框实时过滤，只渲染匹配项（非空时最多展示 200 条，超出提示）。
 * 2. 滚动视窗固定 max-height 280px，内部 overflow-y auto。
 * 3. 已添加项显示 ✓ 禁用态，防止重复。
 * 4. 空搜索时仅显示前 100 条 + "输入关键词搜索更多"提示。
 *
 * 交互：
 * - 输入关键词 → 实时过滤 → 点击 + 添加 → 该项变 ✓ 已添加
 * - ESC 关闭弹层
 */
export function RemoteModelPicker({
  providerId,
  models,
  enabledSet,
  onAdd,
  onClose,
  loading,
  error,
}: RemoteModelPickerProps) {
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  // 自动聚焦搜索框
  useEffect(() => {
    searchRef.current?.focus();
  }, []);

  // ESC 关闭
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // 过滤逻辑：大小写不敏感 + 子串匹配
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return models.slice(0, 100); // 空搜索只展示前 100 条防爆
    return models.filter((m) => m.id.toLowerCase().includes(q)).slice(0, 200);
  }, [models, query]);

  const hasMore = query.trim()
    ? models.filter((m) => m.id.toLowerCase().includes(query.trim().toLowerCase())).length > 200
    : models.length > 100;

  return (
    <div
      style={{
        marginTop: "8px",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--border-primary)",
        background: "var(--bg-level-1)",
        boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
        overflow: "hidden",
      }}
    >
      {/* 标题栏 */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "6px",
        padding: "8px 12px",
        borderBottom: "1px solid var(--border-primary)",
        background: "var(--bg-level-2)",
      }}>
        <Zap style={{ width: "13px", height: "13px", color: "var(--color-primary)" }} />
        <span style={{ fontSize: "12px", fontWeight: "500", color: "var(--text-level-1)" }}>
          官方模型列表 ({models.length})
        </span>
        <span style={{ fontSize: "11px", color: "var(--text-level-4)", marginLeft: "2px" }}>
          {providerId}
        </span>
        <button
          onClick={onClose}
          style={{
            marginLeft: "auto",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "20px",
            height: "20px",
            padding: 0,
            borderRadius: "var(--radius-sm)",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            color: "var(--text-level-3)",
          }}
        >
          <X style={{ width: "14px", height: "14px" }} />
        </button>
      </div>

      {/* 搜索框 */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "6px",
        padding: "8px 12px",
        borderBottom: "1px solid var(--border-primary)",
      }}>
        <Search style={{ width: "14px", height: "14px", color: "var(--text-level-4)", flexShrink: 0 }} />
        <input
          ref={searchRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索模型 ID (如 Qwen, deepseek, gpt...)"
          style={{
            flex: 1,
            border: "none",
            outline: "none",
            background: "transparent",
            fontSize: "13px",
            color: "var(--text-level-2)",
            fontFamily: "monospace",
          }}
        />
        {query && (
          <button
            onClick={() => setQuery("")}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "18px",
              height: "18px",
              padding: 0,
              borderRadius: "50%",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              color: "var(--text-level-4)",
            }}
          >
            <X style={{ width: "12px", height: "12px" }} />
          </button>
        )}
      </div>

      {/* 列表区（滚动视窗，防爆核心） */}
      <div style={{
        maxHeight: "280px",
        overflowY: "auto",
        padding: "4px 0",
      }}>
        {loading ? (
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
            padding: "24px",
            color: "var(--text-level-3)",
            fontSize: "13px",
          }}>
            <Loader2 style={{ width: "14px", height: "14px", animation: "spin 1s linear infinite" }} />
            正在拉取官方模型...
          </div>
        ) : error ? (
          <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "6px",
            padding: "20px",
            color: "var(--color-danger, #ef4444)",
            fontSize: "12px",
            textAlign: "center",
          }}>
            <AlertCircle style={{ width: "20px", height: "20px" }} />
            <span>{error}</span>
          </div>
        ) : filtered.length === 0 ? (
          <div style={{
            padding: "20px",
            textAlign: "center",
            color: "var(--text-level-4)",
            fontSize: "12px",
          }}>
            {query ? `没有匹配 "${query}" 的模型` : "上游返回空列表"}
          </div>
        ) : (
          <>
            {filtered.map((m) => {
              const added = enabledSet.has(m.id);
              const cwLabel = formatContextWindow(m.context_window);
              return (
                <div
                  key={m.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "5px 12px",
                    cursor: added ? "default" : "pointer",
                    transition: "background 0.1s ease",
                  }}
                  onMouseEnter={(e) => {
                    if (!added) e.currentTarget.style.background = "var(--bg-level-2)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                  }}
                  onClick={() => {
                    if (!added) onAdd(m.id);
                  }}
                >
                  <span style={{
                    flex: 1,
                    fontSize: "12px",
                    fontFamily: "monospace",
                    color: added ? "var(--text-level-4)" : "var(--text-level-2)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}>
                    {m.id}
                  </span>
                  {cwLabel && (
                    <span style={{
                      fontSize: "10px",
                      fontFamily: "monospace",
                      color: "var(--text-level-4)",
                      background: "var(--bg-level-2)",
                      padding: "1px 5px",
                      borderRadius: "3px",
                      flexShrink: 0,
                    }}
                      title={`上下文窗口: ${m.context_window?.toLocaleString()} tokens`}
                    >
                      {cwLabel}
                    </span>
                  )}
                  {added ? (
                    <span style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "3px",
                      fontSize: "11px",
                      color: "var(--color-success)",
                      flexShrink: 0,
                    }}>
                      <Check style={{ width: "12px", height: "12px" }} />
                      已添加
                    </span>
                  ) : (
                    <span style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "3px",
                      fontSize: "11px",
                      color: "var(--color-primary)",
                      flexShrink: 0,
                    }}>
                      <Plus style={{ width: "12px", height: "12px" }} />
                      添加
                    </span>
                  )}
                </div>
              );
            })}
            {hasMore && (
              <div style={{
                padding: "6px 12px",
                fontSize: "11px",
                color: "var(--text-level-4)",
                textAlign: "center",
                borderTop: "1px solid var(--border-primary)",
              }}>
                {query
                  ? `仅展示前 200 条，输入更精确的关键词缩小范围`
                  : `仅展示前 100 条，输入关键词搜索更多`}
              </div>
            )}
          </>
        )}
      </div>

      {/* spin 动画内联（避免依赖外部 CSS） */}
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
