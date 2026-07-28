"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Moon,
  Sun,
  Monitor,
  Globe,
  Cpu,
  Sliders,
  Type,
  Key,
} from "lucide-react";
import { useSettings } from "@/hooks/useSettings";

export default function SettingsPage() {
  const router = useRouter();
  const { settings, loading, updateSetting } = useSettings();
  const [saving, setSaving] = useState<string | null>(null);

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
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        background: "var(--bg-level-2)",
      }}>
        <p style={{ color: "var(--text-level-3)" }}>加载中...</p>
      </div>
    );
  }

  return (
    <div style={{
      display: "flex",
      height: "100vh",
      background: "var(--bg-level-2)",
    }}>
      {/* 左侧 Sidebar */}
      <aside style={{
        width: "280px",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        borderRight: "1px solid var(--border-primary)",
        background: "var(--bg-level-1)",
      }}>
        {/* 返回按钮 */}
        <div style={{ padding: "16px" }}>
          <button
            onClick={() => router.back()}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 16px",
              borderRadius: "var(--radius-md)",
              border: "none",
              background: "var(--bg-level-3)",
              cursor: "pointer",
              fontSize: "14px",
              width: "100%",
            }}
          >
            <ArrowLeft style={{ width: "16px", height: "16px" }} />
            <span>返回</span>
          </button>
        </div>

        {/* 导航菜单 */}
        <nav style={{ padding: "0 16px" }}>
          <p style={{
            padding: "0 12px",
            marginBottom: "8px",
            fontSize: "12px",
            fontWeight: "600",
            color: "var(--text-level-4)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}>设置</p>
          {[
            { icon: Moon, label: "主题", href: "#theme" },
            { icon: Globe, label: "语言", href: "#language" },
            { icon: Cpu, label: "模型", href: "#model" },
            { icon: Sliders, label: "人格", href: "#personality" },
            { icon: Type, label: "字体", href: "#font" },
          ].map((item) => (
            <a
              key={item.label}
              href={item.href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "10px 12px",
                borderRadius: "var(--radius-md)",
                background: "transparent",
                cursor: "pointer",
                fontSize: "14px",
                color: "var(--text-level-2)",
                textDecoration: "none",
                marginBottom: "2px",
              }}
            >
              <item.icon style={{ width: "16px", height: "16px" }} />
              <span>{item.label}</span>
            </a>
          ))}
        </nav>
      </aside>

      {/* 右侧内容区 */}
      <main style={{
        flex: 1,
        overflowY: "auto",
        padding: "32px 48px",
      }}>
        <h1 style={{
          fontSize: "24px",
          fontWeight: "600",
          color: "var(--text-level-1)",
          margin: "0 0 32px 0",
        }}>设置</h1>

        {/* 主题设置 */}
        <section id="theme" style={{ marginBottom: "48px" }}>
          <h2 style={{
            fontSize: "18px",
            fontWeight: "600",
            color: "var(--text-level-1)",
            margin: "0 0 16px 0",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}>
            <Moon style={{ width: "20px", height: "20px" }} />
            主题
          </h2>
          <div style={{
            display: "flex",
            gap: "12px",
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
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "8px",
                  padding: "16px 24px",
                  borderRadius: "var(--radius-lg)",
                  border: settings?.theme === theme.value ? "2px solid var(--color-primary)" : "1px solid var(--border-primary)",
                  background: settings?.theme === theme.value ? "var(--color-primary-lighter)" : "var(--bg-level-2)",
                  cursor: "pointer",
                  opacity: saving === "theme" ? 0.7 : 1,
                }}
              >
                <theme.icon style={{
                  width: "24px",
                  height: "24px",
                  color: settings?.theme === theme.value ? "var(--color-primary)" : "var(--text-level-2)",
                }} />
                <span style={{
                  fontSize: "14px",
                  color: settings?.theme === theme.value ? "var(--color-primary)" : "var(--text-level-2)",
                }}>{theme.label}</span>
              </button>
            ))}
          </div>
        </section>

        {/* 语言设置 */}
        <section id="language" style={{ marginBottom: "48px" }}>
          <h2 style={{
            fontSize: "18px",
            fontWeight: "600",
            color: "var(--text-level-1)",
            margin: "0 0 16px 0",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}>
            <Globe style={{ width: "20px", height: "20px" }} />
            语言
          </h2>
          <select
            value={settings?.language || "zh-CN"}
            onChange={(e) => handleUpdate("language", e.target.value)}
            disabled={saving === "language"}
            style={{
              padding: "10px 16px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-2)",
              fontSize: "14px",
              color: "var(--text-level-2)",
              minWidth: "200px",
              opacity: saving === "language" ? 0.7 : 1,
            }}
          >
            <option value="zh-CN">简体中文</option>
            <option value="en">English</option>
          </select>
        </section>

        {/* 模型设置 */}
        <section id="model" style={{ marginBottom: "48px" }}>
          <h2 style={{
            fontSize: "18px",
            fontWeight: "600",
            color: "var(--text-level-1)",
            margin: "0 0 16px 0",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}>
            <Cpu style={{ width: "20px", height: "20px" }} />
            默认模型
          </h2>
          <select
            value={settings?.default_model || "mimo-v2.5-pro"}
            onChange={(e) => handleUpdate("default_model", e.target.value)}
            disabled={saving === "default_model"}
            style={{
              padding: "10px 16px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-2)",
              fontSize: "14px",
              color: "var(--text-level-2)",
              minWidth: "200px",
              opacity: saving === "default_model" ? 0.7 : 1,
            }}
          >
            <option value="mimo-v2.5-pro">MiMo v2.5 Pro</option>
          </select>
        </section>

        {/* 人格设置 */}
        <section id="personality" style={{ marginBottom: "48px" }}>
          <h2 style={{
            fontSize: "18px",
            fontWeight: "600",
            color: "var(--text-level-1)",
            margin: "0 0 16px 0",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}>
            <Sliders style={{ width: "20px", height: "20px" }} />
            默认人格
          </h2>
          <div style={{
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}>
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
                maxWidth: "400px",
                opacity: saving === "default_personality" ? 0.7 : 1,
              }}
            />
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              maxWidth: "400px",
              fontSize: "12px",
              color: "var(--text-level-3)",
            }}>
              <span>极度感性</span>
              <span>平衡</span>
              <span>极度理性</span>
            </div>
            <p style={{
              fontSize: "14px",
              color: "var(--text-level-2)",
              margin: "8px 0 0 0",
            }}>当前值: {settings?.default_personality || "50"}</p>
          </div>
        </section>

        {/* 字体设置 */}
        <section id="font" style={{ marginBottom: "48px" }}>
          <h2 style={{
            fontSize: "18px",
            fontWeight: "600",
            color: "var(--text-level-1)",
            margin: "0 0 16px 0",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}>
            <Type style={{ width: "20px", height: "20px" }} />
            字体大小
          </h2>
          <select
            value={settings?.font_size || "14"}
            onChange={(e) => handleUpdate("font_size", e.target.value)}
            disabled={saving === "font_size"}
            style={{
              padding: "10px 16px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-2)",
              fontSize: "14px",
              color: "var(--text-level-2)",
              minWidth: "200px",
              opacity: saving === "font_size" ? 0.7 : 1,
            }}
          >
            <option value="12">小 (12px)</option>
            <option value="14">标准 (14px)</option>
            <option value="16">大 (16px)</option>
            <option value="18">特大 (18px)</option>
          </select>
        </section>

        {/* API Key 配置 */}
        <section id="api-keys" style={{ marginBottom: "48px" }}>
          <h2 style={{
            fontSize: "18px",
            fontWeight: "600",
            color: "var(--text-level-1)",
            margin: "0 0 16px 0",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}>
            <Key style={{ width: "20px", height: "20px" }} />
            API Key 配置
          </h2>
          <div style={{
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}>
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
                  fontSize: "14px",
                  color: "var(--text-level-2)",
                  minWidth: "120px",
                }}>{apiKey.label}</label>
                <input
                  type="password"
                  value={settings?.[apiKey.key as keyof typeof settings] || ""}
                  onChange={(e) => handleUpdate(apiKey.key, e.target.value)}
                  disabled={saving === apiKey.key}
                  placeholder={apiKey.placeholder}
                  style={{
                    flex: 1,
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
        </section>
      </main>
    </div>
  );
}
