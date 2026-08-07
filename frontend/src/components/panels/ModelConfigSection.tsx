"use client";

import { useState } from "react";
import { Plus, Trash2, Pencil, KeyRound, Globe, ExternalLink } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import {
  useModelConfig,
  CustomModel,
  CustomModelPayload,
} from "@/hooks/useModelConfig";

interface FormState {
  model_id: string;
  name: string;
  provider: string;
  model_name: string;
  api_base: string;
  api_key: string;
  max_tokens: string;
  temperature: string;
}

const emptyForm: FormState = {
  model_id: "",
  name: "",
  provider: "openai",
  model_name: "",
  api_base: "",
  api_key: "",
  max_tokens: "4096",
  temperature: "0.7",
};

export function ModelConfigSection() {
  const { t } = useTranslation();
  const {
    configs,
    customModels,
    loading,
    saveProviderKey,
    createCustomModel,
    updateCustomModel,
    deleteCustomModel,
  } = useModelConfig();

  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [keyInput, setKeyInput] = useState("");
  const [baseInput, setBaseInput] = useState("");
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [savedProvider, setSavedProvider] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingCustom, setEditingCustom] = useState<CustomModel | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [busy, setBusy] = useState(false);

  if (loading) {
    return (
      <p style={{ color: "var(--text-level-3)", fontSize: "13px" }}>
        {t("common.loading")}
      </p>
    );
  }

  const flashSaved = (id: string) => {
    setSavedProvider(id);
    setTimeout(() => setSavedProvider(null), 2000);
  };

  const openProvider = (pId: string, apiBase: string, override: boolean) => {
    setEditingProvider(pId);
    setKeyInput("");
    setBaseInput(override ? apiBase : "");
  };

  const handleSaveProvider = async (pId: string) => {
    setSavingProvider(pId);
    try {
      await saveProviderKey(pId, keyInput || undefined, baseInput);
      flashSaved(pId);
      setEditingProvider(null);
    } catch (err) {
      console.error("Failed to save provider key:", err);
    } finally {
      setSavingProvider(null);
    }
  };

  const handleClearKey = async (pId: string) => {
    setSavingProvider(pId);
    try {
      await saveProviderKey(pId, "");
      flashSaved(pId);
      setKeyInput("");
    } catch (err) {
      console.error("Failed to clear key:", err);
    } finally {
      setSavingProvider(null);
    }
  };

  const openCreateForm = () => {
    setEditingCustom(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  const openEditForm = (cm: CustomModel) => {
    setEditingCustom(cm);
    setForm({
      model_id: cm.model_id,
      name: cm.name,
      provider: cm.provider,
      model_name: cm.model_name,
      api_base: cm.api_base,
      api_key: "",
      max_tokens: String(cm.max_tokens),
      temperature: String(cm.temperature),
    });
    setFormOpen(true);
  };

  const handleSaveCustom = async () => {
    setBusy(true);
    try {
      const payload: CustomModelPayload = {
        model_id: form.model_id.trim(),
        name: form.name.trim(),
        provider: form.provider,
        model_name: form.model_name.trim(),
        api_base: form.api_base.trim(),
        api_key: form.api_key,
        max_tokens: Number(form.max_tokens) || 4096,
        temperature: Number(form.temperature) || 0.7,
        enabled: true,
      };
      if (editingCustom) {
        const patch: Partial<CustomModelPayload> = { ...payload } as Partial<CustomModelPayload>;
        if (!form.api_key) delete patch.api_key;
        delete patch.model_id;
        delete patch.enabled;
        await updateCustomModel(editingCustom.id, patch);
      } else {
        await createCustomModel(payload);
      }
      setFormOpen(false);
    } catch (err) {
      console.error("Failed to save custom model:", err);
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteCustom = async (cm: CustomModel) => {
    if (!confirm(t("settings.model.custom.confirmDelete"))) return;
    setBusy(true);
    try {
      await deleteCustomModel(cm.id);
    } catch (err) {
      console.error("Failed to delete custom model:", err);
    } finally {
      setBusy(false);
    }
  };

  const handleToggleCustom = async (cm: CustomModel) => {
    try {
      await updateCustomModel(cm.id, { enabled: !cm.enabled });
    } catch (err) {
      console.error("Failed to toggle custom model:", err);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
      {/* 模型提供商 */}
      <div>
        <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
          {t("settings.model.providers.title")}
        </h3>
        <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 12px 0" }}>
          {t("settings.model.providers.desc")}
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {configs.map((p) => (
            <div
              key={p.id}
              style={{
                padding: "12px 14px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-2)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)" }}>
                  {p.name}
                </span>
                {p.free && (
                  <span style={{
                    fontSize: "11px",
                    padding: "1px 8px",
                    borderRadius: "999px",
                    background: "var(--color-success-lighter, rgba(16,185,129,0.12))",
                    color: "var(--color-success)",
                  }}>
                    {t("settings.model.providers.free")}
                  </span>
                )}
                {p.website && (
                  <a
                    href={p.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={p.website}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "2px",
                      fontSize: "11px",
                      color: "var(--color-primary)",
                      textDecoration: "none",
                      cursor: "pointer",
                    }}
                  >
                    <ExternalLink style={{ width: "12px", height: "12px" }} />
                    官网
                  </a>
                )}
                <span style={{
                  fontSize: "11px",
                  padding: "1px 8px",
                  borderRadius: "999px",
                  background: p.has_key
                    ? "rgba(16,185,129,0.12)"
                    : "rgba(107,114,128,0.12)",
                  color: p.has_key ? "var(--color-success)" : "var(--text-level-3)",
                }}>
                  {p.has_key
                    ? t("settings.model.providers.configured")
                    : t("settings.model.providers.notConfigured")}
                </span>
                <span style={{ marginLeft: "auto", fontSize: "12px", color: "var(--text-level-4)", fontFamily: "monospace" }}>
                  {p.api_key_masked || "-"}
                </span>
              </div>
              {p.description && (
                <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "6px 0 0 0" }}>
                  {p.description}
                </p>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "8px" }}>
                <button
                  onClick={() => editingProvider === p.id ? setEditingProvider(null) : openProvider(p.id, p.api_base, p.api_base_override)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-primary)",
                    background: "transparent",
                    cursor: "pointer",
                    fontSize: "12px",
                    color: "var(--text-level-2)",
                  }}
                >
                  {t(editingProvider === p.id ? "common.cancel" : "settings.model.providers.configure")}
                </button>
                {p.has_key && (
                  <button
                    onClick={() => handleClearKey(p.id)}
                    disabled={savingProvider === p.id}
                    style={{
                      padding: "4px 10px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid transparent",
                      background: "transparent",
                      cursor: "pointer",
                      fontSize: "12px",
                      color: "var(--color-danger, #ef4444)",
                      opacity: savingProvider === p.id ? 0.6 : 1,
                    }}
                  >
                    {t("settings.model.providers.clearKey")}
                  </button>
                )}
                {savedProvider === p.id && (
                  <span style={{ fontSize: "12px", color: "var(--color-success)" }}>
                    {t("common.saved")}
                  </span>
                )}
              </div>

              {editingProvider === p.id && (
                <div style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                  marginTop: "12px",
                  padding: "12px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--bg-level-1)",
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <label style={{ minWidth: "70px", fontSize: "12px", color: "var(--text-level-2)", display: "flex", alignItems: "center", gap: "4px" }}>
                      <KeyRound style={{ width: "12px", height: "12px" }} />
                      {t("settings.model.providers.keyLabel")}
                    </label>
                    <input
                      type="password"
                      value={keyInput}
                      onChange={(e) => setKeyInput(e.target.value)}
                      placeholder={p.api_key_masked || "sk-..."}
                      style={{
                        flex: 1,
                        padding: "6px 10px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-primary)",
                        background: "var(--bg-level-2)",
                        fontSize: "13px",
                        color: "var(--text-level-2)",
                        outline: "none",
                      }}
                    />
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <label style={{ minWidth: "70px", fontSize: "12px", color: "var(--text-level-2)", display: "flex", alignItems: "center", gap: "4px" }}>
                      <Globe style={{ width: "12px", height: "12px" }} />
                      {t("settings.model.providers.baseLabel")}
                    </label>
                    <input
                      type="text"
                      value={baseInput}
                      onChange={(e) => setBaseInput(e.target.value)}
                      placeholder={p.api_base}
                      style={{
                        flex: 1,
                        padding: "6px 10px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-primary)",
                        background: "var(--bg-level-2)",
                        fontSize: "13px",
                        color: "var(--text-level-2)",
                        outline: "none",
                      }}
                    />
                  </div>
                  <div style={{ display: "flex", justifyContent: "flex-end" }}>
                    <button
                      onClick={() => handleSaveProvider(p.id)}
                      disabled={savingProvider === p.id}
                      style={{
                        padding: "6px 16px",
                        borderRadius: "var(--radius-sm)",
                        border: "none",
                        background: "var(--color-primary)",
                        color: "#fff",
                        cursor: "pointer",
                        fontSize: "13px",
                        fontWeight: "500",
                        opacity: savingProvider === p.id ? 0.7 : 1,
                      }}
                    >
                      {savingProvider === p.id ? t("common.saving") : t("common.save")}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 自定义模型 */}
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
          <div>
            <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
              {t("settings.model.custom.title")}
            </h3>
            <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
              {t("settings.model.custom.desc")}
            </p>
          </div>
          <button
            onClick={openCreateForm}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 14px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "var(--color-primary)",
              color: "#fff",
              cursor: "pointer",
              fontSize: "13px",
              fontWeight: "500",
            }}
          >
            <Plus style={{ width: "14px", height: "14px" }} />
            {t("settings.model.custom.add")}
          </button>
        </div>

        {formOpen && (
          <div style={{
            padding: "14px",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-2)",
            marginBottom: "12px",
            display: "flex",
            flexDirection: "column",
            gap: "10px",
          }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <label style={{ fontSize: "12px", color: "var(--text-level-2)" }}>{t("settings.model.custom.name")}</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder={t("settings.model.custom.name")}
                  style={inputStyle}
                />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <label style={{ fontSize: "12px", color: "var(--text-level-2)" }}>{t("settings.model.custom.modelId")}</label>
                <input
                  value={form.model_id}
                  onChange={(e) => setForm({ ...form, model_id: e.target.value })}
                  placeholder="custom-model-id"
                  disabled={!!editingCustom}
                  style={{ ...inputStyle, opacity: editingCustom ? 0.6 : 1 }}
                />
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <label style={{ fontSize: "12px", color: "var(--text-level-2)" }}>{t("settings.model.custom.provider")}</label>
                <select
                  value={form.provider}
                  onChange={(e) => setForm({ ...form, provider: e.target.value })}
                  style={inputStyle}
                >
                  <option value="openai">OpenAI 兼容</option>
                  {configs.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <label style={{ fontSize: "12px", color: "var(--text-level-2)" }}>{t("settings.model.custom.modelName")}</label>
                <input
                  value={form.model_name}
                  onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                  placeholder="upstream-model-name"
                  style={inputStyle}
                />
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "12px", color: "var(--text-level-2)" }}>{t("settings.model.custom.apiBase")}</label>
              <input
                value={form.api_base}
                onChange={(e) => setForm({ ...form, api_base: e.target.value })}
                placeholder="https://..."
                style={inputStyle}
              />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "10px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <label style={{ fontSize: "12px", color: "var(--text-level-2)" }}>{t("settings.model.custom.apiKey")}</label>
                <input
                  type="password"
                  value={form.api_key}
                  onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                  placeholder="sk-..."
                  style={inputStyle}
                />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <label style={{ fontSize: "12px", color: "var(--text-level-2)" }}>{t("settings.model.custom.maxTokens")}</label>
                <input
                  value={form.max_tokens}
                  onChange={(e) => setForm({ ...form, max_tokens: e.target.value })}
                  style={inputStyle}
                />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <label style={{ fontSize: "12px", color: "var(--text-level-2)" }}>{t("settings.model.custom.temperature")}</label>
                <input
                  value={form.temperature}
                  onChange={(e) => setForm({ ...form, temperature: e.target.value })}
                  style={inputStyle}
                />
              </div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
              <button
                onClick={() => setFormOpen(false)}
                style={secondaryBtn}
              >
                {t("common.cancel")}
              </button>
              <button
                onClick={handleSaveCustom}
                disabled={busy}
                style={{
                  ...primaryBtn,
                  opacity: busy ? 0.7 : 1,
                }}
              >
                {t("common.save")}
              </button>
            </div>
          </div>
        )}

        {customModels.length === 0 && !formOpen ? (
          <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: 0 }}>
            {t("settings.model.custom.noCustom")}
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {customModels.map((cm) => (
              <div
                key={cm.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  padding: "10px 14px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-primary)",
                  background: "var(--bg-level-2)",
                  opacity: cm.enabled ? 1 : 0.55,
                }}
              >
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)" }}>
                      {cm.name}
                    </span>
                    <span style={{ fontSize: "11px", fontFamily: "monospace", color: "var(--text-level-4)" }}>
                      {cm.model_id}
                    </span>
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--text-level-3)", marginTop: "2px" }}>
                    {cm.provider} · {cm.model_name} · {cm.api_base}
                  </div>
                </div>
                <span style={{ fontSize: "11px", color: cm.has_key ? "var(--color-success)" : "var(--text-level-4)" }}>
                  {cm.has_key ? "Key ✓" : "no key"}
                </span>
                <button
                  onClick={() => handleToggleCustom(cm)}
                  style={iconBtn}
                  title={t("settings.model.custom.enabled")}
                >
                  {cm.enabled ? "ON" : "OFF"}
                </button>
                <button
                  onClick={() => openEditForm(cm)}
                  style={iconBtn}
                  title={t("settings.model.custom.edit")}
                >
                  <Pencil style={{ width: "14px", height: "14px" }} />
                </button>
                <button
                  onClick={() => handleDeleteCustom(cm)}
                  style={iconBtn}
                  title={t("settings.model.custom.delete")}
                >
                  <Trash2 style={{ width: "14px", height: "14px", color: "var(--color-danger, #ef4444)" }} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "7px 10px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-primary)",
  background: "var(--bg-level-2)",
  fontSize: "13px",
  color: "var(--text-level-2)",
  outline: "none",
  width: "100%",
  boxSizing: "border-box",
};

const primaryBtn: React.CSSProperties = {
  padding: "6px 16px",
  borderRadius: "var(--radius-sm)",
  border: "none",
  background: "var(--color-primary)",
  color: "#fff",
  cursor: "pointer",
  fontSize: "13px",
  fontWeight: "500",
};

const secondaryBtn: React.CSSProperties = {
  padding: "6px 16px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-primary)",
  background: "transparent",
  cursor: "pointer",
  fontSize: "13px",
  color: "var(--text-level-2)",
};

const iconBtn: React.CSSProperties = {
  padding: "5px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-primary)",
  background: "transparent",
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: "var(--text-level-2)",
  fontSize: "11px",
  minWidth: "30px",
};
