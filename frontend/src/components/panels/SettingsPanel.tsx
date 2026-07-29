"use client";

import { useState } from "react";
import {
  Moon,
  Sun,
  Monitor,
  Cpu,
  Brain,
  Info,
} from "lucide-react";
import { useSettings } from "@/hooks/useSettings";
import { Panel } from "./Panel";

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SettingsPanel({ isOpen, onClose }: SettingsPanelProps) {
  const { settings, loading, updateSetting } = useSettings();
  const [saving, setSaving] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState("general");

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

  if (loading) {
    return (
      <Panel isOpen={isOpen} onClose={onClose} title="设置">
        <p style={{ color: "var(--text-level-3)" }}>正在加载设置...</p>
      </Panel>
    );
  }

  const navItems = [
    { id: "general", label: "通用", icon: Monitor },
    { id: "model", label: "模型", icon: Cpu },
    { id: "ai", label: "AI 行为", icon: Brain },
    { id: "about", label: "关于", icon: Info },
  ];

  return (
    <Panel isOpen={isOpen} onClose={onClose} title="设置" width="700px" variant="center">
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
                  }}>外观</h3>
                  <p style={{
                    fontSize: "12px",
                    color: "var(--text-level-3)",
                    margin: "2px 0 0 0",
                  }}>选择界面主题</p>
                </div>
                <div style={{
                  display: "flex",
                  padding: "3px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--bg-level-2)",
                }}>
                  {[
                    { value: "light", label: "浅色", icon: Sun },
                    { value: "dark", label: "深色", icon: Moon },
                    { value: "system", label: "跟随系统", icon: Monitor },
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
                  }}>语言</h3>
                  <p style={{
                    fontSize: "12px",
                    color: "var(--text-level-3)",
                    margin: "2px 0 0 0",
                  }}>界面显示语言</p>
                </div>
                <div style={{
                  display: "flex",
                  padding: "3px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--bg-level-2)",
                }}>
                  {[
                    { value: "zh-CN", label: "中文" },
                    { value: "en", label: "English" },
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
                }}>字体</h3>
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
                  <option value="system">系统默认</option>
                  <option value="noto-sans-sc">思源黑体</option>
                  <option value="ibm-plex-sans">IBM Plex Sans</option>
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
                    }}>默认模型</h3>
                    <p style={{
                      fontSize: "12px",
                      color: "var(--text-level-3)",
                      margin: "2px 0 0 0",
                    }}>新聊天默认使用的 AI 模型</p>
                  </div>
                  <select
                    value={settings?.default_model || "mimo-v2.5-pro"}
                    onChange={(e) => handleUpdate("default_model", e.target.value)}
                    disabled={saving === "default_model"}
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
                    <option value="mimo-v2.5-pro">MiMo v2.5 Pro</option>
                    <option value="mimo-v2.5">MiMo v2.5</option>
                    <option value="deepseek-chat">DeepSeek Chat</option>
                  </select>
                </div>
              </div>

              {/* API Key */}
              <div>
                <h3 style={{
                  fontSize: "14px",
                  fontWeight: "500",
                  color: "var(--text-level-1)",
                  margin: "0 0 16px 0",
                }}>API 配置</h3>
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
                        value={settings?.[apiKey.key as keyof typeof settings] || ""}
                        onChange={(e) => handleUpdate(apiKey.key, e.target.value)}
                        disabled={saving === apiKey.key}
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
                          opacity: saving === apiKey.key ? 0.7 : 1,
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
                  }}>默认人格</h3>
                  <p style={{
                    fontSize: "12px",
                    color: "var(--text-level-3)",
                    margin: "2px 0 0 0",
                  }}>调整 AI 的理性/感性倾向</p>
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
                <span>极度感性</span>
                <span>平衡</span>
                <span>极度理性</span>
              </div>
            </div>
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
                }}>版本: v1.0.0</p>
                <p style={{
                  fontSize: "13px",
                  color: "var(--text-level-3)",
                  margin: "0 0 12px 0",
                }}>专业的 AI 工作助手</p>
                <p style={{
                  fontSize: "12px",
                  color: "var(--text-level-4)",
                  margin: 0,
                }}>MfkAgent 可能会犯错，请核实重要信息</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}
