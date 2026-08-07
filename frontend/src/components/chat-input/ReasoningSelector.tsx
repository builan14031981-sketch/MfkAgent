"use client";

import { useRef, useEffect } from "react";
import { Brain, Check, ChevronDown } from "lucide-react";
import type { ReasoningEffort } from "@/components/ChatInput";
import { useTranslation } from "@/hooks/useTranslation";
import {
  ghostPillStyle,
  chevronStyle,
  popoverStyle,
  popoverItemStyle,
  itemHoverBackground,
  pillActiveBackground,
  pillActiveColor,
  ghostPillHoverBackground,
  ghostPillHoverColor,
  ghostPillHoverShadow,
} from "./styles";

interface ReasoningSelectorProps {
  reasoningEffort: ReasoningEffort;
  onReasoningChange: (e: ReasoningEffort) => void;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
}

/** 思考模式选择胶囊：none / high / max；受控 open 由 ChatInput 互斥协调 */
export function ReasoningSelector({ reasoningEffort, onReasoningChange, open, onToggle, onClose }: ReasoningSelectorProps) {
  const { t } = useTranslation();
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  const options: { value: ReasoningEffort; label: string }[] = [
    { value: "none", label: t("chat.reasoning.off") },
    { value: "high", label: t("chat.reasoning.fast") },
    { value: "max", label: t("chat.reasoning.deep") },
  ];
  const currentLabel = options.find((o) => o.value === reasoningEffort)?.label ?? "";

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

  return (
    <div style={{ position: "relative", flexShrink: 0 }}>
      <button
        ref={btnRef}
        onClick={onToggle}
        title={currentLabel}
        style={{
          ...ghostPillStyle,
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
        <Brain style={{ width: "13px", height: "13px", color: "var(--text-level-4)", flexShrink: 0 }} />
        <span style={{ fontWeight: 400 }}>{currentLabel}</span>
        <ChevronDown style={{
          ...chevronStyle,
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform var(--transition-normal)",
        }} />
      </button>

      {open && (
        <div ref={popRef} style={popoverStyle}>
          {options.map((opt) => {
            const active = reasoningEffort === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => {
                  onReasoningChange(opt.value);
                  onClose();
                }}
                style={{
                  ...popoverItemStyle,
                  color: active ? "var(--color-primary)" : "var(--text-level-2)",
                  fontWeight: active ? 600 : 400,
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
              >
                <span style={{ flex: 1 }}>{opt.label}</span>
                {active && <Check style={{ width: "14px", height: "14px", color: "var(--color-primary)", flexShrink: 0 }} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
