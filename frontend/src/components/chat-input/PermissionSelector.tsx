"use client";

import { useRef, useEffect } from "react";
import { Shield, Zap, Check, ChevronDown } from "lucide-react";
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

/** 权限模式：strict = 每次询问 / auto_approve = 自动放行 */
export type PermissionMode = "strict" | "auto_approve";

interface PermissionSelectorProps {
  permissionMode: PermissionMode;
  onPermissionChange: (mode: PermissionMode) => void;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
}

/** 权限/执行模式选择胶囊：严格模式 / 最高权限模式；受控 open 由 ChatInput 互斥协调 */
export function PermissionSelector({ permissionMode, onPermissionChange, open, onToggle, onClose }: PermissionSelectorProps) {
  const { t } = useTranslation();
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  const options: { value: PermissionMode; label: string; icon: React.ReactNode; desc: string }[] = [
    {
      value: "strict",
      label: t("chat.permission.strict"),
      icon: <Shield style={{ width: "13px", height: "13px", flexShrink: 0 }} />,
      desc: t("chat.permission.strictDesc"),
    },
    {
      value: "auto_approve",
      label: t("chat.permission.autoApprove"),
      icon: <Zap style={{ width: "13px", height: "13px", flexShrink: 0 }} />,
      desc: t("chat.permission.autoApproveDesc"),
    },
  ];
  const current = options.find((o) => o.value === permissionMode) ?? options[0];

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
        title={current.label}
        style={{
          ...ghostPillStyle,
          background: open ? pillActiveBackground : "transparent",
          color: open
            ? pillActiveColor
            : permissionMode === "auto_approve"
              ? "var(--color-warning, #f59e0b)"
              : "var(--text-level-4)",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = ghostPillHoverBackground;
          e.currentTarget.style.color = ghostPillHoverColor;
          e.currentTarget.style.boxShadow = ghostPillHoverShadow;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = open ? pillActiveBackground : "transparent";
          e.currentTarget.style.color = open
            ? pillActiveColor
            : permissionMode === "auto_approve"
              ? "var(--color-warning, #f59e0b)"
              : "var(--text-level-4)";
          e.currentTarget.style.boxShadow = "none";
        }}
      >
        {permissionMode === "auto_approve" ? (
          <Zap style={{ width: "13px", height: "13px", color: "var(--color-warning, #f59e0b)", flexShrink: 0 }} />
        ) : (
          <Shield style={{ width: "13px", height: "13px", color: "var(--text-level-4)", flexShrink: 0 }} />
        )}
        <span style={{ fontWeight: 400 }}>{current.label}</span>
        <ChevronDown style={{
          ...chevronStyle,
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform var(--transition-normal)",
        }} />
      </button>

      {open && (
        <div ref={popRef} style={popoverStyle}>
          {options.map((opt) => {
            const active = permissionMode === opt.value;
            return (
              <button
                key={opt.value}
                onClick={() => {
                  onPermissionChange(opt.value);
                  onClose();
                }}
                style={{
                  ...popoverItemStyle,
                  color: active ? "var(--color-primary)" : "var(--text-level-2)",
                  fontWeight: active ? 600 : 400,
                  whiteSpace: "normal",
                  alignItems: "flex-start",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
              >
                {opt.icon}
                <span style={{ flex: 1 }}>
                  <span style={{ display: "block", fontWeight: active ? 600 : 500 }}>{opt.label}</span>
                  <span style={{
                    display: "block",
                    fontSize: "11px",
                    color: "var(--text-level-4)",
                    marginTop: "2px",
                    lineHeight: 1.3,
                  }}>{opt.desc}</span>
                </span>
                {active && <Check style={{ width: "14px", height: "14px", color: "var(--color-primary)", flexShrink: 0, marginTop: "1px" }} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
