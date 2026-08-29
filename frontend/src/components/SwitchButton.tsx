"use client";

interface SwitchButtonProps {
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}

/** 通用开关组件（设置项等场景复用） */
export function SwitchButton({ checked, disabled, onChange }: SwitchButtonProps) {
  return (
    <button
      onClick={() => onChange(!checked)}
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      style={{
        width: 34,
        height: 19,
        borderRadius: 999,
        border: "none",
        background: checked ? "var(--color-primary)" : "var(--bg-level-4)",
        cursor: disabled ? "not-allowed" : "pointer",
        position: "relative",
        transition: "background 0.2s ease",
        flexShrink: 0,
        opacity: disabled ? 0.6 : 1,
      }}
    >
      <span style={{
        position: "absolute",
        top: 2,
        left: 2,
        width: 15,
        height: 15,
        borderRadius: "50%",
        background: "#fff",
        boxShadow: "0 1px 2px rgba(0,0,0,0.2)",
        transform: checked ? "translateX(15px)" : "translateX(0)",
        transition: "transform 0.2s cubic-bezier(0.34, 1.3, 0.64, 1)",
      }} />
    </button>
  );
}
