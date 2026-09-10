"use client";

/**
 * ProviderCard —— 模型 Provider 极简卡片（VS Code 风格重构）
 *
 * 核心设计：
 * - 拍平多层折叠嵌套：卡片头部一行涵盖厂商图标、名称、状态、已启用模型预览与配置主按钮
 * - 展开时直接提供 API Key 录入（小眼睛明文查看 + 复制）、连通性测试、推荐模型 Chip 与拉取
 * - 支持禁用/启用总开关
 */
import { useState } from "react";
import { ChevronDown, ExternalLink, Globe, Plus, Trash2, Wifi, X, Zap, Check } from "lucide-react";
import type { RemoteModelInfo, TestConnectionRequest, TestConnectionResponse } from "@/hooks/useProviderConfig";
import { ApiKeyInput } from "@/components/ApiKeyInput";
import { RemoteModelPicker } from "@/components/RemoteModelPicker";
import { SwitchButton } from "@/components/SwitchButton";
import { maskApiKey } from "./constants";
import { ProviderIcon } from "./ProviderIcon";

export const RECOMMENDED_TEXT_NEW = new Set([
  // DeepSeek
  "deepseek-v4-flash",
  // 通义千问
  "qwen3.8-max", "qwen3.7-max", "qwen3.7-plus",
  // Google Gemini
  "gemini-3.6-flash", "gemini-3.5-flash",
  // 智谱 GLM
  "glm-5.1", "glm-5", "glm-4.7-flash",
  // 月之暗面 Kimi
  "kimi-k2.7-code",
  // MiniMax
  "minimax-m2.5",
  // 商汤日日新
  "sensenova-deepseek-v4-flash", "sensenova-6.7-flash-lite",
]);

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
  hideBaseUrl?: boolean;
  providerDisabled?: boolean;
  onToggleDisabled?: () => void;
}

