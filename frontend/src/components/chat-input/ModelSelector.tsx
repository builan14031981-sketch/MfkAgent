"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { Check, ChevronDown, ChevronRight } from "lucide-react";
import type { Model } from "@/hooks/useModels";
import {
  ghostPillStyle,
  chevronStyle,
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
  minimax: "MiniMax",
  siliconflow: "硅基流动",
  custom: "自定义模型",
  custom_2: "自定义模型",
  openai: "OpenAI",
  anthropic: "Anthropic",
  mistral: "Mistral",
  meta: "Meta Llama",
  cohere: "Cohere",
  together: "Together AI",
  groq: "Groq",
  zhipu: "智谱 AI",
  baichuan: "百川",
  yi: "零一万物",
  stepfun: "阶跃星辰",
  minimax2: "MiniMax",
  doubao: "豆包",
  bytedance: "豆包",
  sensenova: "商汤日日新",
};

/** 未知 provider 的友好格式化：下划线转空格、去尾部数字、首字母大写 */
function formatProviderFallback(providerId: string): string {
  return providerId
    .replace(/_/g, " ")
    .replace(/\s*\d+\s*$/, "")
    .trim()
    .replace(/^\w/, (c) => c.toUpperCase());
}

/** 归一化模型 ID：去掉可能的 "models/" 前缀，统一匹配格式 */
function normalizeModelId(id: string | null | undefined): string {
  if (!id) return "";
  return id.replace(/^models\//, "");
}

/** 清理模型显示名：部分 provider 的 name 字段自带 "models/" 前缀，显示时去掉 */
function formatModelName(name: string | null | undefined): string {
  if (!name) return "";
  return name.replace(/^models\//, "");
}

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

const DROPDOWN_WIDTH = 190;
const DROPDOWN_MAX_HEIGHT = 320;

/** 模型选择胶囊：下拉胶囊按钮 + Popover（CSS 绝对定位，按钮正上方展开，零 JS 坐标计算）；受控 open 由 ChatInput 互斥协调 */
export function ModelSelector({ models, selectedId, onSelect, open, onToggle, onClose }: ModelSelectorProps) {
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  // Provider 分组折叠状态：默认全部展开
  const [collapsedProviders, setCollapsedProviders] = useState<Set<string>>(new Set());

  const normalizedSelectedId = normalizeModelId(selectedId);
  const currentModelName = formatModelName(models.find((m) => m.id === normalizedSelectedId)?.name ?? selectedId ?? "");

  // 按 provider 分组，保持 provider 原始顺序（首次出现顺序）
  const providerGroups = useMemo<ProviderGroup[]>(() => {
    const seen = new Set<string>();
    const groups: ProviderGroup[] = [];
    for (const m of models) {
      if (!seen.has(m.provider)) {
        seen.add(m.provider);
        groups.push({
          providerId: m.provider,
          providerName: PROVIDER_NAMES[m.provider] || formatProviderFallback(m.provider),
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
        onClick={onToggle}
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
          maxWidth: "140px",
        }}>{currentModelName}</span>
        <ChevronDown style={{
          ...chevronStyle,
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform var(--transition-normal)",
        }} />
      </button>

      {open && (
        <div
          ref={popRef}
          id="model-dropdown-portal"
          style={{
            position: "absolute",
            bottom: "calc(100% + 6px)",
            left: 0,
            width: DROPDOWN_WIDTH,
            maxHeight: DROPDOWN_MAX_HEIGHT,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "1px",
            padding: "4px",
            borderRadius: "var(--radius-xl)",
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-secondary)",
            boxShadow: "var(--shadow-lg)",
            zIndex: 100,
          }}
        >
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
                  padding: "4px 10px 2px",
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
                const active = model.id === normalizedSelectedId;
                return <button
                    key={model.id}
                    onClick={() => {
                      onSelect(model.id);
                      onClose();
                    }}
                    style={{
                      ...popoverItemStyle,
                      padding: "5px 10px 5px 24px",
                      background: active ? "var(--color-primary-lighter)" : "transparent",
                      color: active ? "var(--color-primary)" : "var(--text-level-2)",
                      fontWeight: active ? 600 : 400,
                    }}
                    onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = itemHoverBackground; }}
                    onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = "transparent"; }}
                  >
                    <span style={{
                      flex: 1,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}>{formatModelName(model.name)}</span>
                    {active && <Check style={{ width: "14px", height: "14px", color: "var(--color-primary)", flexShrink: 0 }} />}
                  </button>;
              })}
            </div>;
          })}
        </div>
      )}
    </div>
  );
}
