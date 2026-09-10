"use client";

/**
 * ModelProvidersBasic —— 模型服务商极简配置（VS Code 风格重构）
 *
 * 核心特性：
 * - 支持全局一键折叠收起 / 展开，解决长列表占地过大痛点
 * - 快速搜索与状态过滤（全部 / 已配置 / 热门原厂）
 * - 保存 Key 时自动激活主力推荐模型
 * - 已配置 Key 的服务商自动置顶
 */
import { useState, useMemo } from "react";
import { Search, ChevronDown, Check, Zap } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { useProviderConfig, type RemoteModelInfo } from "@/hooks/useProviderConfig";
import { ProviderCard, RECOMMENDED_TEXT_NEW } from "./ProviderCard";
import { useSettingsToast, errorMessage } from "@/lib/toastStore";

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
  const [baseInput, setBaseInput] = useState("");
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [savedProvider, setSavedProvider] = useState<string | null>(null);

  // 全局折叠状态：支持收起/展开，持久化到 localStorage
  const [isCollapsed, setIsCollapsed] = useState(() => {
    try {
      return localStorage.getItem("mfk_providers_list_collapsed") === "true";
    } catch {
      return false;
    }
  });

  const toggleCollapsed = () => {
    setIsCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("mfk_providers_list_collapsed", String(next));
      } catch {
        /* noop */
      }
      return next;
    });
  };

  // 搜索与状态过滤
  const [searchQuery, setSearchQuery] = useState("");
  const [filterMode, setFilterMode] = useState<"all" | "configured" | "hot">("all");

  // 远程模型拉取状态
  const [remotePickerOpen, setRemotePickerOpen] = useState<string | null>(null);
  const [remoteModels, setRemoteModels] = useState<RemoteModelInfo[]>([]);
  const [remoteLoading, setRemoteLoading] = useState(false);
  const [remoteError, setRemoteError] = useState<string | null>(null);

  const officialConfigs = configs.filter((c) => c.category !== "custom");
  const configuredConfigs = officialConfigs.filter((c) => c.has_key);
  const configuredCount = configuredConfigs.length;

  // 智能排序与过滤：已配置的排在最前，其次热门原厂
  const filteredAndSorted = useMemo(() => {
    let list = [...officialConfigs];

    if (filterMode === "configured") {
      list = list.filter((c) => c.has_key);
    } else if (filterMode === "hot") {
      list = list.filter((c) => c.tier !== "free");
    }

    const q = searchQuery.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.id.toLowerCase().includes(q) ||
          (c.description && c.description.toLowerCase().includes(q))
      );
    }

    return list.sort((a, b) => {
      if (a.has_key && !b.has_key) return -1;
      if (!a.has_key && b.has_key) return 1;
      return 0;
    });
  }, [officialConfigs, filterMode, searchQuery]);

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
    setBaseInput("");
    try {
      const realKey = await fetchProviderKey(pId);
      setKeyInput(realKey);
    } catch {
      const p = configs.find((c) => c.id === pId);
      setKeyInput(p?.api_key_masked || "");
    }
  };

  const handleSaveProvider = async (pId: string) => {
    setSavingProvider(pId);
    try {
      await saveProviderKey(pId, keyInput || undefined, undefined);
      flashSaved(pId);

      if (keyInput.trim()) {
        const currentEnabled = getEnabled(pId);
        if (currentEnabled.length === 0) {
          const p = configs.find((c) => c.id === pId);
          const candidates = (p?.models || [])
            .map((m) => m.id)
            .filter((mid) => RECOMMENDED_TEXT_NEW.has(mid));
          const toAdd =
            candidates.length > 0
              ? candidates.slice(0, 2)
              : (p?.models.slice(0, 1).map((m) => m.id) || []);
          for (const mid of toAdd) {
            addModel(pId, mid);
          }
        }
      }

      setEditingProvider(null);
      showToast("保存成功，已自动激活推荐主力模型", "success");
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
      showToast("已清除 API Key", "success");
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
      const msg = err instanceof Error ? err.message : "拉取失败，请检查 API Key 与网络";
      setRemoteError(msg);
    } finally {
      setRemoteLoading(false);
    }
  };

  return (
    <div
      style={{
        border: "1px solid var(--border-primary)",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-level-2)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        gap: 0,
      }}
    >
      {/* ── 可折叠的头部栏（无论展开/折叠始终可见）── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 14px",
          cursor: "pointer",
          userSelect: "none",
          gap: "12px",
          background: isCollapsed ? "transparent" : "var(--bg-level-1)",
          borderBottom: isCollapsed ? "none" : "1px solid var(--border-secondary)",
        }}
        onClick={toggleCollapsed}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-level-1)" }}>
                {t("settings.model.providers.title")} ({officialConfigs.length})
              </span>
              <span
                style={{
                  fontSize: "11px",
                  padding: "1px 7px",
                  borderRadius: "999px",
                  background: configuredCount > 0 ? "rgba(16,185,129,0.12)" : "rgba(107,114,128,0.12)",
                  color: configuredCount > 0 ? "var(--color-success)" : "var(--text-level-4)",
                  fontWeight: 500,
                  lineHeight: 1.4,
                }}
              >
                已配置 {configuredCount} 个
              </span>
            </div>
            {isCollapsed ? (
              <p
                style={{
                  fontSize: "12px",
                  color: "var(--text-level-3)",
                  margin: "2px 0 0 0",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {configuredCount > 0
                  ? `已就绪服务商：${configuredConfigs.map((c) => c.name).join("、")}`
                  : "点击展开可配置 DeepSeek、通义千问等服务商"}
              </p>
            ) : (
              <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
                配置服务商 API Key 即可一键激活对应模型
              </p>
            )}
          </div>
        </div>

        {/* 右侧折叠按钮 */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
          <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>
            {isCollapsed ? "展开服务商列表" : "收起列表"}
          </span>
          <ChevronDown
            style={{
              width: "15px",
              height: "15px",
              color: "var(--text-level-4)",
              transform: isCollapsed ? "rotate(0deg)" : "rotate(180deg)",
              transition: "transform var(--transition-fast)",
            }}
          />
        </div>
      </div>

      {/* ── 展开后的主体内容 ── */}
      {!isCollapsed && (
        <div style={{ padding: "12px 14px 14px", display: "flex", flexDirection: "column", gap: "10px" }}>
          {/* 工具栏：搜索框 + 筛选标签 */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "10px",
              flexWrap: "wrap",
            }}
          >
            {/* 搜索框 */}
            <div style={{ position: "relative", flex: 1, minWidth: "160px" }}>
              <Search
                style={{
                  position: "absolute",
                  left: "9px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  width: "13px",
                  height: "13px",
                  color: "var(--text-level-4)",
                  pointerEvents: "none",
                }}
              />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索服务商（如 DeepSeek、通义千问）..."
                style={{
                  width: "100%",
                  height: "30px",
                  padding: "0 10px 0 28px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-primary)",
                  background: "var(--bg-level-1)",
                  fontSize: "12px",
                  color: "var(--text-level-2)",
                  boxSizing: "border-box",
                  outline: "none",
                }}
              />
            </div>

            {/* 筛选标签切换 */}
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                padding: "2px",
                borderRadius: "var(--radius-sm)",
                background: "var(--bg-level-1)",
                border: "1px solid var(--border-secondary)",
              }}
            >
              <button
                type="button"
                onClick={() => setFilterMode("all")}
                style={{
                  padding: "3px 8px",
                  borderRadius: "var(--radius-xs)",
                  border: "none",
                  background: filterMode === "all" ? "var(--bg-level-3)" : "transparent",
                  color: filterMode === "all" ? "var(--text-level-1)" : "var(--text-level-3)",
                  fontSize: "11px",
                  fontWeight: filterMode === "all" ? 600 : 400,
                  cursor: "pointer",
                }}
              >
                全部 ({officialConfigs.length})
              </button>
              <button
                type="button"
                onClick={() => setFilterMode("configured")}
                style={{
                  padding: "3px 8px",
                  borderRadius: "var(--radius-xs)",
                  border: "none",
                  background: filterMode === "configured" ? "var(--bg-level-3)" : "transparent",
                  color: filterMode === "configured" ? "var(--color-primary)" : "var(--text-level-3)",
                  fontSize: "11px",
                  fontWeight: filterMode === "configured" ? 600 : 400,
                  cursor: "pointer",
                }}
              >
                已配置 ({configuredCount})
              </button>
              <button
                type="button"
                onClick={() => setFilterMode("hot")}
                style={{
                  padding: "3px 8px",
                  borderRadius: "var(--radius-xs)",
                  border: "none",
                  background: filterMode === "hot" ? "var(--bg-level-3)" : "transparent",
                  color: filterMode === "hot" ? "var(--text-level-1)" : "var(--text-level-3)",
                  fontSize: "11px",
                  fontWeight: filterMode === "hot" ? 600 : 400,
                  cursor: "pointer",
                }}
              >
                热门原厂
              </button>
            </div>
          </div>

          {/* 卡片列表 */}
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {filteredAndSorted.map((p) => (
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

            {filteredAndSorted.length === 0 && (
              <div
                style={{
                  padding: "20px",
                  textAlign: "center",
                  fontSize: "12px",
                  color: "var(--text-level-4)",
                  background: "var(--bg-level-1)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px dashed var(--border-primary)",
                }}
              >
                未找到匹配的模型服务商
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
