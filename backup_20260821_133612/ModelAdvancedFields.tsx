"use client";

/**
 * ModelAdvancedFields —— 模型高级深水区参数（归属 AdvancedSettingsView）
 * 含：备用识图 + Provider Base URL 覆盖 + 自定义模型表单。
 * 从 ModelConfigSection.tsx 拆分，逻辑与行为零变化。
 */
import { useEffect, useState } from "react";
import { ChevronRight, Globe, Loader2, Pencil, Plus, Trash2, Zap } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { useProviderConfig, type CustomModel, type CustomModelPayload, type RemoteModelInfo } from "@/hooks/useProviderConfig";
import { ApiKeyInput } from "@/components/ApiKeyInput";
import { RemoteModelPicker } from "@/components/RemoteModelPicker";
import { SwitchButton } from "@/components/SwitchButton";
import { VisionConfigSection } from "../VisionConfigSection";
import { TattooImageConfigSection } from "../TattooImageConfigSection";
import { iconBtn, inputStyle, primaryBtn, secondaryBtn } from "./constants";
import { useSettingsToast, errorMessage } from "@/lib/toastStore";
interface FormState {
  model_id: string;
  name: string;
  provider: string;
  model_name: string;
  api_base: string;
  api_key: string;
  max_tokens: string;
  temperature: string;
  supports_vision: boolean;
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
  supports_vision: false,
};

/**
 * ProviderBaseUrlOverride —— Provider Base URL 覆盖独立配置（高级区专用）
 *
 * 字段级边界契约：
 * - 每个 Provider 一个 Base URL 输入框 + 保存/清除按钮
 * - 独立于 ProviderCard 的 editing 表单，state 自管
 * - 保存：saveProviderKey(pId, undefined, baseInput) —— 只改 base，不碰 key
 * - 清除：saveProviderKey(pId, undefined, "") —— 清除 override 恢复默认
 */
