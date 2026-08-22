"use client";

import { useState, useEffect } from "react";
import { Plus, Trash2, Pencil, Globe, ExternalLink, X, Zap, Wifi, ChevronUp, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import {
  useProviderConfig,
  CustomModel,
  CustomModelPayload,
  RemoteModelInfo,
  TestConnectionRequest,
  TestConnectionResponse,
} from "@/hooks/useProviderConfig";
import { ApiKeyInput } from "@/components/ApiKeyInput";
import { RemoteModelPicker } from "@/components/RemoteModelPicker";
import { SwitchButton } from "@/components/SwitchButton";
import { VisionConfigSection } from "./VisionConfigSection";

// ════════════════════════════════════════════════════════════════════
// 前端脱敏工具：仅渲染层使用，不修改 Store 真实数据
// ════════════════════════════════════════════════════════════════════

/**
 * 将 API Key 明文转换为展示用脱敏文本。
 * 规则：保留前 3 位 + 后 4 位，中间替换为 ****。
 * 长度不足 8 时全显示 ****（防止推测出短 Key）。
 * 空值返回空字符串。
 *
 * 示例：
 *   sk-abcdefghijklmnopc718 → sk-****c718
 *   abc123                   → ****
 *   ""                       → ""
 */
function maskApiKey(key: string): string {
  if (!key) return "";
  if (key.length < 8) return "****";
  return key.slice(0, 3) + "****" + key.slice(-4);
}

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
 * 各 Provider 推荐模型快捷添加预设（常驻 + 按钮）。
 * 未命中预设的 provider，快捷添加区退化为仅展示 ProviderConfig.models 池。
 */
// 注：2026-08-11 撤销 — 快捷池改为走后端 PROVIDERS 权威源（P1 修复）。
// 旧版硬编码（含 openai: gpt-4o 等与后端脱钩的条目）见 _trash/20260811_models_drift_fix/ModelConfigSection.tsx.bak

// 2026-08-11 新增：推荐模型白名单（仅展示 3 个新款文本模型，隐藏老款/专用/视觉型号）
// - qwen3.7-plus：Qwen3.7 系列最新版
// - qwen-plus-2025-07-28：Qwen Plus 2025-07 时间戳新版
// - qwen-max：通义千问旗舰
// 其余后端披露的 9 个模型（qwen-flash/qwen-plus/qwen-math-turbo/qwen-mt-flash/...）及 3 个 VL 视觉模型
// 均不作为"快捷入口"展示，但用户仍可在区块3 "手动添加"输入 id 加入候选池。
const RECOMMENDED_TEXT_NEW = new Set(["qwen3.7-plus", "qwen-plus-2025-07-28", "qwen-max"]);

/**
 * @deprecated 字段级边界重构后已拆分为 ModelProvidersBasic + ModelAdvancedFields。
 * 保留此组件仅为向后兼容，新代码请勿引用。
 * 基础区请用 <ModelProvidersBasic />，高级区请用 <ModelAdvancedFields />。
 */
export function ModelConfigSection() {
  const { t } = useTranslation();
  const {
    configs,
    customModels,
    loading,
    saveProviderKey,
    clearProviderKey,
    createCustomModel,
    updateCustomModel,
    deleteCustomModel,
    fetchRemoteModels,
    fetchRemoteModelsDirect,
    testConnection,
    getEnabled,
    addModel,
    removeModel,
  } = useProviderConfig();

  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [keyInput, setKeyInput] = useState("");
  const [baseInput, setBaseInput] = useState("");
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [savedProvider, setSavedProvider] = useState<string | null>(null);
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

  // 2026-08-11：与 ModelAdvancedFields 一致，只展示手动创建的第三方接入（deprecated 组件保持同行为）
  const manualModels = customModels.filter((cm) => (cm.source ?? "manual") === "manual");

  // ── 远程模型拉取状态（按 provider 独立）──
  const [remotePickerOpen, setRemotePickerOpen] = useState<string | null>(null);
  const [remoteModels, setRemoteModels] = useState<RemoteModelInfo[]>([]);
  const [remoteLoading, setRemoteLoading] = useState(false);
  const [remoteError, setRemoteError] = useState<string | null>(null);

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
    // 后端明文下发：回填真实 Key，激活小眼睛查看功能
    const p = configs.find((c) => c.id === pId);
    setKeyInput(p?.api_key_masked || "");
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
      // 状态收敛：clearProviderKey 已封装"后端 purge 关联数据 + 前端 enabled_models 清空"完整流程。
      // 后端 settings 表为唯一权威源，无需再手动 setEnabled([]) 或清 localStorage。
      await clearProviderKey(pId);
      // 清空本地编辑态
      setKeyInput("");
      setBaseInput("");
      // 关闭可能开着的远程拉取弹层
      setRemotePickerOpen(null);
      flashSaved(pId);
    } catch (err) {
      console.error("Failed to clear key:", err);
    } finally {
      setSavingProvider(null);
    }
  };

  /** 一键拉取上游官方模型列表（防爆：结果进 RemoteModelPicker 搜索选择，不平铺） */
  const handleFetchRemote = async (pId: string) => {
    // 切换弹层：再次点击同一 provider 则关闭
    if (remotePickerOpen === pId) {
      setRemotePickerOpen(null);
      return;
    }
    setRemotePickerOpen(pId);
    setRemoteModels([]);
    setRemoteError(null);
    setRemoteLoading(true);
    try {
      const list = await fetchRemoteModels(pId);
      setRemoteModels(list);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "拉取失败，请检查 API Key 与网络";
      // 尝试从 API 错误体提取 detail
      try {
        const body = err as unknown as { detail?: string };
        if (body?.detail) setRemoteError(body.detail);
        else setRemoteError(msg);
      } catch {
        setRemoteError(msg);
      }
    } finally {
      setRemoteLoading(false);
    }
  };

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
      {/* 备用识图模型（双轨 BYOK） */}
      <VisionConfigSection />

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
            <ProviderCard
              key={p.id}
              provider={p}
              editing={editingProvider === p.id}
              keyInput={keyInput}
              baseInput={baseInput}
              savingProvider={savingProvider}
              savedProvider={savedProvider}
              onOpenEdit={() => openProvider(p.id, p.api_base, p.api_base_override)}
              onCloseEdit={() => setEditingProvider(null)}
              onKeyChange={setKeyInput}
              onBaseChange={setBaseInput}
              onSaveProvider={() => handleSaveProvider(p.id)}
              onClearKey={() => handleClearKey(p.id)}
              enabledModels={getEnabled(p.id)}
              onAddModel={(mid) => addModel(p.id, mid)}
              onRemoveModel={(mid) => removeModel(p.id, mid)}
              onFetchRemote={() => handleFetchRemote(p.id)}
              remotePickerOpen={remotePickerOpen === p.id}
              remoteModels={remoteModels}
              remoteLoading={remoteLoading}
              remoteError={remoteError}
              onCloseRemotePicker={() => setRemotePickerOpen(null)}
              onTestConnection={testConnection}
              t={t}
            />
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
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "12px", color: "var(--text-level-2)" }}>{t("settings.model.custom.apiKey")}</label>
              {/* 任务1：自定义模型表单 API Key 复用公共组件 */}
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
    </div>
  );
}

