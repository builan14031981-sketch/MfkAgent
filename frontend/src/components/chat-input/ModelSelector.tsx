"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Check, ChevronDown } from "lucide-react";
import type { Model } from "@/hooks/useModels";
import {
  pillStyle,
  chevronStyle,
  portalDropdownStyle,
  popoverItemStyle,
  itemHoverBackground,
  pillActiveBackground,
  pillActiveColor,
} from "./styles";

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

  const currentModelName = models.find((m) => m.id === selectedId)?.name ?? selectedId ?? "";

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
          ...pillStyle,
          maxWidth: "200px",
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
        <span style={{
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          minWidth: 0,
        }}>{currentModelName}</span>
        <ChevronDown style={{
          ...chevronStyle,
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform var(--transition-normal)",
        }} />
      </button>

      {open && createPortal(
        <div ref={popRef} id="model-dropdown-portal" className="no-scrollbar" style={portalDropdownStyle({ ...dropdownPos, width: dropdownPos.width, maxHeight: 260 })}>
          {models.map((model) => {
            const active = model.id === selectedId;
            return (
              <button
                key={model.id}
                onClick={() => {
                  onSelect(model.id);
                  onClose();
                }}
                style={{
                  ...popoverItemStyle,
                  color: active ? "var(--color-primary)" : "var(--text-level-2)",
                  fontWeight: active ? 600 : 500,
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
              </button>
            );
          })}
        </div>,
        document.body
      )}
    </div>
  );
}
