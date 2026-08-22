"use client";

/**
 * ModelProvidersBasic —— 模型基础配置（归属 BasicSettingsView）
 * 从 ModelConfigSection.tsx 拆分，逻辑与行为零变化。
 */
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { useProviderConfig, type RemoteModelInfo } from "@/hooks/useProviderConfig";
import { ProviderCard } from "./ProviderCard";
import { useSettingsToast, errorMessage } from "@/lib/toastStore";
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
  const { showToast } = useSettingsToast();
  const {
    configs,
    loading,
    fetchProviderKey,
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

  // 2026-08-14：供应商列表级折叠（整行按钮，样式对齐实验主题/字体选择器）。
  // 供应商数量过多时默认折叠；持久化 localStorage，展开/收起状态刷新不丢。
  const [providersExpanded, setProvidersExpanded] = useState(() => {
    try {
      return localStorage.getItem("mfk_providers_list_expanded") === "true";
    } catch {
      return false;
    }
  });
  const toggleProvidersExpanded = () => {
    setProvidersExpanded((prev) => {
      const next = !prev;
      try { localStorage.setItem("mfk_providers_list_expanded", String(next)); } catch { /* noop */ }
      return next;
    });
  };

  // 过滤：official 在基础区展示，custom（如本地网关）移到高级区自定义模型
  const officialConfigs = configs.filter((c) => c.category !== "custom");
  const customConfigs = configs.filter((c) => c.category === "custom");

  const configuredCount = officialConfigs.filter((c) => c.has_key).length;

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

  const openProvider = async (pId: string, _apiBase: string, _override: boolean) => {
    setEditingProvider(pId);
    setBaseInput(""); // 基础区始终不使用 baseInput
    // 调用后端接口获取真实 API Key（明文），回填到输入框，让小眼睛/复制真正可用
    try {
      const realKey = await fetchProviderKey(pId);
      setKeyInput(realKey);
    } catch {
      // 获取失败时回退到脱敏 Key（至少能看到部分信息）
      const p = configs.find((c) => c.id === pId);
      setKeyInput(p?.api_key_masked || "");
    }
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
      showToast(errorMessage(err) || "保存失败", "error");
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
      showToast(errorMessage(err) || "清除失败", "error");
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
      <button
        onClick={toggleProvidersExpanded}
        style={{
          width: "100%",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
          padding: "8px 12px",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-primary)",
          background: "var(--bg-level-2)",
          cursor: "pointer",
          fontSize: "13px",
          color: "var(--text-level-2)",
          transition: "border-color var(--transition-fast)",
          marginBottom: providersExpanded ? "12px" : 0,
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <span style={{ fontWeight: "500", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {t("settings.model.providers.title")} ({officialConfigs.length})
          </span>
          <span style={{ fontSize: "11px", color: "var(--text-level-3)", flexShrink: 0 }}>
            {t("settings.model.providers.configured")} {configuredCount}
          </span>
        </span>
        <ChevronDown style={{
          width: 14, height: 14, flexShrink: 0, color: "var(--text-level-4)",
          transform: providersExpanded ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform var(--transition-fast)",
        }} />
      </button>

      {providersExpanded && (
        <>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "0 0 12px 0" }}>
            {t("settings.model.providers.desc")}
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {officialConfigs.map((p) => (
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
        </>
      )}
    </div>
  );
}