// ── Provider 卡片：含 API Key 配置 + 动态模型 Chip 三区块 ──────────────────

interface ProviderCardProps {
  provider: {
    id: string;
    name: string;
    description?: string;
    free: boolean;
    website?: string;
    api_key_masked: string;
    has_key: boolean;
    api_base: string;
    api_base_override: boolean;
    models: { id: string; name: string }[];
  };
  editing: boolean;
  keyInput: string;
  baseInput: string;
  savingProvider: string | null;
  savedProvider: string | null;
  onOpenEdit: () => void;
  onCloseEdit: () => void;
  onKeyChange: (v: string) => void;
  onBaseChange: (v: string) => void;
  onSaveProvider: () => void;
  onClearKey: () => void;
  enabledModels: string[];
  onAddModel: (modelId: string) => void;
  onRemoveModel: (modelId: string) => void;
  onFetchRemote: () => void;
  remotePickerOpen: boolean;
  remoteModels: RemoteModelInfo[];
  remoteLoading: boolean;
  remoteError: string | null;
  onCloseRemotePicker: () => void;
  onTestConnection: (data: TestConnectionRequest) => Promise<TestConnectionResponse>;
  t: (key: string, params?: Record<string, string>) => string;
  /**
   * 字段级边界重构：是否隐藏 editing 表单中的 Base URL 覆盖输入框。
   * - true（基础区）：隐藏 Base URL，新手绝不会看到深水区参数。
   *   此时 onSaveProvider 内部必须传 undefined 给 apiBase，否则空字符串会误清除已存 override。
   * - false（高级区/完整模式）：显示 Base URL 输入框，保持原行为。
   */
  hideBaseUrl?: boolean;
  /** Provider 总开关：是否被禁用 */
  providerDisabled?: boolean;
  /** 切换 Provider 启用/禁用状态 */
  onToggleDisabled?: () => void;
}