function ProviderBaseUrlOverride() {
  const { t } = useTranslation();
  const { configs, saveProviderKey } = useProviderConfig();
  const { showToast } = useSettingsToast();

  // 默认折叠（99% 用户用不到）；2026-08-11：折叠态持久化（此前纯内存，刷新即丢）
  const [collapsed, setCollapsed] = useState(true);
  useEffect(() => {
    try {
      // 未写过（null）保持默认折叠；"0" = 用户展开过
      setCollapsed(localStorage.getItem("mfk_baseurl_collapsed") !== "0");
    } catch { /* localStorage 不可用时保持折叠 */ }
  }, []);
  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("mfk_baseurl_collapsed", next ? "1" : "0"); } catch { /* noop */ }
      return next;
    });
  };

  // 每个 provider 的 baseInput 草稿（id -> value）
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const getDraft = (p: { id: string; api_base: string; api_base_override: boolean }) =>
    drafts[p.id] !== undefined ? drafts[p.id] : (p.api_base_override ? p.api_base : "");

  const handleSave = async (pId: string) => {
    const val = (drafts[pId] ?? "").trim();
    setSaving(pId);
    try {
      // 只保存 base，不碰 key（apiKey 传 undefined）
      await saveProviderKey(pId, undefined, val || "");
      setSaved(pId);
      setTimeout(() => setSaved(null), 2000);
    } catch (err) {
      console.error("Failed to save base url override:", err);
      showToast(errorMessage(err) || "保存失败", "error");
    } finally {
      setSaving(null);
    }
  };

  const handleClear = async (pId: string) => {
    setSaving(pId);
    try {
      await saveProviderKey(pId, undefined, "");
      setDrafts((d) => ({ ...d, [pId]: "" }));
      setSaved(pId);
      setTimeout(() => setSaved(null), 2000);
    } catch (err) {
      console.error("Failed to clear base url override:", err);
      showToast(errorMessage(err) || "清除失败", "error");
    } finally {
      setSaving(null);
    }
  };

  return (
    <div>
      {/* 可折叠标题 */}
      <div
        onClick={toggleCollapsed}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          cursor: "pointer",
          padding: "4px 0",
          userSelect: "none",
        }}
      >
        <ChevronRight
          style={{
            width: "14px",
            height: "14px",
            color: "var(--text-level-3)",
            transition: "transform 0.2s",
            transform: collapsed ? "rotate(0deg)" : "rotate(90deg)",
          }}
        />
        <Globe style={{ width: "14px", height: "14px", color: "var(--text-level-2)" }} />
        <h3 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-2)", margin: 0 }}>
          {t("settings.model.providers.baseUrlOverrideTitle")}
        </h3>
        <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>
          {collapsed ? t("settings.model.providers.baseUrlCollapsed") : t("settings.model.providers.baseUrlExpanded")}
        </span>
      </div>

      {/* 折叠内容 */}
      {!collapsed && (
        <>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 12px 20px" }}>
            {t("settings.model.providers.baseUrlOverrideDesc")}
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {configs.map((p) => (
          <div
            key={p.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 12px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-2)",
            }}
          >
            <div style={{ minWidth: "80px", flexShrink: 0 }}>
              <div style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)" }}>
                {p.name}
              </div>
              {p.api_base_override ? (
                <span style={{ fontSize: "10px", color: "var(--color-primary)" }}>
                  {t("settings.model.providers.overrideActive")}
                </span>
              ) : (
                <span style={{ fontSize: "10px", color: "var(--text-level-4)" }}>
                  {t("settings.model.providers.defaultEndpoint")}
                </span>
              )}
            </div>
            <input
              type="text"
              value={getDraft(p)}
              onChange={(e) => setDrafts((d) => ({ ...d, [p.id]: e.target.value }))}
              placeholder={p.api_base}
              style={{
                flex: 1,
                minWidth: 0,
                padding: "6px 10px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-1)",
                fontSize: "12px",
                color: "var(--text-level-2)",
                outline: "none",
                fontFamily: "monospace",
              }}
            />
            <button
              type="button"
              onClick={() => handleSave(p.id)}
              disabled={saving === p.id}
              style={{
                padding: "5px 12px",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: "var(--color-primary)",
                color: "#fff",
                cursor: saving === p.id ? "not-allowed" : "pointer",
                fontSize: "12px",
                fontWeight: "500",
                opacity: saving === p.id ? 0.7 : 1,
                whiteSpace: "nowrap",
              }}
            >
              {t("common.save")}
            </button>
            {p.api_base_override && (
              <button
                type="button"
                onClick={() => handleClear(p.id)}
                disabled={saving === p.id}
                style={{
                  padding: "5px 10px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid transparent",
                  background: "transparent",
                  cursor: "pointer",
                  fontSize: "12px",
                  color: "var(--color-danger, #ef4444)",
                  opacity: saving === p.id ? 0.5 : 1,
                  whiteSpace: "nowrap",
                }}
              >
                {t("settings.model.providers.resetBase")}
              </button>
            )}
            {saved === p.id && (
              <span style={{ fontSize: "11px", color: "var(--color-success)" }}>
                {t("common.saved")}
              </span>
            )}
          </div>
        ))}
          </div>
        </>
      )}
    </div>
  );
}

/**
 * ModelAdvancedFields —— 模型高级深水区参数（归属 AdvancedSettingsView）
 *
 * 字段级边界契约：
 * - 渲染：备用识图(VisionConfigSection) + Provider Base URL 覆盖 + 自定义模型表单
 * - 自定义模型表单含 model_id / api_base / temperature / max_tokens 等深水区参数
 * - 不渲染：Provider 卡片的 Key 配置和模型 Chip（这些在基础区 ModelProvidersBasic）
 */
