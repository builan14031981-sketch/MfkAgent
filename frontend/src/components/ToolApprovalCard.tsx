"use client";

import { AlertTriangle, ShieldAlert, Check, X, Lock } from "lucide-react";
import type { ApprovalRequest } from "@/types/runtime";
import { useTranslation } from "@/hooks/useTranslation";

interface ToolApprovalCardProps {
  approval: ApprovalRequest;
  onApprove: (approvalId: string) => void;
  onDeny: (approvalId: string) => void;
}

/** Phase 1.5 工具审批卡片：高危工具调用需用户明确确认后才执行。
 *  - destructive：红色脉冲边框 + 盾牌图标，最高警示级别
 *  - write：黄色警告边框
 *  - 其他：信息色边框
 * 审批结果通过 useChatStream.resolveApproval 提交到 POST /api/chat/{id}/approve。
 * 点击后卡片置为"已批准"/"已拒绝"只读状态，等待 tool_result 到达后自动移除。 */
export function ToolApprovalCard({ approval, onApprove, onDeny }: ToolApprovalCardProps) {
  const { t } = useTranslation();
  const isDestructive = approval.risk_level === "destructive";
  const isWrite = approval.risk_level === "write";
  const isResolved = approval.resolvedAction != null;
  const isApproved = approval.resolvedAction === "approved";

  const accentColor = isDestructive
    ? "var(--color-error)"
    : isWrite
    ? "var(--color-warning)"
    : "var(--color-info)";

  const riskLabel = t(`chat.riskLevel.${approval.risk_level}`);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      gap: "8px",
      marginBottom: "8px",
      padding: "12px 14px",
      borderRadius: "var(--radius-md)",
      background: isDestructive
        ? "color-mix(in srgb, var(--color-error) 10%, var(--bg-level-3))"
        : isWrite
        ? "color-mix(in srgb, var(--color-warning) 8%, var(--bg-level-3))"
        : "color-mix(in srgb, var(--color-info) 6%, var(--bg-level-3))",
      border: "2px solid",
      borderColor: isResolved
        ? "var(--border-primary)"
        : isDestructive
        ? "var(--color-error)"
        : isWrite
        ? "color-mix(in srgb, var(--color-warning) 55%, var(--border-primary))"
        : "color-mix(in srgb, var(--color-info) 40%, var(--border-primary))",
      animation: isDestructive && !isResolved ? "approval-pulse 2s ease-in-out infinite" : "none",
      boxShadow: isDestructive && !isResolved
        ? "0 0 12px color-mix(in srgb, var(--color-error) 25%, transparent)"
        : "none",
      opacity: isResolved ? 0.7 : 1,
      transition: "opacity 0.3s ease, border-color 0.3s ease",
    }}>
      <style>{`
        @keyframes approval-pulse {
          0%, 100% { border-color: var(--color-error); box-shadow: 0 0 8px color-mix(in srgb, var(--color-error) 20%, transparent); }
          50% { border-color: color-mix(in srgb, var(--color-error) 50%, var(--border-primary)); box-shadow: 0 0 18px color-mix(in srgb, var(--color-error) 35%, transparent); }
        }
      `}</style>

      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        {isDestructive ? (
          <ShieldAlert style={{ width: "16px", height: "16px", color: "var(--color-error)", flexShrink: 0 }} />
        ) : (
          <AlertTriangle style={{ width: "14px", height: "14px", color: accentColor, flexShrink: 0 }} />
        )}
        <span style={{
          fontSize: "13px",
          fontWeight: 700,
          color: isDestructive ? "var(--color-error)" : "var(--text-level-1)",
          lineHeight: 1.25,
        }}>
          {isDestructive ? t("chat.approvalDestructiveTitle") : t("chat.approvalTitle")}
        </span>
        {/* 已审批状态徽标 / 风险等级徽标 */}
        {isResolved ? (
          <span style={{
            flexShrink: 0,
            marginLeft: "auto",
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            padding: "1px 8px",
            borderRadius: "var(--radius-xs)",
            fontSize: "10px",
            fontWeight: 700,
            lineHeight: "18px",
            color: "#fff",
            background: isApproved ? "var(--color-primary)" : "var(--color-error)",
            textTransform: "uppercase",
            letterSpacing: "0.5px",
          }}>
            <Lock style={{ width: "10px", height: "10px" }} />
            {isApproved ? t("chat.approvalApproved") : t("chat.approvalRejected")}
          </span>
        ) : (
          <span style={{
            flexShrink: 0,
            marginLeft: "auto",
            padding: "1px 8px",
            borderRadius: "var(--radius-xs)",
            fontSize: "10px",
            fontWeight: 700,
            lineHeight: "18px",
            fontFamily: "var(--font-geist-mono), var(--font-family)",
            color: isDestructive ? "#fff" : accentColor,
            background: isDestructive
              ? "var(--color-error)"
              : "color-mix(in srgb, var(--bg-level-2) 60%, transparent)",
            border: isDestructive ? "none" : "1px solid",
            borderColor: isDestructive ? "transparent" : "color-mix(in srgb, var(--border-primary) 80%, transparent)",
            textTransform: "uppercase",
            letterSpacing: "0.5px",
          }}>{riskLabel}</span>
        )}
      </div>

      {/* 工具名徽标：明确正在请求审批的是哪个工具 */}
      {approval.tool && (
        <span style={{
          alignSelf: "flex-start",
          padding: "1px 8px",
          borderRadius: "var(--radius-xs)",
          fontSize: "11px",
          fontWeight: 600,
          lineHeight: "18px",
          color: accentColor,
          background: "color-mix(in srgb, var(--bg-level-2) 60%, transparent)",
          border: "1px solid",
          borderColor: "color-mix(in srgb, var(--border-primary) 80%, transparent)",
        }}>{approval.tool}</span>
      )}

      <code style={{
        display: "block",
        padding: "8px 10px",
        fontSize: "12px",
        lineHeight: 1.5,
        color: "var(--text-level-1)",
        fontFamily: "var(--font-geist-mono), var(--font-family)",
        background: "var(--bg-level-2)",
        borderRadius: "var(--radius-sm)",
        border: "1px solid var(--border-primary)",
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "pre-wrap",
        wordBreak: "break-all",
        userSelect: "all",
      }}>{approval.command}</code>

      {approval.risk_reason && (
        <p style={{
          margin: 0,
          fontSize: "12px",
          lineHeight: 1.5,
          color: isDestructive ? "var(--color-error)" : "var(--text-level-3)",
          fontWeight: isDestructive ? 500 : 400,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}>{approval.risk_reason}</p>
      )}

      {/* 审批按钮区域：已审批时显示只读状态，否则显示批准/拒绝按钮 */}
      {isResolved ? (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          marginTop: "2px",
          padding: "7px 0",
          fontSize: "12px",
          fontWeight: 500,
          color: isApproved ? "var(--color-primary)" : "var(--color-error)",
        }}>
          {isApproved ? (
            <Check style={{ width: "13px", height: "13px" }} />
          ) : (
            <X style={{ width: "13px", height: "13px" }} />
          )}
          {isApproved ? t("chat.approvalApproved") : t("chat.approvalRejected")}
        </div>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "2px" }}>
          <button
            onClick={() => onApprove(approval.approval_id)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "7px 18px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: isDestructive ? "var(--color-error)" : "var(--color-primary)",
              color: "white",
              cursor: "pointer",
              fontSize: "12px",
              fontWeight: 600,
              transition: "background 0.2s ease, transform 0.1s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = isDestructive
                ? "color-mix(in srgb, var(--color-error) 85%, black)"
                : "var(--color-primary-hover)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = isDestructive ? "var(--color-error)" : "var(--color-primary)";
            }}
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
              padding: "7px 18px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-2)",
              color: "var(--text-level-2)",
              cursor: "pointer",
              fontSize: "12px",
              fontWeight: 500,
              transition: "background 0.2s ease, border-color 0.2s ease, color 0.2s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "color-mix(in srgb, var(--color-error) 10%, var(--bg-level-2))";
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
      )}
    </div>
  );
}
