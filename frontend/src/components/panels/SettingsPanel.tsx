"use client";

import { useState, useEffect } from "react";
import {
  Moon,
  Sun,
  Monitor,
  Cpu,
  Brain,
  Info,
  Bot,
} from "lucide-react";
import { useSettingsStore } from "@/lib/store";
import { useTranslation } from "@/hooks/useTranslation";
import { useModels } from "@/hooks/useModels";
import { useAgents } from "@/hooks/useAgents";
import { Panel } from "./Panel";
import { MemoryPanel } from "./MemoryPanel";

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const { settings, loading, fetchSettings, updateSetting, updateSettings } = useSettingsStore();
  const { t } = useTranslation();
  const { models, loading: modelsLoading } = useModels();
  const { agents } = useAgents();
  const [saving, setSaving] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState("general");
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [savingApiKeys, setSavingApiKeys] = useState(false);
  const [apiKeysSaved, setApiKeysSaved] = useState(false);
  const [apiKeysSynced, setApiKeysSynced] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  // 当 settings 加载完成后，将当前 API Key 值同步到本地暂存（渲染期调整，避免 effect setState）
  if (settings && !apiKeysSynced) {
    setApiKeysSynced(true);
    setApiKeys(prev => {
      const next: Record<string, string> = {};
      for (const key of Object.keys(settings)) {
        if (key.startsWith("api_key_")) {
          next[key] = settings[key] || "";
        }
      }
      return { ...prev, ...next };
    });
  }

  const handleUpdate = async (key: string, value: string) => {
    setSaving(key);
    try {
      await updateSetting(key, value);
    } catch (err) {
      console.error("Failed to update setting:", err);
    } finally {
      setSaving(null);
    }
  };

  const handleSaveApiKeys = async () => {
    setSavingApiKeys(true);
    setApiKeysSaved(false);
    try {
      await updateSettings(apiKeys);
      setApiKeysSaved(true);
      setTimeout(() => setApiKeysSaved(false), 2000);
    } catch (err) {
      console.error("Failed to save API keys:", err);
    } finally {
      setSavingApiKeys(false);
    }
  };

  if (loading) {
    return (
      <Panel isOpen={isOpen} onClose={onClose} title={t("settings.title")}>
        <p style={{ color: "var(--text-level-3)" }}>{t("common.loading")}</p>
      </Panel>
    );
  }

  const navItems = [
    { id: "general", label: t("settings.general.title"), icon: Monitor },
    { id: "model", label: t("settings.model.title"), icon: Cpu },
    { id: "ai", label: t("settings.ai.title"), icon: Brain },
    { id: "memory", label: t("settings.memory.title"), icon: Brain },
    { id: "about", label: t("settings.about.title"), icon: Info },
  ];

  return (
    <Panel isOpen={isOpen} onClose={onClose} title={t("settings.title")} width="700px" variant="center">
      <div style={{
        display: "flex",
        gap: "24px",
        minHeight: "400px",
      }}>
        {/* 左侧导航 */}
        <nav style={{
          width: "140px",
          flexShrink: 0,
          borderRight: "1px solid rgba(0, 0, 0, 0.06)",
          paddingRight: "16px",
          marginRight: "16px",
        }}>
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveSection(item.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                width: "100%",
                padding: "10px 12px",
                borderRadius: "var(--radius-md)",
                border: "none",
                background: activeSection === item.id ? "var(--bg-level-2)" : "transparent",
                cursor: "pointer",
                fontSize: "14px",
                color: activeSection === item.id ? "var(--text-level-1)" : "var(--text-level-3)",
                textAlign: "left",
                marginBottom: "4px",
              }}
            >
              <item.icon style={{ width: "16px", height: "16px" }} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        {/* 右侧内容 */}
        <div style={{ flex: 1 }}>
          {/* 通用设置 */}
          {activeSection === "general" && (
            <>
              {/* 主题 */}
              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "28px",
              }}>
                <div>
                  <h3 style={{
                    fontSize: "14px",
                    fontWeight: "500",
                    color: "var(--text-level-1)",
                    margin: 0,
                  }}>{t("settings.general.theme.title")}</h3>
                  <p style={{
                    fontSize: "12px",
                    color: "var(--text-level-3)",
                    margin: "2px 0 0 0",
                  }}>{t("settings.general.theme.desc")}</p>
                </div>
                <div style={{
                  display: "flex",
                  padding: "3px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--bg-level-2)",
                }}>
                  {[
                    { value: "light", label: t("settings.general.theme.light"), icon: Sun },
                    { value: "dark", label: t("settings.general.theme.dark"), icon: Moon },
                    { value: "system", label: t("settings.general.theme.system"), icon: Monitor },
                  ].map((theme) => (
                    <button
                      key={theme.value}
                      onClick={() => handleUpdate("theme", theme.value)}
                      disabled={saving === "theme"}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: "6px",
                        padding: "6px 14px",
                        borderRadius: "var(--radius-xs)",
                        border: "none",
                        background: settings?.theme === theme.value ? "var(--bg-level-1)" : "transparent",
                        cursor: "pointer",
                        fontSize: "13px",
                        color: settings?.theme === theme.value ? "var(--text-level-1)" : "var(--text-level-3)",
                        opacity: saving === "theme" ? 0.7 : 1,
                      }}
                    >
                      <theme.icon style={{ width: "14px", height: "14px" }} />
                      <span>{theme.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* 语言 */}
              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "28px",
              }}>
                <div>
                  <h3 style={{
                    fontSize: "14px",
                    fontWeight: "500",
                    color: "var(--text-level-1)",
                    margin: 0,
                  }}>{t("settings.general.language.title")}</h3>
                  <p style={{
                    fontSize: "12px",
                    color: "var(--text-level-3)",
                    margin: "2px 0 0 0",
                  }}>{t("settings.general.language.desc")}</p>
                </div>
                <div style={{
                  display: "flex",
                  padding: "3px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--bg-level-2)",
                }}>
                  {[
                    { value: "zh-CN", label: t("settings.general.language.zh-CN") },
                    { value: "en-US", label: t("settings.general.language.en-US") },
                  ].map((lang) => (
                    <button
                      key={lang.value}
                      onClick={() => handleUpdate("language", lang.value)}
                      disabled={saving === "language"}
                      style={{
                        padding: "6px 16px",
                        borderRadius: "var(--radius-xs)",
                        border: "none",
                        background: settings?.language === lang.value ? "var(--bg-level-1)" : "transparent",
                        cursor: "pointer",
                        fontSize: "13px",
                        color: settings?.language === lang.value ? "var(--text-level-1)" : "var(--text-level-3)",
                        opacity: saving === "language" ? 0.7 : 1,
                      }}
                    >
                      {lang.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 字体风格 */}
              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "28px",
              }}>
                <h3 style={{
                  fontSize: "14px",
                  fontWeight: "500",
                  color: "var(--text-level-1)",
                  margin: 0,
                }}>{t("settings.general.font.title")}</h3>
                <select
                  value={settings?.font_family || "system"}
                  onChange={(e) => handleUpdate("font_family", e.target.value)}
                  disabled={saving === "font_family"}
                  style={{
                    padding: "6px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-primary)",
                    background: "var(--bg-level-2)",
                    fontSize: "13px",
                    color: "var(--text-level-2)",
                    opacity: saving === "font_family" ? 0.7 : 1,
                    minWidth: "140px",
                  }}
                >
                  <option value="system">{t("settings.general.font.system")}</option>
                  <option value="source-han-sans">{t("settings.general.font.source-han-sans")}</option>
                  <option value="lxgw-wenkai">{t("settings.general.font.lxgw-wenkai")}</option>
                  <option value="ibm-plex-sans">{t("settings.general.font.ibm-plex-sans")}</option>
                </select>
              </div>
            </>
          )}

          {/* 模型设置 */}
          {activeSection === "model" && (
            <>
              {/* 默认模型 */}
              <div style={{ marginBottom: "28px" }}>
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}>
                  <div>
                    <h3 style={{
                      fontSize: "14px",
                      fontWeight: "500",
                      color: "var(--text-level-1)",
                      margin: 0,
                    }}>{t("settings.model.defaultModel.title")}</h3>
                    <p style={{
                      fontSize: "12px",
                      color: "var(--text-level-3)",
                      margin: "2px 0 0 0",
                    }}>{t("settings.model.defaultModel.desc")}</p>
                  </div>
                  <select
                    value={settings?.default_model || "mimo-v2.5-pro"}
                    onChange={(e) => handleUpdate("default_model", e.target.value)}
                    disabled={saving === "default_model" || modelsLoading}
                    style={{
                      padding: "8px 12px",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border-primary)",
                      background: "var(--bg-level-2)",
                      fontSize: "13px",
                      color: "var(--text-level-2)",
                      opacity: saving === "default_model" ? 0.7 : 1,
                    }}
                  >
                    {modelsLoading ? (
                      <option value="mimo-v2.5-pro">Loading...</option>
                    ) : (
                      models.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.name}
                        </option>
                      ))
                    )}
                  </select>
                </div>
              </div>

              {/* API Key */}
              <div>
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "16px",
                }}>
                  <h3 style={{
                    fontSize: "14px",
                    fontWeight: "500",
                    color: "var(--text-level-1)",
                    margin: 0,
                  }}>{t("settings.model.apiConfig.title")}</h3>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    {apiKeysSaved && (
                      <span style={{ fontSize: "12px", color: "var(--color-success)" }}>
                        {t("common.saved")}
                      </span>
                    )}
                    <button
                      onClick={handleSaveApiKeys}
                      disabled={savingApiKeys}
                      style={{
                        padding: "6px 16px",
                        borderRadius: "var(--radius-sm)",
                        border: "none",
                        background: "var(--color-primary)",
                        color: "white",
                        cursor: savingApiKeys ? "not-allowed" : "pointer",
                        fontSize: "13px",
                        fontWeight: "500",
                        opacity: savingApiKeys ? 0.7 : 1,
                        transition: "all 0.6s ease",
                      }}
                      onMouseEnter={(e) => {
                        if (!savingApiKeys) e.currentTarget.style.background = "var(--color-primary-hover)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "var(--color-primary)";
                      }}
                    >
                      {savingApiKeys ? t("common.saving") : t("common.save")}
                    </button>
                  </div>
                </div>
                <p style={{
                  fontSize: "12px",
                  color: "var(--text-level-4)",
                  margin: "0 0 16px 0",
                }}>{t("settings.model.apiConfig.desc")}</p>
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {[
                    { key: "api_key_mimo", label: "小米 MiMo", placeholder: "sk-..." },
                    { key: "api_key_deepseek", label: "DeepSeek", placeholder: "sk-..." },
                    { key: "api_key_qwen", label: "通义千问", placeholder: "sk-..." },
                    { key: "api_key_glm", label: "智谱 AI", placeholder: "sk-..." },
                    { key: "api_key_moonshot", label: "Moonshot", placeholder: "sk-..." },
                  ].map((apiKey) => (
                    <div key={apiKey.key} style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                    }}>
                      <label style={{
                        fontSize: "13px",
                        color: "var(--text-level-2)",
                        minWidth: "100px",
                      }}>{apiKey.label}</label>
                      <input
                        type="password"
                        value={apiKeys[apiKey.key] || ""}
                        onChange={(e) => setApiKeys(prev => ({ ...prev, [apiKey.key]: e.target.value }))}
                        placeholder={apiKey.placeholder}
                        style={{
                          flex: 1,
                          padding: "8px 12px",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid var(--border-primary)",
                          background: "var(--bg-level-2)",
                          fontSize: "13px",
                          color: "var(--text-level-2)",
                          outline: "none",
                        }}
                      />
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* AI 行为 */}
          {activeSection === "ai" && (
            <div>
              {/* 默认 Agent */}
              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "28px",
              }}>
                <div>
                  <h3 style={{
                    fontSize: "14px",
                    fontWeight: "500",
                    color: "var(--text-level-1)",
                    margin: 0,
                  }}>{t("settings.ai.defaultAgent.title")}</h3>
                  <p style={{
                    fontSize: "12px",
                    color: "var(--text-level-3)",
                    margin: "2px 0 0 0",
                  }}>{t("settings.ai.defaultAgent.desc")}</p>
                </div>
                <select
                  value={settings?.default_agent || "general"}
                  onChange={(e) => handleUpdate("default_agent", e.target.value)}
                  disabled={saving === "default_agent"}
                  style={{
                    padding: "8px 12px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-primary)",
                    background: "var(--bg-level-2)",
                    fontSize: "13px",
                    color: "var(--text-level-2)",
                    opacity: saving === "default_agent" ? 0.7 : 1,
                    minWidth: "140px",
                  }}
                >
                  {agents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.avatar} {agent.name}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "8px",
              }}>
                <div>
                  <h3 style={{
                    fontSize: "14px",
                    fontWeight: "500",
                    color: "var(--text-level-1)",
                    margin: 0,
                  }}>{t("settings.ai.defaultPersonality.title")}</h3>
                  <p style={{
                    fontSize: "12px",
                    color: "var(--text-level-3)",
                    margin: "2px 0 0 0",
                  }}>{t("settings.ai.defaultPersonality.desc")}</p>
                </div>
                <span style={{
                  fontSize: "13px",
                  color: "var(--text-level-2)",
                }}>{settings?.default_personality || "50"}</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="25"
                value={settings?.default_personality || "50"}
                onChange={(e) => handleUpdate("default_personality", e.target.value)}
                disabled={saving === "default_personality"}
                style={{
                  width: "100%",
                  opacity: saving === "default_personality" ? 0.7 : 1,
                }}
              />
              <div style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: "11px",
                color: "var(--text-level-4)",
                marginTop: "4px",
              }}>
                <span>{t("settings.ai.defaultPersonality.veryEmotional")}</span>
                <span>{t("settings.ai.defaultPersonality.balanced")}</span>
                <span>{t("settings.ai.defaultPersonality.veryRational")}</span>
              </div>

              {/* 预设 Agent 列表 */}
              <div style={{ marginTop: "32px" }}>
                <h3 style={{
                  fontSize: "14px",
                  fontWeight: "500",
                  color: "var(--text-level-1)",
                  margin: "0 0 8px 0",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}>
                  <Bot style={{ width: "16px", height: "16px" }} />
                  {t("settings.ai.agents.title")}
                </h3>
                <p style={{
                  fontSize: "12px",
                  color: "var(--text-level-3)",
                  margin: "0 0 16px 0",
                }}>{t("settings.ai.agents.desc")}</p>

                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {agents.map((agent) => (
                    <div
                      key={agent.id}
                      style={{
                        padding: "16px",
                        borderRadius: "var(--radius-md)",
                        background: "var(--bg-level-2)",
                        border: "1px solid var(--border-primary)",
                      }}
                    >
                      <div style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        marginBottom: "12px",
                      }}>
                        <span style={{ fontSize: "24px" }}>{agent.avatar}</span>
                        <div>
                          <p style={{
                            fontSize: "14px",
                            fontWeight: "500",
                            color: "var(--text-level-1)",
                            margin: 0,
                          }}>{agent.name}</p>
                          <p style={{
                            fontSize: "12px",
                            color: "var(--text-level-3)",
                            margin: "2px 0 0 0",
                          }}>{agent.description}</p>
                        </div>
                      </div>
                      <div style={{
                        padding: "12px",
                        borderRadius: "var(--radius-sm)",
                        background: "var(--bg-level-1)",
                        fontSize: "12px",
                        color: "var(--text-level-3)",
                        fontFamily: "monospace",
                        whiteSpace: "pre-wrap",
                        maxHeight: "100px",
                        overflowY: "auto",
                      }}>
                        {agent.system_prompt}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* 记忆 */}
          {activeSection === "memory" && (
            <MemoryPanel embedded isOpen onClose={() => {}} />
          )}

          {/* 关于 */}
          {activeSection === "about" && (
            <div>
              <div style={{
                padding: "16px",
                borderRadius: "var(--radius-md)",
                background: "var(--bg-level-2)",
              }}>
                <p style={{
                  fontSize: "15px",
                  fontWeight: "600",
                  color: "var(--text-level-1)",
                  margin: "0 0 8px 0",
                }}>MfkAgent</p>
                <p style={{
                  fontSize: "13px",
                  color: "var(--text-level-3)",
                  margin: "0 0 4px 0",
                }}>{t("settings.about.version")}</p>
                <p style={{
                  fontSize: "13px",
                  color: "var(--text-level-3)",
                  margin: "0 0 12px 0",
                }}>{t("settings.about.description")}</p>
                <p style={{
                  fontSize: "12px",
                  color: "var(--text-level-4)",
                  margin: 0,
                }}>{t("settings.about.aiMayError")}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}
