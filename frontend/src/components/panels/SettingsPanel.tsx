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
    <Panel isOpen={isOpen} onClose={onClose} title="设置">
      {/* 导航 */}
      <div style={{
        display: "flex",
        gap: "4px",
        marginBottom: "24px",
        padding: "4px",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-level-2)",
      }}>
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveSection(item.id)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "8px 12px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: activeSection === item.id ? "var(--bg-level-1)" : "transparent",
              cursor: "pointer",
              fontSize: "13px",
              color: activeSection === item.id ? "var(--text-level-1)" : "var(--text-level-3)",
              flex: 1,
              justifyContent: "center",
            }}
          >
            <item.icon style={{ width: "14px", height: "14px" }} />
            <span>{item.label}</span>
          </button>
        ))}
      </div>

      {/* 通用设置 */}
      {activeSection === "general" && (
        <>
          {/* 主题 */}
          <div style={{ marginBottom: "24px" }}>
            <h3 style={{
              fontSize: "14px",
              fontWeight: "500",
              color: "var(--text-level-1)",
              margin: "0 0 12px 0",
            }}>外观</h3>
            <div style={{ display: "flex", gap: "8px" }}>
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
                    flexDirection: "column",
                    alignItems: "center",
                    gap: "6px",
                    padding: "12px 16px",
                    borderRadius: "var(--radius-md)",
                    border: settings?.theme === theme.value ? "2px solid var(--color-primary)" : "1px solid var(--border-primary)",
                    background: settings?.theme === theme.value ? "var(--color-primary-lighter)" : "var(--bg-level-2)",
                    cursor: "pointer",
                    flex: 1,
                    opacity: saving === "theme" ? 0.7 : 1,
                  }}
                >
                  <theme.icon style={{
                    width: "18px",
                    height: "18px",
                    color: settings?.theme === theme.value ? "var(--color-primary)" : "var(--text-level-2)",
                  }} />
                  <span style={{
                    fontSize: "12px",
                    color: settings?.theme === theme.value ? "var(--color-primary)" : "var(--text-level-2)",
                  }}>{theme.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* 语言 */}
          <div style={{ marginBottom: "24px" }}>
            <h3 style={{
              fontSize: "14px",
              fontWeight: "500",
              color: "var(--text-level-1)",
              margin: "0 0 12px 0",
            }}>语言</h3>
            <select
              value={settings?.language || "zh-CN"}
              onChange={(e) => handleUpdate("language", e.target.value)}
              disabled={saving === "language"}
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-2)",
                fontSize: "14px",
                color: "var(--text-level-2)",
                opacity: saving === "language" ? 0.7 : 1,
              }}
            >
              <option value="zh-CN">简体中文</option>
              <option value="en">English</option>
            </select>
          </div>

          {/* 字体大小 */}
          <div style={{ marginBottom: "24px" }}>
            <h3 style={{
              fontSize: "14px",
              fontWeight: "500",
              color: "var(--text-level-1)",
              margin: "0 0 12px 0",
            }}>字体大小</h3>
            <select
              value={settings?.font_size || "14"}
              onChange={(e) => handleUpdate("font_size", e.target.value)}
              disabled={saving === "font_size"}
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-2)",
                fontSize: "14px",
                color: "var(--text-level-2)",
                opacity: saving === "font_size" ? 0.7 : 1,
              }}
            >
              <option value="12">小 (12px)</option>
              <option value="14">标准 (14px)</option>
              <option value="16">大 (16px)</option>
              <option value="18">特大 (18px)</option>
            </select>
          </div>
        </>
      )}

      {/* 模型设置 */}
      {activeSection === "model" && (
        <>
          {/* 默认模型 */}
          <div style={{ marginBottom: "24px" }}>
            <h3 style={{
              fontSize: "14px",
              fontWeight: "500",
              color: "var(--text-level-1)",
              margin: "0 0 12px 0",
            }}>默认模型</h3>
            <select
              value={settings?.default_model || "mimo-v2.5-pro"}
              onChange={(e) => handleUpdate("default_model", e.target.value)}
              disabled={saving === "default_model"}
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-2)",
                fontSize: "14px",
                color: "var(--text-level-2)",
                opacity: saving === "default_model" ? 0.7 : 1,
              }}
            >
              <option value="mimo-v2.5-pro">MiMo v2.5 Pro</option>
            </select>
          </div>

          {/* API Key */}
          <div style={{ marginBottom: "24px" }}>
            <h3 style={{
              fontSize: "14px",
              fontWeight: "500",
              color: "var(--text-level-1)",
              margin: "0 0 12px 0",
            }}>API 配置</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {[
                { key: "api_key_mimo", label: "小米 MiMo", placeholder: "sk-..." },
                { key: "api_key_deepseek", label: "DeepSeek", placeholder: "sk-..." },
                { key: "api_key_qwen", label: "通义千问", placeholder: "sk-..." },
                { key: "api_key_glm", label: "智谱 AI", placeholder: "sk-..." },
                { key: "api_key_moonshot", label: "Moonshot", placeholder: "sk-..." },
              ].map((apiKey) => (
                <div key={apiKey.key}>
                  <label style={{
                    display: "block",
                    fontSize: "12px",
                    color: "var(--text-level-3)",
                    marginBottom: "4px",
                  }}>{apiKey.label}</label>
                  <input
                    type="password"
                    value={settings?.[apiKey.key as keyof typeof settings] || ""}
                    onChange={(e) => handleUpdate(apiKey.key, e.target.value)}
                    disabled={saving === apiKey.key}
                    placeholder={apiKey.placeholder}
                    style={{
                      width: "100%",
                      padding: "10px 12px",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid var(--border-primary)",
                      background: "var(--bg-level-2)",
                      fontSize: "14px",
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
        <div style={{ marginBottom: "24px" }}>
          <h3 style={{
            fontSize: "14px",
            fontWeight: "500",
            color: "var(--text-level-1)",
            margin: "0 0 12px 0",
          }}>默认人格</h3>
          <p style={{
            fontSize: "13px",
            color: "var(--text-level-3)",
            margin: "0 0 12px 0",
          }}>调整 AI 的理性/感性倾向</p>
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
          <p style={{
            fontSize: "13px",
            color: "var(--text-level-2)",
            margin: "8px 0 0 0",
          }}>当前值: {settings?.default_personality || "50"}</p>
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
    </Panel>
  );
}