export function ModelAdvancedFields() {
  const { t } = useTranslation();
  const { showToast } = useSettingsToast();
  const {
    configs,
    customModels,
    loading,
    createCustomModel,
    updateCustomModel,
    deleteCustomModel,
    fetchRemoteModelsDirect,
  } = useProviderConfig();

  const [formOpen, setFormOpen] = useState(false);
  const [editingCustom, setEditingCustom] = useState<CustomModel | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [busy, setBusy] = useState(false);
  // ── 自定义模型表单内"拉取模型"状态 ──
  const [customPickerOpen, setCustomPickerOpen] = useState(false);
  const [customRemoteModels, setCustomRemoteModels] = useState<RemoteModelInfo[]>([]);
  const [customRemoteLoading, setCustomRemoteLoading] = useState(false);
  const [customRemoteError, setCustomRemoteError] = useState<string | null>(null);
  // 记录编辑时的初始 Key（明文），用于保存时区分"未变/修改/清除"三种语义
  const [initialApiKey, setInitialApiKey] = useState("");

  // 2026-08-11 自定义模型治理：此区只展示手动创建的第三方接入（source='manual'）。
  // 候选池自动同步的记录（source='sync'）完全隐藏，其生命周期由上方 Provider 卡片的候选池接管，
  // 避免"已配置的 provider 模型重复出现在自定义区"的困惑。旧后端无 source 字段时按 manual 降级。
  const manualModels = customModels.filter((cm) => (cm.source ?? "manual") === "manual");

  if (loading) {
    return (
      <p style={{ color: "var(--text-level-3)", fontSize: "13px" }}>
        {t("common.loading")}
      </p>
    );
  }

  const openCreateForm = () => {
    setEditingCustom(null);
    setForm(emptyForm);
    setInitialApiKey("");
    setCustomPickerOpen?.(false);
    setFormOpen(true);
  };

  const openEditForm = (cm: CustomModel) => {
    setEditingCustom(cm);
    const plainKey = cm.api_key_masked || "";
    setInitialApiKey(plainKey);
    setForm({
      model_id: cm.model_id,
      name: cm.name,
      provider: cm.provider,
      model_name: cm.model_name,
      api_base: cm.api_base,
      api_key: plainKey,
      max_tokens: String(cm.max_tokens),
      temperature: String(cm.temperature),
      supports_vision: cm.supports_vision || false,
    });
    setCustomPickerOpen?.(false);
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
        supports_vision: form.supports_vision,
      };
      if (editingCustom) {
        const patch: Partial<CustomModelPayload> = { ...payload } as Partial<CustomModelPayload>;
        // 明文回填后的保存语义（三态）：
        // - api_key === initialApiKey：未变，不传（避免重复写入相同 Key）
        // - api_key === ""：用户主动清空，传 "" 清除已存 Key
        // - api_key !== initialApiKey 且非空：传新值更新
        if (form.api_key === initialApiKey) delete patch.api_key;
        delete patch.model_id;
        delete patch.enabled;
        await updateCustomModel(editingCustom.id, patch);
      } else {
        await createCustomModel(payload);
      }
      setFormOpen(false);
      setCustomPickerOpen?.(false);
    } catch (err) {
      console.error("Failed to save custom model:", err);
      showToast(errorMessage(err) || "保存失败", "error");
    } finally {
      setBusy(false);
    }
  };

  /** 自定义模型表单：一键拉取上游模型列表 */
  const handleFetchCustomRemote = async () => {
    if (!form.api_key.trim() || !form.api_base.trim()) return;
    setCustomPickerOpen?.(true);
    setCustomRemoteModels?.([]);
    setCustomRemoteError?.(null);
    setCustomRemoteLoading?.(true);
    try {
      const list = await fetchRemoteModelsDirect(form.api_key.trim(), form.api_base.trim());
      setCustomRemoteModels?.(list);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "拉取失败，请检查 API Key 与端点";
      try {
        const body = err as unknown as { detail?: string };
        setCustomRemoteError?.(body?.detail || msg);
      } catch {
        setCustomRemoteError?.(msg);
      }
    } finally {
      setCustomRemoteLoading?.(false);
    }
  };

  /** 从拉取结果中选择一个模型，自动填充表单 */
  const handleSelectCustomRemoteModel = (modelId: string) => {
    setForm((prev) => ({
      ...prev,
      model_name: modelId,
      model_id: prev.model_id || `custom-${modelId}`,
      name: prev.name || modelId,
    }));
    setCustomPickerOpen?.(false);
  };

  const handleDeleteCustom = async (cm: CustomModel) => {
    if (!confirm(t("settings.model.custom.confirmDelete"))) return;
    setBusy(true);
    try {
      await deleteCustomModel(cm.id);
    } catch (err) {
      console.error("Failed to delete custom model:", err);
      showToast(errorMessage(err) || "删除失败", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleToggleCustom = async (cm: CustomModel) => {
    try {
      await updateCustomModel(cm.id, { enabled: !cm.enabled });
    } catch (err) {
      console.error("Failed to toggle custom model:", err);
      showToast(errorMessage(err) || "切换失败", "error");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
      {/* 自定义模型（上移至高级区首位，紧跟基础区"模型提供商"） */}
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
          <div>
            <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
              {t("settings.model.custom.title")}
            </h3>
            <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
              {t("settings.model.custom.desc")}
            </p>
            {/* 2026-08-11：向用户解释为什么候选池模型不出现在这里 */}
            <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "2px 0 0 0" }}>
              {t("settings.model.custom.syncHidden")}
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
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "12px", color: "var(--text-level-2)" }}>{t("settings.model.custom.apiKey")}</label>
              <ApiKeyInput
                value={form.api_key}
                onChange={(v) => setForm({ ...form, api_key: v })}
                placeholder="sk-..."
                showIcon={false}
              />
            </div>
            {/* 一键拉取模型列表按钮 */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <button
                type="button"
                onClick={handleFetchCustomRemote}
                disabled={customRemoteLoading || !form.api_key.trim() || !form.api_base.trim()}
                style={{
                  ...secondaryBtn,
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  opacity: (!form.api_key.trim() || !form.api_base.trim()) ? 0.5 : 1,
                  cursor: (!form.api_key.trim() || !form.api_base.trim()) ? "not-allowed" : "pointer",
                }}
              >
                {customRemoteLoading ? (
                  <Loader2 style={{ width: "12px", height: "12px", animation: "spin 1s linear infinite" }} />
                ) : (
                  <Zap style={{ width: "12px", height: "12px" }} />
                )}
                {t("settings.model.custom.fetchModels")}
              </button>
              {customRemoteError && (
                <span style={{ fontSize: "11px", color: "var(--color-error)" }}>{customRemoteError}</span>
              )}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
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
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <SwitchButton
                checked={form.supports_vision}
                onChange={() => setForm({ ...form, supports_vision: !form.supports_vision })}
              />
              <span style={{ fontSize: "12px", color: "var(--text-level-2)" }}>
                {t("settings.model.custom.supportsVision")}
              </span>
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

        {/* 一键拉取的模型选择器 */}
        {customPickerOpen && (
          <RemoteModelPicker
            providerId="custom"
            models={customRemoteModels}
            enabledSet={new Set<string>()}
            onAdd={handleSelectCustomRemoteModel}
            onClose={() => setCustomPickerOpen(false)}
            loading={customRemoteLoading}
            error={customRemoteError}
          />
        )}

        {manualModels.length === 0 && !formOpen ? (
          <p style={{ fontSize: "12px", color: "var(--text-level-4)", margin: 0 }}>
            {t("settings.model.custom.noCustom")}
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {manualModels.map((cm) => (
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
                    {cm.supports_vision && (
                      <span style={{
                        fontSize: "10px",
                        padding: "1px 6px",
                        borderRadius: "999px",
                        background: "rgba(139,92,246,0.12)",
                        color: "var(--color-primary, #8b5cf6)",
                        lineHeight: 1.4,
                      }}>
                        Vision
                      </span>
                    )}
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

      {/* 纹身图模型（生图专用 BYOK） */}
      <TattooImageConfigSection />

      {/* 备用识图模型（双轨 BYOK） */}
      <VisionConfigSection />

      {/* Provider Base URL 覆盖（深水区端点配置） */}
      <ProviderBaseUrlOverride />
    </div>
  );
}