function ProviderCard({
  provider: p,
  editing,
  keyInput,
  baseInput,
  savingProvider,
  savedProvider,
  onOpenEdit,
  onCloseEdit,
  onKeyChange,
  onBaseChange,
  onSaveProvider,
  onClearKey,
  enabledModels,
  onAddModel,
  onRemoveModel,
  onFetchRemote,
  remotePickerOpen,
  remoteModels,
  remoteLoading,
  remoteError,
  onCloseRemotePicker,
  onTestConnection,
  t,
  hideBaseUrl = false,
  providerDisabled = false,
  onToggleDisabled,
}: ProviderCardProps) {
  // 自定义手动添加输入框（每个 provider 独立）
  const [customInput, setCustomInput] = useState("");
  // 2026-08-11：候选池折叠状态，默认折叠（像字体选择器那样不占空间）+ 持久化记忆（刷新/重启不丢）
  const [poolExpanded, setPoolExpanded] = useState(() => {
    try {
      return localStorage.getItem(`mfk_provider_pool_expanded_${p.id}`) === "true";
    } catch {
      return false;
    }
  });
  const togglePoolExpanded = () => {
    setPoolExpanded((prev) => {
      const next = !prev;
      try { localStorage.setItem(`mfk_provider_pool_expanded_${p.id}`, String(next)); } catch { /* noop */ }
      return next;
    });
  };
  // 2026-08-14：推荐模型快捷添加折叠，默认折叠 + 持久化记忆（样式对齐字体选择器）
  const [quickAddExpanded, setQuickAddExpanded] = useState(() => {
    try {
      return localStorage.getItem(`mfk_provider_quickadd_expanded_${p.id}`) === "true";
    } catch {
      return false;
    }
  });
  const toggleQuickAddExpanded = () => {
    setQuickAddExpanded((prev) => {
      const next = !prev;
      try { localStorage.setItem(`mfk_provider_quickadd_expanded_${p.id}`, String(next)); } catch { /* noop */ }
      return next;
    });
  };

  // ── 连通性测试状态（每张卡片独立，临时 UI 状态）──
  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState<TestConnectionResponse | null>(null);

  // 模型区域收起/展开（持久化到 localStorage，记忆用户偏好；默认折叠，像字体选择器那样不占空间）
  const [modelsExpanded, setModelsExpanded] = useState(() => {
    try {
      return localStorage.getItem(`mfk_provider_expanded_${p.id}`) === "true";
    } catch {
      return false;
    }
  });
  const toggleModelsExpanded = () => {
    setModelsExpanded((prev) => {
      const next = !prev;
      try { localStorage.setItem(`mfk_provider_expanded_${p.id}`, String(next)); } catch { /* noop */ }
      return next;
    });
  };

  // 综合配置状态：has_key（已配置 Key）或 api_base_override（已配置 Base URL 覆盖）
  // 用于控制"清除"按钮显隐：仅配置 Base URL 不填 Key 的本地模型也能正常清除
  const isConfigured = p.has_key || p.api_base_override;

  // 推荐模型：唯一权威源 = ProviderConfig.models（后端 model_providers.py）
  // 历史：之前用 RECOMMENDED_MODELS 硬编码常驻，与后端脱钩导致漂移（百炼新模型漏显示、qwen-turbo 幽灵等）。
  // 2026-08-11 改为单源（见 P1 修复）。百炼一类的聚合 provider 也能露出全部子模型。
  // 2026-08-11 进一步精简：仅展示 3 个新款文本模型（白名单 RECOMMENDED_TEXT_NEW）
  // 其余模型走区块3 "手动添加"输入名字加入。
  const recommended = p.models.map((m) => m.id);
  // 已启用集合（O(1) 查找）
  const enabledSet = new Set(enabledModels);
  // 快捷添加区只展示"白名单 ∩ 尚未启用"的推荐模型
  const quickAddList = recommended.filter((m) => !enabledSet.has(m) && RECOMMENDED_TEXT_NEW.has(m));

  const handleCustomAdd = () => {
    const id = customInput.trim();
    if (!id) return;
    onAddModel(id);
    setCustomInput("");
  };

  /**
   * 连通性测试：使用输入框中的实时草稿值（Draft State）。
   * 关键逻辑：
   *   - api_key: 传入 keyInput 草稿值；为空时不传，后端自动回退读取已存 Key
   *   - api_base: 传入 baseInput 草稿值；为空时不传，后端取默认端点
   *   - 不依赖 Store 中已保存的值，支持"无需保存即可验证"
   */
  const handleTestConnection = async () => {
    setTestLoading(true);
    setTestResult(null);
    try {
      const payload: TestConnectionRequest = { provider_id: p.id };
      // 仅在输入框有值时传入草稿，空值留给后端回退
      const draftKey = keyInput.trim();
      const draftBase = baseInput.trim();
      if (draftKey) payload.api_key = draftKey;
      if (draftBase) payload.api_base = draftBase;
      const result = await onTestConnection(payload);
      setTestResult(result);
    } catch (err) {
      // HTTP 层异常（如网络错误、404 provider 不存在）
      const msg = err instanceof Error ? err.message : String(err);
      setTestResult({ ok: false, latency_ms: 0, detail: msg });
    } finally {
      setTestLoading(false);
    }
  };

  return (
    <div
      style={{
        padding: "12px 14px",
        borderRadius: "var(--radius-md)",
        border: providerDisabled
          ? "1px dashed var(--border-primary)"
          : "1px solid var(--border-primary)",
        background: "var(--bg-level-2)",
        opacity: providerDisabled ? 0.55 : 1,
        transition: "opacity 0.2s ease, border 0.2s ease",
      }}
    >
      {/* ── 头部行：始终可见（收起态仅保留核心信息）── */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        {/* 收起/展开箭头 */}
        <button
          type="button"
          onClick={toggleModelsExpanded}
          title={modelsExpanded ? t("settings.model.providers.collapseModels") : t("settings.model.providers.expandModels")}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: "20px",
            height: "20px",
            padding: 0,
            border: "none",
            background: "transparent",
            cursor: "pointer",
            color: "var(--text-level-4)",
            flexShrink: 0,
            transition: "color 0.15s ease",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-level-2)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-level-4)")}
        >
          {modelsExpanded ? (
            <ChevronDown style={{ width: "14px", height: "14px" }} />
          ) : (
            <ChevronRight style={{ width: "14px", height: "14px" }} />
          )}
        </button>

        {/* Provider 名称（视觉中心） */}
        <span style={{ fontSize: "13px", fontWeight: "600", color: "var(--text-level-1)", flexShrink: 0 }}>
          {p.name}
        </span>

        {/* Provider 总开关：启用/禁用（与设置页其他开关统一的 SwitchButton） */}
        {onToggleDisabled && (
          <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
            <SwitchButton
              checked={!providerDisabled}
              onChange={() => onToggleDisabled()}
            />
            <span
              style={{
                fontSize: "11px",
                color: providerDisabled ? "var(--text-level-4)" : "var(--color-success)",
                fontWeight: 500,
                userSelect: "none",
              }}
            >
              {providerDisabled ? t("settings.model.providers.disabled") : t("settings.model.providers.enabled")}
            </span>
          </div>
        )}

        {/* 右侧：脱敏 Key + 清除按钮 + 配置状态（统一胶囊高度） */}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
          {p.has_key && (
            <span style={{ fontSize: "12px", color: "var(--text-level-4)", fontFamily: "monospace" }}>
              {maskApiKey(p.api_key_masked)}
            </span>
          )}
          {isConfigured && (
            <button
              onClick={onClearKey}
              disabled={savingProvider === p.id}
              title={t("settings.model.providers.clearKey")}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "24px",
                height: "24px",
                padding: 0,
                borderRadius: "var(--radius-sm)",
                border: "1px solid transparent",
                background: "transparent",
                cursor: "pointer",
                color: "var(--text-level-4)",
                opacity: savingProvider === p.id ? 0.6 : 1,
                transition: "all 0.15s ease",
                flexShrink: 0,
              }}
              onMouseEnter={(e) => {
                if (savingProvider !== p.id) {
                  e.currentTarget.style.background = "rgba(239,68,68,0.1)";
                  e.currentTarget.style.color = "var(--color-danger, #ef4444)";
                  e.currentTarget.style.borderColor = "rgba(239,68,68,0.3)";
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.color = "var(--text-level-4)";
                e.currentTarget.style.borderColor = "transparent";
              }}
            >
              <Trash2 style={{ width: "13px", height: "13px" }} />
            </button>
          )}
          <span style={{
            fontSize: "11px",
            padding: "2px 8px",
            borderRadius: "999px",
            background: p.has_key
              ? "rgba(16,185,129,0.12)"
              : "rgba(107,114,128,0.12)",
            color: p.has_key ? "var(--color-success)" : "var(--text-level-3)",
            lineHeight: 1.4,
            flexShrink: 0,
          }}>
            {p.has_key
              ? t("settings.model.providers.configured")
              : t("settings.model.providers.notConfigured")}
          </span>
        </div>
      </div>

      {/* ── 以下内容仅在展开时显示 ── */}
      {modelsExpanded && (
      <>
      {/* 元信息行：免费标签 + 官网链接（收起态隐藏，保持头部简洁） */}
      {(p.free || p.website) && (
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "8px" }}>
          {p.free && (
            <span style={{
              fontSize: "11px",
              padding: "2px 8px",
              borderRadius: "999px",
              background: "var(--color-success-lighter, rgba(16,185,129,0.12))",
              color: "var(--color-success)",
              lineHeight: 1.4,
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
                gap: "3px",
                fontSize: "11px",
                color: "var(--color-primary)",
                textDecoration: "none",
                cursor: "pointer",
              }}
            >
              <ExternalLink style={{ width: "11px", height: "11px" }} />
              {t("settings.model.providers.website")}
            </a>
          )}
        </div>
      )}
      {p.description && (
        <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "6px 0 0 0" }}>
          {p.description}
        </p>
      )}

      {/* ── 动态模型 Chip 三区块 ── */}
      <div style={{ marginTop: "10px", display: "flex", flexDirection: "column", gap: "8px" }}>
        {/* 区块1：已加入候选池的模型（可折叠，像字体选择器一样简洁） */}
        <div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "2px 0",
              fontSize: "11px",
              color: "var(--text-level-3)",
            }}
          >
            <span
              title={t("settings.model.providers.enabledModelsHint")}
              style={{ cursor: "help", textDecoration: "underline dotted var(--text-level-4)" }}
            >
              {t("settings.model.providers.enabledModels")} ({enabledModels.length})
            </span>
            <div style={{ flex: 1 }} />
            {enabledModels.length > 0 && (
              <button
                type="button"
                onClick={togglePoolExpanded}
                aria-label={poolExpanded ? "collapse" : "expand"}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "20px",
                  height: "20px",
                  padding: 0,
                  borderRadius: "var(--radius-xs)",
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  color: "var(--text-level-3)",
                  transition: "color var(--transition-fast), background var(--transition-fast)",
                  outline: "none",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "var(--text-level-1)";
                  e.currentTarget.style.background = "var(--bg-level-3)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "var(--text-level-3)";
                  e.currentTarget.style.background = "transparent";
                }}
              >
                <ChevronDown
                  style={{
                    width: "12px",
                    height: "12px",
                    transform: poolExpanded ? "rotate(180deg)" : "rotate(0deg)",
                    transition: "transform var(--transition-fast)",
                  }}
                />
              </button>
            )}
          </div>

          {/* 展开后：紧湊列表（28px 行高）+ 每行右侧 X 删除按钮 */}
          {poolExpanded && enabledModels.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1px", marginTop: "2px" }}>
              {enabledModels.map((mid) => (
                <div
                  key={mid}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    height: "28px",
                    padding: "0 6px 0 10px",
                    borderRadius: "var(--radius-sm)",
                    background: "color-mix(in srgb, var(--color-primary) 8%, transparent)",
                    border: "1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)",
                  }}
                >
                  <span
                    style={{
                      flex: 1,
                      minWidth: 0,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      fontSize: "12px",
                      fontFamily: "monospace",
                      color: "var(--text-level-1)",
                    }}
                  >
                    {mid}
                  </span>
                  <button
                    type="button"
                    onClick={() => onRemoveModel(mid)}
                    title={t("settings.model.providers.removeModel")}
                    aria-label="remove"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "18px",
                      height: "18px",
                      padding: 0,
                      borderRadius: "50%",
                      border: "none",
                      background: "transparent",
                      cursor: "pointer",
                      color: "var(--text-level-3)",
                      flexShrink: 0,
                      transition: "color var(--transition-fast), background var(--transition-fast)",
                      outline: "none",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.color = "var(--color-error)";
                      e.currentTarget.style.background = "var(--bg-level-3)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.color = "var(--text-level-3)";
                      e.currentTarget.style.background = "transparent";
                    }}
                  >
                    <X style={{ width: "12px", height: "12px" }} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* 折叠状态或空状态：仍显示提示（默认折叠时仅一行 header 文字提示） */}
          {!poolExpanded && enabledModels.length === 0 && (
            <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>
              {t("settings.model.providers.noEnabled")}
            </span>
          )}
        </div>

        {/* 区块2：推荐模型快捷添加（可折叠，样式对齐字体选择器/候选池） */}
        {quickAddList.length > 0 && (
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                padding: "2px 0",
                fontSize: "11px",
                color: "var(--text-level-3)",
              }}
            >
              <span>
                {t("settings.model.providers.quickAdd")} ({quickAddList.length})
              </span>
              <div style={{ flex: 1 }} />
              <button
                type="button"
                onClick={toggleQuickAddExpanded}
                aria-label={quickAddExpanded ? "collapse" : "expand"}
                title={quickAddExpanded ? t("settings.model.providers.collapseModels") : t("settings.model.providers.expandModels")}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "20px",
                  height: "20px",
                  padding: 0,
                  borderRadius: "var(--radius-xs)",
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  color: "var(--text-level-3)",
                  transition: "color var(--transition-fast), background var(--transition-fast)",
                  outline: "none",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "var(--text-level-1)";
                  e.currentTarget.style.background = "var(--bg-level-3)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "var(--text-level-3)";
                  e.currentTarget.style.background = "transparent";
                }}
              >
                <ChevronDown
                  style={{
                    width: "12px",
                    height: "12px",
                    transform: quickAddExpanded ? "rotate(180deg)" : "rotate(0deg)",
                    transition: "transform var(--transition-fast)",
                  }}
                />
              </button>
            </div>
            {quickAddExpanded && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                {quickAddList.map((mid) => (
                  <button
                    key={mid}
                    type="button"
                    onClick={() => onAddModel(mid)}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                      padding: "2px 10px",
                      borderRadius: "999px",
                      background: "transparent",
                      color: "var(--text-level-3)",
                      fontSize: "12px",
                      fontFamily: "monospace",
                      border: "1px dashed var(--border-primary)",
                      cursor: "pointer",
                    }}
                  >
                    <Plus style={{ width: "12px", height: "12px" }} />
                    {mid}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 区块3：自定义手动添加 */}
        <div>
          <div style={{ fontSize: "11px", color: "var(--text-level-3)", marginBottom: "4px" }}>
            {t("settings.model.providers.customAdd")}
          </div>
          <div style={{ display: "flex", gap: "6px" }}>
            <input
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleCustomAdd();
                }
              }}
              placeholder={t("settings.model.providers.customPlaceholder")}
              style={{
                flex: 1,
                padding: "5px 10px",
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
              onClick={handleCustomAdd}
              disabled={!customInput.trim()}
              style={{
                padding: "5px 12px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-primary)",
                background: "transparent",
                color: "var(--text-level-2)",
                fontSize: "12px",
                cursor: customInput.trim() ? "pointer" : "not-allowed",
                opacity: customInput.trim() ? 1 : 0.5,
                whiteSpace: "nowrap",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              <Plus style={{ width: "12px", height: "12px" }} />
              {t("settings.model.providers.addBtn")}
            </button>
          </div>
        </div>
      </div>

      {/* 一键拉取官方模型（防爆：结果进搜索下拉，不平铺） */}
      <div style={{ marginTop: "8px" }}>
        <button
          type="button"
          onClick={onFetchRemote}
          disabled={!p.has_key}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            padding: "4px 12px",
            borderRadius: "var(--radius-sm)",
            border: remotePickerOpen
              ? "1px solid var(--color-primary)"
              : "1px solid var(--border-primary)",
            background: remotePickerOpen
              ? "color-mix(in srgb, var(--color-primary) 8%, transparent)"
              : "transparent",
            color: p.has_key ? "var(--color-primary)" : "var(--text-level-4)",
            fontSize: "12px",
            cursor: p.has_key ? "pointer" : "not-allowed",
            opacity: p.has_key ? 1 : 0.5,
            whiteSpace: "nowrap",
          }}
        >
          <Zap style={{ width: "12px", height: "12px" }} />
          {t("settings.model.providers.fetchRemote")}
        </button>
        {!p.has_key && (
          <span style={{ marginLeft: "6px", fontSize: "11px", color: "var(--text-level-4)" }}>
            {t("settings.model.providers.fetchRemoteHint")}
          </span>
        )}
        {remotePickerOpen && (
          <RemoteModelPicker
            providerId={p.id}
            models={remoteModels}
            enabledSet={enabledSet}
            onAdd={onAddModel}
            onClose={onCloseRemotePicker}
            loading={remoteLoading}
            error={remoteError}
          />
        )}
      </div>

      {/* API Key 配置入口 */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "10px" }}>
        <button
          onClick={editing ? onCloseEdit : onOpenEdit}
          style={{
            padding: "5px 12px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)",
            background: "transparent",
            cursor: "pointer",
            fontSize: "12px",
            color: "var(--text-level-2)",
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = "var(--color-primary)";
            e.currentTarget.style.color = "var(--color-primary)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "var(--border-primary)";
            e.currentTarget.style.color = "var(--text-level-2)";
          }}
        >
          {t(editing ? "common.cancel" : "settings.model.providers.configure")}
        </button>
        {savedProvider === p.id && (
          <span style={{ fontSize: "12px", color: "var(--color-success)" }}>
            {t("common.saved")}
          </span>
        )}
      </div>

      {editing && (
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
            <label style={{ minWidth: "70px", fontSize: "12px", color: "var(--text-level-2)", flexShrink: 0 }}>
              {t("settings.model.providers.keyLabel")}
            </label>
            {/* 任务1：主 Provider API Key 复用公共组件 */}
            <ApiKeyInput
              value={keyInput}
              onChange={onKeyChange}
              placeholder={p.api_key_masked || "sk-..."}
              showIcon={false}
            />
          </div>
          {/* 字段级边界：Base URL 覆盖仅在高级区显示，基础区隐藏 */}
          {!hideBaseUrl && (
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <label style={{ minWidth: "70px", fontSize: "12px", color: "var(--text-level-2)", display: "flex", alignItems: "center", gap: "4px", flexShrink: 0 }}>
                <Globe style={{ width: "12px", height: "12px" }} />
                {t("settings.model.providers.baseLabel")}
              </label>
              <input
                type="text"
                value={baseInput}
                onChange={(e) => onBaseChange(e.target.value)}
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
          )}
          {/* 基础区提示：已配置 override 时告知用户去高级区修改 */}
          {hideBaseUrl && p.api_base_override && (
            <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: 0 }}>
              {t("settings.model.providers.baseUrlInAdvanced")}
            </p>
          )}
          {/* 任务2：连通性测试 —— 使用输入框实时草稿值，无需保存即可验证 */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            flexWrap: "wrap",
            padding: "8px 10px",
            borderRadius: "var(--radius-sm)",
            background: "color-mix(in srgb, var(--color-primary) 4%, transparent)",
            border: "1px dashed color-mix(in srgb, var(--color-primary) 25%, transparent)",
          }}>
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={testLoading}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
                padding: "5px 14px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--color-primary)",
                background: "transparent",
                color: "var(--color-primary)",
                cursor: testLoading ? "not-allowed" : "pointer",
                fontSize: "12px",
                fontWeight: "500",
                opacity: testLoading ? 0.7 : 1,
                whiteSpace: "nowrap",
              }}
            >
              <Wifi style={{ width: "12px", height: "12px" }} />
              {testLoading
                ? t("settings.model.providers.testConnectionTesting")
                : t("settings.model.providers.testConnection")}
            </button>
            <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>
              {t("settings.model.providers.testConnectionHint")}
            </span>
            {/* 内联反馈：成功显示延迟（绿色），失败显示 detail（红色） */}
            {testResult && (
              <span
                style={{
                  fontSize: "12px",
                  fontFamily: "monospace",
                  color: testResult.ok
                    ? "var(--color-success)"
                    : "var(--color-danger, #ef4444)",
                  wordBreak: "break-all",
                  flex: "1 1 auto",
                  minWidth: 0,
                }}
              >
                {testResult.ok
                  ? t("settings.model.providers.testConnectionOk", {
                      latency: String(testResult.latency_ms),
                    })
                  : t("settings.model.providers.testConnectionFail", {
                      detail: testResult.detail,
                    })}
              </span>
            )}
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button
              onClick={onSaveProvider}
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
      </>
      )}
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

