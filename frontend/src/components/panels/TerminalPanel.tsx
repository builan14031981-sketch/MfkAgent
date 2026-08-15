"use client";

import { useCallback, useEffect, useRef } from "react";
import { RotateCw, ShieldAlert } from "lucide-react";
import { useDockStore } from "@/lib/dockStore";
import { useTerminal } from "@/hooks/useTerminal";
import { useTranslation } from "@/hooks/useTranslation";

interface TerminalPanelProps {
  cwd?: string | null;
}

/**
 * 终端内容区（浏览器式右侧面板的"终端"标签内容）。
 * - 无自身外壳/宽度/全屏：外壳与标签栏由 DockPanel 承载
 * - 后台保持运行：只要面板打开就保持 xterm + WS 连接（active=dockOpen），切到其它标签不销毁
 * - 仅当"终端"标签可见时执行 fitAndSync（隐藏时容器 display:none 尺寸为 0，避免向后端发 0 尺寸）
 */
export function TerminalPanel({ cwd }: TerminalPanelProps) {
  const { t } = useTranslation();
  const dockOpen = useDockStore((s) => s.isOpen);
  const terminalActive = useDockStore((s) => s.activeTab === "terminal");

  const containerRef = useRef<HTMLDivElement>(null);
  const { fitAndSync, approve, reject, clear, approval, status } = useTerminal({
    containerRef,
    cwd,
    active: dockOpen,
  });

  // 容器尺寸变化（拖拽调宽 / 全屏 / 初始挂载）→ 重算 xterm 并同步后端
  const doFit = useCallback(() => {
    if (!terminalActive) return;
    fitAndSync();
  }, [terminalActive, fitAndSync]);

  useEffect(() => {
    if (!dockOpen || !terminalActive) return;
    const timer = setTimeout(doFit, 80);
    const ro = new ResizeObserver(() => doFit());
    if (containerRef.current) ro.observe(containerRef.current);
    return () => {
      clearTimeout(timer);
      ro.disconnect();
    };
  }, [dockOpen, terminalActive, doFit]);

  // 清屏：直接调用 xterm clear（终端内操作，不经风险引擎）
  const handleClear = useCallback(() => {
    clear();
  }, [clear]);

  return (
    <>
      {/* 精简内容头：连接状态 + cwd + 清屏（标题/全屏/关闭已上移到标签栏） */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: "3px 8px",
          borderBottom: "1px solid var(--border-primary)",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: "10.5px",
            color: status.connected ? "var(--color-primary)" : "var(--text-level-4)",
          }}
        >
          {status.connected ? "●" : "○"}
        </span>
        {status.cwd && (
          <span
            style={{
              fontSize: "10.5px",
              color: "var(--text-level-4)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              maxWidth: 260,
            }}
            title={status.cwd}
          >
            {status.cwd}
          </span>
        )}
        <button
          onClick={handleClear}
          title={t("terminal.clear")}
          style={{ marginLeft: "auto", ...toolBtnStyle }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
        >
          <RotateCw style={{ width: 13, height: 13 }} />
        </button>
      </div>

      {/* 危险命令审批条 */}
      {approval && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "4px 10px",
            background: "color-mix(in srgb, var(--color-error) 12%, transparent)",
            borderBottom: "1px solid var(--border-primary)",
            flexShrink: 0,
          }}
        >
          <ShieldAlert style={{ width: "13px", height: "13px", color: "var(--color-error)", flexShrink: 0 }} />
          <span
            style={{
              fontSize: "11.5px",
              color: "var(--text-level-2)",
              fontFamily: "var(--font-mono, monospace)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {t("terminal.requireApproval")}: {approval.command}
          </span>
          <div style={{ marginLeft: "auto", display: "flex", gap: "6px", flexShrink: 0 }}>
            <button
              onClick={reject}
              style={{ ...approvalBtnStyle, background: "transparent", color: "var(--text-level-2)", border: "1px solid var(--border-primary)" }}
            >
              {t("common.cancel")}
            </button>
            <button
              onClick={approve}
              style={{ ...approvalBtnStyle, background: "var(--color-error)", color: "#fff" }}
            >
              {t("terminal.executeAnyway")}
            </button>
          </div>
        </div>
      )}

      {/* xterm 容器 */}
      <div ref={containerRef} style={{ flex: 1, minHeight: 0, padding: "4px 6px" }} />
    </>
  );
}

const toolBtnStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: 24,
  height: 22,
  borderRadius: "var(--radius-sm)",
  border: "none",
  background: "transparent",
  cursor: "pointer",
  color: "var(--text-level-3)",
  padding: 0,
  outline: "none",
  transition: "background 0.15s, color 0.15s",
};

const approvalBtnStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  height: 22,
  padding: "0 10px",
  borderRadius: "var(--radius-sm)",
  fontSize: "11px",
  fontWeight: 600,
  cursor: "pointer",
  border: "none",
  outline: "none",
};
