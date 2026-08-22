"use client";

import { useRef, useEffect } from "react";
import { Shield, ShieldAlert, ShieldCheck, Zap, Check, ChevronDown } from "lucide-react";
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

/** Phase 3 T3/T8 权限模式：safe = 安全模式 / standard = 标准模式 / autonomous = 自主模式（会话级，逐会话显式设置） */
export type PermissionMode = "safe" | "standard" | "autonomous";

interface PermissionSelectorProps {
  permissionMode: PermissionMode;
  onPermissionChange: (mode: PermissionMode) => void;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
}

/** 权限模式指示胶囊：显示当前会话安全模式，点击可切换（调用 updateChat 写入会话 permission_mode） */
export function PermissionSelector({ permissionMode, onPermissionChange, open, onToggle, onClose }: PermissionSelectorProps) {
  const { t } = useTranslation();
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  const options: { value: PermissionMode; label: string; icon: React.ReactNode; desc: string }[] = [
    {
      value: "safe",
      label: t("settings.security.permission.safe"),
      icon: <ShieldAlert style={{ width: "13px", height: "13px", flexShrink: 0 }} />,
      desc: t("settings.security.permission.safeDesc"),
    },
    {
      value: "standard",
      label: t("settings.security.permission.standard"),
      icon: <Shield style={{ width: "13px", height: "13px", flexShrink: 0 }} />,
      desc: t("settings.security.permission.standardDesc"),
    },
    {
      value: "autonomous",
      label: t("settings.security.permission.autonomous"),
      icon: <Zap style={{ width: "13px", height: "13px", flexShrink: 0 }} />,
      desc: t("settings.security.permission.autonomousDesc"),
    },
  ];
  const current = options.find((o) => o.value === permissionMode) ?? options[1]; // 默认 standard

  const modeColor = permissionMode === "autonomous"
    ? "var(--color-error)"
    : permissionMode === "standard"
    ? "var(--color-warning, #f59e0b)"
    : "var(--color-info)";

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
          color: open ? pillActiveColor : modeColor,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = ghostPillHoverBackground;
          e.currentTarget.style.color = ghostPillHoverColor;
          e.currentTarget.style.boxShadow = ghostPillHoverShadow;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = open ? pillActiveBackground : "transparent";
          e.currentTarget.style.color = open ? pillActiveColor : modeColor;
          e.currentTarget.style.boxShadow = "none";
        }}
      >
        {current.icon}
        <span style={{ fontWeight: 400 }}>{current.label}</span>
        <ChevronDown style={{
          ...chevronStyle,
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform var(--transition-normal)",
        }} />
      </button>

      {open && (
        <div ref={popRef} style={{
          ...popoverStyle,
          minWidth: btnRef.current?.offsetWidth ?? undefined,
          width: btnRef.current?.offsetWidth ?? undefined,
        }}>
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
                  whiteSpace: "nowrap",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
              >
                {opt.icon}
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {opt.label}
                  {opt.value === "autonomous" && (
                    <span style={{ color: "var(--text-level-4)", fontWeight: 400, marginLeft: "4px" }}>{opt.desc}</span>
                  )}
                </span>
                {active && <Check style={{ width: "14px", height: "14px", color: "var(--color-primary)", flexShrink: 0 }} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