// ════════════════════════════════════════════════════════════════════
// 字段级边界重构：基础区 / 高级区 拆分组件
// ════════════════════════════════════════════════════════════════════

/**
 * ModelProvidersBasic —— 模型基础配置（归属 BasicSettingsView）
 *
 * 字段级边界契约：
 * - 渲染 Provider 卡片（API Key 配置 + 模型 Chip + 连通性测试 + 远程拉取）
 * - 隐藏 Base URL 覆盖输入框（hideBaseUrl=true），新手绝不会看到深水区参数
 * - 保存时仅传 apiKey，apiBase 传 undefined（不修改已存 override，避免空串误清除）
 * - 不渲染：VisionConfigSection、自定义模型表单（这些下沉到 ModelAdvancedFields）
 *
 * 关键安全点：
 *   saveProviderKey(pId, keyInput || undefined, undefined)
 *   第三个参数必须是 undefined 而非 ""，否则会清除已存的 base override。
 */
export function ModelProvidersBasic() {
  const { t } = useTranslation();
  const {
    configs,
    loading,
    saveProviderKey,
    clearProviderKey,
    fetchRemoteModels,
    testConnection,
    getEnabled,
    addModel,
    removeModel,
    isProviderDisabled,
    setProviderDisabled,
  } = useProviderConfig();

  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [keyInput, setKeyInput] = useState("");
  const [baseInput, setBaseInput] = useState(""); // 基础区不使用，但 ProviderCard 接口需要
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [savedProvider, setSavedProvider] = useState<string | null>(null);

  // ── 远程模型拉取状态（按 provider 独立）──
  const [remotePickerOpen, setRemotePickerOpen] = useState<string | null>(null);
  const [remoteModels, setRemoteModels] = useState<RemoteModelInfo[]>([]);
  const [remoteLoading, setRemoteLoading] = useState(false);
  const [remoteError, setRemoteError] = useState<string | null>(null);

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

  const openProvider = (pId: string, _apiBase: string, _override: boolean) => {
    setEditingProvider(pId);
    // 后端明文下发：回填真实 Key 到输入框，让小眼睛真正能查看已存的明文 Key。
    // （此前 setKeyInput("") 导致输入框为空，小眼睛被禁用，形成摆设）
    const p = configs.find((c) => c.id === pId);
    setKeyInput(p?.api_key_masked || "");
    setBaseInput(""); // 基础区始终不使用 baseInput
  };

  const handleSaveProvider = async (pId: string) => {
    setSavingProvider(pId);
    try {
      // 字段级边界关键点：apiBase 传 undefined，绝不修改已存 base override
      await saveProviderKey(pId, keyInput || undefined, undefined);
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
      await clearProviderKey(pId);
      setKeyInput("");
      setBaseInput("");
      setRemotePickerOpen(null);
      flashSaved(pId);
    } catch (err) {
      console.error("Failed to clear key:", err);
    } finally {
      setSavingProvider(null);
    }
  };

  const handleFetchRemote = async (pId: string) => {
    if (remotePickerOpen === pId) {
      setRemotePickerOpen(null);
      return;
    }
    setRemotePickerOpen(pId);
    setRemoteModels([]);
    setRemoteError(null);
    setRemoteLoading(true);
    try {
      const list = await fetchRemoteModels(pId);
      setRemoteModels(list);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "拉取失败，请检查 API Key 与网络";
      try {
        const body = err as unknown as { detail?: string };
        if (body?.detail) setRemoteError(body.detail);
        else setRemoteError(msg);
      } catch {
        setRemoteError(msg);
      }
    } finally {
      setRemoteLoading(false);
    }
  };

  return (
    <div>
      <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
        {t("settings.model.providers.title")}
      </h3>
      <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 12px 0" }}>
        {t("settings.model.providers.desc")}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {configs.map((p) => (
          <ProviderCard
            key={p.id}
            provider={p}
            editing={editingProvider === p.id}
            keyInput={keyInput}
            baseInput={baseInput}
            savingProvider={savingProvider}
            savedProvider={savedProvider}
            onOpenEdit={() => openProvider(p.id, p.api_base, p.api_base_override)}
            onCloseEdit={() => setEditingProvider(null)}
            onKeyChange={setKeyInput}
            onBaseChange={setBaseInput}
            onSaveProvider={() => handleSaveProvider(p.id)}
            onClearKey={() => handleClearKey(p.id)}
            enabledModels={getEnabled(p.id)}
            onAddModel={(mid) => addModel(p.id, mid)}
            onRemoveModel={(mid) => removeModel(p.id, mid)}
            onFetchRemote={() => handleFetchRemote(p.id)}
            remotePickerOpen={remotePickerOpen === p.id}
            remoteModels={remoteModels}
            remoteLoading={remoteLoading}
            remoteError={remoteError}
            onCloseRemotePicker={() => setRemotePickerOpen(null)}
            onTestConnection={testConnection}
            t={t}
            hideBaseUrl={true}
            providerDisabled={isProviderDisabled(p.id)}
            onToggleDisabled={() => setProviderDisabled(p.id, !isProviderDisabled(p.id))}
          />
        ))}
      </div>
    </div>
  );
}

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
      {/* 备用识图模型（双轨 BYOK） */}
      <VisionConfigSection />

      {/* Provider Base URL 覆盖（深水区端点配置） */}
      <ProviderBaseUrlOverride />

      {/* 自定义模型（含 model_id / api_base / temperature / max_tokens 深水区参数） */}
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
    </div>
  );
}
