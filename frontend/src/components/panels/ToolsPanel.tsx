"use client";
/* eslint-disable react-hooks/set-state-in-effect */

import { useState, useEffect } from "react";
import { X, Zap, Terminal, Globe, FileText, Loader2 } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";
import { useTranslation } from "@/hooks/useTranslation";

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

interface ToolsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ToolsPanel({ isOpen, onClose }: ToolsPanelProps) {
  const { t } = useTranslation();
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTool, setSelectedTool] = useState<ToolDefinition | null>(null);
  const [toolParams, setToolParams] = useState<Record<string, string>>({});
  const [result, setResult] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);

  async function fetchTools() {
    try {
      setLoading(true);
      const data = await apiGet<{ definitions?: ToolDefinition[] }>("/api/tools/definitions");
      setTools(data.definitions ?? []);
    } catch (err) {
      console.error("Failed to fetch tools:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchTools();
    }
  }, [isOpen]);

  const handleExecute = async () => {
    if (!selectedTool) return;
    try {
      setExecuting(true);
      setResult(null);
      const data = await apiPost<{ success: boolean; output: string; error: string }>("/api/tools/call", {
        tool_name: selectedTool.name,
        arguments: toolParams,
      });
      if (data.success) {
        setResult(data.output);
      } else {
        setResult(`Error: ${data.error || "Unknown error"}`);
      }
    } catch (err) {
      setResult(`Error: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setExecuting(false);
    }
  };

  const handleParamChange = (key: string, value: string) => {
    setToolParams(prev => ({ ...prev, [key]: value }));
  };

  const getToolIcon = (name: string) => {
    switch (name) {
      case "web_search": return Globe;
      case "file_read": return FileText;
      case "code_exec": return Terminal;
      default: return Zap;
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        width: "400px",
        height: "100vh",
        background: "var(--bg-level-1)",
        borderLeft: "1px solid var(--border-primary)",
        boxShadow: "var(--shadow-lg)",
        zIndex: 1000,
        display: "flex",
        flexDirection: "column",
        animation: "slideIn 0.2s ease",
      }}
    >
      <style jsx>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>

      {/* Header */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "16px 20px",
        borderBottom: "1px solid var(--border-primary)",
      }}>
        <h3 style={{ fontSize: "16px", fontWeight: "600", margin: 0 }}>{t("tools.title")}</h3>
        <button
          onClick={onClose}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "32px",
            height: "32px",
            borderRadius: "var(--radius-md)",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            color: "var(--text-level-3)",
            transition: "all 0.6s ease",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
        >
          <X style={{ width: "18px", height: "18px" }} />
        </button>
      </div>

      {/* Tool List */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
        {loading ? (
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            height: "200px",
            color: "var(--text-level-3)",
          }}>
            <Loader2 style={{ width: "24px", height: "24px", animation: "spin 1s linear infinite" }} />
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {tools.map((tool) => (
              <button
                key={tool.name}
                onClick={() => {
                  setSelectedTool(tool);
                  setToolParams({});
                  setResult(null);
                }}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "12px",
                  padding: "12px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-primary)",
                  background: selectedTool?.name === tool.name ? "var(--bg-level-3)" : "var(--bg-level-2)",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "all 0.6s ease",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--bg-level-3)";
                  e.currentTarget.style.borderColor = "var(--color-primary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = selectedTool?.name === tool.name ? "var(--bg-level-3)" : "var(--bg-level-2)";
                  e.currentTarget.style.borderColor = "var(--border-primary)";
                }}
              >
                {(() => { const Icon = getToolIcon(tool.name); return <Icon style={{ width: "20px", height: "20px", color: "var(--color-primary)", flexShrink: 0, marginTop: "2px" }} />; })()}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: "0 0 4px 0" }}>
                    {tool.name}
                  </p>
                  <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: 0, lineHeight: 1.4 }}>
                    {tool.description}
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Tool Detail / Execution */}
      {selectedTool && (
        <div style={{
          borderTop: "1px solid var(--border-primary)",
          padding: "16px 20px",
          background: "var(--bg-level-2)",
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              {(() => { const Icon = getToolIcon(selectedTool.name); return <Icon style={{ width: "18px", height: "18px", color: "var(--color-primary)" }} />; })()}
              <span style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)" }}>
                {selectedTool.name}
              </span>
            </div>
            <button
              onClick={() => { setSelectedTool(null); setResult(null); }}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "28px",
                height: "28px",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: "transparent",
                cursor: "pointer",
                color: "var(--text-level-4)",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
            >
              <X style={{ width: "14px", height: "14px" }} />
            </button>
          </div>

          {/* Parameters */}
          <div style={{ marginBottom: "16px" }}>
            <p style={{ fontSize: "12px", fontWeight: "500", color: "var(--text-level-3)", margin: "0 0 8px 0" }}>
              {t("tools.parameters")}
            </p>
            {Object.entries(selectedTool.parameters).map(([key, schema]: [string, unknown]) => {
              const s = schema as { type: string; description?: string; required?: boolean };
              return (
                <div key={key} style={{ marginBottom: "12px" }}>
                  <label style={{ display: "block", fontSize: "12px", color: "var(--text-level-2)", marginBottom: "4px" }}>
                    {key} {s.required ? <span style={{ color: "var(--color-error)" }}>*</span> : null}
                  </label>
                  <input
                    type={s.type === "number" ? "number" : "text"}
                    value={toolParams[key] || ""}
                    onChange={(e) => handleParamChange(key, e.target.value)}
                    placeholder={s.description || ""}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border-primary)",
                      background: "var(--bg-level-1)",
                      fontSize: "13px",
                      color: "var(--text-level-2)",
                      outline: "none",
                    }}
                  />
                </div>
              );
            })}
          </div>

          {/* Execute Button */}
          <button
            onClick={handleExecute}
            disabled={executing}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              padding: "10px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: executing ? "var(--bg-level-3)" : "var(--color-primary)",
              cursor: executing ? "not-allowed" : "pointer",
              color: "white",
              fontSize: "13px",
              fontWeight: "500",
              transition: "all 0.6s ease",
            }}
            onMouseEnter={(e) => { if (!executing) e.currentTarget.style.background = "var(--color-primary-hover)"; }}
            onMouseLeave={(e) => { if (!executing) e.currentTarget.style.background = "var(--color-primary)"; }}
          >
            {executing ? <Loader2 style={{ width: "16px", height: "16px", animation: "spin 1s linear infinite" }} /> : null}
            {t(executing ? "tools.executing" : "tools.execute")}
          </button>

          {/* Result */}
          {result && (
            <div style={{ marginTop: "16px" }}>
              <p style={{ fontSize: "12px", fontWeight: "500", color: "var(--text-level-3)", margin: "0 0 8px 0" }}>
                {t("tools.result")}
              </p>
              <pre style={{
                padding: "12px",
                borderRadius: "var(--radius-sm)",
                background: "var(--bg-level-1)",
                border: "1px solid var(--border-primary)",
                fontSize: "11px",
                color: "var(--text-level-2)",
                overflow: "auto",
                maxHeight: "200px",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}>
                {result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}