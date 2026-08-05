"use client";

import { useRef, useEffect } from "react";
import { Check, ChevronDown, Wrench, Compass } from "lucide-react";
import type { ChatMode } from "@/components/ChatInput";
import { useTranslation } from "@/hooks/useTranslation";
import {
  pillStyle,
  chevronStyle,
  popoverStyle,
  popoverItemStyle,
  itemHoverBackground,
  pillActiveBackground,
  pillActiveColor,
} from "./styles";

interface ModeSelectorProps {
  mode: ChatMode;
  onModeChange: (m: ChatMode) => void;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
}

const MODE_OPTIONS: { value: ChatMode; label: string; icon: typeof Wrench }[] = [
  { value: "build", label: "", icon: Wrench },
  { value: "plan", label: "", icon: Compass },
];

/** 工作模式选择胶囊：build 可写 / plan 只读；受控 open 由 ChatInput 互斥协调 */
export function ModeSelector({ mode, onModeChange, open, onToggle, onClose }: ModeSelectorProps) {
  const { t } = useTranslation();
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  const options = MODE_OPTIONS.map((opt) => ({ ...opt, label: t(`chat.mode.${opt.value}`) }));
  const current = options.find((o) => o.value === mode);
  const CurrentIcon = current?.icon ?? Wrench;

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
        title={current?.label}
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
        <CurrentIcon style={{ width: "13px", height: "13px", color: "var(--text-level-3)", flexShrink: 0 }} />
        <span>{current?.label}</span>
        <ChevronDown style={{
          ...chevronStyle,
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform var(--transition-normal)",
        }} />
      </button>

      {open && (
        <div ref={popRef} style={{ ...popoverStyle, minWidth: 112 }}>
          {options.map((opt) => {
            const active = mode === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => {
                  onModeChange(opt.value);
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
                <opt.icon style={{ width: "13px", height: "13px", color: "var(--text-level-3)", flexShrink: 0 }} />
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
