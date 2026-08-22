"use client";

/**
 * ModelAdvancedFields —— 模型高级深水区参数（归属 AdvancedSettingsView）
 * 含：备用识图 + Provider Base URL 覆盖 + 自定义模型表单。
 * 从 ModelConfigSection.tsx 拆分，逻辑与行为零变化。
 */
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronRight, Globe, Loader2, Pencil, Plus, Trash2, Zap } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { useProviderConfig, type CustomModel, type CustomModelPayload, type RemoteModelInfo } from "@/hooks/useProviderConfig";
import { ApiKeyInput } from "@/components/ApiKeyInput";
import { RemoteModelPicker } from "@/components/RemoteModelPicker";
import { SwitchButton } from "@/components/SwitchButton";
import { ProviderCard } from "./ProviderCard";
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
  context_window: string;
  supports_vision: boolean;
}

const emptyForm: FormState = {
  model_id: "",
  name: "",
  provider: "openai",
  model_name: "",
  api_base: "",
  api_key: "",
  max_tokens: "8192",
  temperature: "0.7",
  context_window: "200000",
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
    refresh,
    createCustomModel,
    updateCustomModel,
    deleteCustomModel,
    fetchRemoteModelsDirect,
    fetchRemoteModels,
    createCustomProvider,
    saveProviderKey,
    fetchProviderKey,
    clearProviderKey,
    setProviderDisabled,
    isProviderDisabled,
    testConnection,
    getEnabled,
    addModel,
    removeModel,
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

  // ── 快速接入第三方端点（和供应商卡片一样的体验：填Key+BaseURL → 拉取模型 → 多选批量添加）──
  const [quickApiKey, setQuickApiKey] = useState("");
  const [quickApiBase, setQuickApiBase] = useState("");
  const [quickPickerOpen, setQuickPickerOpen] = useState(false);
  const [quickModels, setQuickModels] = useState<RemoteModelInfo[]>([]);
  const [quickLoading, setQuickLoading] = useState(false);
  const [quickError, setQuickError] = useState<string | null>(null);
  const [quickSelected, setQuickSelected] = useState<Set<string>>(new Set());
  const [quickAdding, setQuickAdding] = useState(false);

  // ── 自定义模型卡片：内联展开编辑状态（一次只展开一个）──
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormState>(emptyForm);
  const [editInitialKey, setEditInitialKey] = useState("");
  const [editRemoteOpen, setEditRemoteOpen] = useState(false);
  const [editRemoteModels, setEditRemoteModels] = useState<RemoteModelInfo[]>([]);
  const [editRemoteLoading, setEditRemoteLoading] = useState(false);
  const [editRemoteError, setEditRemoteError] = useState<string | null>(null);
  const [editSaving, setEditSaving] = useState(false);

  // 2026-08-11 自定义模型治理：此区只展示手动创建的第三方接入（source='manual'）。
  // 候选池自动同步的记录（source='sync'）完全隐藏，其生命周期由上方 Provider 卡片的候选池接管，
  // 避免"已配置的 provider 模型重复出现在自定义区"的困惑。旧后端无 source 字段时按 manual 降级。
  const manualModels = customModels.filter((cm) => (cm.source ?? "manual") === "manual");

  // custom 类供应商（如本地网关 FreeLLMAPI）：从基础区移到高级区自定义模型
  const customProviders = configs.filter((c) => c.category === "custom");

  // 自定义模型区域折叠（默认折叠，持久化 localStorage）
  const [customCollapsed, setCustomCollapsed] = useState(() => {
    try {
      return localStorage.getItem("mfk_custom_models_collapsed") !== "false";
    } catch { return true; }
  });
  const toggleCustomCollapsed = () => {
    setCustomCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("mfk_custom_models_collapsed", String(next)); } catch {}
      return next;
    });
  };

  // ── 自定义端点（ProviderCard）编辑状态 ──
  const [cpEditing, setCpEditing] = useState<string | null>(null);
  const [cpKeyInput, setCpKeyInput] = useState("");
  const [cpBaseInput, setCpBaseInput] = useState("");
  const [cpSaving, setCpSaving] = useState<string | null>(null);
  const [cpSaved, setCpSaved] = useState<string | null>(null);
  const [cpRemotePickerOpen, setCpRemotePickerOpen] = useState<string | null>(null);
  const [cpRemoteModels, setCpRemoteModels] = useState<RemoteModelInfo[]>([]);
  const [cpRemoteLoading, setCpRemoteLoading] = useState(false);
  const [cpRemoteError, setCpRemoteError] = useState<string | null>(null);

  // ── 添加自定义端点弹窗 ──
  const [addEndpointOpen, setAddEndpointOpen] = useState(false);
  const [addEndpointName, setAddEndpointName] = useState("");
  const [addEndpointBase, setAddEndpointBase] = useState("");
  const [addEndpointDesc, setAddEndpointDesc] = useState("");
  const [addEndpointSaving, setAddEndpointSaving] = useState(false);

  const flashCpSaved = (id: string) => {
    setCpSaved(id);
    setTimeout(() => setCpSaved(null), 2000);
  };

  const openCpProvider = async (pId: string) => {
    setCpEditing(pId);
    // 回填已有的 Base URL（api_base_override 为布尔值，实际 override 值存在 settings 表，
    // 此处先用默认 api_base 填充，用户可自行修改；override 值会在保存时覆盖）
    const p = configs.find((c) => c.id === pId);
    setCpBaseInput(p?.api_base || "");
    try {
      const realKey = await fetchProviderKey(pId);
      setCpKeyInput(realKey);
    } catch {
      setCpKeyInput(p?.api_key_masked || "");
    }
  };

  const handleSaveCpProvider = async (pId: string) => {
    setCpSaving(pId);
    try {
      await saveProviderKey(pId, cpKeyInput || undefined, cpBaseInput || undefined);
      flashCpSaved(pId);
      setCpEditing(null);
    } catch (err) {
      showToast(errorMessage(err) || "保存失败", "error");
    } finally {
      setCpSaving(null);
    }
  };

  const handleClearCpKey = async (pId: string) => {
    setCpSaving(pId);
    try {
      await clearProviderKey(pId);
      setCpKeyInput("");
      setCpBaseInput("");
      setCpRemotePickerOpen(null);
      flashCpSaved(pId);
    } catch (err) {
      showToast(errorMessage(err) || "清除失败", "error");
    } finally {
      setCpSaving(null);
    }
  };

  const handleFetchCpRemote = async (pId: string) => {
    if (cpRemotePickerOpen === pId) {
      setCpRemotePickerOpen(null);
      return;
    }
    setCpRemotePickerOpen(pId);
    setCpRemoteLoading(true);
    setCpRemoteError(null);
    try {
      const models = await fetchRemoteModels(pId);
      setCpRemoteModels(models);
    } catch (err) {
      setCpRemoteError(errorMessage(err) || "拉取失败");
    } finally {
      setCpRemoteLoading(false);
    }
  };

  const handleCreateEndpoint = async () => {
    if (!addEndpointName.trim() || !addEndpointBase.trim()) return;
    setAddEndpointSaving(true);
    try {
      await createCustomProvider(addEndpointName, addEndpointBase, addEndpointDesc);
      setAddEndpointOpen(false);
      setAddEndpointName("");
      setAddEndpointBase("");
      setAddEndpointDesc("");
      showToast("自定义端点已添加", "success");
    } catch (err) {
      showToast(errorMessage(err) || "添加失败", "error");
    } finally {
      setAddEndpointSaving(false);
    }
  };

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
    // 后端 GET /custom 直接返回明文 api_key，直接回填即可
    const plainKey = cm.api_key || "";
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
      context_window: String(cm.context_window || 131072),
      supports_vision: cm.supports_vision || false,
    });
    setCustomPickerOpen?.(false);
    setFormOpen(true);
  };

  const handleSaveCustom = async () => {
    setBusy(true);
    // 记录当前滚动位置，保存后恢复（避免每次添加都跳回顶部）
    const scrollY = window.scrollY;
    const scrollContainer = document.querySelector('[class*="scroll"]') || document.documentElement;
    const containerScrollTop = scrollContainer instanceof HTMLElement ? scrollContainer.scrollTop : 0;
    try {
      const payload: CustomModelPayload = {
        model_id: form.model_id.trim(),
        name: form.name.trim(),
        provider: form.provider,
        model_name: form.model_name.trim(),
        api_base: form.api_base.trim(),
        api_key: form.api_key,
        max_tokens: Number(form.max_tokens) || 8192,
        temperature: Number(form.temperature) || 0.7,
        context_window: Number(form.context_window) || 131072,
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
      // 恢复滚动位置（等待 refresh 重新渲染后）
      setTimeout(() => {
        window.scrollTo(0, scrollY);
        if (scrollContainer instanceof HTMLElement) scrollContainer.scrollTop = containerScrollTop;
      }, 100);
    } catch (err) {
      console.error("Failed to save custom model:", err);
      showToast(errorMessage(err) || "保存失败", "error");
    } finally {
      setBusy(false);
    }
  };

  // ── 快速接入：拉取模型列表 ──
  const handleQuickFetch = async () => {
    if (!quickApiKey.trim() || !quickApiBase.trim()) {
      showToast("请先填写 API Key 和端点地址", "error");
      return;
    }
    setQuickPickerOpen(true);
    setQuickModels([]);
    setQuickError(null);
    setQuickSelected(new Set());
    setQuickLoading(true);
    try {
      const list = await fetchRemoteModelsDirect(quickApiKey.trim(), quickApiBase.trim());
      setQuickModels(list);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "拉取失败，请检查 API Key 与端点";
      try {
        const body = err as unknown as { detail?: string };
        setQuickError(body?.detail || msg);
      } catch {
        setQuickError(msg);
      }
    } finally {
      setQuickLoading(false);
    }
  };

  // ── 快速接入：多选/取消选择模型 ──
  const handleQuickToggleSelect = (modelId: string) => {
    setQuickSelected((prev) => {
      const next = new Set(prev);
      if (next.has(modelId)) next.delete(modelId);
      else next.add(modelId);
      return next;
    });
  };

  // ── 快速接入：批量添加选中的模型 ──
  const handleQuickAddSelected = async () => {
    if (quickSelected.size === 0) {
      showToast("请至少选择一个模型", "error");
      return;
    }
    setQuickAdding(true);
    let success = 0;
    let failed = 0;
    for (const modelId of quickSelected) {
      try {
        const modelInfo = quickModels.find((m) => m.id === modelId);
        const payload: CustomModelPayload = {
          model_id: `custom-${modelId}`,
          name: modelId,
          provider: "openai",
          model_name: modelId,
          api_base: quickApiBase.trim(),
          api_key: quickApiKey.trim(),
          max_tokens: 8192,
          temperature: 0.7,
          context_window: modelInfo?.context_window || 131072,
          enabled: true,
          supports_vision: false,
        };
        await createCustomModel(payload);
        success++;
      } catch (err) {
        console.error(`添加模型 ${modelId} 失败:`, err);
        failed++;
      }
    }
    setQuickAdding(false);
    setQuickPickerOpen(false);
    setQuickSelected(new Set());
    await refresh();  // 刷新列表
    if (failed === 0) {
      showToast(`成功添加 ${success} 个模型`, "success");
    } else {
      showToast(`添加完成：成功 ${success} 个，失败 ${failed} 个`, "error");
    }
  };

  // ── 自定义模型卡片：内联展开编辑 ──
  const handleExpandEdit = (cm: CustomModel) => {
    if (expandedId === cm.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(cm.id);
    setEditForm({
      model_id: cm.model_id,
      name: cm.name,
      provider: cm.provider,
      model_name: cm.model_name,
      api_base: cm.api_base,
      api_key: cm.api_key || "",
      max_tokens: String(cm.max_tokens),
      temperature: String(cm.temperature),
      context_window: String(cm.context_window || 131072),
      supports_vision: cm.supports_vision || false,
    });
    setEditInitialKey(cm.api_key || "");
    setEditRemoteOpen(false);
    setEditRemoteModels([]);
    setEditRemoteError(null);
  };

  const handleEditFetchRemote = async () => {
    if (!editForm.api_key.trim() || !editForm.api_base.trim()) {
      showToast("请先填写 API Key 和端点地址", "error");
      return;
    }
    setEditRemoteOpen(true);
    setEditRemoteModels([]);
    setEditRemoteError(null);
    setEditRemoteLoading(true);
    try {
      const list = await fetchRemoteModelsDirect(editForm.api_key.trim(), editForm.api_base.trim());
      setEditRemoteModels(list);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "拉取失败";
      try {
        const body = err as unknown as { detail?: string };
        setEditRemoteError(body?.detail || msg);
      } catch { setEditRemoteError(msg); }
    } finally {
      setEditRemoteLoading(false);
    }
  };

  const handleEditAddModel = async (modelId: string, contextWindow?: number) => {
    try {
      const payload: CustomModelPayload = {
        model_id: `custom-${modelId}`,
        name: modelId,
        provider: "openai",
        model_name: modelId,
        api_base: editForm.api_base.trim(),
        api_key: editForm.api_key.trim(),
        max_tokens: 8192,
        temperature: 0.7,
        context_window: contextWindow || 131072,
        enabled: true,
        supports_vision: false,
      };
      await createCustomModel(payload);
      showToast(`已添加模型 ${modelId}`, "success");
      await refresh();  // 刷新列表
    } catch (err) {
      console.error("添加模型失败:", err);
      showToast(errorMessage(err) || "添加失败", "error");
    }
  };

  const handleEditSave = async () => {
    if (!expandedId) return;
    setEditSaving(true);
    try {
      const patch: Partial<CustomModelPayload> = {
        name: editForm.name.trim(),
        provider: editForm.provider,
        model_name: editForm.model_name.trim(),
        api_base: editForm.api_base.trim(),
        max_tokens: Number(editForm.max_tokens) || 8192,
        temperature: Number(editForm.temperature) || 0.7,
        context_window: Number(editForm.context_window) || 131072,
        supports_vision: editForm.supports_vision,
      };
      // API Key 三态语义
      if (editForm.api_key === editInitialKey) {
        // 未变，不传
      } else if (editForm.api_key === "") {
        patch.api_key = ""; // 主动清空
      } else {
        patch.api_key = editForm.api_key; // 新值
      }
      await updateCustomModel(expandedId, patch);
      showToast("保存成功", "success");
      setExpandedId(null);
      await refresh();  // 保存后刷新，确保 customModels 包含最新的 api_key 等字段
    } catch (err) {
      console.error("保存失败:", err);
      showToast(errorMessage(err) || "保存失败", "error");
    } finally {
      setEditSaving(false);
    }
  };

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
      {/* 自定义模型（可折叠，含 custom 类供应商如本地网关） */}
      <div>
        {/* 可折叠标题栏 */}
        <div
          onClick={toggleCustomCollapsed}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: customCollapsed ? 0 : "12px",
            cursor: "pointer",
            padding: "8px 10px",
            borderRadius: "var(--radius-md)",
            background: customCollapsed ? "var(--bg-level-2)" : "transparent",
            userSelect: "none",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <ChevronRight style={{
              width: "14px", height: "14px", color: "var(--text-level-3)",
              transition: "transform 0.2s",
              transform: customCollapsed ? "rotate(0deg)" : "rotate(90deg)",
            }} />
            <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
              {t("settings.model.custom.title")}
            </h3>
            <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>
              {manualModels.length} 个模型{customProviders.length > 0 && ` · ${customProviders.length} 个端点`}
            </span>
          </div>
          {!customCollapsed && (
            <button
              onClick={(e) => { e.stopPropagation(); setAddEndpointOpen(true); }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
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
              <Plus style={{ width: "12px", height: "12px" }} />
              添加端点
            </button>
          )}
        </div>

        {!customCollapsed && (
        <>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "0 0 12px 22px" }}>
            添加自定义 OpenAI 兼容端点，配置一次 Key 后可添加多个模型，与官方供应商体验一致。
          </p>

          {/* 添加端点按钮 */}
          <div style={{ marginBottom: "12px", paddingLeft: "22px" }}>
            <button
              onClick={() => setAddEndpointOpen(true)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 14px",
                borderRadius: "var(--radius-sm)",
                border: "1px dashed var(--border-primary)",
                background: "transparent",
                color: "var(--text-level-2)",
                cursor: "pointer",
                fontSize: "12px",
                fontWeight: "500",
              }}
            >
              <Plus style={{ width: "12px", height: "12px" }} />
              添加自定义端点
            </button>
          </div>

          {/* 自定义端点列表（复用 ProviderCard，与官方供应商 100% 同构） */}
          {customProviders.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "16px", paddingLeft: "22px" }}>
              {customProviders.map((p) => (
                <ProviderCard
                  key={p.id}
                  provider={p}
                  editing={cpEditing === p.id}
                  keyInput={cpKeyInput}
                  baseInput={cpBaseInput}
                  savingProvider={cpSaving}
                  savedProvider={cpSaved}
                  onOpenEdit={() => openCpProvider(p.id)}
                  onCloseEdit={() => setCpEditing(null)}
                  onKeyChange={setCpKeyInput}
                  onBaseChange={setCpBaseInput}
                  onSaveProvider={() => handleSaveCpProvider(p.id)}
                  onClearKey={() => handleClearCpKey(p.id)}
                  enabledModels={getEnabled(p.id)}
                  onAddModel={(mid) => addModel(p.id, mid)}
                  onRemoveModel={(mid) => removeModel(p.id, mid)}
                  onFetchRemote={() => handleFetchCpRemote(p.id)}
                  remotePickerOpen={cpRemotePickerOpen === p.id}
                  remoteModels={cpRemoteModels}
                  remoteLoading={cpRemoteLoading}
                  remoteError={cpRemoteError}
                  onCloseRemotePicker={() => setCpRemotePickerOpen(null)}
                  onTestConnection={testConnection}
                  t={t}
                  hideBaseUrl={false}
                  providerDisabled={isProviderDisabled(p.id)}
                  onToggleDisabled={() => setProviderDisabled(p.id, !isProviderDisabled(p.id))}
                />
              ))}
            </div>
          )}

          {/* 旧版手动创建的单模型（保留兼容，标记为旧版） */}
          {manualModels.length > 0 && (
            <div style={{ paddingLeft: "22px" }}>
              <div style={{ fontSize: "12px", fontWeight: "500", color: "var(--text-level-3)", marginBottom: "8px" }}>
                旧版单模型（建议迁移到自定义端点）
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {manualModels.map((cm) => (
                  <div key={cm.id} style={{
                    padding: "8px 12px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--border-primary)",
                    background: "var(--bg-level-2)",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: "12px", fontWeight: "500", color: "var(--text-level-1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {cm.name}
                      </div>
                      <div style={{ fontSize: "11px", color: "var(--text-level-4)", fontFamily: "monospace" }}>
                        {cm.model_name} · {cm.api_base}
                      </div>
                    </div>
                    <SwitchButton checked={cm.enabled} onChange={() => handleToggleCustom(cm)} />
                    <button
                      onClick={() => handleDeleteCustom(cm)}
                      style={{
                        display: "inline-flex", alignItems: "center", justifyContent: "center",
                        width: "24px", height: "24px", padding: 0, border: "none",
                        background: "transparent", cursor: "pointer", color: "var(--text-level-4)",
                      }}
                    >
                      <Trash2 style={{ width: "13px", height: "13px" }} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
        )}
      </div>

      {/* 纹身图模型（生图专用 BYOK） */}
      <TattooImageConfigSection />

      {/* 备用识图模型（双轨 BYOK） */}
      <VisionConfigSection />

      {/* Provider Base URL 覆盖（深水区端点配置） */}
      <ProviderBaseUrlOverride />

      {/* 添加自定义端点弹窗（Portal 渲染到 body，脱离 Panel 的 transform 层叠上下文） */}
      {addEndpointOpen && createPortal(
        <div data-portal-popover style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.3)",
          display: "flex", alignItems: "center", justifyContent: "center", zIndex: 2000,
        }} onClick={() => !addEndpointSaving && setAddEndpointOpen(false)}>
          <div style={{
            background: "var(--bg-level-1)", borderRadius: "var(--radius-lg)",
            padding: "20px", width: "420px", maxWidth: "90vw",
            boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
          }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ fontSize: "15px", fontWeight: "600", margin: "0 0 16px 0", color: "var(--text-level-1)" }}>
              添加自定义端点
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div>
                <label style={{ fontSize: "12px", color: "var(--text-level-2)", display: "block", marginBottom: "4px" }}>端点名称</label>
                <input
                  value={addEndpointName}
                  onChange={(e) => setAddEndpointName(e.target.value)}
                  placeholder="如：我的 OpenAI 兼容服务"
                  style={{
                    width: "100%", padding: "8px 10px", borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
                    fontSize: "13px", color: "var(--text-level-1)", outline: "none", boxSizing: "border-box",
                  }}
                />
              </div>
              <div>
                <label style={{ fontSize: "12px", color: "var(--text-level-2)", display: "block", marginBottom: "4px" }}>API Base URL</label>
                <input
                  value={addEndpointBase}
                  onChange={(e) => setAddEndpointBase(e.target.value)}
                  placeholder="https://api.example.com/v1"
                  style={{
                    width: "100%", padding: "8px 10px", borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
                    fontSize: "13px", color: "var(--text-level-1)", outline: "none", boxSizing: "border-box",
                    fontFamily: "monospace",
                  }}
                />
              </div>
              <div>
                <label style={{ fontSize: "12px", color: "var(--text-level-2)", display: "block", marginBottom: "4px" }}>描述（可选）</label>
                <input
                  value={addEndpointDesc}
                  onChange={(e) => setAddEndpointDesc(e.target.value)}
                  placeholder="简短描述这个端点"
                  style={{
                    width: "100%", padding: "8px 10px", borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
                    fontSize: "13px", color: "var(--text-level-1)", outline: "none", boxSizing: "border-box",
                  }}
                />
              </div>
              <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: 0 }}>
                API Key 将在端点创建后，在端点卡片的"配置"中填写。
              </p>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "16px" }}>
              <button
                onClick={() => setAddEndpointOpen(false)}
                disabled={addEndpointSaving}
                style={{
                  padding: "7px 16px", borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-primary)", background: "transparent",
                  color: "var(--text-level-2)", cursor: "pointer", fontSize: "13px",
                }}
              >
                取消
              </button>
              <button
                onClick={handleCreateEndpoint}
                disabled={addEndpointSaving || !addEndpointName.trim() || !addEndpointBase.trim()}
                style={{
                  padding: "7px 16px", borderRadius: "var(--radius-sm)", border: "none",
                  background: "var(--color-primary)", color: "#fff", cursor: "pointer",
                  fontSize: "13px", fontWeight: "500",
                  opacity: (addEndpointSaving || !addEndpointName.trim() || !addEndpointBase.trim()) ? 0.6 : 1,
                }}
              >
                {addEndpointSaving ? "添加中..." : "添加"}
              </button>
            </div>
          </div>
        </div>
      , document.body)}
    </div>
  );
}