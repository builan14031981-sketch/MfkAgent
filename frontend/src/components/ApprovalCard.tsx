"use client";

import { AlertTriangle, Check, X } from "lucide-react";
import type { ApprovalRequest } from "@/types/runtime";
import { useTranslation } from "@/hooks/useTranslation";

interface ApprovalCardProps {
  approval: ApprovalRequest;
  onApprove: (approvalId: string) => void;
  onDeny: (approvalId: string) => void;
}

/** 待审批命令卡片（Phase B-1）：危险命令需用户确认后才执行 */
export function ApprovalCard({ approval, onApprove, onDeny }: ApprovalCardProps) {
  const { t } = useTranslation();

  const color =
    approval.risk_level === "destructive"
      ? "var(--color-error)"
      : approval.risk_level === "write"
      ? "var(--color-warning)"
      : "var(--color-info)";

  const riskLabel = t(`chat.riskLevel.${approval.risk_level}`);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      gap: "8px",
      marginBottom: "8px",
      padding: "10px 12px",
      borderRadius: "var(--radius-md)",
      background: "color-mix(in srgb, var(--color-warning) 6%, var(--bg-level-3))",
      border: "1px solid",
      borderColor: "color-mix(in srgb, var(--color-warning) 45%, var(--border-primary))",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <AlertTriangle style={{ width: "14px", height: "14px", color, flexShrink: 0 }} />
        <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-level-1)", lineHeight: 1.25 }}>
          {t("chat.approvalTitle")}
        </span>
        <span style={{
          flexShrink: 0,
          marginLeft: "auto",
          padding: "0 6px",
          borderRadius: "var(--radius-xs)",
          fontSize: "10px",
          fontWeight: 600,
          lineHeight: "16px",
          fontFamily: "var(--font-geist-mono), var(--font-family)",
          color,
          background: "color-mix(in srgb, var(--bg-level-2) 60%, transparent)",
          border: "1px solid",
          borderColor: "color-mix(in srgb, var(--border-primary) 80%, transparent)",
        }}>{riskLabel}</span>
      </div>

      <code style={{
        fontSize: "12px",
        color: "var(--text-level-1)",
        fontFamily: "var(--font-geist-mono), var(--font-family)",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
        userSelect: "all",
      }}>{approval.command}</code>

      {approval.risk_reason && (
        <p style={{
          margin: 0,
          fontSize: "12px",
          lineHeight: 1.5,
          color: "var(--text-level-3)",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}>{approval.risk_reason}</p>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "2px" }}>
        <button
          onClick={() => onApprove(approval.approval_id)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "6px 16px",
            borderRadius: "var(--radius-md)",
            border: "none",
            background: "var(--color-primary)",
            color: "white",
            cursor: "pointer",
            fontSize: "12px",
            fontWeight: 500,
            transition: "background 0.2s ease",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-primary-hover)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "var(--color-primary)")}
        >
          <Check style={{ width: "13px", height: "13px" }} />
          {t("chat.approvalApprove")}
        </button>
        <button
          onClick={() => onDeny(approval.approval_id)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "6px 16px",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-2)",
            color: "var(--text-level-2)",
            cursor: "pointer",
            fontSize: "12px",
            fontWeight: 500,
            transition: "background 0.2s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "color-mix(in srgb, var(--color-error) 8%, var(--bg-level-2))";
            e.currentTarget.style.borderColor = "var(--color-error)";
            e.currentTarget.style.color = "var(--color-error)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "var(--bg-level-2)";
            e.currentTarget.style.borderColor = "var(--border-primary)";
            e.currentTarget.style.color = "var(--text-level-2)";
          }}
        >
          <X style={{ width: "13px", height: "13px" }} />
          {t("chat.approvalDeny")}
        </button>
      </div>
    </div>
  );
}
