"use client";

import { useState } from "react";
import { Plus, Trash2, Settings2, Check, X, Puzzle } from "lucide-react";
import { usePlugins, PluginInfo } from "@/hooks/usePlugins";
import { useTranslation } from "@/hooks/useTranslation";

/** 插件管理面板：列表 + 激活/停用 + 删除 + 新建 + 配置编辑（DB 持久化） */
export function PluginPanel() {
  const { t } = useTranslation();
  const { plugins, loading, error, createPlugin, setPluginActive, updatePluginConfig, deletePlugin } = usePlugins();

  const [creating, setCreating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [form, setForm] = useState({ name: "", version: "1.0.0", description: "", author: "", config: "" });
  const [configOpenId, setConfigOpenId] = useState<string | null>(null);
  const [configDraft, setConfigDraft] = useState("");
  const [configError, setConfigError] = useState<string | null>(null);

  const statusLabel = (status: PluginInfo["status"]): string => {
    switch (status) {
      case "active": return t("settings.plugins.statusActive");
      case "inactive": return t("settings.plugins.statusInactive");
      case "installed": return t("settings.plugins.statusInstalled");
      case "error": return t("settings.plugins.statusError");
    }
  };

  const statusColor = (status: PluginInfo["status"]): string => {
    switch (status) {
      case "active": return "var(--color-success)";
      case "inactive": return "var(--text-level-4)";
      case "installed": return "var(--color-primary)";
      case "error": return "var(--color-error)";
    }
  };

  const handleCreate = async () => {
    const name = form.name.trim();
    if (!name || isSubmitting) return;
    let config: Record<string, unknown> = {};
    const raw = form.config.trim();
    if (raw) {
      try {
        config = JSON.parse(raw);
      } catch {
        setConfigError(t("settings.plugins.configInvalid"));
        return;
      }
    }
    setIsSubmitting(true);
    setConfigError(null);
    try {
      await createPlugin({
        name,
        version: form.version.trim() || "1.0.0",
        description: form.description.trim(),
        author: form.author.trim(),
        config,
      });
      setForm({ name: "", version: "1.0.0", description: "", author: "", config: "" });
      setCreating(false);
    } catch (err) {
      console.error("Failed to create plugin:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (plugin: PluginInfo) => {
    if (!window.confirm(t("settings.plugins.deleteConfirm"))) return;
    try {
      await deletePlugin(plugin.pluginId);
    } catch (err) {
      console.error("Failed to delete plugin:", err);
    }
  };

  const openConfig = (plugin: PluginInfo) => {
    if (configOpenId === plugin.pluginId) {
      setConfigOpenId(null);
      return;
    }
    setConfigOpenId(plugin.pluginId);
    setConfigDraft(JSON.stringify(plugin.config || {}, null, 2));
    setConfigError(null);
  };

  const saveConfig = async (pluginId: string) => {
    let config: Record<string, unknown> = {};
    const raw = configDraft.trim();
    if (raw) {
      try {
        config = JSON.parse(raw);
      } catch {
        setConfigError(t("settings.plugins.configInvalid"));
        return;
      }
    }
    try {
      await updatePluginConfig(pluginId, config);
      setConfigOpenId(null);
      setConfigError(null);
    } catch (err) {
      console.error("Failed to update config:", err);
    }
  };

  return (
    <div>
      {/* 标题 + 新建入口 */}
      <div style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: "12px",
      }}>
        <div>
          <h3 style={{
            fontSize: "14px",
            fontWeight: "500",
            color: "var(--text-level-1)",
            margin: 0,
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}>
            <Puzzle style={{ width: "16px", height: "16px" }} />
            {t("settings.plugins.title")}
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "4px 0 0 0" }}>
            {t("settings.plugins.desc")}
          </p>
        </div>
        <button
          onClick={() => setCreating((v) => !v)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "8px 14px",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-primary)",
            background: "var(--color-primary-lighter)",
            cursor: "pointer",
            fontSize: "13px",
            fontWeight: "500",
            color: "var(--color-primary)",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
        >
          {creating ? <X style={{ width: "14px", height: "14px" }} /> : <Plus style={{ width: "14px", height: "14px" }} />}
          {creating ? t("settings.plugins.cancelCreate") : t("settings.plugins.create")}
        </button>
      </div>

      {/* 新建表单 */}
      {creating && (
        <div style={{
          marginTop: "12px",
          padding: "12px",
          borderRadius: "var(--radius-md)",
          background: "var(--bg-level-2)",
          border: "1px solid var(--border-primary)",
        }}>
          <div style={{ display: "flex", gap: "12px", marginBottom: "10px", flexWrap: "wrap" }}>
            <label style={{ flex: 1, minWidth: "160px", fontSize: "12px", color: "var(--text-level-3)" }}>
              {t("settings.plugins.name")} *
              <input
                value={form.name}
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                placeholder="my_plugin"
                style={inputStyle}
              />
            </label>
            <label style={{ width: "110px", fontSize: "12px", color: "var(--text-level-3)" }}>
              {t("settings.plugins.version")}
              <input
                value={form.version}
                onChange={(e) => setForm((p) => ({ ...p, version: e.target.value }))}
                style={inputStyle}
              />
            </label>
          </div>
          <div style={{ display: "flex", gap: "12px", marginBottom: "10px", flexWrap: "wrap" }}>
            <label style={{ flex: 1, minWidth: "160px", fontSize: "12px", color: "var(--text-level-3)" }}>
              {t("settings.plugins.description")}
              <input
                value={form.description}
                onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                style={inputStyle}
              />
            </label>
            <label style={{ width: "140px", fontSize: "12px", color: "var(--text-level-3)" }}>
              {t("settings.plugins.author")}
              <input
                value={form.author}
                onChange={(e) => setForm((p) => ({ ...p, author: e.target.value }))}
                style={inputStyle}
              />
            </label>
          </div>
          <label style={{ display: "block", fontSize: "12px", color: "var(--text-level-3)", marginBottom: "4px" }}>
            {t("settings.plugins.config")}
          </label>
          <textarea
            value={form.config}
            onChange={(e) => setForm((p) => ({ ...p, config: e.target.value }))}
            placeholder='{ "key": "value" }'
            rows={3}
            style={{ ...inputStyle, width: "100%", resize: "vertical", fontFamily: "monospace", fontSize: "12px" }}
          />
          {configError && <p style={{ fontSize: "12px", color: "var(--color-error)", margin: "6px 0 0 0" }}>{configError}</p>}
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "10px" }}>
            <button
              onClick={handleCreate}
              disabled={isSubmitting || !form.name.trim()}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "7px 16px",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: "var(--color-primary)",
                color: "#fff",
                cursor: isSubmitting || !form.name.trim() ? "not-allowed" : "pointer",
                fontSize: "13px",
                fontWeight: "500",
                opacity: isSubmitting || !form.name.trim() ? 0.6 : 1,
              }}
            >
              <Check style={{ width: "14px", height: "14px" }} />
              {isSubmitting ? t("common.saving") : t("common.save")}
            </button>
          </div>
        </div>
      )}

      {/* 列表 */}
      {loading ? (
        <p style={{ fontSize: "13px", color: "var(--text-level-3)", marginTop: "16px" }}>{t("common.loading")}</p>
      ) : error ? (
        <p style={{ fontSize: "13px", color: "var(--color-error)", marginTop: "16px" }}>{error}</p>
      ) : plugins.length === 0 ? (
        <p style={{ fontSize: "13px", color: "var(--text-level-3)", marginTop: "16px" }}>{t("settings.plugins.empty")}</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "16px" }}>
          {plugins.map((plugin) => (
            <div
              key={plugin.pluginId}
              style={{
                padding: "12px",
                borderRadius: "var(--radius-md)",
                background: "var(--bg-level-2)",
                border: "1px solid var(--border-primary)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                    <span style={{ fontSize: "13px", fontWeight: "600", color: "var(--text-level-1)" }}>{plugin.name}</span>
                    <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>v{plugin.version}</span>
                    <span style={{
                      fontSize: "11px",
                      padding: "1px 8px",
                      borderRadius: "var(--radius-full)",
                      background: statusColor(plugin.status),
                      color: "#fff",
                      lineHeight: "16px",
                    }}>
                      {statusLabel(plugin.status)}
                    </span>
                    {plugin.author && (
                      <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>{plugin.author}</span>
                    )}
                  </div>
                  {plugin.description && (
                    <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "4px 0 0 0" }}>{plugin.description}</p>
                  )}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
                  {/* 激活/停用开关 */}
                  <button
                    onClick={() => setPluginActive(plugin.pluginId, plugin.status !== "active")}
                    role="switch"
                    aria-checked={plugin.status === "active"}
                    style={{
                      width: 34,
                      height: 19,
                      borderRadius: 999,
                      border: "none",
                      background: plugin.status === "active" ? "var(--color-success)" : "var(--bg-level-4)",
                      cursor: "pointer",
                      position: "relative",
                      transition: "background 0.2s ease",
                      flexShrink: 0,
                    }}
                  >
                    <span style={{
                      position: "absolute",
                      top: 2,
                      left: plugin.status === "active" ? 17 : 2,
                      width: 15,
                      height: 15,
                      borderRadius: "50%",
                      background: "#fff",
                      transition: "left 0.2s ease",
                    }} />
                  </button>
                  <button
                    onClick={() => openConfig(plugin)}
                    title={t("settings.plugins.config")}
                    style={iconBtnStyle}
                  >
                    <Settings2 style={{ width: "14px", height: "14px" }} />
                  </button>
                  <button
                    onClick={() => handleDelete(plugin)}
                    title={t("settings.plugins.delete")}
                    style={iconBtnStyle}
                  >
                    <Trash2 style={{ width: "14px", height: "14px" }} />
                  </button>
                </div>
              </div>

              {/* 配置编辑 */}
              {configOpenId === plugin.pluginId && (
                <div style={{ marginTop: "10px", borderTop: "1px solid var(--border-secondary)", paddingTop: "10px" }}>
                  <label style={{ display: "block", fontSize: "12px", color: "var(--text-level-3)", marginBottom: "4px" }}>
                    {t("settings.plugins.config")} (JSON)
                  </label>
                  <textarea
                    value={configDraft}
                    onChange={(e) => setConfigDraft(e.target.value)}
                    rows={4}
                    style={{ ...inputStyle, width: "100%", resize: "vertical", fontFamily: "monospace", fontSize: "12px" }}
                  />
                  {configError && <p style={{ fontSize: "12px", color: "var(--color-error)", margin: "6px 0 0 0" }}>{configError}</p>}
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "8px" }}>
                    <button
                      onClick={() => setConfigOpenId(null)}
                      style={{ ...iconBtnStyle, padding: "5px 12px", borderRadius: "var(--radius-sm)" }}
                    >
                      {t("common.cancel")}
                    </button>
                    <button
                      onClick={() => saveConfig(plugin.pluginId)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "5px",
                        padding: "5px 12px",
                        borderRadius: "var(--radius-sm)",
                        border: "none",
                        background: "var(--color-primary)",
                        color: "#fff",
                        cursor: "pointer",
                        fontSize: "12px",
                        fontWeight: "500",
                      }}
                    >
                      <Check style={{ width: "13px", height: "13px" }} />
                      {t("common.save")}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "6px 10px",
  marginTop: "4px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-primary)",
  background: "var(--bg-level-1)",
  fontSize: "13px",
  color: "var(--text-level-2)",
  outline: "none",
};

const iconBtnStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: "28px",
  height: "28px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-primary)",
  background: "transparent",
  cursor: "pointer",
  color: "var(--text-level-3)",
  flexShrink: 0,
};