export function ProviderCard({
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
  const [customInput, setCustomInput] = useState("");
  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState<TestConnectionResponse | null>(null);

  const isConfigured = p.has_key || p.api_base_override;
  const recommended = p.models.map((m) => m.id);
  const enabledSet = new Set(enabledModels);
  const quickAddList = recommended.filter((m) => !enabledSet.has(m) && RECOMMENDED_TEXT_NEW.has(m));

  const handleCustomAdd = () => {
    const id = customInput.trim();
    if (!id) return;
    onAddModel(id);
    setCustomInput("");
  };

  const handleTestConnection = async () => {
    setTestLoading(true);
    setTestResult(null);
    try {
      const payload: TestConnectionRequest = { provider_id: p.id };
      const draftKey = keyInput.trim();
      const draftBase = baseInput.trim();
      if (draftKey) payload.api_key = draftKey;
      if (draftBase) payload.api_base = draftBase;
      const result = await onTestConnection(payload);
      setTestResult(result);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setTestResult({ ok: false, latency_ms: 0, detail: msg });
    } finally {
      setTestLoading(false);
    }
  };

  return (
    <div
      style={{
        borderRadius: "var(--radius-md)",
        border: `1px solid ${
          editing
            ? "color-mix(in srgb, var(--color-primary) 40%, var(--border-primary))"
            : providerDisabled
              ? "var(--border-secondary)"
              : "var(--border-primary)"
        }`,
        background: editing
          ? "color-mix(in srgb, var(--color-primary) 3%, var(--bg-level-2))"
          : "var(--bg-level-2)",
        opacity: providerDisabled ? 0.6 : 1,
        transition: "all var(--transition-fast)",
        overflow: "hidden",
      }}
    >
      {/* ── 头部总览行（VS Code 设置卡片标准高度）── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          padding: "10px 14px",
          cursor: "pointer",
          userSelect: "none",
        }}
        onClick={(e) => {
          // 点击非按钮区域切换编辑状态
          const target = e.target as HTMLElement;
          if (target.closest("button, a, input")) return;
          if (editing) onCloseEdit();
          else onOpenEdit();
        }}
      >
        {/* 厂商图标 */}
        <ProviderIcon providerId={p.id} size={20} />

        {/* 厂商名称与标签 */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", minWidth: 0 }}>
          <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-level-1)" }}>
            {p.name}
          </span>
          {p.free && p.id !== "doubao" && (
            <span
              style={{
                fontSize: "10px",
                padding: "1px 6px",
                borderRadius: "999px",
                background: "rgba(16,185,129,0.12)",
                color: "var(--color-success)",
                fontWeight: 500,
                lineHeight: 1.3,
              }}
            >
              含免费额度
            </span>
          )}
        </div>

        {/* 中间：已启用的旗舰模型微缩标签预览（让用户一眼看懂该厂商配置了什么） */}
        <div
          style={{
            flex: 1,
            minWidth: 0,
            display: "flex",
            alignItems: "center",
            gap: "4px",
            overflow: "hidden",
            marginLeft: "4px",
          }}
        >
          {enabledModels.slice(0, 2).map((m) => (
            <span
              key={m}
              style={{
                fontSize: "11px",
                fontFamily: "var(--font-geist-mono), monospace",
                padding: "1px 6px",
                borderRadius: "var(--radius-xs)",
                background: "var(--bg-level-1)",
                color: "var(--text-level-3)",
                border: "1px solid var(--border-secondary)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                maxWidth: "140px",
              }}
            >
              {m}
            </span>
          ))}
          {enabledModels.length > 2 && (
            <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>
              +{enabledModels.length - 2}
            </span>
          )}
          {enabledModels.length === 0 && (
            <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>
              {p.has_key ? "未激活模型" : "未配置 Key"}
            </span>
          )}
        </div>

        {/* 右侧控制区 */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexShrink: 0 }}>
          {/* 脱敏 Key 预览 */}
          {p.has_key && (
            <span
              style={{
                fontSize: "11px",
                color: "var(--text-level-4)",
                fontFamily: "monospace",
                display: "none",
              }}
            >
              {maskApiKey(p.api_key_masked)}
            </span>
          )}

          {/* 状态徽标 */}
          <span
            style={{
              fontSize: "11px",
              padding: "2px 8px",
              borderRadius: "999px",
              background: p.has_key ? "rgba(16,185,129,0.12)" : "rgba(107,114,128,0.12)",
              color: p.has_key ? "var(--color-success)" : "var(--text-level-4)",
              fontWeight: 500,
              lineHeight: 1.4,
            }}
          >
            {p.has_key ? t("settings.model.providers.configured") : t("settings.model.providers.notConfigured")}
          </span>

          {/* 厂商启用开关 */}
          {onToggleDisabled && (
            <SwitchButton
              checked={!providerDisabled}
              onChange={() => onToggleDisabled()}
            />
          )}

          {/* 清除 Key 按钮 */}
          {isConfigured && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onClearKey();
              }}
              disabled={savingProvider === p.id}
              title={t("settings.model.providers.clearKey")}
              className="mf-icon-btn"
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "26px",
                height: "26px",
                padding: 0,
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: "transparent",
                color: "var(--text-level-4)",
                cursor: "pointer",
              }}
            >
              <Trash2 style={{ width: "13px", height: "13px" }} />
            </button>
          )}

          {/* 主配置按钮 */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              if (editing) onCloseEdit();
              else onOpenEdit();
            }}
            style={{
              height: "28px",
              padding: "0 10px",
              borderRadius: "var(--radius-sm)",
              border: `1px solid ${editing ? "var(--color-primary)" : "var(--border-primary)"}`,
              background: editing ? "var(--color-primary-lighter)" : "var(--bg-level-1)",
              color: editing ? "var(--color-primary)" : "var(--text-level-2)",
              fontSize: "12px",
              fontWeight: 500,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            {editing ? "收起" : t("settings.model.providers.configure")}
            <ChevronDown
              style={{
                width: "12px",
                height: "12px",
                transform: editing ? "rotate(180deg)" : "rotate(0deg)",
                transition: "transform var(--transition-fast)",
              }}
            />
          </button>
        </div>
      </div>

      {/* ── 展开编辑区（直截了当，无需二次折叠）── */}
      {editing && (
        <div
          style={{
            padding: "14px",
            borderTop: "1px solid var(--border-secondary)",
            background: "var(--bg-level-1)",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}
        >
          {/* 官网与说明 */}
          {(p.website || p.description) && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px" }}>
              <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: 0 }}>
                {p.description || "填入官方 API Key 即可使用该服务商的大模型。"}
              </p>
              {p.website && (
                <a
                  href={p.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                    fontSize: "11px",
                    color: "var(--color-primary)",
                    textDecoration: "none",
                    whiteSpace: "nowrap",
                  }}
                >
                  <ExternalLink style={{ width: "11px", height: "11px" }} />
                  {t("settings.model.providers.website")}
                </a>
              )}
            </div>
          )}

          {/* API Key 输入行 */}
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <label style={{ fontSize: "12px", fontWeight: 500, color: "var(--text-level-2)" }}>
              {t("settings.model.providers.keyLabel")}
            </label>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div style={{ flex: 1 }}>
                <ApiKeyInput
                  value={keyInput}
                  onChange={onKeyChange}
                  placeholder={p.api_key_masked || "sk-..."}
                  showIcon={false}
                  settingKey={`api_key_${p.id}`}
                />
              </div>
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={testLoading}
                style={{
                  height: "32px",
                  padding: "0 12px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-primary)",
                  background: "var(--bg-level-2)",
                  color: "var(--text-level-2)",
                  fontSize: "12px",
                  cursor: testLoading ? "not-allowed" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "5px",
                  whiteSpace: "nowrap",
                }}
              >
                <Wifi style={{ width: "13px", height: "13px" }} />
                {testLoading ? "测试中…" : "测试连通性"}
              </button>
            </div>

            {/* 测试结果提示 */}
            {testResult && (
              <div
                style={{
                  fontSize: "11px",
                  padding: "4px 8px",
                  borderRadius: "var(--radius-sm)",
                  background: testResult.ok ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)",
                  color: testResult.ok ? "var(--color-success)" : "var(--color-danger, #ef4444)",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                {testResult.ok ? (
                  <>
                    <Check style={{ width: "12px", height: "12px" }} />
                    连通成功 · 延迟 {testResult.latency_ms}ms
                  </>
                ) : (
                  <>
                    <X style={{ width: "12px", height: "12px" }} />
                    {testResult.detail || "测试失败，请核对 API Key"}
                  </>
                )}
              </div>
            )}
          </div>

          {/* 高级模式下才显示的 Base URL 覆盖 */}
          {!hideBaseUrl && (
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label style={{ fontSize: "12px", color: "var(--text-level-3)", display: "flex", alignItems: "center", gap: "4px" }}>
                <Globe style={{ width: "12px", height: "12px" }} />
                {t("settings.model.providers.baseLabel")}（可选覆盖）
              </label>
              <input
                type="text"
                value={baseInput}
                onChange={(e) => onBaseChange(e.target.value)}
                placeholder={p.api_base}
                style={{
                  padding: "6px 10px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-primary)",
                  background: "var(--bg-level-2)",
                  fontSize: "12px",
                  color: "var(--text-level-2)",
                  outline: "none",
                  fontFamily: "monospace",
                  height: "32px",
                }}
              />
            </div>
          )}

          {/* 已启用模型与快捷添加 */}
          <div style={{ borderTop: "1px solid var(--border-secondary)", paddingTop: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ fontSize: "12px", fontWeight: 500, color: "var(--text-level-2)" }}>
                已激活使用的模型 ({enabledModels.length})
              </span>
              {p.has_key && (
                <button
                  type="button"
                  onClick={onFetchRemote}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                    border: "none",
                    background: "transparent",
                    color: "var(--color-primary)",
                    fontSize: "11px",
                    cursor: "pointer",
                    padding: 0,
                  }}
                >
                  <Zap style={{ width: "11px", height: "11px" }} />
                  {t("settings.model.providers.fetchRemote")}
                </button>
              )}
            </div>

            {/* 远程拉取弹窗 */}
            {remotePickerOpen && (
              <div style={{ marginBottom: "8px" }}>
                <RemoteModelPicker
                  providerId={p.id}
                  models={remoteModels}
                  enabledSet={enabledSet}
                  onAdd={onAddModel}
                  onClose={onCloseRemotePicker}
                  loading={remoteLoading}
                  error={remoteError}
                />
              </div>
            )}

            {/* 已启用模型 Chip 列表 */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "8px" }}>
              {enabledModels.map((mid) => (
                <span
                  key={mid}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    height: "26px",
                    padding: "0 6px 0 8px",
                    borderRadius: "var(--radius-sm)",
                    background: "color-mix(in srgb, var(--color-primary) 10%, transparent)",
                    border: "1px solid color-mix(in srgb, var(--color-primary) 25%, transparent)",
                    fontSize: "12px",
                    fontFamily: "monospace",
                    color: "var(--text-level-1)",
                  }}
                >
                  {mid}
                  <button
                    type="button"
                    onClick={() => onRemoveModel(mid)}
                    title="移除该模型"
                    style={{
                      border: "none",
                      background: "transparent",
                      padding: 0,
                      cursor: "pointer",
                      display: "inline-flex",
                      color: "var(--text-level-3)",
                    }}
                  >
                    <X style={{ width: "11px", height: "11px" }} />
                  </button>
                </span>
              ))}
              {enabledModels.length === 0 && (
                <span style={{ fontSize: "12px", color: "var(--text-level-4)" }}>
                  尚未激活模型。点击保存将自动为您激活推荐主力模型。
                </span>
              )}
            </div>

            {/* 推荐快捷添加 */}
            {quickAddList.length > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap", marginBottom: "8px" }}>
                <span style={{ fontSize: "11px", color: "var(--text-level-4)" }}>推荐添加：</span>
                {quickAddList.map((mid) => (
                  <button
                    key={mid}
                    type="button"
                    onClick={() => onAddModel(mid)}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "3px",
                      padding: "2px 8px",
                      borderRadius: "999px",
                      border: "1px dashed var(--border-primary)",
                      background: "transparent",
                      color: "var(--text-level-3)",
                      fontSize: "11px",
                      fontFamily: "monospace",
                      cursor: "pointer",
                    }}
                  >
                    <Plus style={{ width: "10px", height: "10px" }} />
                    {mid}
                  </button>
                ))}
              </div>
            )}

            {/* 自定义手动输入型号 */}
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
                  height: "28px",
                  padding: "0 8px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-primary)",
                  background: "var(--bg-level-2)",
                  fontSize: "11px",
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
                  height: "28px",
                  padding: "0 10px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-primary)",
                  background: "var(--bg-level-2)",
                  color: "var(--text-level-2)",
                  fontSize: "11px",
                  cursor: customInput.trim() ? "pointer" : "not-allowed",
                  opacity: customInput.trim() ? 1 : 0.5,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "3px",
                }}
              >
                <Plus style={{ width: "11px", height: "11px" }} />
                {t("settings.model.providers.addBtn")}
              </button>
            </div>
          </div>

          {/* 底部操作条：保存并启用主力模型 */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "8px", marginTop: "4px" }}>
            <button
              type="button"
              onClick={onCloseEdit}
              style={{
                height: "32px",
                padding: "0 14px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-primary)",
                background: "transparent",
                color: "var(--text-level-3)",
                fontSize: "12px",
                cursor: "pointer",
              }}
            >
              {t("common.cancel")}
            </button>
            <button
              type="button"
              onClick={onSaveProvider}
              disabled={savingProvider === p.id}
              className="mf-btn-primary"
              style={{
                height: "32px",
                padding: "0 16px",
                borderRadius: "var(--radius-sm)",
                border: "none",
                background: "var(--color-primary)",
                color: "#fff",
                fontSize: "12px",
                fontWeight: 500,
                cursor: savingProvider === p.id ? "not-allowed" : "pointer",
                opacity: savingProvider === p.id ? 0.7 : 1,
              }}
            >
              {savingProvider === p.id ? "保存中…" : "保存并激活"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
