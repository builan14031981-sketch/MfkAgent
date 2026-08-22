"use client";

import React, { useRef, useEffect } from "react";
import type { Agent } from "@/hooks/useAgents";
import { AgentIcon } from "@/components/AgentIcon";
import { Users } from "lucide-react";

interface MentionPopoverProps {
  candidates: Agent[];
  selectedIndex: number;
  onSelect: (agent: Agent) => void;
  isRoundtable?: boolean;
}

export function MentionPopover({
  candidates,
  selectedIndex,
  onSelect,
  isRoundtable = false,
}: MentionPopoverProps) {
  const listRef = useRef<HTMLDivElement>(null);

  // 自动滚动跟随选中的项目
  useEffect(() => {
    if (!listRef.current) return;
    const selectedEl = listRef.current.children[selectedIndex] as HTMLElement;
    if (selectedEl) {
      selectedEl.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  if (candidates.length === 0) {
    return (
      <div
        style={{
          position: "absolute",
          bottom: "calc(100% + 8px)",
          left: "14px",
          zIndex: 100,
          background: "var(--bg-level-2)",
          border: "1px solid var(--border-primary)",
          borderRadius: "var(--radius-md)",
          padding: "8px 12px",
          boxShadow: "var(--shadow-md), 0 4px 16px rgba(0,0,0,0.12)",
          fontSize: "12px",
          color: "var(--text-level-3)",
          animation: "fadeIn 0.12s ease forwards",
        }}
      >
        未匹配到相关成员
      </div>
    );
  }

  return (
    <div
      style={{
        position: "absolute",
        bottom: "calc(100% + 8px)",
        left: "14px",
        zIndex: 100,
        width: "260px",
        maxHeight: "240px",
        background: "var(--bg-level-2)",
        border: "1px solid var(--border-primary)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-lg), 0 8px 24px rgba(0,0,0,0.14)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        animation: "slideUp 0.15s cubic-bezier(0.16, 1, 0.3, 1) forwards",
      }}
    >
      {/* 头部提示 */}
      <div
        style={{
          padding: "6px 10px",
          background: "var(--bg-level-3)",
          borderBottom: "1px solid var(--border-secondary)",
          display: "flex",
          alignItems: "center",
          gap: "6px",
          fontSize: "11px",
          fontWeight: 600,
          color: "var(--text-level-3)",
        }}
      >
        <Users size={13} style={{ color: "var(--color-primary)" }} />
        <span>{isRoundtable ? "圆桌参会专家" : "选择需要 @ 的 Agent"}</span>
        <span style={{ fontSize: "10px", fontWeight: 400, marginLeft: "auto", color: "var(--text-level-4)" }}>
          ↑↓ 切换 · Enter 选中
        </span>
      </div>

      {/* 列表区 */}
      <div
        ref={listRef}
        style={{
          overflowY: "auto",
          padding: "4px",
          display: "flex",
          flexDirection: "column",
          gap: "2px",
        }}
      >
        {candidates.map((agent, index) => {
          const isSelected = index === selectedIndex;
          return (
            <div
              key={agent.id}
              onClick={() => onSelect(agent)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "6px 8px",
                borderRadius: "var(--radius-sm)",
                background: isSelected
                  ? "color-mix(in srgb, var(--color-primary) 12%, var(--bg-level-3))"
                  : "transparent",
                border: isSelected
                  ? "1px solid var(--color-primary)"
                  : "1px solid transparent",
                cursor: "pointer",
                transition: "all var(--transition-fast)",
              }}
              onMouseEnter={(e) => {
                if (!isSelected) {
                  e.currentTarget.style.background = "var(--bg-level-3)";
                }
              }}
              onMouseLeave={(e) => {
                if (!isSelected) {
                  e.currentTarget.style.background = "transparent";
                }
              }}
            >
              {/* 图标 */}
              <div style={{ flexShrink: 0, color: isSelected ? "var(--color-primary)" : "var(--text-level-2)" }}>
                <AgentIcon id={agent.id} icon={agent.avatar} size={16} />
              </div>

              {/* 姓名与简介 */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: "12px",
                    fontWeight: 600,
                    color: isSelected ? "var(--color-primary)" : "var(--text-level-1)",
                    lineHeight: "1.25",
                  }}
                >
                  {agent.name}
                </div>
                <div
                  style={{
                    fontSize: "10px",
                    color: "var(--text-level-3)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    marginTop: "1px",
                  }}
                >
                  {agent.description || agent.identity?.slice(0, 24) || "专业助手"}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
