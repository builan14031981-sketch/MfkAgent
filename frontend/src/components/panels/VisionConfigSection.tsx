"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Eye, KeyRound, Globe, Cpu, Check, Download, Loader2 } from "lucide-react";
import { useProviderConfig } from "@/hooks/useProviderConfig";
import type { RemoteModelInfo } from "@/hooks/useProviderConfig";
import { useTranslation } from "@/hooks/useTranslation";
import { ApiKeyInput } from "@/components/ApiKeyInput";
import { apiPost } from "@/lib/api";

/** 内置识图服务商预设（Base URL 与默认模型名供快速填充） */
const VISION_PRESETS: { id: string; label: string; baseUrl: string; model: string }[] = [
  { id: "siliconflow", label: "SiliconFlow", baseUrl: "https://api.siliconflow.cn/v1", model: "Qwen/Qwen3-VL-32B-Instruct" },
  { id: "qwen-vl", label: "Qwen-VL (通义千问视觉)", baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-vl-max" },
  { id: "openai", label: "OpenAI (GPT-4o)", baseUrl: "https://api.openai.com/v1", model: "gpt-4o" },
  { id: "custom", label: "自定义", baseUrl: "", model: "" },
];

/** 防抖延迟（ms）：用户停止输入后等待多久才向后端发送保存请求 */
const DEBOUNCE_MS = 500;

/**
 * 备用识图模型（双轨 BYOK）配置卡片。
 *
 * 后端明文下发策略（V2 重构）：
 * - vision_api_key 后端直接返回明文，前端 ApiKeyInput 的 value 回填明文，
 *   用户点击"小眼睛"可随时查看/核对已保存的真实 Key。
 *
 * 防抖策略：
 * - vision_base_url / vision_model 输入框使用本地 draft state，
 *   用户连续输入时只更新 draft（无网络请求），停止输入 DEBOUNCE_MS 后才触发 updateSetting。
 * - 消除此前每次按键都调 updateSetting 的"性能炸弹"。
 * - 切换服务商时批量更新 baseUrl/model，draft 通过 useEffect 自动同步。
 */
export function VisionConfigSection() {
  const { t } = useTranslation();
  const { settings, updateSetting, hasVisionKey } = useProviderConfig();

  const [savingKey, setSavingKey] = useState(false);
  const [keySaved, setKeySaved] = useState(false);
  const [providerSaving, setProviderSaving] = useState<string | null>(null);

  // ── 拉取官方识图模型列表 ──
  const [fetchingVL, setFetchingVL] = useState(false);
  const [fetchVLError, setFetchVLError] = useState<string | null>(null);
  const [remoteVLModels, setRemoteVLModels] = useState<RemoteModelInfo[]>([]);
  const [showVLDropdown, setShowVLDropdown] = useState(false);
  const vlDropdownRef = useRef<HTMLDivElement>(null);

  const provider = settings?.vision_provider || "";
  const baseUrl = settings?.vision_base_url || "";
  const model = settings?.vision_model || "";
  const visionKey = settings?.vision_api_key || ""; // 后端明文下发

  // ── API Key 草稿：从后端明文同步 ──
  // 首次加载 + 保存/清除后 refresh 时同步；用户编辑时仅更新 draft 不触发同步。
  const [apiKeyDraft, setApiKeyDraft] = useState(visionKey);
  useEffect(() => {
    setApiKeyDraft(visionKey);
  }, [visionKey]);

  // ── Base URL 草稿 + 防抖保存 ──
  const [baseUrlDraft, setBaseUrlDraft] = useState(baseUrl);
  useEffect(() => {
    setBaseUrlDraft(baseUrl);
  }, [baseUrl]);
  useEffect(() => {
    if (baseUrlDraft === baseUrl) return; // 与后端一致，无需保存
    const timer = setTimeout(() => {
      updateSetting("vision_base_url", baseUrlDraft);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [baseUrlDraft, baseUrl, updateSetting]);

  // ── Model 草稿 + 防抖保存 ──
  const [modelDraft, setModelDraft] = useState(model);
  useEffect(() => {
    setModelDraft(model);
  }, [model]);
  useEffect(() => {
    if (modelDraft === model) return; // 与后端一致，无需保存
    const timer = setTimeout(() => {
      updateSetting("vision_model", modelDraft);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [modelDraft, model, updateSetting]);

  const handleProviderChange = async (newProvider: string) => {
    setProviderSaving("vision_provider");
    const preset = VISION_PRESETS.find((p) => p.id === newProvider);
    try {
      // 批量更新：provider + 预设的 baseUrl / model（自定义则不清空已有值）
      await updateSetting("vision_provider", newProvider);
      if (preset && preset.id !== "custom") {
        await updateSetting("vision_base_url", preset.baseUrl);
        await updateSetting("vision_model", preset.model);
      }
    } catch (err) {
      console.error("Failed to save vision provider:", err);
    } finally {
      setProviderSaving(null);
    }
  };

  const handleSaveApiKey = async () => {
    // 明文回显后 apiKeyDraft 可能与后端一致（未改），此时无需保存
    if (apiKeyDraft === visionKey) return;
    setSavingKey(true);
    try {
      await updateSetting("vision_api_key", apiKeyDraft.trim());
      setKeySaved(true);
      setTimeout(() => setKeySaved(false), 2000);
    } catch (err) {
      console.error("Failed to save vision api key:", err);
    } finally {
      setSavingKey(false);
    }
  };

  const handleClearApiKey = async () => {
    setSavingKey(true);
    try {
      await updateSetting("vision_api_key", "");
      setKeySaved(true);
      setTimeout(() => setKeySaved(false), 2000);
    } catch (err) {
      console.error("Failed to clear vision api key:", err);
    } finally {
      setSavingKey(false);
    }
  };

  // 已配置判定：provider + model 非空，且 vision_api_key 非空（明文）
  const isConfigured = !!(provider && model && hasVisionKey());

  // ── 点击外部关闭下拉 ──
  useEffect(() => {
    if (!showVLDropdown) return;
    const handler = (e: MouseEvent) => {
      if (vlDropdownRef.current && !vlDropdownRef.current.contains(e.target as Node)) {
        setShowVLDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showVLDropdown]);

  // ── 拉取官方识图模型列表 ──
  const handleFetchVLModels = useCallback(async () => {
    const key = apiKeyDraft.trim() || visionKey;
    if (!key) {
      setFetchVLError("请先配置 API Key");
      return;
    }
    const apiBase = (baseUrlDraft || baseUrl || "").trim();
    if (!apiBase) {
      setFetchVLError("请先配置 API Base URL");
      return;
    }
    setFetchingVL(true);
    setFetchVLError(null);
    setRemoteVLModels([]);
    setShowVLDropdown(true);
    try {
      const data = await apiPost<{ models: RemoteModelInfo[] }>("/api/models/fetch_remote", {
        api_key: key,
        api_base: apiBase,
        filter_vision: true,
      });
      const list = data.models || [];
      if (list.length === 0) {
        setFetchVLError("未找到识图模型，请确认该服务商支持多模态");
      } else {
        setRemoteVLModels(list);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "拉取失败，请检查 API Key 和 API Base";
      setFetchVLError(typeof msg === "string" ? msg : "拉取失败");
    } finally {
      setFetchingVL(false);
    }
  }, [apiKeyDraft, visionKey, baseUrlDraft, baseUrl]);

  const handleSelectVLModel = (modelName: string) => {
    setModelDraft(modelName);
    setShowVLDropdown(false);
    setFetchVLError(null);
  };

  return (
    <div style={{
      padding: "14px",
      borderRadius: "var(--radius-md)",
      border: `1px solid ${isConfigured ? "color-mix(in srgb, var(--color-primary) 35%, var(--border-primary))" : "var(--border-primary)"}`,
      background: isConfigured
        ? "color-mix(in srgb, var(--color-primary) 4%, var(--bg-level-2))"
        : "var(--bg-level-2)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
        <Eye style={{ width: "15px", height: "15px", color: "var(--color-primary)" }} />
        <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
          {t("settings.model.vision.title")}
        </h3>
        <span style={{
          fontSize: "11px",
          padding: "1px 8px",
          borderRadius: "999px",
          background: isConfigured ? "rgba(16,185,129,0.12)" : "rgba(107,114,128,0.12)",
          color: isConfigured ? "var(--color-success)" : "var(--text-level-3)",
        }}>
          {isConfigured ? t("settings.model.vision.configured") : t("settings.model.vision.notConfigured")}
        </span>
      </div>
      <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "0 0 12px 0" }}>
        {t("settings.model.vision.desc")}
      </p>

      {/* 服务商选择 */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px" }}>
        <label style={{
          minWidth: "70px",
          fontSize: "12px",
          color: "var(--text-level-2)",
          display: "flex",
          alignItems: "center",
          gap: "4px",
          flexShrink: 0,
        }}>
          <Cpu style={{ width: "12px", height: "12px" }} />
          {t("settings.model.vision.provider")}
        </label>
        <select
          value={provider || "custom"}
          onChange={(e) => handleProviderChange(e.target.value)}
          disabled={providerSaving != null}
          style={{
            flex: 1,
            padding: "7px 10px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-1)",
            fontSize: "13px",
            color: "var(--text-level-2)",
            outline: "none",
            opacity: providerSaving ? 0.7 : 1,
          }}
        >
          {!provider && <option value="custom">{t("settings.model.vision.selectProvider")}</option>}
          {VISION_PRESETS.map((p) => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
      </div>

      {/* Base URL（防抖保存：连续输入只更新 draft，停止 500ms 后才发请求） */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px" }}>
        <label style={{
          minWidth: "70px",
          fontSize: "12px",
          color: "var(--text-level-2)",
          display: "flex",
          alignItems: "center",
          gap: "4px",
          flexShrink: 0,
        }}>
          <Globe style={{ width: "12px", height: "12px" }} />
          {t("settings.model.vision.baseUrl")}
        </label>
        <input
          type="text"
          value={baseUrlDraft}
          onChange={(e) => setBaseUrlDraft(e.target.value)}
          placeholder="https://api.example.com/v1"
          style={{
            flex: 1,
            padding: "7px 10px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-1)",
            fontSize: "13px",
            color: "var(--text-level-2)",
            outline: "none",
          }}
        />
      </div>

      {/* 模型名（防抖保存 + 拉取官方模型） */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: "10px", marginBottom: "10px" }}>
        <label style={{
          minWidth: "70px",
          fontSize: "12px",
          color: "var(--text-level-2)",
          flexShrink: 0,
          paddingTop: "7px",
        }}>
          {t("settings.model.vision.model")}
        </label>
        <div ref={vlDropdownRef} style={{ flex: 1, position: "relative" }}>
          <div style={{ display: "flex", gap: "6px" }}>
            <input
              type="text"
              value={modelDraft}
              onChange={(e) => setModelDraft(e.target.value)}
              placeholder="qwen-vl-max"
              style={{
                flex: 1,
                padding: "7px 10px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-1)",
                fontSize: "13px",
                color: "var(--text-level-2)",
                outline: "none",
              }}
            />
            <button
              onClick={handleFetchVLModels}
              disabled={fetchingVL}
              title="从服务商拉取可用的识图模型列表"
              style={{
                padding: "7px 10px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-primary)",
                background: fetchingVL ? "var(--bg-level-2)" : "var(--bg-level-1)",
                color: "var(--text-level-2)",
                cursor: fetchingVL ? "not-allowed" : "pointer",
                fontSize: "12px",
                whiteSpace: "nowrap",
                display: "flex",
                alignItems: "center",
                gap: "4px",
                opacity: fetchingVL ? 0.6 : 1,
              }}
            >
              {fetchingVL ? (
                <Loader2 style={{ width: "12px", height: "12px", animation: "spin 1s linear infinite" }} />
              ) : (
                <Download style={{ width: "12px", height: "12px" }} />
              )}
              拉取模型
            </button>
          </div>

          {/* 错误提示 */}
          {fetchVLError && !showVLDropdown && (
            <div style={{
              marginTop: "4px",
              fontSize: "11px",
              color: "var(--color-danger, #ef4444)",
            }}>
              {fetchVLError}
            </div>
          )}

          {/* 模型下拉列表 */}
          {showVLDropdown && (
            <div style={{
              position: "absolute",
              top: "100%",
              left: 0,
              right: 0,
              zIndex: 100,
              marginTop: "2px",
              maxHeight: "200px",
              overflowY: "auto",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-1)",
              boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
            }}>
              {fetchingVL ? (
                <div style={{
                  padding: "12px",
                  fontSize: "12px",
                  color: "var(--text-level-3)",
                  textAlign: "center",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "6px",
                }}>
                  <Loader2 style={{ width: "12px", height: "12px", animation: "spin 1s linear infinite" }} />
                  正在拉取...
                </div>
              ) : fetchVLError ? (
                <div style={{
                  padding: "12px",
                  fontSize: "12px",
                  color: "var(--color-danger, #ef4444)",
                  textAlign: "center",
                }}>
                  {fetchVLError}
                </div>
              ) : remoteVLModels.length === 0 ? (
                <div style={{
                  padding: "12px",
                  fontSize: "12px",
                  color: "var(--text-level-3)",
                  textAlign: "center",
                }}>
                  暂无可用模型
                </div>
              ) : (
                remoteVLModels.map((m) => (
                  <div
                    key={m.id}
                    onClick={() => handleSelectVLModel(m.id)}
                    style={{
                      padding: "7px 10px",
                      fontSize: "12px",
                      color: m.id === modelDraft ? "var(--color-primary)" : "var(--text-level-2)",
                      background: m.id === modelDraft ? "color-mix(in srgb, var(--color-primary) 8%, transparent)" : "transparent",
                      cursor: "pointer",
                      borderBottom: "1px solid var(--border-primary)",
                      transition: "background 0.15s",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                    onMouseEnter={(e) => {
                      if (m.id !== modelDraft) {
                        (e.target as HTMLElement).style.background = "var(--bg-level-2)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (m.id !== modelDraft) {
                        (e.target as HTMLElement).style.background = "transparent";
                      }
                    }}
                  >
                    <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {m.id}
                    </span>
                    {m.context_window != null && (
                      <span style={{
                        fontSize: "10px",
                        fontFamily: "monospace",
                        color: "var(--text-level-4)",
                        background: "var(--bg-level-2)",
                        padding: "1px 5px",
                        borderRadius: "3px",
                        flexShrink: 0,
                      }}
                        title={`上下文窗口: ${m.context_window.toLocaleString()} tokens`}
                      >
                        {m.context_window >= 1_000_000
                          ? `${(m.context_window / 1_000_000).toFixed(1)}M`
                          : `${(m.context_window / 1_000).toFixed(0)}K`}
                      </span>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* API Key（明文回显 + 小眼睛查看） */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
        <label style={{
          minWidth: "70px",
          fontSize: "12px",
          color: "var(--text-level-2)",
          display: "flex",
          alignItems: "center",
          gap: "4px",
          flexShrink: 0,
        }}>
          <KeyRound style={{ width: "12px", height: "12px" }} />
          {t("settings.model.vision.apiKey")}
        </label>
        <ApiKeyInput
          value={apiKeyDraft}
          onChange={setApiKeyDraft}
          placeholder="sk-..."
          showIcon={false}
        />
        <button
          onClick={handleSaveApiKey}
          disabled={savingKey || apiKeyDraft === visionKey}
          style={{
            padding: "7px 16px",
            borderRadius: "var(--radius-sm)",
            border: "none",
            background: "var(--color-primary)",
            color: "#fff",
            cursor: savingKey || apiKeyDraft === visionKey ? "not-allowed" : "pointer",
            fontSize: "12px",
            fontWeight: "500",
            opacity: savingKey || apiKeyDraft === visionKey ? 0.5 : 1,
            whiteSpace: "nowrap",
          }}
        >
          {t("common.save")}
        </button>
        {visionKey && (
          <button
            onClick={handleClearApiKey}
            disabled={savingKey}
            style={{
              padding: "7px 12px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid transparent",
              background: "transparent",
              cursor: "pointer",
              fontSize: "12px",
              color: "var(--color-danger, #ef4444)",
              opacity: savingKey ? 0.5 : 1,
              whiteSpace: "nowrap",
            }}
          >
            {t("settings.model.providers.clearKey")}
          </button>
        )}
        {keySaved && (
          <span style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "12px", color: "var(--color-success)" }}>
            <Check style={{ width: "12px", height: "12px" }} />
            {t("common.saved")}
          </span>
        )}
      </div>
    </div>
  );
}
