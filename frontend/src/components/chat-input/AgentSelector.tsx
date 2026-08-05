"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { ChevronDown } from "lucide-react";
import { AgentIcon } from "@/components/AgentIcon";
import { useAgents } from "@/hooks/useAgents";
import { useTranslation } from "@/hooks/useTranslation";
import {
  pillStyle,
  chevronStyle,
  portalDropdownStyle,
  itemHoverBackground,
  pillActiveBackground,
  pillActiveColor,
} from "./styles";

interface AgentSelectorProps {
  open: boolean;
  onToggle: () => void;
  selectedId?: string | null;
  onSelect: (agentId: string) => void;
  onClose: () => void;
}

/** Agent 选择胶囊：仅一级入口展示，向上弹出（portal 定位） */
export function AgentSelector({ open, onToggle, selectedId, onSelect, onClose }: AgentSelectorProps) {
  const { t } = useTranslation();
  const { agents, loading: agentsLoading } = useAgents();
  const [dropdownPos, setDropdownPos] = useState({ bottom: 0, left: 0 });
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  const currentAgentName = agents.find((a) => a.id === selectedId)?.name ?? selectedId ?? "";

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

  if (agentsLoading) {
    return <span style={{ fontSize: "12px", color: "var(--text-level-3)", flexShrink: 0 }}>{t("common.loading")}</span>;
  }

  return (
    <div style={{ position: "relative", flexShrink: 0 }}>
      <button
        ref={btnRef}
        onClick={() => {
          const rect = btnRef.current?.getBoundingClientRect();
          if (rect) {
            setDropdownPos({
              bottom: window.innerHeight - rect.top,
              left: Math.max(8, Math.min(rect.left, window.innerWidth - 170)),
            });
          }
          onToggle();
        }}
        style={{
          ...pillStyle,
          background: open ? pillActiveBackground : "var(--bg-level-3)",
          color: open ? pillActiveColor : "var(--text-level-2)",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = pillActiveBackground;
          e.currentTarget.style.color = pillActiveColor;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = open ? pillActiveBackground : "var(--bg-level-3)";
          e.currentTarget.style.color = open ? pillActiveColor : "var(--text-level-2)";
        }}
      >
        <AgentIcon id={selectedId ?? undefined} size={14} style={{ flexShrink: 0 }} />
        <span style={{ fontWeight: 500 }}>{currentAgentName || selectedId}</span>
        <ChevronDown style={{
          ...chevronStyle,
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform var(--transition-normal)",
        }} />
      </button>
      {open && createPortal(
        <div ref={popRef} id="agent-dropdown-portal" className="no-scrollbar" style={portalDropdownStyle({ ...dropdownPos, maxHeight: 220 })}>
          {agents.map((agent) => {
            const active = agent.id === selectedId;
            return (
              <button
                key={agent.id}
                onClick={() => {
                  onSelect(agent.id);
                  onClose();
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  width: "100%",
                  padding: "6px 10px",
                  border: "none",
                  borderRadius: "var(--radius-sm)",
                  background: active ? "var(--color-primary-lighter)" : "transparent",
                  cursor: "pointer",
                  textAlign: "left",
                  fontSize: "12px",
                  fontWeight: 500,
                  lineHeight: 1.25,
                  outline: "none",
                  transition: "background 0.1s",
                }}
                onMouseEnter={(e) => {
                  if (!active) e.currentTarget.style.background = itemHoverBackground;
                }}
                onMouseLeave={(e) => {
                  if (!active) e.currentTarget.style.background = "transparent";
                }}
              >
                <AgentIcon id={agent.id} size={13} style={{ flexShrink: 0, color: "var(--text-level-3)" }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: "12px",
                    fontWeight: "500",
                    lineHeight: 1.25,
                    color: active ? "var(--color-primary)" : "var(--text-level-1)",
                  }}>{agent.name}</div>
                  <div style={{
                    fontSize: "10px",
                    lineHeight: 1.25,
                    color: "var(--text-level-4)",
                  }}>{agent.description}</div>
                </div>
                {active && (
                  <span style={{
                    width: "6px", height: "6px",
                    borderRadius: "50%",
                    background: "var(--color-primary)",
                    flexShrink: 0,
                  }} />
                )}
              </button>
            );
          })}
        </div>,
        document.body
      )}
    </div>
  );
}
