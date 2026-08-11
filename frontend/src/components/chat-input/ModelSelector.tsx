"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown, ChevronRight } from "lucide-react";
import type { Model } from "@/hooks/useModels";
import {
  ghostPillStyle,
  chevronStyle,
  portalDropdownStyle,
  popoverItemStyle,
  itemHoverBackground,
  pillActiveBackground,
  pillActiveColor,
  ghostPillHoverBackground,
  ghostPillHoverColor,
  ghostPillHoverShadow,
} from "./styles";

/** Provider ID → 中文展示名映射（与后端 model_providers.py 保持同步） */
const PROVIDER_NAMES: Record<string, string> = {
  deepseek: "DeepSeek",
  qwen: "通义千问",
  google: "Google Gemini",
  glm: "智谱 AI",
  moonshot: "Moonshot",
  freellmapi: "FreeLLMAPI",
  mimo: "小米 MiMo",
  wenxin: "百度文心",
  spark: "讯飞星火",
  minimax: "MiniMax",
  siliconflow: "硅基流动",
};

/** 按 provider 分组后的结构 */
interface ProviderGroup {
  providerId: string;
  providerName: string;
  models: Model[];
}

interface ModelSelectorProps {
  models: Model[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
}

/** 模型选择胶囊：下拉胶囊按钮 + Popover（向上弹出，完整显示）；受控 open 由 ChatInput 互斥协调 */
export function ModelSelector({ models, selectedId, onSelect, open, onToggle, onClose }: ModelSelectorProps) {
  const [dropdownPos, setDropdownPos] = useState({ bottom: 0, left: 0, width: 0 });
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  // Provider 分组折叠状态：默认全部展开
  const [collapsedProviders, setCollapsedProviders] = useState<Set<string>>(new Set());

  const currentModelName = models.find((m) => m.id === selectedId)?.name ?? selectedId ?? "";

  // 按 provider 分组，保持 provider 原始顺序（首次出现顺序）
  const providerGroups = useMemo<ProviderGroup[]>(() => {
    const seen = new Set<string>();
    const groups: ProviderGroup[] = [];
    for (const m of models) {
      if (!seen.has(m.provider)) {
        seen.add(m.provider);
        groups.push({
          providerId: m.provider,
          providerName: PROVIDER_NAMES[m.provider] || m.provider,
          models: [],
        });
      }
      const group = groups.find((g) => g.providerId === m.provider);
      if (group) group.models.push(m);
    }
    return groups;
  }, [models]);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (btnRef.current?.contains(target)) return;
      if (popRef.current?.contains(target)) return;
      onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, onClose]);

  if (models.length === 0) return null;

  return (
    <div style={{ position: "relative", minWidth: 0, maxWidth: "200px", flexShrink: 0 }}>
      <button
        ref={btnRef}
        onClick={() => {
          const rect = btnRef.current?.getBoundingClientRect();
          if (rect) {
            setDropdownPos({
              bottom: window.innerHeight - rect.top,
              left: Math.max(8, Math.min(rect.left, window.innerWidth - 200)),
              width: Math.max(180, Math.min(rect.width, 220)),
            });
          }
          onToggle();
        }}
        title={currentModelName}
        style={{
          ...ghostPillStyle,
          maxWidth: "200px",
          background: open ? pillActiveBackground : "transparent",
          color: open ? pillActiveColor : "var(--text-level-4)",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = ghostPillHoverBackground;
          e.currentTarget.style.color = ghostPillHoverColor;
          e.currentTarget.style.boxShadow = ghostPillHoverShadow;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = open ? pillActiveBackground : "transparent";
          e.currentTarget.style.color = open ? pillActiveColor : "var(--text-level-4)";
          e.currentTarget.style.boxShadow = "none";
        }}
      >
        <span style={{
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          minWidth: 0,
          // 2026-08-11：限制最长胶囊宽度，避免长模型名撞爆窄容器工具栏
          maxWidth: "140px",
        }}>{currentModelName}</span>
        <ChevronDown style={{
          ...chevronStyle,
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform var(--transition-normal)",
        }} />
      </button>

      {open && createPortal(
        <div ref={popRef} id="model-dropdown-portal" className="no-scrollbar" style={portalDropdownStyle({ ...dropdownPos, width: dropdownPos.width, maxHeight: 320 })}>
          {providerGroups.map((group, gi) => {
            const isCollapsed = collapsedProviders.has(group.providerId);
            return <div key={group.providerId}>
              {/* 分隔线（第一个 group 前不显示） */}
              {gi > 0 && (
                <div style={{
                  height: "1px",
                  margin: "4px 8px",
                  background: "var(--border-primary)",
                  opacity: 0.5,
                }} />
              )}

              {/* Provider 分组标题（可点击折叠/展开） */}
              <div
                onClick={() => {
                  setCollapsedProviders((prev) => {
                    const next = new Set(prev);
                    if (next.has(group.providerId)) {
                      next.delete(group.providerId);
                    } else {
                      next.add(group.providerId);
                    }
                    return next;
                  });
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  padding: "5px 10px 3px",
                  fontSize: "10px",
                  fontWeight: 600,
                  color: "var(--text-level-4)",
                  textTransform: "uppercase",
                  letterSpacing: "0.5px",
                  cursor: "pointer",
                  userSelect: "none",
                }}
              >
                {isCollapsed ? (
                  <ChevronRight style={{ width: "10px", height: "10px", opacity: 0.5, flexShrink: 0 }} />
                ) : (
                  <ChevronDown style={{ width: "10px", height: "10px", opacity: 0.5, flexShrink: 0 }} />
                )}
                <span style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}>{group.providerName}</span>
              </div>

              {/* 该 Provider 下的模型列表（折叠时隐藏） */}
              {!isCollapsed && group.models.map((model) => {
                const active = model.id === selectedId;
                return <button
                    key={model.id}
                    onClick={() => {
                      onSelect(model.id);
                      onClose();
                    }}
                    style={{
                      ...popoverItemStyle,
                      paddingLeft: "24px",
                      color: active ? "var(--color-primary)" : "var(--text-level-2)",
                      fontWeight: active ? 600 : 400,
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                  >
                    <span style={{
                      flex: 1,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}>{model.name}</span>
                    {active && <Check style={{ width: "14px", height: "14px", color: "var(--color-primary)", flexShrink: 0 }} />}
                  </button>;
              })}
            </div>;
          })}
        </div>,
        document.body
      )}
    </div>
  );
}